import random
from sqlalchemy import nullslast, or_
from app import db, celery
from sqlalchemy.sql.expression import func
from src.automation.models import (
    PhantomBusterConfig,
    PhantomBusterType,
    PhantomBusterPayload,
)
from model_import import Client, ClientSDR, ProspectStatus, GeneratedMessageType
from src.automation.models import PhantomBusterAgent
from tqdm import tqdm
from src.campaigns.models import OutboundCampaign
from src.client.models import ClientArchetype
from src.prospecting.services import update_prospect_status_linkedin
from src.utils.slack import send_slack_message, URL_MAP
import json
import requests
import os
import io
import csv

PHANTOMBUSTER_API_KEY = os.environ.get("PHANTOMBUSTER_API_KEY")
GET_PHANTOMBUSTER_AGENTS_URL = "https://api.phantombuster.com/api/v2/agents/fetch-all"


def create_phantom_buster_config(
    client_id: int,
    client_sdr_id: int,
    phantom_name: str,
    phantom_uuid: str,
    phantom_type: PhantomBusterType,
):
    existing_config: PhantomBusterConfig = PhantomBusterConfig.query.filter(
        PhantomBusterConfig.client_sdr_id == client_sdr_id,
        PhantomBusterConfig.pb_type == phantom_type,
    ).first()
    if existing_config:
        return {"phantom_buster_config_id": existing_config.id}

    pb_config = PhantomBusterConfig(
        client_id=client_id,
        client_sdr_id=client_sdr_id,
        pb_type=phantom_type,
        phantom_name=phantom_name,
        phantom_uuid=phantom_uuid,
    )
    db.session.add(pb_config)
    db.session.commit()

    return {"phantom_buster_config_id": pb_config.id}


def get_all_phantom_busters(
    pb_type: PhantomBusterType,
    search_term: str = None,
):
    headers = {
        "accept": "application/json",
        "X-Phantombuster-Key": "UapzERoGG1Q7qcY1jmoisJgR6MNJUmdL2w4UcLCtOJQ",
    }

    response = requests.get(GET_PHANTOMBUSTER_AGENTS_URL, headers=headers)
    response_json = json.loads(response.text)

    phantom_map = []
    for x in response_json:
        if search_term and search_term not in x["name"]:
            continue

        config: PhantomBusterConfig = PhantomBusterConfig.query.filter(
            PhantomBusterConfig.phantom_uuid == x["id"],
            PhantomBusterConfig.pb_type == pb_type,
        ).first()
        phantom_map.append(
            {
                "config_id": config and config.id,
                "phantom_name": x["name"],
                "client_id": config and config.client_id,
                "client_sdr_id": config and config.client_sdr_id,
                "google_sheets_uuid": config and config.google_sheets_uuid,
                "phantom_uuid": config and config.phantom_uuid,
                "phantom_id": x["id"],
            }
        )

    return phantom_map


