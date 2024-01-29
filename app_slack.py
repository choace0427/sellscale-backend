# Slack
import os
from slack_bolt import App as SlackApp
from slack_bolt.authorization import AuthorizeResult as SlackAuthorizeResult
from slack_bolt.adapter.flask import SlackRequestHandler
from src.utils.access import is_production


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
    if not is_production():
        print("Using development config, Slack App will not be initialized")
        return None

    # Slack
    print("Initializing Slack App")
    slack_app = SlackApp(
        token=os.environ.get("SLACK_BOT_TOKEN"),
        signing_secret=os.environ.get("SLACK_SIGNING_SECRET"),
        authorize=authorize,
    )

    handler = SlackRequestHandler(slack_app)

    print("Slack App initialized")
    return slack_app, handler
