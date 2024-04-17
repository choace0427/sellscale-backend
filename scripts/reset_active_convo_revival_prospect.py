from app import db
from model_import import (
    Prospect,
    ProspectOverallStatus,
    ProspectStatus,
)
from src.message_generation.models import GeneratedMessageAutoBump

exec(
    """
def reset_active_convo_revival_prospect(prospect_id: int):
    prospect: Prospect = Prospect.get_by_id(prospect_id)
    if prospect:
        prospect_status_records = ProspectStatusRecords.query.filter(
            ProspectStatusRecords.prospect_id == prospect_id,
            ProspectStatusRecords.to_status.in_(
                [ProspectStatus.ACTIVE_CONVO_REVIVAL, ProspectStatus.ACTIVE_CONVO]
            ),
        )

        for record in prospect_status_records:
            db.session.delete(record)

        prospect.overall_status = ProspectOverallStatus.BUMPED
        prospect.status = ProspectStatus.RESPONDED
        db.session.add(prospect)

        auto_generated_messages: list[GeneratedMessageAutoBump] = GeneratedMessageAutoBump.query.filter(
            GeneratedMessageAutoBump.prospect_id == prospect_id
        ).all()
        for message in auto_generated_messages:
            db.session.delete(message)

        db.session.commit()

        return True
"""
)