def create_inbox_scraper_agent(client_sdr_id: int, linkedin_session_cookie: str):
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client: Client = Client.query.get(client_sdr.client_id)
    client_sdr_name: str = client_sdr.name
    client_company = client.company
    url = "https://api.phantombuster.com/api/v2/agents/save"

    phantom_name = "LinkedIn Inbox Scraper - {company} ({sdr_name})".format(
        company=client_company, sdr_name=client_sdr_name
    )

    payload = json.dumps(
        {
            "org": "phantombuster",
            "script": "LinkedIn Inbox Scraper.js",
            "branch": "master",
            "environment": "release",
            "name": phantom_name,
            "argument": '{\n\t"inboxFilter": "all",\n\t"sessionCookie": "'
            + linkedin_session_cookie
            + '",\n\t"numberOfThreadsToScrape": 100\n}',
            "launchType": "repeatedly",
            "repeatedLaunchTimes": {
                "day": [
                    1,
                    2,
                    3,
                    4,
                    5,
                    6,
                    7,
                    8,
                    9,
                    10,
                    11,
                    12,
                    13,
                    14,
                    15,
                    16,
                    17,
                    18,
                    19,
                    20,
                    21,
                    22,
                    23,
                    24,
                    25,
                    26,
                    27,
                    28,
                    29,
                    30,
                    31,
                ],
                "dow": ["mon", "tue", "wed", "thu", "fri", "sat"],
                "hour": [9],
                "month": [
                    "jan",
                    "feb",
                    "mar",
                    "apr",
                    "may",
                    "jun",
                    "jul",
                    "aug",
                    "sep",
                    "oct",
                    "nov",
                    "dec",
                ],
                "minute": [14],
                "timezone": "America/Los_Angeles",
                "simplePreset": "Once per day",
                "isSimplePresetEnabled": False,
            },
            "notifications": {
                "slackWebHook": "https://hooks.slack.com/services/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",
                "mailManualExitError": False,
                "mailManualTimeError": False,
                "slackManualExitError": False,
                "slackManualTimeError": False,
                "mailManualExitSuccess": False,
                "mailManualLaunchError": False,
                "mailAutomaticExitError": False,
                "mailAutomaticTimeError": False,
                "slackManualExitSuccess": False,
                "slackManualLaunchError": False,
                "slackAutomaticExitError": False,
                "slackAutomaticTimeError": False,
                "mailAutomaticExitSuccess": False,
                "mailAutomaticLaunchError": False,
                "slackAutomaticExitSuccess": False,
                "slackAutomaticLaunchError": False,
            },
            "applyScriptManifestDefaultSettings": False,
            "fileMgmt": "mix",
            "maxParallelism": 1,
        }
    )
    headers = {
        "X-Phantombuster-Key": PHANTOMBUSTER_API_KEY,
        "accept": "application/json",
        "Content-Type": "application/json",
    }

    response = requests.request("POST", url, headers=headers, data=payload)
    phantom_id = response.json()["id"]
    return phantom_id, phantom_name


