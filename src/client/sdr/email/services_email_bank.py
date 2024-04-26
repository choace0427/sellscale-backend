from datetime import time
from app import db, celery

import requests
import os
from typing import Optional, Union


from src.client.models import ClientSDR, Client
from src.client.sdr.email.models import EmailType, SDREmailBank, SDREmailSendSchedule
from src.client.sdr.email.services_email_schedule import create_sdr_email_send_schedule
from src.client.sdr.services_client_sdr import update_sla_schedule_email_limit
from src.domains.models import Domain
from src.smartlead.services import get_email_warmings, get_warmup_percentage
from src.smartlead.smartlead import Smartlead
from src.utils.slack import URL_MAP, send_slack_message


def get_sdr_email_banks_for_client(client_id: int) -> list[dict]:
    """Gets all email banks for a given client, separated by SDR

    Args:
        client_id (int): ID of the client

    Returns:
        list[dict]: List of email banks
    """
    sdrs: list[ClientSDR] = ClientSDR.query.filter_by(client_id=client_id).all()

    result = []
    for sdr in sdrs:
        sdr_details = sdr.to_dict(include_email_bank=True)
        result.append(sdr_details)

    return result


def get_sdr_email_banks(
    client_sdr_id: int, active_only: Optional[bool] = True
) -> list[dict]:
    """Gets all emails for a given SDR that are active or inactive

    Returns:
        list[dict]: List of SDREmailBank objects
    """
    # Get all EmailBanks belonging to this SDR
    sdr_email_banks: list[SDREmailBank] = SDREmailBank.query.filter_by(
        client_sdr_id=client_sdr_id
    ).all()

    result = []
    for sdr_email_bank in sdr_email_banks:
        sdr_dict = sdr_email_bank.to_dict()
        sdr_dict["domain_details"] = {}

        domain_details: Domain = Domain.query.get(sdr_email_bank.domain_id)
        domain_details_dict = domain_details.to_dict() if domain_details else {}
        sdr_dict["domain_details"] = domain_details_dict

        result.append(sdr_dict)

    return result


def get_sdr_email_bank(
    email_bank_id: Optional[int] = None,
    email_address: Optional[str] = None,
    nylas_account_id: Optional[str] = None,
) -> Union[SDREmailBank, None]:
    """Gets an SDR Email Bank

    Args:
        email_bank_id (Optional[int], optional): ID of the email bank. Defaults to None.
        email_address (Optional[str], optional): Email address. Defaults to None.
        nylas_account_id (Optional[str], optional): Nylas account ID. Defaults to None.

    Returns:
        Union[SDREmailBank, None]: SDREmailBank object if found, None if not found
    """
    if email_bank_id:
        return SDREmailBank.query.filter(SDREmailBank.id == email_bank_id).first()
    elif email_address:
        return SDREmailBank.query.filter(
            SDREmailBank.email_address == email_address
        ).first()
    elif nylas_account_id:
        return SDREmailBank.query.filter(
            SDREmailBank.nylas_account_id == nylas_account_id
        ).first()

    return None


def update_sdr_email_bank(
    email_bank_id: int,
    active: Optional[bool] = None,
    email_type: Optional[EmailType] = None,
) -> tuple[bool, str]:
    """Updates an SDR Email Bank

    Args:
        email_bank_id (int): ID of the email bank
        active (Optional[bool], optional): Whether or not the email is active. Defaults to None.
        email_type (Optional[EmailType], optional): Type of email. Defaults to None.

    Returns:
        bool: Whether or not the update was successful
        str: Message if the update was not successful
    """
    email_bank: SDREmailBank = SDREmailBank.query.filter(
        SDREmailBank.id == email_bank_id
    ).first()

    if not email_bank:
        return False, "Email bank not found"

    if active is not None:
        email_bank.active = active

    if email_type is not None:
        # If the email_type is "anchor", replace all other anchor emails with alias
        if email_type == EmailType.ANCHOR:
            anchor_email_banks: list[SDREmailBank] = SDREmailBank.query.filter(
                SDREmailBank.email_type == EmailType.ANCHOR,
                SDREmailBank.client_sdr_id == email_bank.client_sdr_id,
            ).all()
            for anchor_email_bank in anchor_email_banks:
                anchor_email_bank.email_type = EmailType.ALIAS
                db.session.add(anchor_email_bank)
                db.session.commit()

        email_bank.email_type = email_type

    db.session.commit()

    return True, None


