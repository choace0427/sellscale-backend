import datetime
from typing import Optional
from src.client.models import ClientSDR, Client
from src.operator_dashboard.models import (
    OperatorDashboardEntry,
    OperatorDashboardEntryPriority,
    OperatorDashboardEntryStatus,
    OperatorDashboardTaskType,
)
from app import db
from src.utils.slack import send_slack_message


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
    send_slack: bool = False,
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

    task_id = entry.id

    if send_slack:
        sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
        client: Client = Client.query.get(sdr.client_id)
        sdr_name = sdr.name
        direct_link = "https://app.sellscale.com/authenticate?stytch_token_type=direct&token={auth_token}&redirect=task/{task_id}".format(
            auth_token=sdr.auth_token,
            task_id=task_id,
        )

        urgency_str = "⚪️ unknown"
        if urgency == OperatorDashboardEntryPriority.HIGH:
            urgency_str = "🔴 high"
        elif urgency == OperatorDashboardEntryPriority.MEDIUM:
            urgency_str = "🟡 medium"
        elif urgency == OperatorDashboardEntryPriority.LOW:
            urgency_str = "🟢 low"
        elif urgency == OperatorDashboardEntryPriority.COMPLETED:
            urgency_str = "🔵 complete"

        send_slack_message(
            message=f"New task: {emoji} {title}",
            blocks=[
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"New task: {emoji} {title}",
                        "emoji": True,
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*User*: `{sdr_name}`\n*Priority*: `{urgency_str}`\n*Instructions*: _{subtitle}_\n",
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "Complete this task by clicking the button:",
                    },
                    "accessory": {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": cta,
                            "emoji": True,
                        },
                        "value": direct_link,
                        "url": direct_link,
                        "action_id": "button-action",
                    },
                },
            ],
            webhook_urls=[client.pipeline_notifications_webhook_url],
        )

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
