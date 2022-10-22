from src.automation.models import PhantomBusterType, PhantomBusterConfig
from model_import import ProspectStatus, Prospect
from src.utils.slack import send_slack_message
import requests
import json
import os
from src.prospecting.services import (
    get_linkedin_slug_from_url,
    find_prospect_by_linkedin_slug,
)
from src.prospecting.services import update_prospect_status

PHANTOMBUSTER_API_KEY = os.environ.get("PHANTOMBUSTER_API_KEY")


def get_inbox_scraper_config(client_sdr_id: int):
    pb_config: PhantomBusterConfig = PhantomBusterConfig.query.filter(
        PhantomBusterConfig.client_sdr_id == client_sdr_id,
        PhantomBusterConfig.pb_type == PhantomBusterType.INBOX_SCRAPER,
    ).first()

    return pb_config


def get_phantom_buster_agent(config: PhantomBusterConfig):
    """Get the payload of a phantom buster config"""
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


def process_inbox(message_payload):
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
        is_group_message = len(message["linkedInUrls"]) > 1
        is_last_message_from = message["isLastMessageFromMe"]
        recipient = get_linkedin_slug_from_url(message["linkedInUrls"][0])
        last_message = message["message"]

        prospect: Prospect = find_prospect_by_linkedin_slug(recipient)

        if is_group_message or not prospect:
            continue

        if prospect.status == ProspectStatus.SENT_OUTREACH and is_last_message_from:
            send_slack_block(
                message_suffix=" accepted your invite! 😀",
                prospect=prospect,
                new_status=ProspectStatus.ACCEPTED,
                li_message_payload=message,
            )
        elif (
            prospect.status == ProspectStatus.SENT_OUTREACH and not is_last_message_from
        ):
            send_slack_block(
                message_suffix=" responded to your outreach! 🙌🏽",
                prospect=prospect,
                new_status=ProspectStatus.ACTIVE_CONVO,
                li_message_payload=message,
            )
        elif (
            prospect.status == ProspectStatus.ACTIVE_CONVO and not is_last_message_from
        ):
            send_slack_block(
                message_suffix=" sent you a follow up 👀",
                prospect=prospect,
                li_message_payload=message,
            )


def send_slack_block(
    message_suffix: str,
    prospect: Prospect,
    li_message_payload: any,
    new_status: ProspectStatus = None,
):
    send_slack_message(
        message=prospect.full_name + message_suffix,
        blocks=[
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": prospect.full_name + message_suffix,
                },
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": "*Company:*\n<{link}|{name}>".format(
                            link=prospect.company_url, name=prospect.company
                        ),
                    },
                    {
                        "type": "mrkdwn",
                        "text": "*Title:*\n{}".format(prospect.title),
                    },
                ],
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Last Message*\n{}".format(li_message_payload["message"]),
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "This is a section block with a button.",
                },
                "accessory": {
                    "type": "button",
                    "text": {
                        "type": "View LI Conversation Thread",
                        "text": "Thread",
                        "emoji": true,
                    },
                    "value": li_message_payload["threadUrl"],
                    "url": li_message_payload["threadUrl"],
                    "action_id": "button-action",
                },
            },
        ],
    )

    # if new_status:
    #   update_prospect_status(
    #         prospect_id=prospect.id, new_status=new_status
    #   )


def scrape_inbox(client_sdr_id: int):
    """Scrape the inbox of a client on Linkedin"""
    pb_config = get_inbox_scraper_config(client_sdr_id=client_sdr_id)
    if not pb_config:
        raise Exception(
            "No inbox scraper config found for client #{}".format(client_sdr_id)
        )

    agent = get_phantom_buster_agent(config=pb_config)
    s3Folder = agent["s3Folder"]
    orgS3Folder = agent["orgS3Folder"]

    data_payload = get_phantom_buster_payload(
        s3Folder=s3Folder, orgS3Folder=orgS3Folder
    )

    process_inbox(message_payload=data_payload)

    return True
