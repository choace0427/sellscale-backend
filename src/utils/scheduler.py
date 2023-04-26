from apscheduler.schedulers.background import BackgroundScheduler
import atexit
import time
import os

ENV = os.environ.get("FLASK_ENV")


def scrape_all_inboxes_job():
    from src.automation.inbox_scraper import scrape_all_inboxes

    if (
        os.environ.get("FLASK_ENV") == "production"
        and os.environ.get("SCHEDULING_INSTANCE") == True
    ):
        scrape_all_inboxes.delay()


def fill_in_daily_notifications():
    from src.daily_notifications.services import fill_in_daily_notifications

    if (
        os.environ.get("FLASK_ENV") == "production"
        and os.environ.get("SCHEDULING_INSTANCE") == True
    ):
        fill_in_daily_notifications.delay()


def clear_daily_notifications():
    from src.daily_notifications.services import clear_daily_notifications

    if (
        os.environ.get("FLASK_ENV") == "production"
        and os.environ.get("SCHEDULING_INSTANCE") == True
    ):
        clear_daily_notifications.delay()


def refresh_fine_tune_statuses_job():
    from src.ml.services import check_statuses_of_fine_tune_jobs

    if (
        os.environ.get("FLASK_ENV") == "production"
        and os.environ.get("SCHEDULING_INSTANCE") == True
    ):
        check_statuses_of_fine_tune_jobs.delay()


def update_all_phantom_buster_run_statuses_job():
    from src.automation.services import update_all_phantom_buster_run_statuses

    if (
        os.environ.get("FLASK_ENV") == "production"
        and os.environ.get("SCHEDULING_INSTANCE") == True
    ):
        update_all_phantom_buster_run_statuses()


def run_next_client_sdr_li_conversation_scraper_job():
    from src.li_conversation.services import run_next_client_sdr_scrape
    from src.li_conversation.conversation_analyzer.analyzer import (
        run_all_conversation_analyzers,
    )

    if (
        os.environ.get("FLASK_ENV") == "production"
        and os.environ.get("SCHEDULING_INSTANCE") == True
    ):
        run_next_client_sdr_scrape.apply_async(
            link=run_all_conversation_analyzers.signature(immutable=True)
        )


def run_backfill_analytics_for_sdrs_job():
    from src.integrations.vessel_analytics_job import (
        backfill_analytics_for_sdrs,
    )

    if (
        os.environ.get("FLASK_ENV") == "production"
        and os.environ.get("SCHEDULING_INSTANCE") == True
    ):
        backfill_analytics_for_sdrs.delay()


def run_scrape_campaigns_for_day_job():
    from src.integrations.vessel_analytics_job import (
        scrape_campaigns_for_day,
    )

    if (
        os.environ.get("FLASK_ENV") == "production"
        and os.environ.get("SCHEDULING_INSTANCE") == True
    ):
        scrape_campaigns_for_day.delay()


def run_sync_vessel_mailboxes_and_sequences_job():
    from src.integrations.vessel import sync_vessel_mailboxes_and_sequences

    if (
        os.environ.get("FLASK_ENV") == "production"
        and os.environ.get("SCHEDULING_INSTANCE") == True
    ):
        sync_vessel_mailboxes_and_sequences()


# Using Voyager!
def scrape_li_inboxes():
    from src.li_conversation.services import scrape_conversations_inbox

    if (
        os.environ.get("FLASK_ENV") == "production"
        and os.environ.get("SCHEDULING_INSTANCE") == True
    ):
        scrape_conversations_inbox.delay()


# Using Voyager!
def scrape_li_convos():
    from src.li_conversation.services import scrape_conversation_queue

    if (
        os.environ.get("FLASK_ENV") == "production"
        and os.environ.get("SCHEDULING_INSTANCE") == True
    ):
        scrape_conversation_queue.delay()


# Add all jobs to scheduler
scheduler = BackgroundScheduler(timezone="America/Los_Angeles")
scheduler.add_job(func=scrape_all_inboxes_job, trigger="interval", hours=1)
scheduler.add_job(
    func=update_all_phantom_buster_run_statuses_job, trigger="interval", hours=1
)
scheduler.add_job(
    func=run_next_client_sdr_li_conversation_scraper_job,
    trigger="cron",
    hour="9-17",
    minute="*/10",
)
# scheduler.add_job(func=refresh_fine_tune_statuses_job, trigger="interval", minutes=10)
scheduler.add_job(func=fill_in_daily_notifications, trigger="interval", hours=1)
scheduler.add_job(func=clear_daily_notifications, trigger="interval", hours=1)
scheduler.add_job(func=run_backfill_analytics_for_sdrs_job, trigger="interval", hours=1)
scheduler.add_job(func=run_scrape_campaigns_for_day_job, trigger="interval", hours=6)
scheduler.add_job(
    func=run_sync_vessel_mailboxes_and_sequences_job, trigger="interval", hours=24
)

scheduler.add_job(func=scrape_li_inboxes, trigger="interval", minutes=5)
scheduler.add_job(func=scrape_li_convos, trigger="interval", minutes=1)

scheduler.start()

atexit.register(lambda: scheduler.shutdown())
