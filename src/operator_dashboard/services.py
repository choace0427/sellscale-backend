import datetime
from typing import Optional
from src.client.models import ClientSDR, Client
from src.operator_dashboard.models import (
    OperatorDashboardEntry,
    OperatorDashboardEntryPriority,
    OperatorDashboardEntryStatus,
    OperatorDashboardTaskType,
)
from app import db, celery
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
    send_slack: bool = True,
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
        if urgency == OperatorDashboardEntryPriority.HIGH or urgency == "HIGH":
            urgency_str = "🔴 Blocker"
        elif urgency == OperatorDashboardEntryPriority.MEDIUM or urgency == "MEDIUM":
            urgency_str = "🟡 Non-blocker"
        elif urgency == OperatorDashboardEntryPriority.LOW or urgency == "LOW":
            urgency_str = "🟢 Non-blocker"
        elif (
            urgency == OperatorDashboardEntryPriority.COMPLETED
            or urgency == "COMPLETED"
            or urgency == "COMPLETED"
        ):
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


def send_task_reminder(task_id: int):
    task: OperatorDashboardEntry = OperatorDashboardEntry.query.get(task_id)
    client_sdr_id: int = task.client_sdr_id

    urgency = task.urgency
    emoji = task.emoji
    title = task.title
    subtitle = task.subtitle
    cta = task.cta

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
        message=f"Task Reminder: {emoji} {title}",
        blocks=[
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"Task Reminder: {emoji} {title}",
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


def get_operator_dashboard_entries_for_sdr(sdr_id: int) -> list[OperatorDashboardEntry]:
    entries = OperatorDashboardEntry.query.filter_by(client_sdr_id=sdr_id).all()

    return entries


def mark_task_complete(client_sdr_id: int, task_id: int, silent: bool = False) -> bool:
    entry: OperatorDashboardEntry = (
        OperatorDashboardEntry.query.filter_by(id=task_id)
        .filter_by(client_sdr_id=client_sdr_id)
        .first()
    )

    if not entry:
        return False

    entry.status = OperatorDashboardEntryStatus.COMPLETED
    db.session.commit()

    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client: Client = Client.query.get(client_sdr.client_id)
    first_name = client_sdr.name.split(" ")[0]
    priority = "⚪️ `unknown`"
    if entry.urgency == OperatorDashboardEntryPriority.HIGH:
        priority = "🔴 `high`"
    elif entry.urgency == OperatorDashboardEntryPriority.MEDIUM:
        priority = "🟡 `medium`"
    elif entry.urgency == OperatorDashboardEntryPriority.LOW:
        priority = "🟢 `low`"
    if not silent:
        send_slack_message(
            message="A new task was cleared by {first_name}".format(
                first_name=first_name
            ),
            blocks=[
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "A new task was cleared from {first_name}'s operator dash! ✅".format(
                            first_name=first_name
                        ),
                        "emoji": True,
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*Task name*: {task_name}\n*Priority*: {priority}".format(
                            task_name=entry.title, priority=priority
                        ),
                    },
                },
            ],
            webhook_urls=[client.pipeline_notifications_webhook_url],
        )

    return True


def dismiss_task(client_sdr_id: int, task_id: int, days=int) -> bool:
    entry: OperatorDashboardEntry = (
        OperatorDashboardEntry.query.filter_by(id=task_id)
        .filter_by(client_sdr_id=client_sdr_id)
        .first()
    )

    if not entry:
        return False

    entry.status = OperatorDashboardEntryStatus.DISMISSED
    # entry.hidden_until = datetime.datetime.utcnow() + datetime.timedelta(days=days)

    db.session.commit()

    return True


@celery.task
def auto_resolve_linkedin_tasks():
    query = """
    select 
        client_sdr.id client_sdr_id, operator_dashboard_entry.id task_id
    from client_sdr
        join client on client_sdr.client_id = client.id 
        join operator_dashboard_entry 
            on operator_dashboard_entry.client_sdr_id = client_sdr.id
                and operator_dashboard_entry.task_type in ('LINKEDIN_DISCONNECTED', 'CONNECT_LINKEDIN')
                and operator_dashboard_entry.status = 'PENDING'
    where 
        client.active and client_sdr.active
        and client_sdr.li_at_token is not null and client_sdr.li_at_token <> 'INVALID';
    """

    tasks = db.session.execute(query).fetchall()
    if not tasks:
        return

    success = True
    for task in tasks:
        client_sdr_id = task[0]
        task_id = task[1]
        success = success and mark_task_complete(client_sdr_id, task_id, silent=True)

    return success
