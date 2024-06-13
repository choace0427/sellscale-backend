from app import celery, db
from src.automation.models import PhantomBusterType, PhantomBusterConfig
from model_import import ProspectStatus, Prospect, ClientSDR, GeneratedMessage
import requests
import json
import os
from src.prospecting.services import get_linkedin_slug_from_url
from tqdm import tqdm

from src.prospecting.services import update_prospect_status_linkedin
from src.utils.slack import send_slack_message, URL_MAP
from fuzzywuzzy import fuzz

PHANTOMBUSTER_API_KEY = os.environ.get("PHANTOMBUSTER_API_KEY")


def get_inbox_scraper_config(client_sdr_id: int):
    pb_config: PhantomBusterConfig = PhantomBusterConfig.query.filter(
        PhantomBusterConfig.client_sdr_id == client_sdr_id,
        PhantomBusterConfig.pb_type == PhantomBusterType.INBOX_SCRAPER,
    ).first()

    return pb_config


def get_phantom_buster_agent(config: PhantomBusterConfig):
    """Get the payload of a phantom buster config

    config = {
        'phantom_uuid': '123456789',
    }
    """
    phantom_uuid = config.phantom_uuid
    url = "https://api.phantombuster.com/api/v2/agents/fetch?id={}".format(phantom_uuid)

    headers = {
        "X-Phantombuster-Key": PHANTOMBUSTER_API_KEY,
        "accept": "application/json",
    }

    response = requests.request("GET", url, headers=headers, data={})
    return json.loads(response.text)


def get_phantom_buster_payload(s3Folder, orgS3Folder):
    url = "https://phantombuster.s3.amazonaws.com/{orgS3Folder}/{s3Folder}/result.json".format(
        orgS3Folder=orgS3Folder, s3Folder=s3Folder
    )

    headers = {"X-Phantombuster-Key": "UapzERoGG1Q7qcY1jmoisJgR6MNJUmdL2w4UcLCtOJQ"}
    response = requests.request("GET", url, headers=headers, data={})

    return json.loads(response.text)


def process_inbox(message_payload, client_sdr_id):
    """
     data_payload = [{
        "firstnameFrom": "Zaheer",
        "isLastMessageFromMe": true,
        "lastMessageDate": "2022-10-20T06:01:08.960Z",
        "lastMessageFromUrl": "https://www.linkedin.com/in/zmohiuddin/",
        "lastnameFrom": "Mohiuddin",
        "linkedInUrls": [
            "https://www.linkedin.com/in/doug-ayers-7b8b10b/"
        ],
        "message": "looking forward to it!",
        "occupationFrom": "Co-Founder at Levels.fyi | Get Paid, Not Played",
        "readStatus": true,
        "threadUrl": "https://www.linkedin.com/messaging/thread/2-MDllMWY4YzEtZGFjNy00NWU1LWFhYWYtZWVlZTczZmFjNWJkXzAxMg==",
        "timestamp": "2022-10-20T06:06:54.106Z"
    },
    ...]
    """
    deep_scrape_count = 0
    for message in message_payload:
        try:
            is_group_message = len(message["linkedInUrls"]) > 1
            is_last_message_from_me = message["isLastMessageFromMe"]
            thread_url = message["threadUrl"]
            li_last_message_timestamp = message["lastMessageDate"]
            recipient = get_linkedin_slug_from_url(message["linkedInUrls"][0])

            prospect: Prospect = Prospect.query.filter(
                Prospect.linkedin_url.like(f"%{recipient}%"),
                Prospect.client_sdr_id == client_sdr_id,
            ).first()

            if is_group_message or not prospect:
                continue

            # Check if the last message timestamp is different from the one in the db
            # If it is, then we should deep scrape the prospect
            last_message_timestamp = prospect.li_last_message_timestamp
            if (
                last_message_timestamp
                and last_message_timestamp != li_last_message_timestamp
            ):
                deep_scrape_count += 1
                prospect.li_should_deep_scrape = True

            prospect.li_conversation_thread_id = thread_url
            try:
                prospect.li_conversation_urn_id = thread_url.split('thread/')[-1].split('/')[0]
            except:
                continue
            prospect.li_is_last_message_from_sdr = is_last_message_from_me
            prospect.li_last_message_timestamp = li_last_message_timestamp
            if not is_last_message_from_me:
                prospect.li_last_message_from_prospect = message["message"]

            db.session.add(prospect)
            db.session.commit()

            if (
                prospect.status == ProspectStatus.SENT_OUTREACH
                and is_last_message_from_me
            ):
                update_prospect_status_linkedin(
                    prospect_id=prospect.id,
                    new_status=ProspectStatus.ACCEPTED,
                    message=message,
                )
            elif (
                prospect.status
                in (
                    ProspectStatus.SENT_OUTREACH,
                    ProspectStatus.ACCEPTED,
                    ProspectStatus.RESPONDED,
                )
                and not is_last_message_from_me
            ):
                update_prospect_status_linkedin(
                    prospect_id=prospect.id,
                    new_status=ProspectStatus.ACTIVE_CONVO,
                    message=message,
                )

            if (
                prospect.status
                == ProspectStatus.ACCEPTED  # Check if prospect has been bumped
                and is_last_message_from_me
            ):
                sent_message: GeneratedMessage = GeneratedMessage.query.get(
                    prospect.approved_outreach_message_id
                ).completion
                pure_sent_message = (
                    sent_message.strip().lower()
                )  # Strip and lower case the message
                pure_last_message = (
                    message["message"].strip().lower()
                )  # Strip and lower case the message
                if (
                    fuzz.ratio(pure_sent_message, pure_last_message) < 90
                ):  # Check if the message is similar - less than 90 most likely means the message is a bump.
                    update_prospect_status_linkedin(
                        prospect_id=prospect.id,
                        new_status=ProspectStatus.RESPONDED,
                        message=message,
                    )
        except:
            continue

    return deep_scrape_count


@celery.task
def scrape_inbox(client_sdr_id: int):
    """Scrape the inbox of a client on Linkedin"""
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)

    if not client_sdr:
        return False

    client_sdr_name = client_sdr.name

    pb_config = get_inbox_scraper_config(client_sdr_id=client_sdr_id)
    if not pb_config:
        return False

    agent = get_phantom_buster_agent(config=pb_config)
    if not agent:
        return False
    s3Folder = agent.get("s3Folder")
    orgS3Folder = agent.get("orgS3Folder")

    data_payload = get_phantom_buster_payload(
        s3Folder=s3Folder, orgS3Folder=orgS3Folder
    )

    deep_scrape_count = process_inbox(
        message_payload=data_payload, client_sdr_id=client_sdr_id
    )

    return True


@celery.task
def scrape_all_inboxes():
    client_sdr_ids = [x.id for x in ClientSDR.query.all()]
    for cs_id in tqdm(client_sdr_ids):
        scrape_inbox.delay(client_sdr_id=cs_id)

    send_slack_message(
        message="🔎 Finished basic scrape for all SDRs",
        webhook_urls=[URL_MAP["eng-sandbox"]],
    )
    return
