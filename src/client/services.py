from app import db
from src.ml.models import GNLPModel, GNLPModelType, ModelProvider
from src.client.models import Client, ClientArchetype, ClientSDR
from src.message_generation.models import GeneratedMessageCTA
from src.onboarding.services import create_sight_onboarding
from src.utils.random_string import generate_random_alphanumeric
from src.prospecting.models import ProspectStatus
from typing import Optional
from src.ml.fine_tuned_models import get_latest_custom_model
from src.utils.slack import send_slack_message
import os

STYTCH_PROJECT_ID = os.environ.get("STYTCH_PROJECT_ID")
STYTCH_SECRET = os.environ.get("STYTCH_SECRET")


def get_client(client_id: int):
    c: Client = Client.query.get(client_id)
    return c


def create_client(
    company: str,
    contact_name: str,
    contact_email: str,
    linkedin_outbound_enabled: bool,
    email_outbound_enabled: bool,
):
    c: Client = Client.query.filter_by(company=company).first()
    if c:
        return {"client_id": c.id}

    c: Client = Client(
        company=company,
        contact_name=contact_name,
        contact_email=contact_email,
        active=True,
        notification_allowlist=[
            ProspectStatus.SCHEDULING,
            ProspectStatus.DEMO_SET,
            ProspectStatus.ACTIVE_CONVO,
            ProspectStatus.ACCEPTED,
        ],
        linkedin_outbound_enabled=linkedin_outbound_enabled,
        email_outbound_enabled=email_outbound_enabled,
    )
    db.session.add(c)
    db.session.commit()

    return {"client_id": c.id}


def get_client_archetype(client_archetype_id: int):
    ca: ClientArchetype = ClientArchetype.query.get(client_archetype_id)
    return ca


def create_client_archetype(
    client_id: int,
    client_sdr_id: int,
    archetype: str,
    filters: any,
    base_archetype_id: Optional[int] = None,
    disable_ai_after_prospect_engaged: bool = False,
):
    c: Client = get_client(client_id=client_id)
    if not c:
        return None

    client_archetype = ClientArchetype(
        client_id=client_id,
        client_sdr_id=client_sdr_id,
        archetype=archetype,
        filters=filters,
        disable_ai_after_prospect_engaged=disable_ai_after_prospect_engaged,
    )
    db.session.add(client_archetype)
    db.session.commit()
    archetype_id = client_archetype.id

    if base_archetype_id:
        _, model_id = get_latest_custom_model(base_archetype_id, GNLPModelType.OUTREACH)
        base_model: GNLPModel = GNLPModel.query.get(model_id)
        model = GNLPModel(
            model_provider=base_model.model_provider,
            model_type=base_model.model_type,
            model_description="baseline_model_{}".format(archetype),
            model_uuid=base_model.model_uuid,
            archetype_id=archetype_id,
        )
        db.session.add(model)
        db.session.commit()
    else:
        model: GNLPModel = GNLPModel(
            model_provider=ModelProvider.OPENAI_GPT3,
            model_type=GNLPModelType.OUTREACH,
            model_description="baseline_model_{}".format(archetype),
            model_uuid="davinci:ft-personal-2022-07-23-19-55-19",
            archetype_id=archetype_id,
        )
        db.session.add(model)
        db.session.commit()

    return {"client_archetype_id": client_archetype.id}


def get_client_sdr(client_sdr_id: int):
    """Gets a Client SDR

    Args:
        client_sdr_id (int): The ID of the Client SDR

    Returns:
        ClientSDR: ClientSDR
    """
    csdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    return csdr


def create_client_sdr(client_id: int, name: str, email: str):
    c: Client = get_client(client_id=client_id)
    if not c:
        return None

    sdr = ClientSDR(
        client_id=client_id,
        name=name,
        email=email,
        weekly_li_outbound_target=100,
        notification_allowlist=[
            ProspectStatus.SCHEDULING,
            ProspectStatus.DEMO_SET,
            ProspectStatus.ACTIVE_CONVO,
            ProspectStatus.ACCEPTED,
        ],
    )
    db.session.add(sdr)
    db.session.commit()

    create_sight_onboarding(sdr.id)

    return {"client_sdr_id": sdr.id}


def reset_client_sdr_sight_auth_token(client_sdr_id: int):
    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if not sdr:
        return None

    sdr.auth_token = generate_random_alphanumeric(32)
    db.session.commit()

    return {"token": sdr.auth_token}


def rename_archetype(new_name: str, client_archetype_id: int):
    """
    Rename an archetype
    """
    ca: ClientArchetype = ClientArchetype.query.get(client_archetype_id)
    if not ca:
        return None

    ca.archetype = new_name
    db.session.add(ca)
    db.session.commit()

    return True


def toggle_archetype_active(archetype_id: int):
    """
    Toggle an archetype's active status
    """
    ca: ClientArchetype = ClientArchetype.query.get(archetype_id)
    if not ca:
        return None

    ca.active = not ca.active
    db.session.add(ca)
    db.session.commit()

    return True


def update_client_sdr_scheduling_link(client_sdr_id: int, scheduling_link: str):
    """
    Update the scheduling link for a Client SDR
    """
    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if not sdr:
        return None

    sdr.scheduling_link = scheduling_link
    db.session.add(sdr)
    db.session.commit()

    return True


def update_client_sdr_email(client_sdr_id: int, email: str):
    """
    Update the email for a Client SDR
    """
    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if not sdr:
        return None

    sdr.email = email
    db.session.add(sdr)
    db.session.commit()

    return True


