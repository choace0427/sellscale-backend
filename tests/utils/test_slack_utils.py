from decorators import use_app_context
from test_utils import test_app

from src.utils.slack import *
from src.prospecting.models import ProspectStatus
from src.automation.slack_notification import send_slack_block
from test_utils import basic_client, basic_archetype, basic_prospect
from model_import import Client
from app import db
import mock


@use_app_context
@mock.patch("src.automation.slack_notification.send_slack_message")
def test_send_slack_block_with_no_webhook_config(mock_send_slack_message):
    client = basic_client()
    archetype = basic_archetype(client=client)
    prospect = basic_prospect(client=client, archetype=archetype)

    message_suffix = "testing 123"
    li_message_payload = {}
    new_status = ProspectStatus.ACCEPTED

    send_slack_block(
        message_suffix=message_suffix,
        prospect=prospect,
        li_message_payload=li_message_payload,
        new_status=new_status,
    )
    assert mock_send_slack_message.call_count == 1

    args, kwargs = mock_send_slack_message.call_args
    assert len(kwargs.get("webhook_urls")) == 1


@use_app_context
@mock.patch("src.automation.slack_notification.send_slack_message")
def test_send_slack_block_with_webhook_config_but_not_allowlist(
    mock_send_slack_message,
):
    client: Client = basic_client()
    client.pipeline_notifications_webhook_url = "123.com/webhook"
    db.session.add(client)
    db.session.commit()
    archetype = basic_archetype(client=client)
    prospect = basic_prospect(client=client, archetype=archetype)

    message_suffix = "testing 123"
    li_message_payload = {}
    new_status = ProspectStatus.ACCEPTED

    send_slack_block(
        message_suffix=message_suffix,
        prospect=prospect,
        li_message_payload=li_message_payload,
        new_status=new_status,
    )
    assert mock_send_slack_message.call_count == 1

    args, kwargs = mock_send_slack_message.call_args
    assert len(kwargs.get("webhook_urls")) == 1


@use_app_context
@mock.patch("src.automation.slack_notification.send_slack_message")
def test_send_slack_block_with_webhook_config_and_allowlist(mock_send_slack_message):
    client: Client = basic_client()
    client.pipeline_notifications_webhook_url = "123.com/webhook"
    client.notification_allowlist = [ProspectStatus.ACCEPTED]
    db.session.add(client)
    db.session.commit()
    archetype = basic_archetype(client=client)
    prospect = basic_prospect(client=client, archetype=archetype)

    message_suffix = "testing 123"
    li_message_payload = {}
    new_status = ProspectStatus.ACCEPTED

    send_slack_block(
        message_suffix=message_suffix,
        prospect=prospect,
        li_message_payload=li_message_payload,
        new_status=new_status,
    )
    assert mock_send_slack_message.call_count == 1

    args, kwargs = mock_send_slack_message.call_args
    assert len(kwargs.get("webhook_urls")) == 2


@mock.patch("src.utils.slack.WebhookClient")
@mock.patch("os.environ.get", return_value="production")
def test_send_slack_message(os_get, webhook_client_mock):
    send_slack_message("testing123", ["webhook123"], blocks=[])
