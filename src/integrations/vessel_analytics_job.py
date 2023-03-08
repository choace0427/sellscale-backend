from model_import import (
    ClientSDR,
    Prospect,
    ProspectEmail,
    SalesEngagementInteractionSource,
)
from datetime import timedelta, datetime
from tqdm import tqdm
from src.integrations.vessel_convert_analytics_job import (
    convert_vessel_raw_payload_to_ss,
)
from src.email_outbound.ss_data import SSData
from src.email_outbound.services import (
    create_sales_engagement_interaction_raw,
    collect_and_update_status_from_ss_data,
)
from src.integrations.vessel import SalesEngagementIntegration
from app import db, celery
from src.campaigns.models import OutboundCampaign


def get_prospects_to_collect_analytics_for(client_sdr_id: int) -> list:
    prospects: list = (
        db.session.query(Prospect, ProspectEmail)
        .filter(
            Prospect.client_sdr_id == client_sdr_id,
            Prospect.approved_prospect_email_id.isnot(None),
            Prospect.vessel_contact_id.isnot(None),
            ProspectEmail.id == Prospect.approved_prospect_email_id,
        )
        .filter(
            ProspectEmail.vessel_sequence_id.isnot(None),
            # ProspectEmail.updated_at < datetime.now() - timedelta(hours=48),
        )
        .all()
    )
    return prospects


def process_analytics_for_campaign(campaign_id: int):
    campaign: OutboundCampaign = OutboundCampaign.query.get(campaign_id)
    if not campaign:
        return False, "Campaign not found"
    client_sdr_id = campaign.client_sdr_id
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client_id = client_sdr.client_id
    prospect_ids = campaign.prospect_ids
    prospects: list = (
        db.session.query(Prospect, ProspectEmail)
        .filter(
            Prospect.client_sdr_id == client_sdr_id,
            Prospect.approved_prospect_email_id.isnot(None),
            Prospect.vessel_contact_id.isnot(None),
            ProspectEmail.id == Prospect.approved_prospect_email_id,
            Prospect.id.in_(prospect_ids),
        )
        .filter(
            ProspectEmail.vessel_sequence_id.isnot(None),
            # ProspectEmail.updated_at < datetime.now() - timedelta(hours=48),
        )
        .all()
    )
    process_analytics_for_prospects(client_id, client_sdr_id, prospects)


def create_vessel_engagement_ss_raw(client_sdr_id: int) -> tuple[bool, str]:
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if not client_sdr:
        return False, "Client SDR not found"

    prospects = get_prospects_to_collect_analytics_for(client_sdr_id)
    process_analytics_for_prospects(client_sdr_id, client_sdr_id, prospects)


def process_analytics_for_prospects(
    client_id: int, client_sdr_id: int, prospects: list
):
    sei = SalesEngagementIntegration(client_id)
    raw_payloads = []
    for entry in tqdm(prospects):
        prospect: Prospect = entry[0]
        prospect_email: ProspectEmail = entry[1]
        contact_id = prospect.vessel_contact_id
        sequence_id = prospect_email.vessel_sequence_id
        emails = sei.get_emails_for_contact(contact_id, sequence_id)
        open_count = 0
        click_count = 0
        reply_count = 0
        is_bounced = False
        has_replied = False
        for email in emails:
            open_count = max(open_count, email.get("openCount", 0))
            click_count = max(click_count, email.get("clickCount", 0))
            if email.get("replyCount", 0):
                reply_count = max(reply_count, email.get("replyCount", 0))
            is_bounced = email.get("isBounced", False) or is_bounced
            has_replied = email.get("hasReplied", False) or has_replied

        payload = {
            "prospect_id": prospect.id,
            "sequence_id": sequence_id,
            "open_count": open_count,
            "click_count": click_count,
            "reply_count": reply_count,
            "is_bounced": is_bounced,
            "has_replied": has_replied,
        }
        raw_payloads.append(payload)

    sei_raw_id = create_sales_engagement_interaction_raw(
        client_id=client_id,
        client_sdr_id=client_sdr_id,
        source=SalesEngagementInteractionSource.VESSEL.value,
        payload=raw_payloads,
        sequence_name="Vessel Anaytics - SDR#{sdr_id} - {date}".format(
            sdr_id=str(client_sdr_id), date=datetime.now().strftime("%Y-%m-%d")
        ),
    )
    if sei_raw_id is None:
        return False, "Failed to ingest data from Vessel."

    sei_ss_id = convert_vessel_raw_payload_to_ss(
        client_id, client_sdr_id, sei_raw_id, raw_payloads
    )
    collect_and_update_status_from_ss_data.delay(sei_ss_id)

    return True, "OK"
