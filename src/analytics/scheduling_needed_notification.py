import datetime
from app import db, celery
from src.utils.slack import URL_MAP, send_slack_message


@celery.task(name="scheduling_notification")
def notify_clients_regarding_scheduling():
    sql = """
        with d as (
            select 
                client.company, 
                client_sdr.name, 
                prospect.full_name, 
                prospect.company,
                prospect.company_url,
                prospect.linkedin_url,
                prospect.li_last_message_from_prospect,
                prospect_status_records.created_at,
                prospect.linkedin_url,
                client_sdr.auth_token,
                prospect.id "prospect_id",
                client.pipeline_notifications_webhook_url
            from prospect
                join client_sdr on client_sdr.id = prospect.client_sdr_id
                join client on client.id = client_sdr.client_id
                join prospect_status_records on prospect_status_records.prospect_id = prospect.id 
                    and prospect_status_records.to_status = 'ACTIVE_CONVO_SCHEDULING'
            where prospect.status = 'ACTIVE_CONVO_SCHEDULING'
                and client_sdr.active and client.active
                and client.id <> 1
                and mod(EXTRACT('days' from NOW() - prospect_status_records.created_at), 3) = 0
    )
    select *
    from d
    where d.created_at <= NOW() - INTERVAL '3 days'
    """

    # Execute Query
    result = db.engine.execute(sql)
    clients = result.fetchall()

    # Check if there are clients to notify
    if not clients:
        send_slack_message(
            message="No clients with scheduling needed in the last 3 days.",
            webhook_urls=[URL_MAP["ops-scheduling_needed"]],
        )

    entries_grouped_by_sdr = {}
    for client in clients:
        if client.name not in entries_grouped_by_sdr:
            entries_grouped_by_sdr[client.name] = []
        entries_grouped_by_sdr[client.name].append(client)

    sent_prospect_ids = []
    for sdr in entries_grouped_by_sdr:
        unique_names = len(set([c.full_name for c in entries_grouped_by_sdr[sdr]]))
        message = f":alarm_clock: {unique_names} prospect trying to schedule {sdr} for `3+ Days`"
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f":alarm_clock: {unique_names} prospect trying to schedule {sdr} for `3+ Days`",
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"@{sdr} - please let us know if any are unqualified, booked, or still trying to schedule.",
                },
            },
        ]
        pipeline_notifications_webhook_url = None
        for client in entries_grouped_by_sdr[sdr]:
            pipeline_notifications_webhook_url = (
                client.pipeline_notifications_webhook_url
            )
            direct_link = "https://app.sellscale.com/authenticate?stytch_token_type=direct&token={auth_token}&redirect=prospects/{prospect_id}".format(
                auth_token=client.auth_token, prospect_id=client.prospect_id
            )
            prospect_i = entries_grouped_by_sdr[sdr].index(client) + 1

            if client.prospect_id in sent_prospect_ids:
                continue

            sent_prospect_ids.append(client.prospect_id)

            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"""
Prospect #{prospect_i}
> :bust_in_silhouette: {client.full_name} @ <{client.company_url}|{client.company}>
> *Status*: :fire: *`Scheduling`* for `{max(0, int((datetime.datetime.now() - client.created_at).days))}` days
> *Last message from prospect*: | <{direct_link}|View convo ->>
> ```
{client.li_last_message_from_prospect}
```
---
                        """,
                    },
                }
            )
        send_slack_message(
            message=message,
            webhook_urls=[
                URL_MAP["ops-scheduling_needed"],
                pipeline_notifications_webhook_url,
            ],
            blocks=blocks,
        )
        print(f"Sent message to {sdr}")