def update_client_pipeline_notification_webhook(client_id: int, webhook: str):
    """
    Update the Slack pipeline notification webhook for a Client
    """
    c: Client = Client.query.get(client_id)
    if not c:
        return None

    c.pipeline_notifications_webhook_url = webhook
    db.session.add(c)
    db.session.commit()

    return True


def test_client_pipeline_notification_webhook(client_id: int):
    """
    Test the Slack pipeline notification webhook for a Client
    """
    c: Client = Client.query.get(client_id)
    if not c:
        return None

    if not c.pipeline_notifications_webhook_url:
        return None

    send_slack_message(
        message="This is a test message from the Sight Pipeline",
        webhook_urls=[c.pipeline_notifications_webhook_url],
    )

    return True


def update_client_sdr_pipeline_notification_webhook(client_sdr_id: int, webhook: str):
    """Update the Slack pipeline notification webhook for a Client SDR

    Args:
        client_sdr_id (int): ID of the Client SDR
        webhook (str): Webhook URL

    Returns:
        bool: True if successful, None otherwise
    """
    csdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if not csdr:
        return None

    csdr.pipeline_notifications_webhook_url = webhook
    db.session.add(csdr)
    db.session.commit()

    return True


def test_client_sdr_pipeline_notification_webhook(client_sdr_id: int):
    """Test the Slack pipeline notification webhook for a Client SDR

    Args:
        client_sdr_id (int): ID of the Client SDR

    Returns:
        bool: True if successful, None otherwise
    """
    csdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if not csdr:
        return None

    if not csdr.pipeline_notifications_webhook_url:
        return None

    send_slack_message(
        message="This is a test message from the Sight Pipeline",
        webhook_urls=[csdr.pipeline_notifications_webhook_url],
    )

    return True


def make_stytch_call(email: str):
    from stytch import Client

    client = Client(
        project_id=STYTCH_PROJECT_ID,
        secret=STYTCH_SECRET,
        environment="live",
    )
    client.magic_links.email.login_or_create(email=email)


def authenticate_stytch_client_sdr_token(token: str):
    from stytch import Client

    client = Client(
        project_id=STYTCH_PROJECT_ID,
        secret=STYTCH_SECRET,
        environment="live",
    )
    return client.magic_links.authenticate(token).json()


def send_stytch_magic_link(client_sdr_email: int):
    """Send a Stytch magic link to a Client SDR"""
    sdr: ClientSDR = ClientSDR.query.filter_by(email=client_sdr_email).first()
    if not sdr:
        return None

    email = sdr.email
    try:
        make_stytch_call(email)
    except:
        return False
    return True


def approve_stytch_client_sdr_token(client_sdr_email: str, token: str):
    """Authenticate a Stytch token and return a SellScale Sight auth token"""
    stytch_response = authenticate_stytch_client_sdr_token(token)
    emails = stytch_response.get("user").get("emails")
    if not emails or len(emails) == 0:
        return None
    email_found = False
    for email in emails:
        if (email.get("email")).lower() == client_sdr_email.lower():
            email_found = True

    if not email_found:
        return None

    client_sdr: ClientSDR = ClientSDR.query.filter_by(email=client_sdr_email).first()
    reset_client_sdr_sight_auth_token(client_sdr.id)

    client_sdr: ClientSDR = ClientSDR.query.filter_by(email=client_sdr_email).first()
    token = client_sdr.auth_token

    return {"token": token}


def verify_client_sdr_auth_token(auth_token: str):
    """Verify a Client SDR auth token"""
    client_sdr: ClientSDR = ClientSDR.query.filter_by(auth_token=auth_token).first()
    if not client_sdr:
        return None

    return True


def update_client_sdr_manual_warning_message(client_sdr_id: int, manual_warning: str):
    """Update the manual warning text value for a Client SDR

    Args:
        client_sdr_id (int): ID of the Client SDR
        manual_warning_message (str): Manual warning text

    Returns:
        bool: True if successful, None otherwise
    """
    csdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if not csdr:
        return None

    csdr.manual_warning_message = manual_warning
    db.session.add(csdr)
    db.session.commit()

    return True


def update_client_sdr_weekly_li_outbound_target(
    client_sdr_id: int, weekly_li_outbound_target: int
):
    """Update the weekly LinkedIn outbound target for a Client SDR

    Args:
        client_sdr_id (int): ID of the Client SDR
        weekly_li_outbound_target (int): Weekly LinkedIn outbound target

    Returns:
        bool: True if successful, None otherwise
    """
    csdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if not csdr:
        return None

    csdr.weekly_li_outbound_target = weekly_li_outbound_target
    db.session.add(csdr)
    db.session.commit()

    return True


def update_client_sdr_weekly_email_outbound_target(
    client_sdr_id: int, weekly_email_outbound_target: int
):
    """Update the weekly email outbound target for a Client SDR

    Args:
        client_sdr_id (int): ID of the Client SDR
        weekly_email_outbound_target (int): Weekly email outbound target

    Returns:
        bool: True if successful, None otherwise
    """
    csdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if not csdr:
        return None

    csdr.weekly_email_outbound_target = weekly_email_outbound_target
    db.session.add(csdr)
    db.session.commit()

    return True


def get_ctas(client_archetype_id: int):
    """Get all CTAs for a Client Archetype

    Args:
        client_archetype_id (int): ID of the Client Archetype

    Returns:
        list: List of CTAs
    """
    ctas = GeneratedMessageCTA.query.filter_by(archetype_id=client_archetype_id).all()
    return ctas