def create_sdr_email_bank(
    client_sdr_id: int,
    email_address: str,
    email_type: EmailType,
    nylas_auth_code: Optional[str] = None,
    nylas_account_id: Optional[str] = None,
    nylas_active: Optional[bool] = False,
    aws_workmail_user_id: Optional[str] = None,
    aws_username: Optional[str] = None,
    aws_password: Optional[str] = None,
    smartlead_account_id: Optional[int] = None,
    domain_id: Optional[int] = None,
) -> int:
    """Creates an SDR Email Bank

    Args:
        client_sdr_id (int): ID of the Client SDR
        email_address (str): Email address
        email_type (EmailType): Type of email
        nylas_auth_code (Optional[str], optional): Nylas auth code. Defaults to None.
        nylas_account_id (Optional[str], optional): Nylas account ID. Defaults to None.
        nylas_active (Optional[bool], optional): Whether or not the email is active in Nylas. Defaults to False.
        aws_workmail_user_id (Optional[str], optional): AWS Workmail user ID. Defaults to None.
        aws_username (Optional[str], optional): AWS Workmail username. Defaults to None.
        aws_password (Optional[str], optional): AWS Workmail password. Defaults to None.
        smartlead_account_id (Optional[int], optional): Smartlead account ID. Defaults to None.
        domain_id (Optional[int], optional): Domain ID. Defaults to None.

    Returns:
        int: ID of the created email bank
    """
    duplicate: SDREmailBank = SDREmailBank.query.filter(
        SDREmailBank.email_address == email_address
    ).first()

    if duplicate:
        if aws_workmail_user_id:
            duplicate.aws_workmail_user_id = aws_workmail_user_id
            duplicate.aws_username = aws_username
            duplicate.aws_password = aws_password
            db.session.add(duplicate)
            db.session.commit()
        return duplicate.id

    # If the email_type is "anchor", replace all other anchor emails with alias
    if email_type == EmailType.ANCHOR:
        old_anchors: list[SDREmailBank] = SDREmailBank.query.filter(
            SDREmailBank.email_type == EmailType.ANCHOR,
            SDREmailBank.client_sdr_id == client_sdr_id,
        ).all()
        for anchor_email_bank in old_anchors:
            anchor_email_bank.email_type = EmailType.ALIAS
            db.session.add(anchor_email_bank)
            db.session.commit()

    # Create the new email bank
    email_bank = SDREmailBank(
        client_sdr_id=client_sdr_id,
        email_address=email_address,
        email_type=email_type,
        nylas_auth_code=nylas_auth_code,
        nylas_account_id=nylas_account_id,
        nylas_active=nylas_active,
        aws_workmail_user_id=aws_workmail_user_id,
        aws_username=aws_username,
        aws_password=aws_password,
        smartlead_account_id=smartlead_account_id,
        domain_id=domain_id,
    )
    db.session.add(email_bank)
    db.session.commit()

    # Get the client SDR
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)

    # Create a default email send schedule
    create_sdr_email_send_schedule(
        client_sdr_id=client_sdr_id,
        email_bank_id=email_bank.id,
        time_zone=client_sdr.timezone,
        days=[0, 1, 2, 3, 4],
        start_time=time(hour=8),
        end_time=time(hour=17),
    )

    return email_bank.id


