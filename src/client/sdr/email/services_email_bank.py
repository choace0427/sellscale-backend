from app import db

import requests
import os
from typing import Optional


from src.client.models import ClientSDR
from src.client.sdr.email.models import EmailType, SDREmailBank


def get_sdr_email_banks(client_sdr_id: int, active_only: Optional[bool] = True) -> list[SDREmailBank]:
    """ Gets all emails for a given SDR that are active or inactive

    Returns:
        list[SDREmailBank]: List of SDREmailBank objects
    """
    query = SDREmailBank.query
    query = query.filter(SDREmailBank.client_sdr_id == client_sdr_id)

    if active_only:
        query = query.filter(SDREmailBank.active == True)

    return query.all()


def update_sdr_email_bank(
    email_bank_id: int,
    active: Optional[bool] = None,
    email_type: Optional[EmailType] = None,
) -> tuple[bool, str]:
    """ Updates an SDR Email Bank

    Args:
        email_bank_id (int): ID of the email bank
        active (Optional[bool], optional): Whether or not the email is active. Defaults to None.
        email_type (Optional[EmailType], optional): Type of email. Defaults to None.

    Returns:
        bool: Whether or not the update was successful
        str: Message if the update was not successful
    """
    email_bank: SDREmailBank = SDREmailBank.query.filter(SDREmailBank.id == email_bank_id).first()

    if not email_bank:
        return False, "Email bank not found"

    if active is not None:
        email_bank.active = active

    if email_type is not None:
        # If the email_type is "anchor", replace all other anchor emails with alias
        if email_type == EmailType.ANCHOR:
            anchor_email_banks: list[SDREmailBank] = SDREmailBank.query.filter(
                SDREmailBank.email_type == EmailType.ANCHOR,
                SDREmailBank.client_sdr_id == email_bank.client_sdr_id
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
) -> int:
    """ Creates an SDR Email Bank

    Args:
        client_sdr_id (int): ID of the Client SDR
        email_address (str): Email address
        email_type (EmailType): Type of email
        nylas_auth_code (Optional[str], optional): Nylas auth code. Defaults to None.
        nylas_account_id (Optional[str], optional): Nylas account ID. Defaults to None.
        nylas_active (Optional[bool], optional): Whether or not the email is active in Nylas. Defaults to False.

    Returns:
        int: ID of the created email bank
    """
    duplicate: SDREmailBank = SDREmailBank.query.filter(
        SDREmailBank.email_address == email_address
    ).first()

    if duplicate:
        return duplicate.id

    email_bank = SDREmailBank(
        client_sdr_id=client_sdr_id,
        email_address=email_address,
        email_type=email_type,
        nylas_auth_code=nylas_auth_code,
        nylas_account_id=nylas_account_id,
        nylas_active=nylas_active,
    )
    db.session.add(email_bank)
    db.session.commit()

    return email_bank.id


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
    response = response.get("email_address")
    if not response:
        return False, {"message": "Error getting email address", "status_code": 500}

    # Create the email bank object
    email_bank_id = create_sdr_email_bank(
        client_sdr_id=client_sdr_id,
        email_address=response,
        email_type=EmailType.ALIAS,
        nylas_auth_code=access_token,
        nylas_account_id=account_id,
        nylas_active=True,
    )

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

