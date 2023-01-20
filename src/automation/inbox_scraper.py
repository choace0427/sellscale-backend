from src.automation.models import PhantomBusterType, PhantomBusterConfig
from model_import import ProspectStatus, Prospect, ClientSDR, GeneratedMessage
import requests
import json
import os
from src.prospecting.services import (
    get_linkedin_slug_from_url,
    find_prospect_by_linkedin_slug,
)
from tqdm import tqdm
from app import celery, db
from src.automation.slack_notification import send_slack_block
from src.prospecting.services import update_prospect_status
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


def process_inbox(message_payload, client_id):
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
    for message in message_payload:
        try:
            is_group_message = len(message["linkedInUrls"]) > 1
            is_last_message_from_me = message["isLastMessageFromMe"]
            thread_url = message["threadUrl"]
            li_last_message_timestamp = message["timestamp"]
            recipient = get_linkedin_slug_from_url(message["linkedInUrls"][0])

            prospect: Prospect = find_prospect_by_linkedin_slug(
                recipient, client_id=client_id
            )
            if is_group_message or not prospect:
                continue

            prospect.li_conversation_thread_id = thread_url
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
                update_prospect_status(
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
                    ProspectStatus.NOT_INTERESTED,
                )
                and not is_last_message_from_me
            ):
                update_prospect_status(
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
                    update_prospect_status(
                        prospect_id=prospect.id,
                        new_status=ProspectStatus.RESPONDED,
                        message=message,
                    )
        except:
            continue


def scrape_inbox(client_sdr_id: int):
    """Scrape the inbox of a client on Linkedin"""
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)

    if not client_sdr:
        return False
    client_id = client_sdr.client_id

    pb_config = get_inbox_scraper_config(client_sdr_id=client_sdr_id)
    if not pb_config:
        return False

    agent = get_phantom_buster_agent(config=pb_config)
    s3Folder = agent["s3Folder"]
    orgS3Folder = agent["orgS3Folder"]

    data_payload = get_phantom_buster_payload(
        s3Folder=s3Folder, orgS3Folder=orgS3Folder
    )

    process_inbox(message_payload=data_payload, client_id=client_id)
    return True


@celery.task
def scrape_all_inboxes():
    client_sdr_ids = [x.id for x in ClientSDR.query.all()]
    for cs_id in tqdm(client_sdr_ids):
        scrape_inbox(client_sdr_id=cs_id)
