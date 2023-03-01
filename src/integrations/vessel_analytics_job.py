from model_import import (
    ClientSDR,
    Prospect,
    ProspectEmail,
    SalesEngagementInteractionRaw,
    SalesEngagementInteractionSource,
    SalesEngagementInteractionSS,
)
from src.email_outbound.services import create_sales_engagement_interaction_raw
from src.integrations.vessel import SalesEngagementIntegration
from app import db
from typing import Optional


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
        )
        .all()
    )
    return prospects


def create_vessel_engagement_ss_raw(client_sdr_id: int) -> tuple[bool, str]:
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if not client_sdr:
        return False, "Client SDR not found"

    prospects = get_prospects_to_collect_analytics_for(client_sdr_id)
    sei = SalesEngagementIntegration(client_sdr.client_id)
    raw_payloads = []
    for entry in prospects:
        prospect: Prospect = entry[0]
        prospect_email: ProspectEmail = entry[1]
        contact_id = prospect.vessel_contact_id
        sequence_id = str(prospect_email.vessel_sequence_id)
        emails = sei.get_emails_for_contact(contact_id, sequence_id)
        open_count = 0
        click_count = 0
        reply_count = 0
        is_bounced = False
        has_replied = False
        for email in emails:
            open_count = max(open_count, email.get("openCount", 0))
            click_count = max(click_count, email.get("clickCount", 0))
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

    create_sales_engagement_interaction_raw(
        client_id=client_sdr.client_id,
        client_sdr_id=client_sdr_id,
        source=SalesEngagementInteractionSource.VESSEL.value,
        payload=raw_payloads,
    )

    return True, "OK"
