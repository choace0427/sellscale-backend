from app import celery
from src.client.models import ClientSDR
from src.slack.models import SlackNotificationType
from src.slack.slack_notification_center import (
    create_and_send_slack_notification_class_message,
)


@celery.task
def send_daily_pipeline_activity_notification_for_active_sdrs():
    # Get all active SDRs
    sdrs: list[ClientSDR] = ClientSDR.query.filter_by(active=True)

    for sdr in sdrs:
        # Send daily pipeline activity notification
        success = create_and_send_slack_notification_class_message(
            notification_type=SlackNotificationType.PIPELINE_ACTIVITY_DAILY,
            arguments={
                "client_sdr_id": sdr.id,
            },
        )

    return True
