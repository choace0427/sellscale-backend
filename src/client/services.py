from app import db
from flask import jsonify
from src.ml.models import GNLPModel, GNLPModelType, ModelProvider
from src.prospecting.models import ProspectUploadsRawCSV, ProspectUploads
from src.client.models import Client, ClientArchetype, ClientSDR
from src.message_generation.models import GeneratedMessageCTA, GeneratedMessage, GeneratedMessageStatus
from src.onboarding.services import create_sight_onboarding
from src.utils.random_string import generate_random_alphanumeric
from src.prospecting.models import Prospect, ProspectStatus, ProspectChannels
from typing import Optional
from src.ml.fine_tuned_models import get_latest_custom_model
from src.utils.slack import send_slack_message
import os

STYTCH_PROJECT_ID = os.environ.get("STYTCH_PROJECT_ID")
STYTCH_SECRET = os.environ.get("STYTCH_SECRET")
STYTCH_BASE_URL = os.environ.get("STYTCH_BASE_URL")


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


def get_client_archetypes(client_sdr_id: int, query: Optional[str] = "") -> list:
    """Gets a list of all Client Archetypes, with a search filter on the archetype name

    Args:
        client_sdr_id (int): The ID of the Client SDR
        query (str): The search query

    Returns:
        list: The list of Client Archetypes
    """
    client_archetypes: list[ClientArchetype] = ClientArchetype.query.filter(
        ClientArchetype.client_sdr_id == client_sdr_id,
        ClientArchetype.archetype.ilike(f"%{query}%"),
    ).all()

    client_archetype_dicts = []
    for ca in client_archetypes:
        performance = get_client_archetype_performance(client_sdr_id, ca.id)
        merged_dicts = {**ca.to_dict(), **{"performance": performance}}
        client_archetype_dicts.append(merged_dicts)

    return client_archetype_dicts


def get_client_archetype_performance(
    client_sdr_id: int, client_archetype_id: int
) -> dict:
    """Gets the performance of a Client Archetype

    Args:
        client_archetype_id (int): The ID of the Client Archetype

    Returns:
        dict: Client Archetype and performance statistics
    """
    # Get Prospects and find total_count and status_count
    archetype_prospects: list[Prospect] = Prospect.query.filter(
        Prospect.client_sdr_id == client_sdr_id,
        Prospect.archetype_id == client_archetype_id,
    ).all()
    status_map = {}
    for p in archetype_prospects:
        if p.overall_status is None:
            continue

        if p.overall_status.value in status_map:
            status_map[p.overall_status.value] += 1
        else:
            status_map[p.overall_status.value] = 1
    total_prospects = len(archetype_prospects)

    performance = {"total_prospects": total_prospects, "status_map": status_map}

    return performance


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


def get_client_sdr(client_sdr_id: int) -> dict:
    """Gets and returns Client SDR information

    Args:
        client_sdr_id (int): The ID of the Client SDR

    Returns:
        dict: The Client SDR information
    """
    csdr: ClientSDR = ClientSDR.query.get(client_sdr_id)

    return csdr.to_dict()


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


def toggle_client_sdr_autopilot_enabled(client_sdr_id: int):
    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if not sdr:
        return None

    sdr.autopilot_enabled = not sdr.autopilot_enabled
    db.session.add(sdr)
    db.session.commit()

    return {"autopilot_enabled": sdr.autopilot_enabled}


def reset_client_sdr_sight_auth_token(client_sdr_id: int):
    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if not sdr:
        return None

    sdr.auth_token = generate_random_alphanumeric(32)
    db.session.commit()

    return {"token": sdr.auth_token}


def get_sdr_available_outbound_channels(client_sdr_id: int) -> dict:
    """Gets the available outbound channels for a Client SDR

    Args:
        client_sdr_id (int): The ID of the Client SDR

    Returns:
        dict: The available outbound channels
    """

    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if not client_sdr:
        return None

    # Get all channels
    all_channels = ProspectChannels.to_dict_verbose()

    # Get the channels that are available to the SDR
    sdr_channels = {}
    li_enabled = client_sdr.weekly_li_outbound_target is not None
    if li_enabled:
        sdr_channels[ProspectChannels.LINKEDIN.value] = all_channels.get(
            ProspectChannels.LINKEDIN.value
        )
    email_enabled = client_sdr.weekly_email_outbound_target is not None
    if email_enabled:
        sdr_channels[ProspectChannels.EMAIL.value] = all_channels.get(
            ProspectChannels.EMAIL.value
        )
    if li_enabled or email_enabled:
        sdr_channels[ProspectChannels.SELLSCALE.value] = all_channels.get(
            ProspectChannels.SELLSCALE.value
        )

    return sdr_channels


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
    client.magic_links.email.login_or_create(
        email=email,
        login_magic_link_url=STYTCH_BASE_URL,
    )


def authenticate_stytch_client_sdr_token(token: str):
    from stytch import Client

    client = Client(
        project_id=STYTCH_PROJECT_ID,
        secret=STYTCH_SECRET,
        environment="live",
    )
    return client.magic_links.authenticate(token).json()


