####################################################
# INSTRUCTIONS FOR ADDING A NEW SLACK NOTIFICATION #
####################################################
#
# 1. Add a new SlackNotificationType to src/slack_notifications/models.py and perform a migration.
# 2. Add a new Slack Notification to src/slack_notifications/notifications.py, which should inherit from src/slack_notifications/slack_notification.py's SlackNotificationClass
# 3. After testing, add the new Slack Notification to src/slack_notifications/slack.py's send_slack_message() function


from typing import Optional


class SlackNotificationClass:
    """The base class for all Slack notifications.

    `client_sdr_id`: The ID of the ClientSDR that sent the notification
    `developer_mode`: Whether or not the notification is being sent in developer mode. Developer mode sends to a testing channel and does not send to the actual Slack channel.
    `send_notification()`: Sends a notification to Slack using the class's attributes and the Slack API. There should be no parameters to this function.
    `send_notification_preview()`: Sends a test notification (using dummy data) to Slack using the class's attributes and the Slack API. There should be no parameters to this function.

    This class should be inherited by all Slack notifications. This class should not be instantiated directly.
    """
    required_fields = {}

    def __init__(self, client_sdr_id: int, developer_mode: Optional[bool] = False):
        """Initializes a SlackNotification object. The parameters should be the attributes of the class (e.g. client_sdr_id). These parameters will influence the message sent.

        `client_sdr_id` and `developer_mode` are strongly recommended to be included in all instances of SlackNotificationClass.

        Args:
            client_sdr_id (int): The ID of the ClientSDR that sent the notification
            developer_mode (bool, optional): Whether or not the notification is being sent in developer mode. Defaults to False.
        """
        self.client_sdr_id = client_sdr_id
        self.developer_mode = developer_mode

        return
    
    def validate_required_fields(self, fields: dict):
        """Validates that all required fields are present in the fields dictionary."""
        if not set(self.required_fields).issubset(fields):
            missing_fields = set(self.required_fields) - set(fields)
            raise ValueError(f"Missing required fields: {', '.join(missing_fields)}")
    
    def send_notification(self, preview_mode: bool) -> bool:
        """Sends a notification to Slack using the class's attributes and the Slack API. There should be no parameters to this function.

        Args:
            preview_mode (bool): Whether or not the notification is being sent in preview mode. Preview mode sends to a 'dummy' message to the channel.

        Returns:
            bool: Whether or not the message was successfully sent
        """

        def get_preview_fields() -> dict:
            """Gets the fields to be used in the preview message. This function should be overridden by the child class."""
            return {}

        def get_fields() -> dict:
            """Gets the fields to be used in the message. This function should be overridden by the child class."""
            return {}

        return True

    def send_notification_preview(self) -> bool:
        """Sends a notification preview (using dummy data) to Slack using the class's attributes and the Slack API. There should be no parameters to this function.

        Returns:
            bool: Whether or not the message was successfully sent
        """
        return self.send_notification(preview_mode=True)
