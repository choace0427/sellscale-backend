# Slack
import os
from slack_bolt import App as SlackApp
from slack_bolt.authorization import AuthorizeResult as SlackAuthorizeResult
from slack_bolt.adapter.socket_mode import SocketModeHandler as SlackSocketModeHandler


def authorize(enterprise_id, team_id, logger) -> SlackAuthorizeResult:
    """Authorization function for Slack

    Returns:
        SlackAuthorizeResult: The authorization result
    """
    pass


def initialize_slack_app():
    """Initializes the Slack app

    Returns:
        SlackApp (slack_bolt.App): The Slack app
    """
    if os.environ["APP_SETTINGS"] != "config.ProductionConfig":
        print("Using development config, Slack App will not be initialized")
        return None

    # Slack
    print("Initializing Slack App")
    slack_app = SlackApp(
        token=os.environ.get("SLACK_BOT_TOKEN"),
        signing_secret=os.environ.get("SLACK_SIGNING_SECRET"),
        authorize=authorize,
    )

    handler = SlackSocketModeHandler(slack_app, os.environ["SLACK_APP_TOKEN"])
    handler.connect()

    print("Slack App initialized")
    return slack_app
