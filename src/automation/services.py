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
        else:
            update_prospect_status_linkedin(prospect_id=prospect.id, new_status=ProspectStatus.SENT_OUTREACH)
            message: GeneratedMessage = GeneratedMessage.query.get(message_id)
            message.message_status = GeneratedMessageStatus.SENT
            message.date_sent = datetime.now()
            message.failed_outreach_error = None
            sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
            send_slack_message(
                message=f"LinkedIn Autoconnect: {sdr.name} sent a message to {prospect.linkedin_url}\nmessage: {message.completion}",
                webhook_urls=[URL_MAP["operations-li-sent-messages"]],
            )

        messages.append(message)

    db.session.bulk_save_objects(messages)
    db.session.commit()

    return True



def backfill_func():
    from app import db
    from model_import import Prospect, GeneratedMessage, GeneratedMessageStatus, ProspectStatus, ProspectOverallStatus
    backfill_prospect_ids = [int(num) for num in """34614
        34616
        34618
        34619
        34622
        34623
        34624
        34625
        34626
        34628
        34629
        34630
        34632
        34633
        34634
        34635
        34636
        34637
        34639
        34640
        34641
        34642
        34644
        34645
        34646
        34647
        34648
        34649
        34650
        34652
        34653
        34654
        34655
        34656
        34658
        34659
        34660
        34661
        34662
        34663
        34664
        50793
        50823
        50831
        50841
        50861
        50878
        50880
        50902
        50911
        50962
        50978
        50981
        51018
        51048
        51052
        51054
        51063
        51130
        51135
        51144
        51150
        51194
        51205
        51206
        51220
        51224
        51253
        51295
        51318
        51334
        51363
        51428
        51436
        51460
        51469
        51478
        51600
        51658
        51678
        51767
        51822
        52287
        52295
        52304
        52314
        52318
        52321
        52323
        52324
        52326
        52345
        52358
        52361
        52393
        52395
        52434
        52440
        52455
        52456
        52485
        52509
        52528
        52565
        52578
        52587
        52601
        52630
        52647
        52661
        52667
        52681
        52921
        53080
        50681
        50776
        50778
        50806
        50852
        50867
        50869
        50875
        50876
        50889
        50915
        50939
        50967
        50999
        51002
        51025
        51060
        51116
        51126
        51129
        51143
        51201
        51221
        51473
        51475
        51490
        51579
        51621
        51740
        51843
        51964
        52043
        52292
        52294
        52297
        52301
        52319
        52335
        52338
        52340
        52341
        52356
        52359
        52368
        52370
        52376
        52411
        52412
        52413
        52417
        52429
        52436
        52443
        52447
        52464
        52476
        52500
        52511
        52526
        52529
        52537
        52538
        52548
        52551
        52563
        52573
        52665
        52736
        52738
        52821
        52974
        53008
        53037
        53049
        53072
        32359
        32385
        32686
        32730
        32815
        32823
        32848
        32856
        32860
        32889
        32916
        32933
        33018
        33036
        33043
        33107
        33125
        33154
        33203
        33214
        33221
        33224
        33239
        33250
        33326
        33349
        33386
        33401
        33415
        33445
        33460
        33524
        33528
        33532
        33533
        33541
        33565
        33586
        33588
        33633
        33635
        33653
        33756
        33774
        33846
        33892
        33942
        33977
        34000
        34025
        34051
        34069
        34133
        34144
        34148
        34167
        34174
        34183
        34204
        34253
        34264
        34291
        34328
        34346
        34373
        34396
        34397
        34418
        34462
        34482
        34493
        34515
        34547
        34570
        32352
        32363
        32425
        32520
        32531
        32535
        32628
        32643
        32690
        32708
        32725
        32786
        32814
        32833
        32904
        32921
        32942
        32955
        32983
        33095
        33114
        33120
        33201
        33207
        33212
        33233
        33266
        33323
        33411
        33416
        33525
        33569
        33612
        33730
        33769
        33820
        33824
        33831
        33873
        33875
        33946
        33954
        33959
        34013
        34113
        34203
        34209
        34230
        34296
        34317
        34338
        34345
        34351
        34424
        34453
        34458
        34469
        34507
        34511
        34631
    """.split()]
    updated_prospects = []
    updated_messages = []
    for prospect_id in backfill_prospect_ids:
        prospect: Prospect = Prospect.query.get(prospect_id)
        prospect.status = ProspectStatus.QUEUED_FOR_OUTREACH
        prospect.overall_status = ProspectOverallStatus.PROSPECTED
        gm: GeneratedMessage = GeneratedMessage.query.get(prospect.approved_outreach_message_id)
        gm.message_status = GeneratedMessageStatus.QUEUED_FOR_OUTREACH
        updated_prospects.append(prospect)
        updated_messages.append(gm)
    db.session.bulk_save_objects(updated_prospects)
    db.session.bulk_save_objects(updated_messages)
    db.session.commit()