def remove_sdr_email_bank(
    email_bank_id: int,
) -> tuple[bool, str]:
    """Removes an SDR Email Bank.

    Removes:
    - AWS Workmail User
    - Smartlead Account

    DOES NOT REMOVE NYLAS CONNECTIONS. TODO: Add this functionality.

    Args:
        email_bank_id (int): ID of the email bank

    Returns:
        tuple[bool, str]: Tuple containing the success status and message
    """
    from src.domains.services import delete_workmail_inbox
    from src.smartlead.services import smartlead_deactivate_email_account

    email_bank: SDREmailBank = SDREmailBank.query.get(email_bank_id)

    if not email_bank:
        return False, "Email bank not found"

    # Remove AWS Workmail User
    if email_bank.aws_workmail_user_id:
        success, msg = delete_workmail_inbox(
            workmail_user_id=email_bank.aws_workmail_user_id
        )
        if success:  # Remove the AWS Workmail User ID
            email_bank.aws_workmail_user_id = None
            email_bank.aws_username = None
            email_bank.aws_password = None
            db.session.commit()
        else:
            return False, msg

    # Remove Smartlead Account
    if email_bank.smartlead_account_id:
        success = smartlead_deactivate_email_account(
            email_account_id=email_bank.smartlead_account_id
        )
        if success:  # Remove the Smartlead Account ID
            email_bank.smartlead_account_id = None
            email_bank.smartlead_warmup_enabled = False
            email_bank.smartlead_reputation = 0
            db.session.commit()
        else:
            return False, "Error removing Smartlead account"

    # Get and delete the SendSchedules
    send_schedule: SDREmailSendSchedule = SDREmailSendSchedule.query.filter(
        SDREmailSendSchedule.email_bank_id == email_bank_id
    ).all()
    for schedule in send_schedule:
        db.session.delete(schedule)
    db.session.commit()

    # Delete the email bank
    db.session.delete(email_bank)
    db.session.commit()

    return True, None


def remove_all_sdr_email_banks(client_sdr_id: int) -> tuple[bool, str]:
    """Removes all SDR Email Banks for a given Client SDR

    Args:
        client_sdr_id (int): ID of the Client SDR

    Returns:
        tuple[bool, str]: Tuple containing the success status and message
    """
    email_banks: list[SDREmailBank] = SDREmailBank.query.filter(
        SDREmailBank.client_sdr_id == client_sdr_id
    ).all()

    removal_statuses = {}
    overall_success = True

    for email_bank in email_banks:
        success, msg = remove_sdr_email_bank(email_bank_id=email_bank.id)
        removal_statuses[email_bank.email_address] = {
            "success": success,
            "message": msg,
        }
        overall_success = overall_success and success

    return overall_success, removal_statuses


def email_belongs_to_sdr(client_sdr_id: int, email_address: str) -> bool:
    """Checks if an email belongs to an SDR

    Args:
        client_sdr_id (int): ID of the Client SDR
        email_address (str): Email address

    Returns:
        bool: Whether or not the email belongs to the SDR
    """
    email_bank: SDREmailBank = SDREmailBank.query.filter(
        SDREmailBank.client_sdr_id == client_sdr_id,
        SDREmailBank.email_address == email_address,
    ).first()

    if not email_bank:
        return False

    return True


def nylas_exchange_for_authorization_code(
    client_sdr_id: int, code: str
) -> tuple[bool, dict]:
    """Exchange authentication token for Nylas authorization code

    Args:
        client_sdr_id (int): ID of the Client SDR
        code (str): Authorization code

    Returns:
        tuple[bool, str]: Tuple containing the success status and message
    """

    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)

    # Exchange for access token
    response = post_nylas_oauth_token(code)

    # Validate response
    if response.get("status_code") and response.get("status_code") == 500:
        return False, {
            "message": "Error exchanging for access token",
            "status_code": 500,
        }

    # Get access token
    access_token = response.get("access_token")
    if not access_token:
        return False, {
            "message": "Error exchanging for access token",
            "status_code": 500,
        }

    # Get account id
    account_id = response.get("account_id")
    if not account_id:
        return False, {"message": "Error getting account id", "status_code": 500}

    # Validate email matches Client SDR
    email_address = response.get("email_address")
    if not email_address:
        return False, {"message": "Error getting email address", "status_code": 500}

    # Check if the email bank object already exists
    email_bank: SDREmailBank = get_sdr_email_bank(email_address=email_address)
    if not email_bank:
        # Create the email bank object
        email_bank_id = create_sdr_email_bank(
            client_sdr_id=client_sdr_id,
            email_address=email_address,
            email_type=EmailType.ALIAS,
            nylas_auth_code=access_token,
            nylas_account_id=account_id,
            nylas_active=True,
        )
        email_bank = SDREmailBank.query.get(email_bank_id)

    # Update email bank
    email_bank.nylas_account_id = account_id
    email_bank.nylas_auth_code = access_token
    email_bank.nylas_active = True

    # Update Client SDR
    client_sdr.nylas_auth_code = access_token
    client_sdr.nylas_account_id = account_id
    client_sdr.nylas_active = True

    db.session.add(client_sdr)
    db.session.commit()

    return True, {"message": "Success", "status_code": 200, "data": access_token}


