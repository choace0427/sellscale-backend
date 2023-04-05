from model_import import BumpFramework
from app import db
from src.prospecting.models import ProspectOverallStatus
from typing import Optional


def create_bump_framework(
    description: str,
    overall_status: ProspectOverallStatus,
    active: bool = True,
    client_sdr_id: Optional[int] = None,
) -> BumpFramework:
    """
    Create a new bump framework
    """
    bump_framework = BumpFramework(
        description=description,
        overall_status=overall_status,
        active=active,
        client_sdr_id=client_sdr_id,
    )
    db.session.add(bump_framework)
    db.session.commit()
    return bump_framework


def delete_bump_framework(bump_framework_id: int) -> None:
    """
    Delete a bump framework
    """
    bump_framework = BumpFramework.query.get(bump_framework_id)
    db.session.delete(bump_framework)
    db.session.commit()


def get_bump_frameworks_for_sdr(
    client_sdr_id: int,
    overall_status: ProspectOverallStatus,
) -> list[BumpFramework]:
    """
    Get all bump frameworks for a given SDR
    """
    bf_list = BumpFramework.query.filter(
        BumpFramework.client_sdr_id == client_sdr_id,
        BumpFramework.overall_status == overall_status,
    ).all()
    return [bf.to_dict() for bf in bf_list]


def toggle_bump_framework_active(bump_framework_id: int) -> None:
    """
    Toggle the active status of a bump framework
    """
    bump_framework = BumpFramework.query.get(bump_framework_id)
    bump_framework.active = not bump_framework.active
    db.session.add(bump_framework)
    db.session.commit()
