from app import db
from sqlalchemy.orm import attributes


def get_outstanding_inbox(client_sdr_id: int):
    """Returns a list of outstanding inbox items.

    return_value:
    [
        {
            "prospect_id": int,
            "prospect_full_name": str,
            "prospect_title": str,
            "prospect_linkedin": str,
            "prospect_linkedin_conversation_thread": str,
            "prospect_sdr_name": str,
            "prospect_client_name": str,
            "prospect_last_reviwed_date": datetime,
            "prospect_status: ProspectStatus,


            "actions": RECORD_BUMP | NOT_INTERESTED | ACTIVE_CONVO | SCHEDULING | DEMO_SET,

            "last_message": todo(Aakash) implement this,
            "last_message_timestamp": todo(Aakash) implement this
        }
        ...
    ]

    This will be mapped in SellScale in an inbox view.
    """
    return []
