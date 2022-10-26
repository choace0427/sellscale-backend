from model_import import ProspectStatus, Prospect, Client
from src.utils.slack import send_slack_message
from src.prospecting.services import update_prospect_status


def send_slack_block(
    message_suffix: str,
    prospect: Prospect,
    li_message_payload: any,
    new_status: ProspectStatus = None,
):
    client: Client = Client.query.get(prospect.client_id)

    send_slack_message(
        message=prospect.full_name + message_suffix,
        blocks=[
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": prospect.full_name
                    + "#"
                    + str(prospect.id)
                    + message_suffix,
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Title:* {}".format(prospect.title),
                },
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "plain_text",
                        "text": "👣 SDR: <INSERT HERE>",
                        "emoji": True,
                    },
                    {
                        "type": "plain_text",
                        "text": "🧳 SellScale Client: {}".format(client.company),
                        "emoji": True,
                    },
                ],
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "Next steps: Respond on Linkedin conversation thread",
                },
                "accessory": {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Click to see Linkedin Thread",
                        "emoji": True,
                    },
                    "value": li_message_payload.get("threadUrl")
                    or "https://www.linkedin.com",
                    "url": li_message_payload.get("threadUrl")
                    or "https://www.linkedin.com",
                    "action_id": "button-action",
                },
            },
            {"type": "divider"},
        ],
    )
