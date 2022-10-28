from model_import import ProspectStatus, Prospect, Client, ClientSDR
from src.utils.slack import send_slack_message
from src.prospecting.services import update_prospect_status
from src.utils.slack import URL_MAP


def send_slack_block(
    message_suffix: str,
    prospect: Prospect,
    li_message_payload: any,
    new_status: ProspectStatus = None,
):
    client: Client = Client.query.get(prospect.client_id)
    client_sdr: ClientSDR = ClientSDR.query.get(prospect.client_sdr_id)

    webhook_urls = [URL_MAP["sellscale_pipeline_all_clients"]]
    if client.pipeline_notifications_webhook_url and new_status in (
        ProspectStatus.SCHEDULING,
        ProspectStatus.DEMO_SET,
        ProspectStatus.ACTIVE_CONVO,
    ):
        webhook_urls.append(client.pipeline_notifications_webhook_url)

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
                        "text": "😎 Contact: {}".format(
                            client_sdr.name if client_sdr else "NOT FOUND"
                        ),
                        "emoji": True,
                    },
                    {
                        "type": "plain_text",
                        "text": "🧳 Representing: {}".format(client.company),
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
        webhook_urls=webhook_urls,
    )
