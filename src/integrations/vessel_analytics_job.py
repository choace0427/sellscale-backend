from model_import import (
    ClientSDR,
    Prospect,
    ProspectEmail,
    SalesEngagementInteractionSource,
)
from model_import import (
    SalesEngagementInteractionSS,
    EmailInteractionState,
    EmailSequenceState,
)
from src.email_outbound.ss_data import SSData
from src.email_outbound.services import (
    create_sales_engagement_interaction_raw,
    collect_and_update_status_from_ss_data,
)
from src.integrations.vessel import SalesEngagementIntegration
from app import db, celery
from datetime import datetime


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

    sei_raw_id = create_sales_engagement_interaction_raw(
        client_id=client_sdr.client_id,
        client_sdr_id=client_sdr_id,
        source=SalesEngagementInteractionSource.VESSEL.value,
        payload=raw_payloads,
        sequence_name="Vessel Anaytics - SDR#{sdr_id} - {date}".format(
            sdr_id=str(client_sdr_id), date=datetime.now().strftime("%Y-%m-%d")
        ),
    )
    if sei_raw_id is None:
        return False, "Failed to ingest data from Vessel."

    convert_vessel_raw_payload_to_ss.apply_async(
        args=[client_sdr.client_id, client_sdr_id, sei_raw_id, raw_payloads],
        link=collect_and_update_status_from_ss_data.s(),
    )

    return True, "OK"


@celery.task(bind=True, max_retries=3)
def convert_vessel_raw_payload_to_ss(
    self: any,
    client_id: int,
    client_sdr_id: int,
    sales_engagement_interaction_raw_id: int,
    payload: list,
) -> int:
    """Converts the Vessel raw payload to SalesEngagementInteractionSS

    Args:
        client_id (int): The client ID
        client_archetype_id (int): The client archetype ID
        client_sdr_id (int): The client SDR ID
        sales_engagement_interaction_raw_id (int): The SalesEngagementInteractionRaw ID
        payload (list): The raw Vessel payload
            payload looks like
                [
                    {
                        "is_bounced": false,
                        "open_count": 0,
                        "click_count": 0,
                        "has_replied": true,
                        "prospect_id": 40501,
                        "reply_count": 1,
                        "sequence_id": "2999800"
                    }
                ]

    Returns:
        int: The SalesEngagementInteractionSS ID
    """
    try:
        list_ss_prospects = []
        for entry in payload:
            is_bounced = entry.get("is_bounced", False)
            has_replied = entry.get("has_replied", False)

            open_count = entry.get("open_count", 0)
            click_count = entry.get("click_count", 0)
            reply_count = entry.get("reply_count", 0)

            prospect_id = entry.get("prospect_id", None)
            sequence_id = entry.get("sequence_id", None)

            prospect: Prospect = Prospect.query.get(prospect_id)

            email = prospect.email
            if has_replied:
                sequence_state = EmailSequenceState.COMPLETED
            elif is_bounced:
                sequence_state = EmailSequenceState.BOUNCED
            else:
                sequence_state = EmailSequenceState.UNKNOWN

            if has_replied or reply_count > 0:
                interaction_state = EmailInteractionState.EMAIL_REPLIED
            elif click_count > 0:
                interaction_state = EmailInteractionState.EMAIL_CLICKED
            elif open_count > 0:
                interaction_state = EmailInteractionState.EMAIL_OPENED
            else:
                interaction_state = EmailInteractionState.EMAIL_SENT

            ss_prospect_dict = SSData(
                email=email,
                email_interaction_state=interaction_state,
                email_sequence_state=sequence_state,
            )
            list_ss_prospects.append(ss_prospect_dict.to_str_dict())

        sei_ss = SalesEngagementInteractionSS(
            client_id=client_id,
            client_sdr_id=client_sdr_id,
            sales_engagement_interaction_raw_id=sales_engagement_interaction_raw_id,
            ss_status_data=list_ss_prospects,
        )
        db.session.add(sei_ss)
        db.session.commit()
        return sei_ss.id
    except Exception as e:
        db.session.rollback()
        raise self.retry(exc=e, countdown=2**self.request.retries)
