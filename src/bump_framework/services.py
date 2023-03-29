from model_import import BumpFramework
from app import db
from src.prospecting.models import ProspectOverallStatus


def create_bump_framework(
    title: str,
    description: str,
    client_sdr_id: int,
    overall_status: ProspectOverallStatus,
    active: bool = True,
) -> BumpFramework:
    """
    Create a new bump framework
    """
    bump_framework = BumpFramework(
        title=title,
        description=description,
        client_sdr_id=client_sdr_id,
        overall_status=overall_status,
        active=active,
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
    client_sdr_id: int, overall_status: ProspectOverallStatus
) -> list[BumpFramework]:
    """
    Get all bump frameworks for a given SDR
    """
    bf_list = BumpFramework.query.filter_by(
        client_sdr_id=client_sdr_id, overall_status=overall_status
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
