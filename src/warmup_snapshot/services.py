import json
from typing import Optional

from src.smartlead.services import (
    get_email_warmings,
    get_warmup_percentage,
)
from model_import import ClientSDR
import requests
from src.smartlead.smartlead import Smartlead
from src.utils.domains.pythondns import (
    dkim_record_valid,
    dmarc_record_valid,
    spf_record_valid,
)
from src.utils.slack import URL_MAP, send_slack_message
from src.warmup_snapshot.models import WarmupSnapshot
from src.utils.abstract.attr_utils import deep_get
from app import db, celery


def pass_through_smartlead_warmup_request(client_sdr_id: int) -> list[dict]:
    """Calls Smartlead's request for getting warmup status on inboxes.

    Args:
        client_sdr_id (int): The client SDR ID.

    Returns:
        list[dict]: The list of inbox warmup statuses.
    """
    client_sdr: ClientSDR = ClientSDR.query.filter_by(id=client_sdr_id).first()
    if not client_sdr:
        return []

    sdr_name: str = client_sdr.name
    sdr_name_lowercased = sdr_name.lower()

    url = "https://fe-gql.smartlead.ai/v1/graphql"
    headers = {
        "authority": "fe-gql.smartlead.ai",
        "accept": "*/*",
        "accept-language": "en-US,en;q=0.9",
        "authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyIjp7ImVtYWlsIjoiYWxmcmVkb0B0cnlsYXRjaGJpby5jb20iLCJpZCI6MTQwOTgsIm5hbWUiOiJBbGZyZWRvIEFuZGVyZSIsInV1aWQiOiJhNmFmMjA1MS1hNjBkLTRkNWItYWUxOS05OTRmZjlmMjJmMjQiLCJyb2xlIjoidXNlciIsInByb3ZpZGVyIjoiYXBwIn0sImh0dHBzOi8vaGFzdXJhLmlvL2p3dC9jbGFpbXMiOnsieC1oYXN1cmEtYWxsb3dlZC1yb2xlcyI6WyJ1c2VycyJdLCJ4LWhhc3VyYS1kZWZhdWx0LXJvbGUiOiJ1c2VycyIsIngtaGFzdXJhLXVzZXItaWQiOiIxNDA5OCIsIngtaGFzdXJhLXVzZXItdXVpZCI6ImE2YWYyMDUxLWE2MGQtNGQ1Yi1hZTE5LTk5NGZmOWYyMmYyNCIsIngtaGFzdXJhLXVzZXItbmFtZSI6IkFsZnJlZG8gQW5kZXJlIiwieC1oYXN1cmEtdXNlci1yb2xlIjoidXNlciIsIngtaGFzdXJhLXVzZXItZW1haWwiOiJhbGZyZWRvQHRyeWxhdGNoYmlvLmNvbSJ9LCJpYXQiOjE2OTYzNjg1NDF9.X6ecPcacAbYYxYeeiOigTWyjFQTjNriHKWwWUqvlueM",
        "content-type": "application/json",
        "dnt": "1",
        "origin": "https://app.smartlead.ai",
        "referer": "https://app.smartlead.ai/",
        "sec-ch-ua": '"Not=A?Brand";v="99", "Chromium";v="118"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"macOS"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-site",
        "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
    }
    raw_data = {
        "operationName": "getEmailAccountsQuery",
        "variables": {
            "offset": 0,
            "limit": 25,
            "where": {
                "_or": [
                    {"from_name": {"_ilike": f"%{sdr_name_lowercased}%"}},
                    {"from_email": {"_ilike": f"%{sdr_name_lowercased}%"}},
                ]
            },
        },
        "query": "query getEmailAccountsQuery($offset: Int\u0021, $limit: Int\u0021, $where: email_accounts_bool_exp\u0021) {\n  email_accounts(\n    where: $where\n    offset: $offset\n    limit: $limit\n    order_by: {id: desc}\n  ) {\n    ...BasicEmailAccountsFragment\n    type\n    smtp_host\n    is_smtp_success\n    is_imap_success\n    message_per_day\n    daily_sent_count\n    dns_validation_status\n    email_warmup_details {\n      status\n      warmup_reputation\n      __typename\n    }\n    email_account_tag_mappings {\n      tag {\n        ...TagsFragment\n        __typename\n      }\n      __typename\n    }\n    client_id\n    client {\n      email\n      __typename\n    }\n    __typename\n  }\n}\n\nfragment BasicEmailAccountsFragment on email_accounts {\n  id\n  from_name\n  from_email\n  __typename\n}\n\nfragment TagsFragment on tags {\n  id\n  name\n  color\n  __typename\n}",
    }
    raw_data = json.dumps(raw_data)
    data_bytes = raw_data.encode("utf-8")

    response = requests.post(url, headers=headers, data=data_bytes)

    if response.status_code != 200:
        return []

    result = response.text
    result = json.loads(result)
    result = deep_get(result, "data.email_accounts")

    return result