def send_stytch_magic_link(client_sdr_email: str):
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
    try:
        stytch_response = authenticate_stytch_client_sdr_token(token)
    except Exception as e:
        return jsonify({"error_type": "Stytch failed", "message": e.error_message}), 400

    emails = stytch_response.get("user").get("emails")
    if not emails or len(emails) == 0:
        return None
    email_found = False
    for email in emails:
        if (email.get("email")).lower() == client_sdr_email.lower():
            email_found = True

    if not email_found:
        return jsonify({"message": "Email not found in Stytch response"}), 400

    client_sdr: ClientSDR = ClientSDR.query.filter_by(email=client_sdr_email).first()
    reset_client_sdr_sight_auth_token(client_sdr.id)

    client_sdr: ClientSDR = ClientSDR.query.filter_by(email=client_sdr_email).first()
    token = client_sdr.auth_token

    return jsonify({"message": "Success", "token": token}), 200


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


def get_cta_by_archetype_id(client_sdr_id: int, archetype_id: int) -> dict:
    """Get CTAs belonging to an Archetype, alongside stats.

    This function is authenticated.

    Args:
        client_sdr_id (int): ID of the Client SDR
        archetype_id (int): ID of the Archetype

    Returns:
        dict: Dict containing the CTAs and their stats, message, and status code
    """
    # Get Archetype
    archetype: ClientArchetype = ClientArchetype.query.get(archetype_id)
    if not archetype:
        return {"message": "Archetype not found", "status_code": 404}
    elif archetype.client_sdr_id != client_sdr_id:
        return {"message": "Archetype does not belong to you", "status_code": 403}

    # Get CTAs belonging to the Archetype
    ctas: list[GeneratedMessageCTA] = GeneratedMessageCTA.query.filter(
        GeneratedMessageCTA.archetype_id == archetype_id
    )

    # Convert to dict and calculate stats
    cta_dicts = []
    for cta in ctas:
        raw_cta = cta.to_dict()
        raw_cta["performance"] = get_cta_stats(cta.id)
        cta_dicts.append(raw_cta)

    return {"message": "Success", "status_code": 200, "ctas": cta_dicts}


def get_prospect_upload_stats_by_upload_id(client_sdr_id: int, prospect_uploads_raw_csv_id: int) -> dict:
    """Get the basic stats for a prospect upload

    This function is authenticated.

    Args:
        client_sdr_id (int): ID of the Client SDR
        prospect_uploads_raw_csv_id (int): ID of the upload

    Returns:
        dict: Dict containing the upload stats
    """

    # Validate parameters
    prospect_uploads_raw_csv: ProspectUploadsRawCSV = ProspectUploadsRawCSV.query.get(prospect_uploads_raw_csv_id)
    if not prospect_uploads_raw_csv:
        return {'message': 'Upload not found', "status_code": 404}
    elif prospect_uploads_raw_csv.client_sdr_id != client_sdr_id:
        return {'message': 'Not authorized', "status_code": 401}

    # Get stats for the upload
    upload_stats = db.session.execute(
        """
        select
          count(status) FILTER (WHERE status = 'UPLOAD_COMPLETE') success,
          count(status) FILTER (WHERE status = 'UPLOAD_IN_PROGRESS') in_progress,
          count(status) FILTER (WHERE status = 'UPLOAD_QUEUED') queued,
          count(status) FILTER (WHERE status = 'UPLOAD_NOT_STARTED') not_started,
          count(status) FILTER (WHERE status = 'DISQUALIFIED') disqualified,
          count(status) FILTER (WHERE status = 'UPLOAD_FAILED') failed,
          count(status) total
        from prospect_uploads
        where prospect_uploads.prospect_uploads_raw_csv_id = {upload_id} and prospect_uploads.client_sdr_id = {client_sdr_id}
        """.format(
          upload_id=prospect_uploads_raw_csv_id,
          client_sdr_id=client_sdr_id
        )
      ).fetchall()

    # index to status map
    status_map = {
      0: 'success',
      1: 'in_progress',
      2: 'queued',
      3: 'not_started',
      4: 'disqualified',
      5: 'failed',
      6: 'total'
    }

    # Convert and format output
    upload_stats = [tuple(row) for row in upload_stats][0]
    upload_stats = {status_map.get(i, 'unknown'): row for i, row in enumerate(upload_stats)}

    return {"message": "Success", "status_code": 200, "stats": upload_stats}



