import json
import subprocess
from model_import import ClientSDR
import requests
from src.channel_warmup.models import ChannelWarmup
from src.utils.abstract.attr_utils import deep_get


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


def set_channel_warmups_for_sdr(client_sdr_id):
    email_warmups = pass_through_smartlead_warmup_request(client_sdr_id)

    # PAYLOAD
    # [{'id': 511112, 'from_name': 'Hristina Bell', 'from_email': 'hristina@doppler-tech.com', '__typename': 'email_accounts', 'type': 'GMAIL', 'smtp_host': None, 'is_smtp_success': True, 'is_imap_success': True, 'message_per_day': 5, 'daily_sent_count': 0, 'dns_validation_status': {}, 'email_warmup_details': {'status': 'ACTIVE', 'warmup_reputation': 100, '__typename': 'email_warmup_details'}, 'email_account_tag_mappings': [], 'client_id': None, 'client': None}, {'id': 507298, 'from_name': 'Hristina Bell', 'from_email': 'hristina@dopplersecret.net', '__typename': 'email_accounts', 'type': 'GMAIL', 'smtp_host': None, 'is_smtp_success': True, 'is_imap_success': True, 'message_per_day': 5, 'daily_sent_count': 0, 'dns_validation_status': {}, 'email_warmup_details': {'status': 'ACTIVE', 'warmup_reputation': 100, '__typename': 'email_warmup_details'}, 'email_account_tag_mappings': [], 'client_id': None, 'client': None}, {'id': 507290, 'from_name': 'Hristina Bell', 'from_email': 'hristina@dopplertechnology.net', '__typename': 'email_accounts', 'type': 'GMAIL', 'smtp_host': None, 'is_smtp_success': True, 'is_imap_success': True, 'message_per_day': 5, 'daily_sent_count': 0, 'dns_validation_status': {}, 'email_warmup_details': {'status': 'ACTIVE', 'warmup_reputation': 92, '__typename': 'email_warmup_details'}, 'email_account_tag_mappings': [], 'client_id': None, 'client': None}, {'id': 507282, 'from_name': 'Hristina Bell', 'from_email': 'hristina@dopplersecret.com', '__typename': 'email_accounts', 'type': 'GMAIL', 'smtp_host': None, 'is_smtp_success': True, 'is_imap_success': True, 'message_per_day': 5, 'daily_sent_count': 0, 'dns_validation_status': {}, 'email_warmup_details': {'status': 'ACTIVE', 'warmup_reputation': 92, '__typename': 'email_warmup_details'}, 'email_account_tag_mappings': [], 'client_id': None, 'client': None}, {'id': 493757, 'from_name': 'Hristina Bell', 'from_email': 'h.bell@usedoppler.net', '__typename': 'email_accounts', 'type': 'GMAIL', 'smtp_host': None, 'is_smtp_success': True, 'is_imap_success': True, 'message_per_day': 5, 'daily_sent_count': 0, 'dns_validation_status': {}, 'email_warmup_details': {'status': 'ACTIVE', 'warmup_reputation': 94, '__typename': 'email_warmup_details'}, 'email_account_tag_mappings': [], 'client_id': None, 'client': None}, {'id': 493756, 'from_name': 'Hristina Bell', 'from_email': 'hristinabell@usedoppler.net', '__typename': 'email_accounts', 'type': 'GMAIL', 'smtp_host': None, 'is_smtp_success': True, 'is_imap_success': True, 'message_per_day': 5, 'daily_sent_count': 0, 'dns_validation_status': {}, 'email_warmup_details': {'status': 'ACTIVE', 'warmup_reputation': 93, '__typename': 'email_warmup_details'}, 'email_account_tag_mappings': [], 'client_id': None, 'client': None}, {'id': 493755, 'from_name': 'Hristina Bell', 'from_email': 'hristina.bell@usedoppler.net', '__typename': 'email_accounts', 'type': 'GMAIL', 'smtp_host': None, 'is_smtp_success': True, 'is_imap_success': True, 'message_per_day': 5, 'daily_sent_count': 0, 'dns_validation_status': {}, 'email_warmup_details': {'status': 'ACTIVE', 'warmup_reputation': 93, '__typename': 'email_warmup_details'}, 'email_account_tag_mappings': [], 'client_id': None, 'client': None}, {'id': 492954, 'from_name': 'Hristina Bell', 'from_email': 'hristina@usedoppler.net', '__typename': 'email_accounts', 'type': 'GMAIL', 'smtp_host': None, 'is_smtp_success': True, 'is_imap_success': True, 'message_per_day': 5, 'daily_sent_count': 0, 'dns_validation_status': {}, 'email_warmup_details': {'status': 'ACTIVE', 'warmup_reputation': 97, '__typename': 'email_warmup_details'}, 'email_account_tag_mappings': [], 'client_id': None, 'client': None}]

    for email_warmup in email_warmups:
        email = email_warmup["from_email"]
        warmup_reputation = email_warmup["email_warmup_details"]["warmup_reputation"]
        daily_sent_count = email_warmup["daily_sent_count"]
        daily_limit = email_warmup["message_per_day"]

        channel_warmup: ChannelWarmup = ChannelWarmup(
            client_sdr_id=client_sdr_id,
            channel_type="EMAIL",
            daily_sent_count=daily_sent_count,
            daily_limit=daily_limit,
            warmup_enabled=True,
            reputation=warmup_reputation,
            account_name=email,
        )
