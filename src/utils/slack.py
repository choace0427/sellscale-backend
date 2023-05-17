from slack_sdk.webhook import WebhookClient
import os

URL_MAP = {
    "autodetect-scheduling": "https://hooks.slack.com/services/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",
    "eng-sandbox": "https://hooks.slack.com/services/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",
    "user-errors": "https://hooks.slack.com/services/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",
    "sellscale_pipeline_all_clients": "https://hooks.slack.com/services/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",
    "operations-ready-campaigns": "https://hooks.slack.com/services/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",
    "operations-voice-update-requests": "https://hooks.slack.com/services/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",
    "operations-prospect-uploads": "https://hooks.slack.com/services/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",
    "operations-csm-mailman": "https://hooks.slack.com/services/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",
    "linkedin-credentials": "https://hooks.slack.com/services/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",
    "operations-campaign-generation": "https://hooks.slack.com/services/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",
    "outreach-send-to": "https://hooks.slack.com/services/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",
    "operations-li-sent-messages": "https://hooks.slack.com/services/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",
    "operations-pulse-change": "https://hooks.slack.com/services/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",
    "operations-linkedin-scraping-with-voyager": "https://hooks.slack.com/services/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",
    "operations-li-invalid-cookie": "https://hooks.slack.com/services/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",
    "csm-demo-feedback": "https://hooks.slack.com/services/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",
    "csm-convo-sorter": "https://hooks.slack.com/services/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",
    "csm-human-response": "https://hooks.slack.com/services/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",
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
 