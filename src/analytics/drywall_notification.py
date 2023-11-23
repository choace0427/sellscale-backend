from app import db
from src.utils.slack import URL_MAP, send_slack_message


def notify_clients_with_no_updates():
    # SQL Query
    sql = """
    with d as (
        select 
            client.company,
            count(distinct prospect.id) filter (where prospect_status_records.to_status in ('ACCEPTED', 'ACTIVE_CONVO', 'DEMO_SET') and prospect_status_records.created_at > NOW() - '24 hours'::INTERVAL) "# Notifications in 24 Hours",
            max(prospect_status_records.created_at) filter (where prospect_status_records.to_status  in ('ACCEPTED', 'ACTIVE_CONVO', 'DEMO_SET')) "Latest Notification"
        from client
            join client_sdr on client_sdr.client_id = client.id
            join prospect on prospect.client_sdr_id = client_sdr.id
            join prospect_status_records on prospect_status_records.prospect_id = prospect.id
        where 
            client.active and client_sdr.active and client.id <> 1
        group by 1
    )
    select 
        company,
        concat(
            EXTRACT('days' from NOW() - d."Latest Notification") * 24 + EXTRACT('hours' from NOW() - d."Latest Notification"),
            ' hours ago'
        ) "Days Since Last Ping"
    from d
    where d."# Notifications in 24 Hours" = 0;
    """

    # Execute Query
    result = db.engine.execute(sql)
    clients = result.fetchall()

    # Check if there are clients to notify
    if not clients:
        return "No clients with no updates in the last 24 hours."

    # Format Message
    message_lines = [
        "*Attention: These clients have had no updates in the last 24 hours*"
    ]
    for company, hours_since_last_ping in clients:
        message_lines.append(f"- {company}: {hours_since_last_ping}")

    message = "\n".join(message_lines)

    # Send Slack Notification
    send_slack_message(
        message=message,
        webhook_urls=[URL_MAP["eng-sandbox"]],
        blocks=[
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": message,
                },
            }
        ],
    )
    return "Notification sent successfully."