def get_transformers_by_archetype_id(client_sdr_id: int, archetype_id: int, email: bool) -> dict:
    """Gets all transformers belonging to an Archetype, alongside stats.

    This function is authenticated.

    Args:
        client_sdr_id (int): ID of the Client SDR
        archetype_id (int): ID of the archetype

    Returns:
        dict: Dict containing the transformer stats
    """

    # Validate parameters
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    archetype: ClientArchetype = ClientArchetype.query.get(archetype_id)
    if not archetype:
        return {'message': 'Archetype not found', "status_code": 404}
    elif archetype.client_id != client_sdr.client_id:
        return {'message': 'Not authorized', "status_code": 401}

    # Get transformer stats
    transformer_stats = db.session.execute(
        """
        select
          client_archetype.archetype,
          research_point.research_point_type,
          count(distinct prospect.id) num_prospects,
          count(distinct prospect.id) filter (where prospect_status_records.to_status = 'ACCEPTED') num_accepted_prospects,
          count(distinct prospect.id) filter (where prospect_status_records.to_status = 'ACCEPTED') / cast(count(distinct prospect.id) as float) percent_accepted
        from prospect
          join client_archetype on client_archetype.id = prospect.archetype_id
          join generated_message on generated_message.prospect_id = prospect.id
          join research_point on research_point.id = any(generated_message.research_points)
          join prospect_status_records on prospect_status_records.prospect_id = prospect.id
          {email_join}
        where prospect.archetype_id = {archetype_id} {email_filter}
        group by 1,2
        order by 5 desc
        """.format(
          archetype_id=archetype_id,
          email_join='left outer join prospect_email on prospect.id = prospect_email.prospect_id' if email else '',
          email_filter='and prospect_email.prospect_id is null' if email else ''
        )
      ).fetchall()

    # index to column
    column_map = {
      0: 'archetype',
      1: 'research_point_type',
      2: 'num_prospects',
      3: 'num_accepted_prospects',
      4: 'percent_accepted',
    }

    # Convert and format output
    transformer_stats = [{column_map.get(i, 'unknown'): value for i, value in enumerate(tuple(row))} for row in transformer_stats]

    return {"message": "Success", "status_code": 200, "stats": transformer_stats}


def get_prospect_upload_details_by_upload_id(client_sdr_id: int, prospect_uploads_raw_csv_id: int) -> dict:
    """Get the individual prospect details of the prospect upload

    This function is authenticated.

    Args:
        client_sdr_id (int): ID of the Client SDR
        prospect_uploads_raw_csv_id (int): ID of the upload

    Returns:
        dict: Dict containing the upload details
    """

    # Validate parameters
    prospect_uploads_raw_csv: ProspectUploadsRawCSV = ProspectUploadsRawCSV.query.get(prospect_uploads_raw_csv_id)
    if not prospect_uploads_raw_csv:
        return {'message': 'Upload not found', "status_code": 404}
    elif prospect_uploads_raw_csv.client_sdr_id != client_sdr_id:
        return {'message': 'Not authorized', "status_code": 401}


    # Get all prospect details of the upload
    all_prospect_details = ProspectUploads.query.filter_by(
        prospect_uploads_raw_csv_id=prospect_uploads_raw_csv_id,
        client_sdr_id=client_sdr_id,
    ).order_by(ProspectUploads.updated_at.desc()).all()

    return {"message": "Success", "status_code": 200, "uploads": [x.to_dict() for x in all_prospect_details] }


def get_all_uploads_by_archetype_id(client_sdr_id: int, archetype_id: int) -> dict:
    """Get all uploads for an Archetype

    This function is authenticated.

    Args:
        client_sdr_id (int): ID of the Client SDR
        archetype_id (int): ID of the Archetype

    Returns:
        dict: Dict containing the archetype's upload data
    """

    # Validate parameters
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    archetype: ClientArchetype = ClientArchetype.query.get(archetype_id)
    if not archetype:
        return {'message': 'Archetype not found', "status_code": 404}
    elif archetype.client_id != client_sdr.client_id:
        return {'message': 'Not authorized', "status_code": 401}

    # Get all uploads
    all_uploads = ProspectUploadsRawCSV.query.filter_by(
        client_archetype_id=archetype_id,
        client_sdr_id=client_sdr_id,
    ).order_by(ProspectUploadsRawCSV.created_at.desc()).all()

    return {"message": "Success", "status_code": 200, "uploads": [x.to_dict() for x in all_uploads] }


def get_cta_stats(cta_id: int) -> dict:
    """Get stats for a CTA.

    Args:
        cta_id (int): ID of the CTA

    Returns:
        dict: Dict containing the stats and total count
    """
    # Get GeneratedMessages
    generated_messages: list[GeneratedMessage] = GeneratedMessage.query.filter(
        GeneratedMessage.message_cta == cta_id,
        GeneratedMessage.message_status == GeneratedMessageStatus.SENT,
    ).all()

    # Get Prospect IDs
    prospect_id_set = set()
    for message in generated_messages:
        prospect_id_set.add(message.prospect_id)

    # Get Prospect
    prospects: list[Prospect] = Prospect.query.filter(
        Prospect.id.in_(prospect_id_set)
    ).all()
    statuses_map = {}
    for prospect in prospects:
        if prospect.overall_status is None:
            continue
        if prospect.overall_status.value not in statuses_map:
            statuses_map[prospect.overall_status.value] = 1
        else:
            statuses_map[prospect.overall_status.value] += 1

    return {"status_map": statuses_map, "total_count": len(prospects)}
