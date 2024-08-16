from slack_sdk.webhook import WebhookClient
import os
import linecache
import sys
import requests
from datetime import datetime
from src.utils.access import is_production

URL_MAP = {
    "ops-demo-set-detection": "https://hooks.slack.com/services/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",
    "ops-demo-reminders": "https://hooks.slack.com/services/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",
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
    "operations-auto-bump-msg-gen": "https://hooks.slack.com/services/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",
    "operations-persona-filters": "https://hooks.slack.com/services/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",
    "operations-autobump": "https://hooks.slack.com/services/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",
    "csm-demo-feedback": "https://hooks.slack.com/services/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",
    "csm-msg-feedback": "https://hooks.slack.com/services/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",
    "csm-convo-sorter": "https://hooks.slack.com/services/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",
    "csm-human-response": "https://hooks.slack.com/services/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",
    "csm-urgent-alerts": "https://hooks.slack.com/services/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",
    "csm-notifications-cta-expired": "https://hooks.slack.com/services/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",
    "company-pipeline": "https://hooks.slack.com/services/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",
    "csm-demo-date": "https://hooks.slack.com/services/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",
    "ops-scribe-submissions": "https://hooks.slack.com/services/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",
    "sales-leads-plg-demo": "https://hooks.slack.com/services/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",
    "csm-individuals": "https://hooks.slack.com/services/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",
    "prospect-demo-soon": "https://hooks.slack.com/services/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",
    "eng-icp-errors": "https://hooks.slack.com/services/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",
    "operations-sla-updater": "https://hooks.slack.com/services/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",
    "messages-ops": "https://hooks.slack.com/services/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",
    "ops-email-detected": "https://hooks.slack.com/services/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",
    "operations-withdraw-invite": "https://hooks.slack.com/services/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",
    "operations-auto-bump-email": "https://hooks.slack.com/services/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",
    "operations-nylas-connection": "https://hooks.slack.com/services/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",
    "operations-icrawler": "https://hooks.slack.com/services/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",
    "ops-outbound-warming": "https://hooks.slack.com/services/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",
    "ops-auto-send-campaign": "https://hooks.slack.com/services/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",
    "csm-drywall": "https://hooks.slack.com/services/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",
    "ops-email-notifications": "https://hooks.slack.com/services/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",
    "ops-scheduling_needed": "https://hooks.slack.com/services/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",
    "ops-auto-send-auto-deleted-messages": "https://hooks.slack.com/services/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",
    "ops-domain-setup-notifications": "https://hooks.slack.com/services/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",
    "csm-client-requests": "https://hooks.slack.com/services/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",
    "continue-sequence-alerts": "https://hooks.slack.com/services/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",
    "honeypot-email-grader": "https://hooks.slack.com/services/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",
    "ops-rep-intervention": "https://hooks.slack.com/services/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",
    "ops-territory-scraper": "https://hooks.slack.com/services/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",
    "ops-alerts-opportunity-changed": "https://hooks.slack.com/services/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",
    "ops-crm-sync-updates": "https://hooks.slack.com/services/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",
    "sales-visitors": "https://hooks.slack.com/services/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",
    "selix-sessions": "https://hooks.slack.com/services/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"
}

CHANNEL_NAME_MAP = {
    "csm-urgent-alerts": "C0594T0SAEN",
    "prospect-demo-soon": "C05LXA34QF9",
}


def send_slack_message(message: str, webhook_urls: list, blocks: any = []):
    if not is_production():
        print(message)
        return False

    for url in webhook_urls:
        if url is None:
            continue
        webhook = WebhookClient(url)
        response = webhook.send(text=message, blocks=blocks)

    from model_import import Client
    from app import db

    for webhook in webhook_urls:
        if not webhook or len(webhook) < 10:
            continue

        clients: list[Client] = Client.query.filter(
            Client.pipeline_notifications_webhook_url.like(f"%{webhook}%")
        ).all()

        for client in clients:
            if client:
                client.last_slack_msg_date = datetime.now()
                db.session.add(client)
    db.session.commit()

    return True


def send_delayed_slack_message(
    message: str, channel_name: str, delay_date: datetime
) -> bool:
    if not is_production():
        return
    if delay_date < datetime.datetime.now():
        return

    zapier_slack_hook = "https://hooks.zapier.com/hooks/catch/13803519/39efpuo/"

    response = requests.post(
        zapier_slack_hook,
        headers={
            "Content-Type": "application/json",
        },
        json={
            "delay_date": delay_date.strftime("%a %b %d %Y"),
            "message": message,
            "channel_name": channel_name,
        },
    )
    return response.status_code == 200


def exception_to_str():
    exc_type, exc_obj, tb = sys.exc_info()
    if tb is None:
        return ""
    f = tb.tb_frame
    lineno = tb.tb_lineno
    filename = f.f_code.co_filename
    linecache.checkcache(filename)
    line = linecache.getline(filename, lineno, f.f_globals)
    return 'EXCEPTION IN ({}, LINE {} "{}"): {}'.format(
        filename, lineno, line.strip(), exc_obj
    )
