from app import slack_app, db
from src.slack.auth.models import SlackAuthentication
from src.slack.channels.models import SlackConnectedChannel


def slack_get_connected_channels(client_id: int) -> list[dict]:
    """Gets a list of Slack channels for a client

    Args:
        client_id (int): The ID of the client

    Returns:
        list[dict]: A list of Slack channels
    """
    connected_channels: list[
        SlackConnectedChannel
    ] = SlackConnectedChannel.query.filter_by(client_id=client_id).all()
    return [channel.to_dict() for channel in connected_channels]


def slack_join_channel(client_id: int, channel_id: str) -> tuple[bool, str]:
    """Joins a Slack channel

    Args:
        client_id (int): The ID of the client
        channel_id (str): The ID of the Slack channel

    Returns:
        tuple[bool, str]: A tuple containing a boolean indicating if the channel was joined and a string containing the response
    """
    # Get the Slack access token
    auth: SlackAuthentication = SlackAuthentication.query.filter_by(
        client_id=client_id
    ).first()
    if not auth:
        return False, "Slack authentication not found"

    # Join the channel
    response = slack_app.client.conversations_join(
        token=auth.slack_access_token, channel=channel_id
    )
    ok = response.get("ok", False)
    if not ok:
        return False, response.get("error", "Unknown error")

    channel = response.get("channel", {})
    if not channel:
        return False, "Channel not found in response"

    # Store the channel in the database
    connected_channel = SlackConnectedChannel(
        client_id=client_id,
        slack_payload=response.data,
        slack_channel_id=channel.get("id", ""),
        slack_channel_name=channel.get("name", ""),
        slack_channel_is_channel=channel.get("is_channel", False),
        slack_channel_is_group=channel.get("is_group", False),
        slack_channel_is_im=channel.get("is_im", False),
        slack_channel_created=channel.get("created", 0),
        slack_channel_creator=channel.get("creator", ""),
        slack_channel_is_archived=channel.get("is_archived", False),
        slack_channel_is_general=channel.get("is_general", False),
        slack_channel_unlinked=channel.get("unlinked", 0),
        slack_channel_name_normalized=channel.get("name_normalized", ""),
        slack_channel_is_shared=channel.get("is_shared", False),
        slack_channel_is_ext_shared=channel.get("is_ext_shared", False),
        slack_channel_is_org_shared=channel.get("is_org_shared", False),
        slack_channel_pending_shared=channel.get("pending_shared", []),
        slack_channel_is_pending_ext_shared=channel.get("is_pending_ext_shared", False),
        slack_channel_is_member=channel.get("is_member", False),
        slack_channel_is_private=channel.get("is_private", False),
        slack_channel_is_mpim=channel.get("is_mpim", False),
        slack_channel_topoic=channel.get("topic", {}),
        slack_channel_purpose=channel.get("purpose", {}),
    )
    db.session.add(connected_channel)
    db.session.commit()

    return True, "Channel joined successfully"
