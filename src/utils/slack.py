from slack_sdk.webhook import WebhookClient

URL_MAP = {
    "eng-sandbox": "https://hooks.slack.com/services/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"
}


def send_slack_message(message: str, blocks: any = [], channel: str = "eng-sandbox"):
    webhook = WebhookClient(URL_MAP[channel])
    response = webhook.send(text=message, blocks=blocks)
    return response