def create_auto_connect_agent(client_sdr_id: int, linkedin_session_cookie: str):
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client_sdr_id = client_sdr.id
    client: Client = Client.query.get(client_sdr.client_id)
    client_sdr_name: str = client_sdr.name
    client_company = client.company
    url = "https://api.phantombuster.com/api/v2/agents/save"

    phantom_name = "LinkedIn Auto Connect - {company} ({sdr_name})".format(
        company=client_company, sdr_name=client_sdr_name
    )
    api_url = os.environ.get("SELLSCALE_API_URL")
    csv_api = f"{api_url}/automation/phantombuster/auto_connect_csv/{client_sdr_id}"
    phantom_webhook = (
        f"{api_url}/automation/phantombuster/auto_connect_webhook/{client_sdr_id}"
    )

    # Get random integer to represent minute, between 0 and 59
    random_minute = random.randint(0, 59)

    payload = json.dumps(
        {
            "org": "phantombuster",
            "script": "LinkedIn Auto Connect.js",
            "branch": "master",
            "environment": "release",
            "name": phantom_name,
            "argument": '{\n\t"onlySecondCircle": false,\n\t"waitDuration": 30,\n\t"skipProfiles": true,\n\t"dwellTime": true,\n\t"sessionCookie": "'
            + linkedin_session_cookie
            + '",\n\t"spreadsheetUrl": "'
            + csv_api
            + '",\n\t"message": "#Message#",\n\t"spreadsheetUrlExclusionList": [],\n\t"numberOfAddsPerLaunch": 2\n}',
            "launchType": "repeatedly",
            "repeatedLaunchTimes": {
                "day": [
                    1,
                    2,
                    3,
                    4,
                    5,
                    6,
                    7,
                    8,
                    9,
                    10,
                    11,
                    12,
                    13,
                    14,
                    15,
                    16,
                    17,
                    18,
                    19,
                    20,
                    21,
                    22,
                    23,
                    24,
                    25,
                    26,
                    27,
                    28,
                    29,
                    30,
                    31,
                ],
                "dow": ["thu", "fri", "wed", "tue"],
                "hour": [9, 11, 12, 15, 16, 17, 14, 10],
                "month": [
                    "jan",
                    "feb",
                    "mar",
                    "apr",
                    "may",
                    "jun",
                    "jul",
                    "aug",
                    "sep",
                    "oct",
                    "nov",
                    "dec",
                ],
                "minute": [random_minute],
                "timezone": "America/Los_Angeles",
                "simplePreset": "Once per working hour, excluding weekends",
                "isSimplePresetEnabled": False,
            },
            "notifications": {
                "slackWebHook": "https://hooks.slack.com/services/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",
                "mailManualExitError": False,
                "mailManualTimeError": False,
                "slackManualExitError": True,
                "slackManualTimeError": True,
                "mailManualExitSuccess": False,
                "mailManualLaunchError": False,
                "mailAutomaticExitError": False,
                "mailAutomaticTimeError": False,
                "slackManualExitSuccess": False,
                "slackManualLaunchError": True,
                "slackAutomaticExitError": True,
                "slackAutomaticTimeError": True,
                "mailAutomaticExitSuccess": False,
                "mailAutomaticLaunchError": False,
                "slackAutomaticExitSuccess": False,
                "slackAutomaticLaunchError": True,
                "webhook": phantom_webhook,
            },
            "proxyAddress": "",
            "proxyType": "none",
            "applyScriptManifestDefaultSettings": False,
            "fileMgmt": "mix",
            "maxParallelism": 1,
        }
    )
    headers = {
        "X-Phantombuster-Key": PHANTOMBUSTER_API_KEY,
        "accept": "application/json",
        "Content-Type": "application/json",
    }

    response = requests.request("POST", url, headers=headers, data=payload)
    phantom_id = response.json()["id"]
    return phantom_id, phantom_name


def get_all_agent_groups():
    url = "https://api.phantombuster.com/api/v2/orgs/fetch-agent-groups"

    headers = {
        "accept": "application/json",
        "X-Phantombuster-Key": "UapzERoGG1Q7qcY1jmoisJgR6MNJUmdL2w4UcLCtOJQ",
    }

    response = requests.get(url, headers=headers)

    return response.json()


def save_agent_groups(agent_groups: list):
    url = "https://api.phantombuster.com/api/v2/orgs/save-agent-groups"

    payload = {"agentGroups": agent_groups}
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "X-Phantombuster-Key": "UapzERoGG1Q7qcY1jmoisJgR6MNJUmdL2w4UcLCtOJQ",
    }

    response = requests.post(url, json=payload, headers=headers)

    return response.json()


def has_phantom_buster_config(client_sdr_id: int):
    pb_config: PhantomBusterConfig = PhantomBusterConfig.query.filter(
        PhantomBusterConfig.client_sdr_id == client_sdr_id
    ).first()
    return pb_config is not None


def create_new_auto_connect_phantom(client_sdr_id: int, linkedin_session_cookie: str):
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if not client_sdr:
        return None, None
    client_sdr_name = client_sdr.name
    client_sdr.li_at_token = linkedin_session_cookie
    client: Client = Client.query.filter(Client.id == client_sdr.client_id).first()
    client_id = client.id
    company_name = client.company

    inbox_scraper_agent_id, inbox_scraper_agent_name = create_inbox_scraper_agent(
        client_sdr_id, linkedin_session_cookie
    )
    auto_connect_agent_id, auto_connect_agent_name = create_auto_connect_agent(
        client_sdr_id, linkedin_session_cookie
    )

    agent_groups = get_all_agent_groups()
    agent_groups.append(
        {
            "id": "{} - {}".format(company_name, client_sdr_name),
            "name": "{} - {}".format(company_name, client_sdr_name),
            "agents": [inbox_scraper_agent_id, auto_connect_agent_id],
        }
    )
    success = save_agent_groups(agent_groups)

    inbox_scraper_pb_config = create_phantom_buster_config(
        client_id=client_id,
        client_sdr_id=client_sdr_id,
        phantom_name=inbox_scraper_agent_name,
        phantom_uuid=inbox_scraper_agent_id,
        phantom_type=PhantomBusterType.INBOX_SCRAPER,
    )
    auto_connect_pb_config = create_phantom_buster_config(
        client_id=client_id,
        client_sdr_id=client_sdr_id,
        phantom_name=auto_connect_agent_name,
        phantom_uuid=auto_connect_agent_id,
        phantom_type=PhantomBusterType.OUTBOUND_ENGINE,
    )

    return inbox_scraper_pb_config, auto_connect_pb_config


