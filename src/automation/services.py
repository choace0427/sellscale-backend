from app import db, celery
from sqlalchemy.sql.expression import func
from src.automation.models import PhantomBusterConfig, PhantomBusterType
from model_import import Client, ClientSDR, ProspectStatus
from src.automation.models import PhantomBusterAgent
from tqdm import tqdm
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


def create_auto_connect_agent(
    client_sdr_id: int, linkedin_session_cookie: str, google_spreadsheet_uuid: str
):
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
    phantom_webhook = f"{api_url}/automation/phantombuster/auto_connect_webhook/1"

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
                "webhook": phantom_webhook
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
    client_sdr_id: int, linkedin_session_cookie: str
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
    """ Updates a PhantomBuster's LinkedIn authentication token

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
        if 'sessionCookie' in arguments:
            pb_agent.update_argument(key='sessionCookie', new_value=li_at)

    sdr: ClientSDR = ClientSDR.query.filter(ClientSDR.id == client_sdr_id).first()
    if not sdr:
        return "No client sdr found with this id", 400

    sdr.li_at_token = li_at
    db.session.add(sdr)
    db.session.commit()

    return "OK", 200


def create_pb_linkedin_invite_csv(client_sdr_id: int) -> list:
    """ Creates a CSV used by the phantom buster agent to invite people on LinkedIn

    Args:
        client_sdr_id (int): ID of the client SDR
    """
    from model_import import Prospect, GeneratedMessage, GeneratedMessageStatus

    # Grab two random  messages that belong to the ClientSDR
    joined_prospect_message = (
        db.session.query(
            Prospect.linkedin_url.label("linkedin_url"),
            GeneratedMessage.completion.label("completion"),
        )
        .join(GeneratedMessage, Prospect.id == GeneratedMessage.prospect_id)
        .filter(
            Prospect.client_sdr_id == client_sdr_id,
            Prospect.approved_outreach_message_id != None,
            GeneratedMessage.message_status == GeneratedMessageStatus.QUEUED_FOR_OUTREACH,
        )
        .order_by(func.random())
        .limit(2)
    ).all()

    data = []
    # Write the data rows
    for message in joined_prospect_message:
        data.append({
            "Linkedin": message.linkedin_url,
            "Message": message.completion,
        })

    return data


def update_pb_linkedin_send_status(client_sdr_id: int, pb_payload: dict) -> bool:
    """ Updates the status of a LinkedIn message sent by the phantom buster agent

    Args:
        client_sdr_id (int): ID of the client SDR
        pb_payload (dict): Payload from the phantom buster agent

    Example resultObject (use JSON Formatter to view):
        [{"0":"linkedin.com/in/steve-hyndman-8a57b816","fullName":"Steve Hyndman","firstName":"Steve","lastName":"Hyndman","connectionDegree":"1st","url":"https://www.linkedin.com/in/steve-hyndman-8a57b816","Message":"Hi Steve! I read that you have a passion for diversity and inclusion and experience in transformation risk and financial crime - an impressive career you have there! Id love to show you how monday can help your team’s productivity. No harm in benchmarking against your current system - up for a chat?","baseUrl":"linkedin.com/in/steve-hyndman-8a57b816","profileId":"steve-hyndman-8a57b816","profileUrl":"https://www.linkedin.com/in/steve-hyndman-8a57b816/","error":"Already in network","timestamp":"2023-03-28T16:42:40.033Z"},{"0":"linkedin.com/in/supriya-uchil","fullName":"Supriya Uchil","firstName":"Supriya","lastName":"Uchil","connectionDegree":"2nd","url":"https://www.linkedin.com/in/supriya-uchil","Message":"Hi Supriya! I read you've worked for great companies like Depop, Self Employed and BookingGo. Now as Vice Chair at Ounass, I'm sure you're looking for the best tools to help your team with productivity. Heard of monday.com? I'd love to show you how it can help supercharge your team - open to chat?","baseUrl":"linkedin.com/in/supriya-uchil","profileId":"supriya-uchil","profileUrl":"https://www.linkedin.com/in/supriya-uchil/","message":"Hi Supriya! I read you've worked for great companies like Depop, Self Employed and BookingGo. Now as Vice Chair at Ounass, I'm sure you're looking for the best tools to help your team with productivity. Heard of monday.com? I'd love to show you how it can help supercharge your team - open to chat?","error":"Email needed to add this person","timestamp":"2023-03-28T16:43:59.678Z"}]
    """
    from model_import import Prospect, GeneratedMessage, GeneratedMessageStatus
    from datetime import datetime

    # Check if the payload is valid
    exit_code = pb_payload.get("exitCode")
    if exit_code != 0:
        return False

    # Grab the result object
    result_object = pb_payload.get("resultObject")
    result_object = json.loads(result_object)
    if not result_object:
        return False

    # Loop through the results
    messages: list[GeneratedMessage] = []
    for result in result_object:
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
            update_prospect_status_linkedin(prospect_id=prospect_id, new_status=ProspectStatus.SEND_OUTREACH_FAILED)
            message.message_status = GeneratedMessageStatus.FAILED_TO_SEND
            message.failed_outreach_error = error
        else:
            update_prospect_status_linkedin(prospect_id=prospect_id, new_status=ProspectStatus.SENT_OUTREACH)
            message: GeneratedMessage = GeneratedMessage.query.get(message_id)
            message.message_status = GeneratedMessageStatus.SENT
            message.date_sent = datetime.now()
            message.failed_outreach_error = None
            sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
            sdr_name = sdr.name
            message_completion = message.completion

            send_slack_message(
                message=f"LinkedIn Autoconnect: {sdr_name} sent a message to {prospect_li}\nmessage: {message_completion}",
                webhook_urls=[URL_MAP["operations-li-sent-messages"]],
            )

        messages.append(message)

    db.session.bulk_save_objects(messages)
    db.session.commit()

    return True



def backfill_func():
    from app import db
    from model_import import Prospect, GeneratedMessage, GeneratedMessageStatus, ProspectStatus, ProspectOverallStatus
    backfill_prospect_ids: list[int] = [int(num) for num in """
    22797
