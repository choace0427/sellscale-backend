import datetime
from app import db, celery
from src.utils.slack import URL_MAP, send_slack_message


@celery.task(name="drywall_notification")
def notify_clients_with_no_updates():
    # SQL Query - Old query, delete if no longer needed after December 4th, 2023
    # sql = """
    # with d as (
    #     select
    #         client.company,
    #         count(distinct prospect.id) filter (where prospect_status_records.to_status in ('ACCEPTED', 'ACTIVE_CONVO', 'DEMO_SET') and prospect_status_records.created_at > NOW() - '48 hours'::INTERVAL) "# Notifications in 48 Hours",
    #         max(prospect_status_records.created_at) filter (where prospect_status_records.to_status  in ('ACCEPTED', 'ACTIVE_CONVO', 'DEMO_SET')) "Latest Notification"
    #     from client
    #         join client_sdr on client_sdr.client_id = client.id
    #         join prospect on prospect.client_sdr_id = client_sdr.id
    #         join prospect_status_records on prospect_status_records.prospect_id = prospect.id
    #     where
    #         client.active and client_sdr.active and client.id <> 1
    #     group by 1
    # )
    # select
    #     company,
    #     concat(
    #         EXTRACT('days' from NOW() - d."Latest Notification") * 24 + EXTRACT('hours' from NOW() - d."Latest Notification"),
    #         ' hours ago'
    #     ) "Days Since Last Ping"
    # from d
    # where d."# Notifications in 48 Hours" = 0;
    # """
    # SQL Query - old query, delete if no longer needed after December 4th, 2023

    # using client.last_slack_msg_date
    sql = """
        select 
            client.company "Company",
            concat(
                EXTRACT('days' from NOW() - client.last_slack_msg_date) * 24 + EXTRACT('hours' from NOW() - client.last_slack_msg_date),
                ' hours ago'
            ) "Hours Since Last Ping"
        from client
            join client_sdr on client_sdr.client_id = client.id
        where client.active and client_sdr.active
            and client.last_slack_msg_date < NOW() - '24 hours'::INTERVAL
        group by 1,2;
    """

    # Execute Query
    result = db.engine.execute(sql)
    clients = result.fetchall()

    # Check if there are clients to notify
    if not clients:
        return "No clients with no updates in the last 48 hours."

    message_header = (
        "*Attention: These clients have had no updates in the last 48 hours on: "
        + datetime.datetime.now().strftime("%m/%d/%Y")
        + "*"
    )

    send_slack_message(
        message=message_header,
        webhook_urls=[URL_MAP["csm-drywall"]],
        blocks=[
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": message_header,
                },
            }
        ],
    )

    for company, hours_since_last_ping in clients:
        update = f"- {company}: {hours_since_last_ping}"

        send_slack_message(
            message=update,
            webhook_urls=[URL_MAP["csm-drywall"]],
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": update,
                    },
                }
            ],
        )

    return "Notification sent successfully."
