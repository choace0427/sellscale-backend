from slack_sdk.webhook import WebhookClient
import os

URL_MAP = {
    "eng-sandbox": "https://hooks.slack.com/services/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",
    "sellscale_pipeline_all_clients": "https://hooks.slack.com/services/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",
    "operations-ready-campaigns": "https://hooks.slack.com/services/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",
}


def send_slack_message(message: str, webhook_urls: list, blocks: any = []):
    if (
        os.environ.get("FLASK_ENV") != "production"
        and os.environ.get("FLASK_ENV") != "celery-production"
    ):
        return

    for url in webhook_urls:
        webhook = WebhookClient(url)
        webhook.send(text=message, blocks=blocks)

    return True
