import datetime
import json
import subprocess

from httpx import Client
from model_import import ClientSDR
import requests
from src.channel_warmup.models import ChannelWarmup
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
def set_channel_warmups_for_all_active_sdrs():
    active_sdrs: list[ClientSDR] = ClientSDR.query.filter_by(is_active=True).all()
    for active_sdr in active_sdrs:
        set_channel_warmups_for_sdr.delay(active_sdr.id)


@celery.task(bind=True)
def set_channel_warmups_for_sdr(self, client_sdr_id):
    try:
        client_sdr: ClientSDR = ClientSDR.query.filter_by(id=client_sdr_id).first()
        if not client_sdr:
            return
        name: str = client_sdr.name
        print(f"Setting channel warmups for {name}")

        # Clear all warmups
        ChannelWarmup.query.filter_by(client_sdr_id=client_sdr_id).delete()

        # Create Email Warmups
        email_warmups = pass_through_smartlead_warmup_request(client_sdr_id)
        for email_warmup in email_warmups:
            email = email_warmup["from_email"]
            warmup_reputation = email_warmup["email_warmup_details"][
                "warmup_reputation"
            ]
            daily_sent_count = email_warmup["daily_sent_count"]
            daily_limit = email_warmup["message_per_day"]

            email_channel_warmup: ChannelWarmup = ChannelWarmup(
                client_sdr_id=client_sdr_id,
                channel_type="EMAIL",
                daily_sent_count=daily_sent_count,
                daily_limit=daily_limit,
                warmup_enabled=True,
                reputation=warmup_reputation,
                account_name=email,
            )
            db.session.add(email_channel_warmup)
            db.session.commit()

        print(f"Finished setting channel warmups for {name}")

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
            linkedin_channel_warmup: ChannelWarmup = ChannelWarmup(
                client_sdr_id=client_sdr_id,
                channel_type="LINKEDIN",
                daily_sent_count=linkedin_warmups[0][1],
                daily_limit=linkedin_warmups[0][2],
                warmup_enabled=linkedin_warmups[0][3],
                reputation=linkedin_warmups[0][4],
                account_name=linkedin_warmups[0][5],
            )
            db.session.add(linkedin_channel_warmup)
            db.session.commit()

        print(f"Finished setting channel warmups for {name}")
    except Exception as e:
        print("Error setting warmups for sdr", client_sdr_id)
        raise e
