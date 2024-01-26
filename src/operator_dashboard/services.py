import datetime
from typing import Optional
from src.operator_dashboard.models import (
    OperatorDashboardEntry,
    OperatorDashboardEntryPriority,
    OperatorDashboardEntryStatus,
    OperatorDashboardTaskType,
)
from app import db


def create_operator_dashboard_entry(
    client_sdr_id: int,
    urgency: OperatorDashboardEntryPriority,
    tag: str,
    emoji: str,
    title: str,
    subtitle: str,
    cta: str,
    cta_url: str,
    status: OperatorDashboardEntryStatus,
    due_date: datetime.datetime,
    task_type: OperatorDashboardTaskType,
    recurring: bool = False,
    task_data: dict = {},
) -> Optional[OperatorDashboardEntry]:
    pending_notification = OperatorDashboardEntry.query.filter_by(
        client_sdr_id=client_sdr_id,
        tag=tag,
        status=OperatorDashboardEntryStatus.PENDING,
    ).first()
    if pending_notification:
        return None

    non_pending_notification = OperatorDashboardEntry.query.filter(
        OperatorDashboardEntry.client_sdr_id == client_sdr_id,
        OperatorDashboardEntry.tag == tag,
        OperatorDashboardEntry.status != OperatorDashboardEntryStatus.PENDING,
    ).first()
    if non_pending_notification and not recurring:
        return None

    entry = OperatorDashboardEntry(
        client_sdr_id=client_sdr_id,
        urgency=urgency,
        tag=tag,
        emoji=emoji,
        title=title,
        subtitle=subtitle,
        cta=cta,
        cta_url=cta_url,
        status=status,
        due_date=due_date,
        task_type=task_type,
        task_data=task_data,
    )

    db.session.add(entry)
    db.session.commit()

    return entry


def get_operator_dashboard_entries_for_sdr(sdr_id: int) -> list[OperatorDashboardEntry]:
    entries = OperatorDashboardEntry.query.filter_by(client_sdr_id=sdr_id).all()

    return entries


def mark_task_complete(client_sdr_id: int, task_id: int) -> bool:
    entry = (
        OperatorDashboardEntry.query.filter_by(id=task_id)
        .filter_by(client_sdr_id=client_sdr_id)
        .first()
    )

    if not entry:
        return False

    entry.status = OperatorDashboardEntryStatus.COMPLETED
    db.session.commit()

    return True


def dismiss_task(client_sdr_id: int, task_id: int) -> bool:
    entry = (
        OperatorDashboardEntry.query.filter_by(id=task_id)
        .filter_by(client_sdr_id=client_sdr_id)
        .first()
    )

    if not entry:
        return False

    entry.status = OperatorDashboardEntryStatus.DISMISSED
    db.session.commit()

    return True