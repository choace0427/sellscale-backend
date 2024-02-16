# Slack
import os
from slack_bolt import App as SlackApp
from slack_bolt.authorization import AuthorizeResult as SlackAuthorizeResult
from slack_bolt.adapter.flask import SlackRequestHandler
from src.utils.access import is_celery, is_production, is_scheduling_instance


class SlackAppHandlerPair:
    _app_instance = None
    _handler_instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._app_instance or not cls._handler_instance:
            cls._app_instance = super().__new__(cls)
            cls._handler_instance = super().__new__(cls)

            # Initialize the Slack app
            cls._app_instance, cls._handler_instance = initialize_slack_app()

        return cls._app_instance, cls._handler_instance


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
    # If this is not PURELY production
    if not is_production():
        print("Not in production environment, Slack App will not be initialized")
        return None, None

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
