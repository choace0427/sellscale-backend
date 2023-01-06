import json
from src.automation.models import PhantomBusterConfig, PhantomBusterType
from model_import import Client, ClientSDR
from src.automation.models import PhantomBusterAgent
from app import db
import requests
import os
from tqdm import tqdm
from app import celery

PHANTOMBUSTER_API_KEY = os.environ.get("PHANTOMBUSTER_API_KEY")
GET_PHANTOMBUSTER_AGENTS_URL = "https://api.phantombuster.com/api/v2/agents/fetch-all"


def create_phantom_buster_config(
    client_id: int,
    client_sdr_id: int,
    phantom_name: str,
    phantom_uuid: str,
    phantom_type: PhantomBusterType,
    google_sheets_uuid: str = None,
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
        google_sheets_uuid=google_sheets_uuid,
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


def create_auto_connect_agent(
    client_sdr_id: int, linkedin_session_cookie: str, google_spreadsheet_uuid: str
):
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client: Client = Client.query.get(client_sdr.client_id)
    client_sdr_name: str = client_sdr.name
    client_company = client.company
    url = "https://api.phantombuster.com/api/v2/agents/save"

    phantom_name = "LinkedIn Auto Connect - {company} ({sdr_name})".format(
        company=client_company, sdr_name=client_sdr_name
    )
    google_sheet_link = (
        "https://docs.google.com/spreadsheets/d/{}/edit?usp=sharing".format(
            google_spreadsheet_uuid
        )
    )

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
            + google_sheet_link
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
                "minute": [41],
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


def create_new_auto_connect_phantom(
    client_sdr_id: int, linkedin_session_cookie: str, google_sheet_uuid: str
):
    client_sdr: ClientSDR = ClientSDR.query.filter(
        ClientSDR.id == client_sdr_id
    ).first()
    client_sdr_name = client_sdr.name
    client: Client = Client.query.filter(Client.id == client_sdr.client_id).first()
    client_id = client.id
    company_name = client.company

    inbox_scraper_agent_id, inbox_scraper_agent_name = create_inbox_scraper_agent(
        client_sdr_id, linkedin_session_cookie
    )
    auto_connect_agent_id, auto_connect_agent_name = create_auto_connect_agent(
        client_sdr_id, linkedin_session_cookie, google_sheet_uuid
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
        google_sheets_uuid=google_sheet_uuid,
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
    pb_agent: PhantomBusterAgent = PhantomBusterAgent(
        id=phantom_id, api_key=PHANTOMBUSTER_API_KEY
    )
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
