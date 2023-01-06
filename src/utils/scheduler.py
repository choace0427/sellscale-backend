from apscheduler.schedulers.background import BackgroundScheduler
import atexit
import time
import os
from src.utils.slack import URL_MAP

ENV = os.environ.get("FLASK_ENV")

from src.utils.slack import send_slack_message


def scrape_all_inboxes_job():
    from src.automation.inbox_scraper import scrape_all_inboxes

    if os.environ.get("FLASK_ENV") == "production":
        scrape_all_inboxes.delay()


def refresh_fine_tune_statuses_job():
    from src.ml.services import check_statuses_of_fine_tune_jobs

    if os.environ.get("FLASK_ENV") == "production":
        check_statuses_of_fine_tune_jobs.delay()


def update_all_phantom_buster_run_statuses_job():
    from src.automation.services import update_all_phantom_buster_run_statuses

    if os.environ.get("FLASK_ENV") == "production":
        update_all_phantom_buster_run_statuses()


scheduler = BackgroundScheduler()
scheduler.add_job(func=scrape_all_inboxes_job, trigger="interval", hours=1)
scheduler.add_job(
    func=update_all_phantom_buster_run_statuses_job, trigger="interval", minutes=10
)
# scheduler.add_job(func=refresh_fine_tune_statuses_job, trigger="interval", minutes=10)
scheduler.start()

atexit.register(lambda: scheduler.shutdown())