@celery.task(bind=True)
def set_warmup_snapshots_for_all_active_sdrs(self):
    from src.automation.orchestrator import add_process_list

    active_sdrs: list[ClientSDR] = ClientSDR.query.filter_by(active=True).all()
    # for active_sdr in active_sdrs:
    #     print(f"Setting channel warmups for {active_sdr.name}")
    #     set_warmup_snapshot_for_sdr.delay(active_sdr.id)

    add_process_list(
        type="set_warmup_snapshot_for_sdr",
        args_list=[{"client_sdr_id": active_sdr.id} for active_sdr in active_sdrs],
        buffer_wait_minutes=5,
        append_to_end=True,
    )


@celery.task(bind=True)
def set_warmup_snapshots_for_client(self, client_id: int):
    from src.automation.orchestrator import add_process_list

    active_sdrs: list[ClientSDR] = ClientSDR.query.filter_by(
        client_id=client_id,
        active=True,
    ).all()
    # for active_sdr in active_sdrs:
    #     print(f"Setting channel warmups for {active_sdr.name}")
    #     # set_warmup_snapshot_for_sdr.delay(active_sdr.id)
    #     set_warmup_snapshot_for_sdr(active_sdr.id)

    add_process_list(
        type="set_warmup_snapshot_for_sdr",
        args_list=[{"client_sdr_id": active_sdr.id} for active_sdr in active_sdrs],
        buffer_wait_minutes=5,
        append_to_end=True,
    )

    return True