22883
22890
22893
22899
22901
22920
23065
23068
23075
23092
23107
23109
23112
23148
23177
23185
23186
23228
23232
23234
23240
23257
23311
23338
23362
23407
23415
23420
23422
23440
23458
23462
23466
23502
23503
26045
26051
26096
26133
26139
26149
26162
26172
26180
26189
26191
26220
26223
26318
26338
26350
26355
26361
26373
26378
26380
26418
26419
26447
22555
22573
22577
22588
22622
22678
22709
22712
22726
22739
22746
22761
22772
22774
22786
22805
22812
22819
22846
22849
22855
22876
22878
22916
22949
23022
23026
23042
23069
23117
23209
23282
23296
23316
23325
23326
23331
23356
23371
23433
23434
23436
23460
23476
23488
23513
26040
26063
26065
26098
26108
26128
26134
26157
26163
26165
26174
26192
26214
26231
26268
26277
26303
26305
26343
26356
26357
26368
26396
26407
26411
26426
26431
26437
26443
22654
22679
22727
22755
22756
22757
22773
22784
22817
22825
22842
22845
22851
22866
22881
22907
22924
22939
22942
22944
22964
22982
22986
22993
23002
23018
23049
23052
23115
23122
23130
23131
23134
23160
23161
23168
23190
23199
23200
23201
23225
23229
23252
23288
23294
23298
23336
23351
23374
23376
23396
23448
23498
26059
26105
26107
26110
26117
26118
26121
26130
26136
26148
26153
26199
26230
26263
26275
26329
26375
26405
26433
26434
26435
22547
22554
22561
22547
22554
22561
22588
22603
22644
22653
22676
22678
22681
22704
22748
22758
22772
22781
22794
22802
22830
22831
22836
22842
22857
22869
22897
22901
22991
22993
22994
23036
23059
23108
23113
23124
23125
23184
23216
23230
23264
23269
23275
23318
23363
23377
23381
23382
23400
23405
23417
23448
23451
23455
23467
23470
23489
23501
23505
26071
26102
26151
26160
26182
26185
26195
26211
26219
26270
26277
26318
26323
26356
26370
26373
26384
26508
29839
    """.split()]
    print(backfill_prospect_ids)
    updated_prospects = []
    updated_messages = []
    from tqdm import tqdm
    for prospect_id in tqdm(backfill_prospect_ids):
        prospect: Prospect = Prospect.query.get(prospect_id)
        if prospect is None:
            continue
        prospect.status = ProspectStatus.QUEUED_FOR_OUTREACH
        prospect.overall_status = ProspectOverallStatus.PROSPECTED
        gm: GeneratedMessage = GeneratedMessage.query.get(prospect.approved_outreach_message_id)
        gm.message_status = GeneratedMessageStatus.QUEUED_FOR_OUTREACH
        updated_prospects.append(prospect)
        updated_messages.append(gm)
    db.session.bulk_save_objects(updated_prospects)
    db.session.bulk_save_objects(updated_messages)
    db.session.commit()