def get_all_phantom_buster_ids():
    import requests

    url = "https://api.phantombuster.com/api/v2/agents/fetch-all"

    payload = {}
    headers = {
        "X-Phantombuster-Key": PHANTOMBUSTER_API_KEY,
        "accept": "application/json",
    }

    response = requests.request("GET", url, headers=headers, data=payload)

    data = response.json()
    return [x["id"] for x in data]


def update_all_phantom_buster_run_statuses():
    phantom_buster_ids = get_all_phantom_buster_ids()

    for phantom_id in tqdm(phantom_buster_ids):
        update_phantom_buster_run_status.delay(phantom_id)


@celery.task
def update_phantom_buster_run_status(phantom_id: str):
    pb_agent: PhantomBusterAgent = PhantomBusterAgent(id=phantom_id)
    last_run_date = pb_agent.get_last_run_date()
    error_message = pb_agent.get_error_message()

    pb_config = PhantomBusterConfig.query.filter(
        PhantomBusterConfig.phantom_uuid == phantom_id
    ).first()

    if pb_config:
        pb_config.last_run_date = last_run_date
        pb_config.error_message = error_message
        db.session.add(pb_config)
        db.session.commit()


def update_phantom_buster_li_at(client_sdr_id: int, li_at: str):
    """Updates a PhantomBuster's LinkedIn authentication token

    Args:
        client_sdr_id (int): ID of the client SDR
        li_at (str): LinkedIn authentication token

    Returns:
        status_code (int), message (str): HTTP status code
    """
    pbs: PhantomBusterConfig = PhantomBusterConfig.query.filter(
        PhantomBusterConfig.client_sdr_id == client_sdr_id
    ).all()
    if not pbs:
        return "No phantoms found for this client sdr", 400

    for pb in pbs:
        pb_id = pb.phantom_uuid
        pb_agent: PhantomBusterAgent = PhantomBusterAgent(id=pb_id)
        arguments = pb_agent.get_arguments()
        if "sessionCookie" in arguments:
            pb_agent.update_argument(key="sessionCookie", new_value=li_at)

    sdr: ClientSDR = ClientSDR.query.filter(ClientSDR.id == client_sdr_id).first()
    if not sdr:
        return "No client sdr found with this id", 400

    sdr.li_at_token = li_at
    db.session.add(sdr)
    db.session.commit()

    return "OK", 200


