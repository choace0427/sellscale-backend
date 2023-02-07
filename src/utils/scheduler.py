from apscheduler.schedulers.background import BackgroundScheduler
import atexit
import time
import os

ENV = os.environ.get("FLASK_ENV")


def scrape_all_inboxes_job():
    from src.automation.inbox_scraper import scrape_all_inboxes

    if os.environ.get("FLASK_ENV") == "production":
        scrape_all_inboxes.delay()


def fill_in_daily_notifications():
    from src.daily_notifications.services import fill_in_daily_notifications

    if os.environ.get("FLASK_ENV") == "production":
        fill_in_daily_notifications.delay()


def clear_daily_notifications():
    from src.daily_notifications.services import clear_daily_notifications

    if os.environ.get("FLASK_ENV") == "production":
        clear_daily_notifications.delay()


def refresh_fine_tune_statuses_job():
    from src.ml.services import check_statuses_of_fine_tune_jobs

    if os.environ.get("FLASK_ENV") == "production":
        check_statuses_of_fine_tune_jobs.delay()


def update_all_phantom_buster_run_statuses_job():
    from src.automation.services import update_all_phantom_buster_run_statuses

    if os.environ.get("FLASK_ENV") == "production":
        update_all_phantom_buster_run_statuses()


def run_next_client_sdr_li_conversation_scraper_job():
    from src.li_conversation.services import run_next_client_sdr_scrape

    if os.environ.get("FLASK_ENV") == "production":
        run_next_client_sdr_scrape.delay()


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
scheduler.add_job(func=fill_in_daily_notifications, trigger="interval", hours=24)
scheduler.add_job(func=clear_daily_notifications, trigger="interval", hours=24)
# TODO For testing, remove this:
scheduler.add_job(func=fill_in_daily_notifications, trigger="interval", seconds=10)
scheduler.start()

atexit.register(lambda: scheduler.shutdown())
