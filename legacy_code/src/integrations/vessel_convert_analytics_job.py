from model_import import (
    Prospect,
)
from model_import import (
    SalesEngagementInteractionSS,
    EmailInteractionState,
    EmailSequenceState,
)
from src.email_outbound.ss_data import SSData

from src.integrations.vessel import SalesEngagementIntegration
from app import db, celery


def convert_vessel_raw_payload_to_ss(
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