def post_nylas_oauth_token(code: str) -> dict:
    """Wrapper for https://api.nylas.com/oauth/token

    Args:
        code (str): Authentication token

    Returns:
        dict: Dict containing the response
    """
    secret = os.environ.get("NYLAS_CLIENT_SECRET")
    response = requests.post(
        "https://api.nylas.com/oauth/token",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        auth=(secret or "", ""),
        json={
            "grant_type": "authorization_code",
            "client_id": os.environ.get("NYLAS_CLIENT_ID"),
            "client_secret": os.environ.get("NYLAS_CLIENT_SECRET"),
            "code": code,
        },
    )
    if response.status_code != 200:
        return {"message": "Error exchanging for access token", "status_code": 500}

    return response.json()


@celery.task
def sync_email_bank_statistics_for_all_active_sdrs() -> tuple[bool, str]:
    """Syncs the statistics for all active SDRs

    Returns:
        tuple[bool, str]: _description_
    """
    from src.automation.orchestrator import add_process_list

    active_sdrs: list[ClientSDR] = ClientSDR.query.filter_by(
        active=True,
    ).all()

    add_process_list(
        type="sync_email_bank_statistics_for_sdr",
        args_list=[{"client_sdr_id": active_sdr.id} for active_sdr in active_sdrs],
    )


@celery.task
def sync_email_bank_statistics_for_client(client_id: int) -> tuple[bool, str]:
    """Syncs the statistics for an entire client

    Args:
        client_id (int): _description_

    Returns:
        tuple[bool, str]: _description_
    """
    from src.automation.orchestrator import add_process_list

    active_sdrs: list[ClientSDR] = ClientSDR.query.filter_by(
        client_id=client_id,
        active=True,
    ).all()

    add_process_list(
        type="sync_email_bank_statistics_for_sdr",
        args_list=[{"client_sdr_id": active_sdr.id} for active_sdr in active_sdrs],
    )

    return True


