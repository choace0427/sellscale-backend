from app import slack_app, db
from src.client.models import Client, ClientSDR
from src.slack.auth.models import SlackAuthentication

import os

SLACK_CLIENT_ID = os.environ.get("SLACK_CLIENT_ID")
SLACK_CLIENT_SECRET = os.environ.get("SLACK_CLIENT_SECRET")


def exchange_slack_auth_code(client_sdr_id: int, code: str) -> tuple[bool, str]:
    """Exchanges the Slack OAuth code for an access token, and saves the result to the database

    Args:
        client_sdr_id (int): The ID of the Client SDR
        code (str): The Slack OAuth code

    Returns:
        tuple[bool, str]: A tuple containing the success status and the error message (if any)
    """
    # Perform the exchange
    payload = slack_app.client.oauth_v2_access(
        client_id=os.environ.get("SLACK_CLIENT_ID"),
        client_secret=os.environ.get("SLACK_CLIENT_SECRET"),
        code=code,
    )
    ok = payload.get("ok", False)
    if not ok:
        return False, payload.get("error", "Unknown error")

    # Save the result to the database
    client_sdr: ClientSDR = ClientSDR.query.filter_by(id=client_sdr_id).first()
    if not client_sdr:
        return False, "SellScale: Invalid Client SDR ID"
    client: Client = Client.query.filter_by(id=client_sdr.client_id).first()
    if not client:
        return False, "SellScale: Invalid Client ID"

    slack_team = payload.get("team") or {}
    slack_enterprise = payload.get("enterprise") or {}
    slack_authed_user = payload.get("authed_user") or {}

    slack_auth = SlackAuthentication(
        client_id=client.id,
        client_sdr_id=client_sdr.id,
        slack_payload=payload,
        slack_access_token=payload.get("access_token", ""),
        slack_token_type=payload.get("token_type", ""),
        slack_scope=payload.get("scope", ""),
        slack_bot_user_id=payload.get("bot_user_id", ""),
        slack_app_id=payload.get("app_id", ""),
        slack_team_name=slack_team.get("name", ""),
        slack_team_id=slack_team.get("id", ""),
        slack_enterprise_name=slack_enterprise.get("name", ""),
        slack_enterprise_id=slack_enterprise.get("id", ""),
        slack_authed_user_id=slack_authed_user.get("id", ""),
        slack_authed_user_scope=slack_authed_user.get("scope", ""),
        slack_authed_user_access_token=slack_authed_user.get("access_token", ""),
        slack_authed_user_token_type=slack_authed_user.get("token_type", ""),
    )
    db.session.add(slack_auth)
    db.session.commit()

    return True, ""