def create_pb_linkedin_invite_csv(client_sdr_id: int) -> list:
    """Creates a CSV used by the phantom buster agent to invite people on LinkedIn

    Args:
        client_sdr_id (int): ID of the client SDR
    """
    from model_import import Prospect, GeneratedMessage, GeneratedMessageStatus

    # CSV limit is default to 10
    csv_limit = 2

    # Get the phantom buster for config data
    pb: PhantomBusterConfig = PhantomBusterConfig.query.filter(
        PhantomBusterConfig.client_sdr_id == client_sdr_id,
        PhantomBusterConfig.pb_type == PhantomBusterType.OUTBOUND_ENGINE,
    ).first()
    if pb:
        pb_agent = PhantomBusterAgent(pb.phantom_uuid)
        if pb_agent:
            config_data = pb_agent.get_agent_data()
            if config_data:
                argument = config_data.get("argument")
                if argument:
                    argument: dict = json.loads(argument)
                    csv_limit = argument.get("numberOfAddsPerLaunch", csv_limit)

    # Grab two random  messages that belong to the ClientSDR
    joined_prospect_message = (
        db.session.query(
            Prospect.id.label("prospect_id"),
            Prospect.full_name.label("full_name"),
            Prospect.icp_fit_score.label("icp_fit_score"),
            Prospect.icp_fit_reason.label("icp_fit_reason"),
            Prospect.title.label("title"),
            Prospect.company.label("company"),
            Prospect.img_url.label("img_url"),
            Prospect.linkedin_url.label("linkedin_url"),
            Prospect.approved_outreach_message_id.label("generated_message_id"),
            ClientArchetype.archetype.label("archetype"),
            GeneratedMessage.id.label("message_id"),
            GeneratedMessage.completion.label("completion"),
        )
        .join(
            GeneratedMessage,
            Prospect.approved_outreach_message_id == GeneratedMessage.id,
        )
        .join(
            ClientArchetype,
            ClientArchetype.id == Prospect.archetype_id,
        )
        .outerjoin(
            OutboundCampaign,
            OutboundCampaign.id == GeneratedMessage.outbound_campaign_id,
        )
        .filter(
            Prospect.client_sdr_id == client_sdr_id,
            GeneratedMessage.message_status
            == GeneratedMessageStatus.QUEUED_FOR_OUTREACH,
            or_(
                GeneratedMessage.pb_csv_count <= 2,
                GeneratedMessage.pb_csv_count == None,
            ),  # Only grab messages that have not been sent twice
        )
    )

    total_count = joined_prospect_message.count()

    joined_prospect_message = (
        joined_prospect_message.order_by(OutboundCampaign.priority_rating.desc())
        .order_by(nullslast(GeneratedMessage.priority_rating.desc()))
        .order_by(nullslast(Prospect.icp_fit_score.desc()))
        .order_by(nullslast(GeneratedMessage.created_at.desc()))
        .limit(csv_limit)
        .all()
    )

    data = []
    print(len(joined_prospect_message))
    # Write the data rows
    wrote_prospect = set()
    for message in joined_prospect_message:
        if message.prospect_id in wrote_prospect:
            continue
        wrote_prospect.add(message.prospect_id)
        data.append(
            {
                "Linkedin": message.linkedin_url,
                "Message": message.completion,
            }
        )
        prospect_id = message.prospect_id
        generated_message_id = message.generated_message_id

        # Update the pb_csv_count
        gm: GeneratedMessage = GeneratedMessage.query.get(generated_message_id)
        if not gm:
            continue
        if gm.pb_csv_count is None:
            gm.pb_csv_count = 0
        gm.pb_csv_count += 1

        # If the message has now been sent more than twice, we mark it as failed until the PB webhook is called
        if gm.pb_csv_count > 2:
            gm.message_status = GeneratedMessageStatus.FAILED_TO_SEND
            update_prospect_status_linkedin(
                prospect_id=prospect_id, new_status=ProspectStatus.SEND_OUTREACH_FAILED
            )
        db.session.commit()

    return data


