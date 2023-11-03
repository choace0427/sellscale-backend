from app import app, db
from tests.test_utils.decorators import use_app_context
from src.client.sdr.email.models import EmailType, SDREmailBank
from src.client.sdr.email.services_email_bank import create_sdr_email_bank, email_belongs_to_sdr, get_sdr_email_banks, update_sdr_email_bank
from tests.test_utils.test_utils import (
    test_app,
    basic_client,
    basic_client_sdr,
    basic_sdr_email_bank,
)


@use_app_context
def test_get_sdr_email_banks():
    """Tests get_sdr_email_banks"""
    client = basic_client()
    client_sdr = basic_client_sdr(client)
    email_bank = basic_sdr_email_bank(client_sdr)

    email_banks: list[SDREmailBank] = get_sdr_email_banks(
        client_sdr_id=client_sdr.id
    )
    assert len(email_banks) == 1
    assert email_banks[0].id == email_bank.id


@use_app_context
def test_update_sdr_email_bank():
    """Tests update_sdr_email_bank"""
    client = basic_client()
    client_sdr = basic_client_sdr(client)
    email_bank = basic_sdr_email_bank(client_sdr)

    success, message = update_sdr_email_bank(
        email_bank_id=email_bank.id,
        active=False,
        email_type=EmailType.ALIAS
    )
    assert success
    assert not email_bank.active
    assert email_bank.email_type == EmailType.ALIAS


@use_app_context
def test_create_sdr_email_bank():
    """Tests create_sdr_email_bank"""
    client = basic_client()
    client_sdr = basic_client_sdr(client)

    id = create_sdr_email_bank(
        client_sdr_id=client_sdr.id,
        email_address="test@sellscale.com",
        email_type=EmailType.ANCHOR
    )
    assert id
    assert SDREmailBank.query.count() == 1
    assert SDREmailBank.query.first().id == id


@use_app_context
def test_email_belongs_to_sdr():
    """Tests that an email belongs to an SDR"""
    client = basic_client()
    client_sdr = basic_client_sdr(client)
    email_bank = basic_sdr_email_bank(client_sdr)

    assert email_belongs_to_sdr(
        client_sdr_id=client_sdr.id,
        email_address=email_bank.email_address
    )

    assert not email_belongs_to_sdr(
        client_sdr_id=client_sdr.id,
        email_address='fake@sellscale.com'
    )
