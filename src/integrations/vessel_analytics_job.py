from model_import import (
    ClientSDR,
    Prospect,
    ProspectEmail,
    SalesEngagementInteractionRaw,
    SalesEngagementInteractionSource,
    SalesEngagementInteractionSS,
)
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


def process_vessel_integrated_analytics(client_sdr_id: int) -> tuple[bool, str]:
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if not client_sdr:
        return False, "Client SDR not found"

    prospects = get_prospects_to_collect_analytics_for(client_sdr_id)
    sei = SalesEngagementIntegration(client_sdr.client_id)
    for entry in prospects:
        prospect: Prospect = entry[0]
        prospect_email: ProspectEmail = entry[1]
        contact_id = prospect.vessel_contact_id
        sequence_id = str(prospect_email.vessel_sequence_id)
        emails = sei.get_emails_for_contact(contact_id, sequence_id)
        print(emails)

    return True, "OK"
