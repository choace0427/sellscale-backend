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

@celery.task
def detect_demo():
    query = """
    SELECT 
        client.company AS "Client",
        client_sdr.name AS "Rep",
        CONCAT(
            'https://app.sellscale.com/authenticate?stytch_token_type=direct&token=', client_sdr.auth_token, '&redirect=prospects/', prospect.id
        ) AS "Sight",
        prospect.full_name AS "Prospect",
        prospect.status AS "Status",
        prospect.overall_status AS "Overall Status",
        MAX(
            CONCAT(linkedin_conversation_entry.author, ': "', linkedin_conversation_entry.message, '"')
        ) AS "Caught Msg"
    FROM prospect
    JOIN prospect_status_records ON prospect_status_records.prospect_id = prospect.id AND prospect_status_records.to_status = 'ACTIVE_CONVO_SCHEDULING'
    JOIN linkedin_conversation_entry ON linkedin_conversation_entry.thread_urn_id = prospect.li_conversation_urn_id
    JOIN client_sdr ON client_sdr.id = prospect.client_sdr_id
    JOIN client ON client.id = client_sdr.client_id
    WHERE
        prospect.overall_status = 'ACTIVE_CONVO'
        AND (
            linkedin_conversation_entry.message ILIKE '%sent an invite%' OR
            linkedin_conversation_entry.message ILIKE '%sent out an invite%' OR
            linkedin_conversation_entry.message ILIKE '%sent%' AND linkedin_conversation_entry.message ILIKE '%placeholder%' OR
            linkedin_conversation_entry.message ILIKE '%calendar invite%' AND linkedin_conversation_entry.message ILIKE '%@%.%' AND linkedin_conversation_entry.message NOT ILIKE '%?%' OR
            linkedin_conversation_entry.message ILIKE '%@%.%' AND linkedin_conversation_entry.connection_degree <> 'You' OR
            linkedin_conversation_entry.message ILIKE '%email is%' AND linkedin_conversation_entry.connection_degree <> 'You' OR
            linkedin_conversation_entry.message ILIKE '%would be great%' AND linkedin_conversation_entry.connection_degree <> 'You' OR
            linkedin_conversation_entry.message ILIKE '%my email%' AND linkedin_conversation_entry.connection_degree <> 'You' OR
            linkedin_conversation_entry.message ILIKE '%put time on%' AND linkedin_conversation_entry.connection_degree <> 'You' OR
            linkedin_conversation_entry.message ILIKE '%can do monday%' AND linkedin_conversation_entry.connection_degree <> 'You' OR
            linkedin_conversation_entry.message ILIKE '%can do tuesday%' AND linkedin_conversation_entry.connection_degree <> 'You' OR
            linkedin_conversation_entry.message ILIKE '%can do wednesday%' AND linkedin_conversation_entry.connection_degree <> 'You' OR
            linkedin_conversation_entry.message ILIKE '%can do thursday%' AND linkedin_conversation_entry.connection_degree <> 'You' OR
            linkedin_conversation_entry.message ILIKE '%can do friday%' AND linkedin_conversation_entry.connection_degree <> 'You' OR
            linkedin_conversation_entry.message ILIKE '%can do tomorrow%' AND linkedin_conversation_entry.connection_degree <> 'You' OR
            linkedin_conversation_entry.message ILIKE '%can do today%' AND linkedin_conversation_entry.connection_degree <> 'You' OR
            linkedin_conversation_entry.message ILIKE '%meeting link%' OR
            linkedin_conversation_entry.message ILIKE '%your time today%' OR
            linkedin_conversation_entry.message ILIKE '%forward to chatting%' OR
            linkedin_conversation_entry.message ILIKE '%attend the meeting%' OR
            linkedin_conversation_entry.message ILIKE '%participate in the discussion%' OR
            linkedin_conversation_entry.message ILIKE '%connect on the call%' OR
            linkedin_conversation_entry.message ILIKE '%hop on the call%' OR
            linkedin_conversation_entry.message ILIKE '%dial into the meeting%' OR
            linkedin_conversation_entry.message ILIKE '%log into the call%' OR
            linkedin_conversation_entry.message ILIKE '%join our discussion%' OR
            linkedin_conversation_entry.message ILIKE '%attend our call%' OR
            linkedin_conversation_entry.message ILIKE '%join our meeting%' OR
            linkedin_conversation_entry.message ILIKE '%participate in our call%' OR
            linkedin_conversation_entry.message ILIKE '%connect on our call%' OR
            linkedin_conversation_entry.message ILIKE '%hop on our meeting%' OR
            linkedin_conversation_entry.message ILIKE '%dial into our call%' OR
            linkedin_conversation_entry.message ILIKE '%log into our meeting%' OR
            linkedin_conversation_entry.message ILIKE '%join our call%' OR
            linkedin_conversation_entry.message ILIKE '%attend our meeting%' OR
            linkedin_conversation_entry.message ILIKE '%participate in our discussion%' OR
            linkedin_conversation_entry.message ILIKE '%connect for our meeting%' OR
            linkedin_conversation_entry.message ILIKE '%hop on our call%' OR
            linkedin_conversation_entry.message ILIKE '%participate in our meeting%' OR
            linkedin_conversation_entry.message ILIKE '%connect for the call%' OR
            linkedin_conversation_entry.message ILIKE '%sent the details%' OR
            linkedin_conversation_entry.message ILIKE '%shared the calendar%' OR
            linkedin_conversation_entry.message ILIKE '%confirmed the time%' OR
            linkedin_conversation_entry.message ILIKE '%scheduled on%' OR
            linkedin_conversation_entry.message ILIKE '%set for%' OR
            linkedin_conversation_entry.message ILIKE '%looking forward to s%' OR
            linkedin_conversation_entry.message ILIKE '%looking forward to our meeting%' OR
            linkedin_conversation_entry.message ILIKE '%meeting scheduled%' OR
            linkedin_conversation_entry.message ILIKE '%appointment confirmed%' OR
            linkedin_conversation_entry.message ILIKE '%time set%' OR
            linkedin_conversation_entry.message ILIKE '%meeting confirmed%' OR
            linkedin_conversation_entry.message ILIKE '%call scheduled%' OR
            linkedin_conversation_entry.message ILIKE '%call confirmed%' OR
            linkedin_conversation_entry.message ILIKE '%see you then%' OR
            linkedin_conversation_entry.message ILIKE '%looking forward to our call%' OR
            linkedin_conversation_entry.message ILIKE '%demo set for%' OR
            linkedin_conversation_entry.message ILIKE '%talk soon%' OR
            linkedin_conversation_entry.message ILIKE '%confirmed for demo%' OR
            linkedin_conversation_entry.message ILIKE '%give you a ring%' OR
            linkedin_conversation_entry.message ILIKE '%just booked%' OR
            linkedin_conversation_entry.message ILIKE '%your call%' OR
            linkedin_conversation_entry.message ilike '%scheduled our call%'

        )
        AND client.active AND client_sdr.active
    GROUP BY 1, 2, 3, 4, 5, 6;
    """

    result = db.session.execute(query)
    results = result.fetchall()

    for row in results:
        rep = row["Rep"]
        sight = row["Sight"]
        prospect = row["Prospect"]
        status = row["Status"]
        caught_msg = row["Caught Msg"]

        send_slack_message(
            message=f"""
            🎉🎉🎉 !!!!! DEMO SET !!!!!! 🎉🎉🎉
            ```
            {caught_msg}
            ```
            ⏰ Current Status: "{status}"

            > 🤖 Rep: {rep} | 👥 Prospect: {prospect}

            🎊🎈 Take action and mark as ✅ (if wrong, inform an engineer)
            🔗 Direct Link: {sight}
            """,
            webhook_urls=[URL_MAP["csm-urgent-alerts"]],
        )
    
    result = db.session.execute(query)
    return result.fetchall()