@celery.task
def sync_email_bank_statistics_for_sdr(client_sdr_id: int) -> tuple[bool, str]:
    """Syncs the statistics for an SDR Email Bank, currently using Smartlead

    Args:
        client_sdr_id (int): ID of the Client SDR

    Returns:
        tuple[bool, str]: Tuple containing the success status and message
    """
    try:
        from src.domains.services import create_domain_entry

        client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
        if not client_sdr:
            return False, "Client SDR not found"

        total_daily_smartlead_outbound_quota = 0

        # Get Smartlead email warmings
        smartlead_email_statuses = get_email_warmings(client_sdr_id=client_sdr_id)
        for email_status in smartlead_email_statuses:
            email_address = email_status["from_email"]

            # Get the email bank to update
            email_bank: SDREmailBank = get_sdr_email_bank(email_address=email_address)
            # If the email bank doesn't exist, we need to create it
            if not email_bank:
                managed_domain = email_address.split("@")[1]

                # Find the domain
                domain: Domain = Domain.query.filter(
                    Domain.domain == managed_domain
                ).first()
                # If the domain doesn't exist, we need to create it
                if not domain:
                    client: Client = Client.query.get(client_sdr.client_id)
                    domain_id = create_domain_entry(
                        domain=managed_domain,
                        client_id=client_sdr.client_id,
                        forward_to=client.domain,
                        aws=False,
                    )
                    domain = Domain.query.get(domain_id)

                # Create the email bank
                email_bank_id = create_sdr_email_bank(
                    client_sdr_id=client_sdr_id,
                    email_address=email_status["from_email"],
                    email_type=EmailType.SELLSCALE,
                    smartlead_account_id=email_status["id"],
                    domain_id=domain.id,
                )
                email_bank = SDREmailBank.query.get(email_bank_id)

            # This is an edge case where:
            # 1. There are 2 SDRs that share the same name
            # 2. The email inbox was not registered through SellScale (this may have happened to older accounts)
            if email_bank.client_sdr_id != client_sdr_id:
                continue

            # Update the email bank
            warmup_reputation = email_status["warmup_details"]["warmup_reputation"]
            warmup_reputation = (
                float(warmup_reputation.rstrip("%"))
                if warmup_reputation or warmup_reputation == "None"
                else 0
            )
            total_sent_count = email_status["warmup_details"]["total_sent_count"]
            daily_sent_count = email_status["daily_sent_count"]
            daily_limit = email_status["message_per_day"]

            email_bank.previous_total_sent_count = email_bank.total_sent_count
            email_bank.smartlead_reputation = warmup_reputation
            email_bank.smartlead_warmup_enabled = True
            email_bank.total_sent_count = total_sent_count
            email_bank.daily_sent_count = daily_sent_count
            email_bank.daily_limit = daily_limit
            email_bank.smartlead_account_id = email_status["id"]

            # If the daily limit is not at 30 (full potential), and the warmup reputation is at 100% with over 100 total sends, we should update the daily limit!
            if (
                daily_limit != 30
                and warmup_reputation == 100
                and total_sent_count > 100
            ):
                sl = Smartlead()
                response = sl.update_email_account(
                    email_account_id=email_status["id"],
                    max_email_per_day=30,
                )
                ok = response.get("ok")
                if ok:
                    email_bank.daily_limit = 30
                else:
                    send_slack_message(
                        message=f"SMARTLEAD: Error updating daily limit for {email_bank.email_address}",
                        webhook_urls=[URL_MAP["ops-outbound-warming"]],
                    )

            db.session.add(email_bank)
            db.session.commit()

            total_daily_smartlead_outbound_quota += email_bank.daily_limit

        send_email_bank_warming_update(client_sdr_id=client_sdr_id)

        update_sla_schedule_email_limit(
            client_sdr_id=client_sdr_id,
            daily_limit=total_daily_smartlead_outbound_quota,
        )

        return True, "Success"
    except Exception as e:
        return False, f"Error: {e}"


def send_email_bank_warming_update(client_sdr_id: int) -> bool:
    """Sends a slack notification for the email bank update.

    Args:
        client_sdr_id (int): ID of the client SDR.

    Returns:
        bool: True if successful, False otherwise.
    """
    # Get email banks for the client SDR
    email_banks: list[SDREmailBank] = SDREmailBank.query.filter_by(
        client_sdr_id=client_sdr_id,
    ).all()

    client_sdr: ClientSDR = ClientSDR.query.filter_by(id=client_sdr_id).first()

    already_warmed_accounts = []
    warmed_blocks = []
    not_warmed_blocks = []
    for email in email_banks:
        total_sent_count = email.total_sent_count or 0
        previous_total_sent_count = email.previous_total_sent_count or 0
        current_perc = get_warmup_percentage(total_sent_count)
        previous_perc = get_warmup_percentage(previous_total_sent_count)

        if current_perc == 100 and previous_perc < 100:
            warmed_blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"🔥 *{email.email_address}* Progress {int(previous_perc)}% -> {int(current_perc)}%",
                    },
                }
            )
        elif current_perc == 100 and previous_perc == 100:
            already_warmed_accounts.append(email.email_address)
        elif current_perc < 100 and previous_perc < 100:
            not_warmed_blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"📈 *{email.email_address}* Progress {int(previous_perc)}% -> {int(current_perc)}%",
                    },
                }
            )

    if (
        len(warmed_blocks) == 0
        and len(not_warmed_blocks) == 0
        and len(already_warmed_accounts) == 0
    ):
        return False

    send_slack_message(
        message=f"Email Bank updated for {client_sdr.name}",
        webhook_urls=[URL_MAP["ops-outbound-warming"]],
        blocks=[
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"Email Bank updated for {client_sdr.name}",
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