@celery.task(bind=True)
def set_warmup_snapshot_for_sdr(self, client_sdr_id: int):
    try:
        from src.automation.orchestrator import add_process_for_future

        client_sdr: ClientSDR = ClientSDR.query.filter_by(id=client_sdr_id).first()
        if not client_sdr:
            return False, "Client SDR not found"
        name: str = client_sdr.name
        print(f"Setting channel warmups for {name}")

        # Create Email Warmups
        email_warmups = get_email_warmings(client_sdr_id=client_sdr_id)
        for email_warmup in email_warmups:
            email = email_warmup["from_email"]
            warmup_reputation = email_warmup["warmup_details"]["warmup_reputation"]
            total_sent_count = email_warmup["warmup_details"]["total_sent_count"]
            daily_sent_count = email_warmup["daily_sent_count"]
            daily_limit = email_warmup["message_per_day"]

            warmup_reputation = float(warmup_reputation.rstrip("%"))

            # Get SPF, DMARC, DKIM Record
            domain = email.split("@")[1]
            spf_record, spf_valid = spf_record_valid(domain=domain)
            dmarc_record, dmarc_valid = dmarc_record_valid(domain=domain)
            dkim_record, dkim_valid = dkim_record_valid(domain=domain)

            # Get the old warmup
            old_warmup: WarmupSnapshot = WarmupSnapshot.query.filter_by(
                client_sdr_id=client_sdr_id,
                channel_type="EMAIL",
                account_name=email,
            ).first()
            previous_total_sent_count = old_warmup.total_sent_count if old_warmup else 0

            # Create the new warmup
            email_warmup_snapshot: WarmupSnapshot = WarmupSnapshot(
                client_sdr_id=client_sdr_id,
                channel_type="EMAIL",
                daily_sent_count=daily_sent_count,
                daily_limit=daily_limit,
                total_sent_count=total_sent_count,
                previous_total_sent_count=previous_total_sent_count,
                warmup_enabled=True,
                reputation=warmup_reputation,
                account_name=email,
                dmarc_record=dmarc_record,
                dmarc_record_valid=dmarc_valid,
                spf_record=spf_record,
                spf_record_valid=spf_valid,
                dkim_record=dkim_record,
                dkim_record_valid=dkim_valid,
            )
            db.session.add(email_warmup_snapshot)
            db.session.commit()

            # Delete the old warmup
            if old_warmup:
                db.session.delete(old_warmup)
                db.session.commit()

        send_warmup_snapshot_update(client_sdr_id=client_sdr_id)

        print(f"Finished setting channel warmups for {name}")

        # Delete LinkedIn Warmups
        linkedin_warmups = WarmupSnapshot.query.filter_by(
            client_sdr_id=client_sdr_id, channel_type="LINKEDIN"
        ).all()
        for linkedin_warmup in linkedin_warmups:
            db.session.delete(linkedin_warmup)
            db.session.commit()

        # Create Linkedin Warmups
        linkedin_query = """
        select
            'LINKEDIN' channel_type,
            count(distinct prospect.id) filter (where prospect_status_records.to_status = 'SENT_OUTREACH' and prospect_status_records.created_at > NOW() - '24 hours'::INTERVAL) daily_sent_count,
            client_sdr.weekly_li_outbound_target / 5 daily_limit,
            case when client_sdr.created_at > NOW() - '30 days'::INTERVAL then TRUE else FALSE END warmup_enabled,
            100 warmup_reputation,
            concat(client_sdr.name, ' LinkedIn') account_name

        from
            client_sdr
            join prospect on prospect.client_sdr_id = client_sdr.id
            join prospect_status_records on prospect_status_records.prospect_id = prospect.id
        where client_sdr.id = {client_sdr_id}
        group by 1,3,4,5,6
        limit 1
        """.format(
            client_sdr_id=client_sdr_id
        )
        linkedin_warmups = db.session.execute(linkedin_query).fetchall()
        if len(linkedin_warmups) > 0:
            linkedin_warmup_snapshot: WarmupSnapshot = WarmupSnapshot(
                client_sdr_id=client_sdr_id,
                channel_type="LINKEDIN",
                daily_sent_count=linkedin_warmups[0][1],
                daily_limit=linkedin_warmups[0][2],
                warmup_enabled=linkedin_warmups[0][3],
                reputation=linkedin_warmups[0][4],
                account_name=linkedin_warmups[0][5],
            )
            db.session.add(linkedin_warmup_snapshot)
            db.session.commit()

        print(f"Finished setting channel warmups for {name}")
        return True, "Success"
    except Exception as e:
        print("Error setting warmups for sdr", client_sdr_id, e)
        return False, "Error", e


def send_warmup_snapshot_update(client_sdr_id: int) -> bool:
    """Sends a slack notification for the warmup snapshot update.

    Args:
        client_sdr_id (int): ID of the client SDR.

    Returns:
        bool: True if successful, False otherwise.
    """
    # Get warmups for the client SDR
    warmups: list[WarmupSnapshot] = WarmupSnapshot.query.filter_by(
        client_sdr_id=client_sdr_id,
        channel_type="EMAIL",
    ).all()

    client_sdr: ClientSDR = ClientSDR.query.filter_by(id=client_sdr_id).first()

    already_warmed_accounts = []
    warmed_blocks = []
    not_warmed_blocks = []
    for warmup in warmups:
        total_sent_count = warmup.total_sent_count
        previous_total_sent_count = warmup.previous_total_sent_count
        current_perc = get_warmup_percentage(total_sent_count)
        previous_perc = get_warmup_percentage(previous_total_sent_count)

        if current_perc == 100 and previous_perc < 100:
            warmed_blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"🔥 *{warmup.account_name}* {previous_perc}% -> {current_perc}%",
                    },
                }
            )
        elif current_perc == 100 and previous_perc == 100:
            already_warmed_accounts.append(warmup.account_name)
        elif current_perc < 100 and previous_perc < 100:
            not_warmed_blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"📈 *{warmup.account_name}* {previous_perc}% -> {current_perc}%",
                    },
                }
            )

    send_slack_message(
        message=f"Warmup Snapshot updated for {client_sdr.name}",
        webhook_urls=[URL_MAP["ops-outbound-warming"]],
        blocks=[
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"Warmup Snapshot updated for {client_sdr.name}",
                },
            }
        ]
        + warmed_blocks
        + not_warmed_blocks
        + [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"🟢 Already warmed accounts: {', '.join(already_warmed_accounts)}",
                },
            }
        ],
    )

    return True
