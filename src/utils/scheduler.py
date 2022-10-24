from apscheduler.schedulers.background import BackgroundScheduler
import atexit
import time
import os

ENV = os.environ.get("FLASK_ENV")

from src.utils.slack import send_slack_message


def scrape_all_inboxes_job():
    from src.automation.inbox_scraper import scrape_all_inboxes

    scrape_all_inboxes.delay()
    send_slack_message(
        "📨 Scraped all the inboxes at {}".format(
            time.strftime("%A, %d. %B %Y %I:%M:%S %p")
        )
    )


if ENV == "production":
    scheduler = BackgroundScheduler()
    scheduler.add_job(func=scrape_all_inboxes_job, trigger="interval", hours=1)
    scheduler.start()

    atexit.register(lambda: scheduler.shutdown())
