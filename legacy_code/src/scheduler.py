def run_backfill_analytics_for_sdrs_job():
    from src.integrations.vessel_analytics_job import (
        backfill_analytics_for_sdrs,
    )

    if (
        os.environ.get("FLASK_ENV") == "production"
        and os.environ.get("SCHEDULING_INSTANCE") == "true"
    ):
        backfill_analytics_for_sdrs.delay()


def run_scrape_campaigns_for_day_job():
    from src.integrations.vessel_analytics_job import (
        scrape_campaigns_for_day,
    )

    if (
        os.environ.get("FLASK_ENV") == "production"
        and os.environ.get("SCHEDULING_INSTANCE") == "true"
    ):
        scrape_campaigns_for_day.delay()


def run_sync_vessel_mailboxes_and_sequences_job():
    from src.integrations.vessel import sync_vessel_mailboxes_and_sequences

    if (
        os.environ.get("FLASK_ENV") == "production"
        and os.environ.get("SCHEDULING_INSTANCE") == "true"
    ):
        sync_vessel_mailboxes_and_sequences()


scheduler.add_job(func=run_backfill_analytics_for_sdrs_job, trigger="interval", hours=1)
scheduler.add_job(func=run_scrape_campaigns_for_day_job, trigger="interval", hours=6)
scheduler.add_job(
    func=run_sync_vessel_mailboxes_and_sequences_job, trigger=daily_trigger
)