def update_pb_linkedin_send_status(client_sdr_id: int, pb_payload: dict) -> bool:
    """Updates the status of a LinkedIn message sent by the phantom buster agent

    Args:
        client_sdr_id (int): ID of the client SDR
        pb_payload (dict): Payload from the phantom buster agent

    Example resultObject (use JSON Formatter to view):
        [{"0":"linkedin.com/in/steve-hyndman-8a57b816","fullName":"Steve Hyndman","firstName":"Steve","lastName":"Hyndman","connectionDegree":"1st","url":"https://www.linkedin.com/in/steve-hyndman-8a57b816","Message":"Hi Steve! I read that you have a passion for diversity and inclusion and experience in transformation risk and financial crime - an impressive career you have there! Id love to show you how monday can help your team’s productivity. No harm in benchmarking against your current system - up for a chat?","baseUrl":"linkedin.com/in/steve-hyndman-8a57b816","profileId":"steve-hyndman-8a57b816","profileUrl":"https://www.linkedin.com/in/steve-hyndman-8a57b816/","error":"Already in network","timestamp":"2023-03-28T16:42:40.033Z"},{"0":"linkedin.com/in/supriya-uchil","fullName":"Supriya Uchil","firstName":"Supriya","lastName":"Uchil","connectionDegree":"2nd","url":"https://www.linkedin.com/in/supriya-uchil","Message":"Hi Supriya! I read you've worked for great companies like Depop, Self Employed and BookingGo. Now as Vice Chair at Ounass, I'm sure you're looking for the best tools to help your team with productivity. Heard of monday.com? I'd love to show you how it can help supercharge your team - open to chat?","baseUrl":"linkedin.com/in/supriya-uchil","profileId":"supriya-uchil","profileUrl":"https://www.linkedin.com/in/supriya-uchil/","message":"Hi Supriya! I read you've worked for great companies like Depop, Self Employed and BookingGo. Now as Vice Chair at Ounass, I'm sure you're looking for the best tools to help your team with productivity. Heard of monday.com? I'd love to show you how it can help supercharge your team - open to chat?","error":"Email needed to add this person","timestamp":"2023-03-28T16:43:59.678Z"}]
    """
    from model_import import Prospect, GeneratedMessage, GeneratedMessageStatus
    from datetime import datetime

    # Create the payload
    payload: PhantomBusterPayload = PhantomBusterPayload(
        client_sdr_id=client_sdr_id,
        pb_type=PhantomBusterType.OUTBOUND_ENGINE,
        pb_payload=pb_payload,
    )
    db.session.add(payload)
    db.session.commit()

    # Check if the payload is valid
    exit_code = pb_payload.get("exitCode")
    if exit_code != 0:
        return False

    # Grab the result object
    result_object = pb_payload.get("resultObject")
    if not result_object:
        return False
    result_object = json.loads(result_object)
    if not result_object:
        return False

    # Loop through the results
    for result in result_object:
        if result.get("0") is None:
            continue

        # Grab the prospect
        prospect: Prospect = Prospect.query.filter(
            Prospect.linkedin_url == result.get("0"),
            Prospect.client_sdr_id == client_sdr_id,
        ).first()
        if not prospect:
            continue
        prospect_id = prospect.id
        prospect_li = prospect.linkedin_url

        # Grab the message
        message: GeneratedMessage = GeneratedMessage.query.filter(
            GeneratedMessage.id == prospect.approved_outreach_message_id
        ).first()
        if not message:
            continue
        message_id = message.id

        # Check for error, otherwise set the message to sent
        error = result.get("error")
        if error:
            message.message_status = GeneratedMessageStatus.FAILED_TO_SEND
            message.failed_outreach_error = error
            db.session.add(message)
            db.session.commit()

            update_prospect_status_linkedin(
                prospect_id=prospect_id, new_status=ProspectStatus.SEND_OUTREACH_FAILED
            )
        else:
            message.message_status = GeneratedMessageStatus.SENT
            message.date_sent = datetime.now()
            message.failed_outreach_error = None
            sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
            sdr_name = sdr.name
            message_completion = message.completion
            db.session.add(message)
            db.session.commit()

            update_prospect_status_linkedin(
                prospect_id=prospect_id, new_status=ProspectStatus.SENT_OUTREACH
            )

            send_slack_message(
                message=f"LinkedIn Autoconnect: {sdr_name} sent a message to {prospect_li}\nmessage: {message_completion}",
                webhook_urls=[URL_MAP["operations-li-sent-messages"]],
            )

    db.session.commit()

    return True
