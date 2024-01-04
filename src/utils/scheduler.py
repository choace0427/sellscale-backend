from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import atexit
import os

from pytz import timezone

ENV = os.environ.get("FLASK_ENV")


def process_queue():
    from src.automation.orchestrator import process_queue

    if (
        os.environ.get("FLASK_ENV") == "production"
        and os.environ.get("SCHEDULING_INSTANCE") == "true"
    ):
        process_queue.apply_async(
            args=[],
            queue="orchestrator",
            routing_key="orchestrator",
            priority=1,
        )


def scrape_all_inboxes_job():
    from src.automation.inbox_scraper import scrape_all_inboxes

    if (
        os.environ.get("FLASK_ENV") == "production"
        and os.environ.get("SCHEDULING_INSTANCE") == "true"
    ):
        scrape_all_inboxes.delay()


def fill_in_daily_notifications():
    from src.daily_notifications.services import fill_in_daily_notifications

    if (
        os.environ.get("FLASK_ENV") == "production"
        and os.environ.get("SCHEDULING_INSTANCE") == "true"
    ):
        fill_in_daily_notifications.delay()


def clear_daily_notifications():
    from src.daily_notifications.services import clear_daily_notifications

    if (
        os.environ.get("FLASK_ENV") == "production"
        and os.environ.get("SCHEDULING_INSTANCE") == "true"
    ):
        clear_daily_notifications.delay()


def refresh_fine_tune_statuses_job():
    from src.ml.services import check_statuses_of_fine_tune_jobs

    if (
        os.environ.get("FLASK_ENV") == "production"
        and os.environ.get("SCHEDULING_INSTANCE") == "true"
    ):
        check_statuses_of_fine_tune_jobs.delay()


def update_all_phantom_buster_run_statuses_job():
    from src.automation.services import update_all_phantom_buster_run_statuses

    if (
        os.environ.get("FLASK_ENV") == "production"
        and os.environ.get("SCHEDULING_INSTANCE") == "true"
    ):
        update_all_phantom_buster_run_statuses()


def run_next_client_sdr_li_conversation_scraper_job():
    from src.li_conversation.services import run_next_client_sdr_scrape
    from src.li_conversation.conversation_analyzer.analyzer import (
        run_all_conversation_analyzers,
    )

    if (
        os.environ.get("FLASK_ENV") == "production"
        and os.environ.get("SCHEDULING_INSTANCE") == "true"
    ):
        run_next_client_sdr_scrape.apply_async(
            link=run_all_conversation_analyzers.signature(immutable=True)
        )


# Using Voyager!
def scrape_li_inboxes():
    from src.li_conversation.services import scrape_conversations_inbox

    if (
        os.environ.get("FLASK_ENV") == "production"
        and os.environ.get("SCHEDULING_INSTANCE") == "true"
    ):
        scrape_conversations_inbox.delay()


# Using Voyager!
def scrape_li_convos():
    from src.li_conversation.services import scrape_conversation_queue

    if (
        os.environ.get("FLASK_ENV") == "production"
        and os.environ.get("SCHEDULING_INSTANCE") == "true"
    ):
        scrape_conversation_queue.delay()


def auto_send_bumps():
    from src.li_conversation.services import send_autogenerated_bumps

    if (
        os.environ.get("FLASK_ENV") == "production"
        and os.environ.get("SCHEDULING_INSTANCE") == "true"
    ):
        send_autogenerated_bumps.apply_async([], priority=1)


def replenish_sdr_credits():
    from src.ml.services import replenish_all_ml_credits_for_all_sdrs
    from src.email_outbound.email_store.hunter import (
        replenish_all_email_credits_for_all_sdrs,
    )

    if (
        os.environ.get("FLASK_ENV") == "production"
        and os.environ.get("SCHEDULING_INSTANCE") == "true"
    ):
        replenish_all_ml_credits_for_all_sdrs()
        replenish_all_email_credits_for_all_sdrs()


def generate_message_bumps():
    from src.message_generation.services import generate_message_bumps

    if (
        os.environ.get("FLASK_ENV") == "production"
        and os.environ.get("SCHEDULING_INSTANCE") == "true"
    ):
        generate_message_bumps.delay()


def reset_phantom_buster_scrapes_and_launches_job():
    from src.automation.services import reset_phantom_buster_scrapes_and_launches

    if (
        os.environ.get("FLASK_ENV") == "production"
        and os.environ.get("SCHEDULING_INSTANCE") == "true"
    ):
        reset_phantom_buster_scrapes_and_launches.delay()


# def generate_email_bumps():
#     from src.email_sequencing.services import generate_email_bumps

#     if (
#         os.environ.get("FLASK_ENV") == "production"
#         and os.environ.get("SCHEDULING_INSTANCE") == "true"
#     ):
#         generate_email_bumps.delay()


def auto_mark_uninterested_bumped_prospects_job():
    from src.prospecting.services import auto_mark_uninterested_bumped_prospects

    if (
        os.environ.get("FLASK_ENV") == "production"
        and os.environ.get("SCHEDULING_INSTANCE") == "true"
    ):
        auto_mark_uninterested_bumped_prospects.delay()


def auto_run_daily_revival_cleanup_job():
    from src.li_conversation.conversation_analyzer.daily_revival_cleanup_job import (
        run_daily_prospect_to_revival_status_cleanup_job,
    )

    if (
        os.environ.get("FLASK_ENV") == "production"
        and os.environ.get("SCHEDULING_INSTANCE") == "true"
    ):
        run_daily_prospect_to_revival_status_cleanup_job.delay()


def run_sales_navigator_launches():
    from src.automation.phantom_buster.services import (
        collect_and_trigger_phantom_buster_sales_navigator_launches,
    )

    if (
        os.environ.get("FLASK_ENV") == "production"
        and os.environ.get("SCHEDULING_INSTANCE") == "true"
    ):
        collect_and_trigger_phantom_buster_sales_navigator_launches()


def run_sales_navigator_reset():
    from src.automation.phantom_buster.services import (
        reset_sales_navigator_config_counts,
    )

    if (
        os.environ.get("FLASK_ENV") == "production"
        and os.environ.get("SCHEDULING_INSTANCE") == "true"
    ):
        reset_sales_navigator_config_counts.delay()

    return


def run_scrape_for_demos():
    from src.client.services import scrape_for_demos

    if (
        os.environ.get("FLASK_ENV") == "production"
        and os.environ.get("SCHEDULING_INSTANCE") == "true"
    ):
        scrape_for_demos.delay()

    return


def run_collect_and_trigger_email_store_hunter_verify():
    from src.email_outbound.email_store.services import (
        collect_and_trigger_email_store_hunter_verify,
    )

    if (
        os.environ.get("FLASK_ENV") == "production"
        and os.environ.get("SCHEDULING_INSTANCE") == "true"
    ):
        collect_and_trigger_email_store_hunter_verify.delay()


def process_sdr_stats_job():
    from src.analytics.services_sdr_stats_puller import process_sdr_stats

    if (
        os.environ.get("FLASK_ENV") == "production"
        and os.environ.get("SCHEDULING_INSTANCE") == "true"
    ):
        process_sdr_stats.delay()


def run_queued_gm_jobs():
    from src.message_generation.services import run_queued_gm_job

    if (
        os.environ.get("FLASK_ENV") == "production"
        and os.environ.get("SCHEDULING_INSTANCE") == "true"
    ):
        run_queued_gm_job.delay()


def run_auto_update_sdr_linkedin_sla_jobs():
    from src.client.sdr.services_client_sdr import automatic_sla_schedule_loader

    if (
        os.environ.get("FLASK_ENV") == "production"
        and os.environ.get("SCHEDULING_INSTANCE") == "true"
    ):
        automatic_sla_schedule_loader.delay()


def run_daily_editor_assignments():
    from src.editor.services import send_editor_assignments_notification

    if (
        os.environ.get("FLASK_ENV") == "production"
        and os.environ.get("SCHEDULING_INSTANCE") == "true"
    ):
        send_editor_assignments_notification.delay()


def run_hourly_email_finder_job():
    from src.li_conversation.conversation_analyzer.li_email_finder import (
        update_all_outstanding_prospect_emails,
    )

    if (
        os.environ.get("FLASK_ENV") == "production"
        and os.environ.get("SCHEDULING_INSTANCE") == "true"
    ):
        update_all_outstanding_prospect_emails.delay()


def run_weekday_phantom_buster_updater():
    from src.client.services import daily_pb_launch_schedule_update

    if (
        os.environ.get("FLASK_ENV") == "production"
        and os.environ.get("SCHEDULING_INSTANCE") == "true"
    ):
        daily_pb_launch_schedule_update.delay()


def run_collect_and_generate_email_messaging_schedule_entries():
    from src.email_scheduling.services import (
        collect_and_generate_email_messaging_schedule_entries,
    )

    if (
        os.environ.get("FLASK_ENV") == "production"
        and os.environ.get("SCHEDULING_INSTANCE") == "true"
    ):
        collect_and_generate_email_messaging_schedule_entries.apply_async(
            args=[],
            queue="email_scheduler",
            routing_key="email_scheduler",
            priority=2,
        )


def run_set_warmup_snapshots():
    from src.warmup_snapshot.services import set_warmup_snapshots_for_all_active_sdrs
    from src.domains.services import validate_all_domain_configurations

    if (
        os.environ.get("FLASK_ENV") == "production"
        and os.environ.get("SCHEDULING_INSTANCE") == "true"
    ):
        set_warmup_snapshots_for_all_active_sdrs.delay()
        validate_all_domain_configurations.delay()


def run_collect_and_send_email_messaging_schedule_entries():
    from src.email_scheduling.services import (
        collect_and_send_email_messaging_schedule_entries,
    )

    if (
        os.environ.get("FLASK_ENV") == "production"
        and os.environ.get("SCHEDULING_INSTANCE") == "true"
    ):
        collect_and_send_email_messaging_schedule_entries.apply_async(
            args=[],
            queue="email_scheduler",
            routing_key="email_scheduler",
            priority=1,
        )


def run_find_and_run_queued_question_enrichment_row_job():
    from src.prospecting.question_enrichment.services import (
        find_and_run_queued_question_enrichment_row,
    )

    if (
        os.environ.get("FLASK_ENV") == "production"
        and os.environ.get("SCHEDULING_INSTANCE") == "true"
    ):
        find_and_run_queued_question_enrichment_row.delay(20)  # num_rows


def run_analytics_backfill_jobs():
    from src.voyager.services import run_fast_analytics_backfill
    from src.li_conversation.services_linkedin_initial_message_templates import (
        backfill_linkedin_initial_message_template_library_stats,
    )

    if (
        os.environ.get("FLASK_ENV") == "production"
        and os.environ.get("SCHEDULING_INSTANCE") == "true"
    ):
        run_fast_analytics_backfill.delay()
        backfill_linkedin_initial_message_template_library_stats.delay()


def run_daily_collect_and_generate_campaigns_for_sdr():
    from src.campaigns.autopilot.services import (
        daily_collect_and_generate_campaigns_for_sdr,
    )

    if (
        os.environ.get("FLASK_ENV") == "production"
        and os.environ.get("SCHEDULING_INSTANCE") == "true"
    ):
        daily_collect_and_generate_campaigns_for_sdr.delay()


def run_daily_drywall_notifications():
    from src.analytics.drywall_notification import notify_clients_with_no_updates

    if (
        os.environ.get("FLASK_ENV") == "production"
        and os.environ.get("SCHEDULING_INSTANCE") == "true"
    ):
        notify_clients_with_no_updates.delay()


def run_sync_all_campaign_leads():
    from src.smartlead.services import sync_all_campaign_leads

    if (
        os.environ.get("FLASK_ENV") == "production"
        and os.environ.get("SCHEDULING_INSTANCE") == "true"
    ):
        sync_all_campaign_leads.delay()


def run_auto_send_campaigns_and_send_approved_messages_job():
    from src.campaigns.autopilot.services import (
        auto_send_campaigns_and_send_approved_messages_job,
    )

    if (
        os.environ.get("FLASK_ENV") == "production"
        and os.environ.get("SCHEDULING_INSTANCE") == "true"
    ):
        auto_send_campaigns_and_send_approved_messages_job.delay()


def run_daily_auto_notify_about_scheduling():
    from src.analytics.scheduling_needed_notification import (
        notify_clients_regarding_scheduling,
    )

    if (
        os.environ.get("FLASK_ENV") == "production"
        and os.environ.get("SCHEDULING_INSTANCE") == "true"
    ):
        notify_clients_regarding_scheduling.delay()


def run_daily_auto_send_report_email():
    from src.analytics.daily_message_generation_sample import (
        send_report_email,
    )

    if (
        os.environ.get("FLASK_ENV") == "production"
        and os.environ.get("SCHEDULING_INSTANCE") == "true"
    ):
        send_report_email.delay()


def run_daily_trigger_runner():
    from src.triggers.services import (
        run_all_triggers,
    )

    if (
        os.environ.get("FLASK_ENV") == "production"
        and os.environ.get("SCHEDULING_INSTANCE") == "true"
    ):
        run_all_triggers.delay()


def run_daily_demo_reminders():
    from src.client.services import (
        send_demo_reminders,
    )

    if (
        os.environ.get("FLASK_ENV") == "production"
        and os.environ.get("SCHEDULING_INSTANCE") == "true"
    ):
        send_demo_reminders.delay()


daily_trigger = CronTrigger(hour=9, timezone=timezone("America/Los_Angeles"))
weekly_trigger = CronTrigger(
    day_of_week=0, hour=9, timezone=timezone("America/Los_Angeles")
)
mid_week_trigger = CronTrigger(
    day_of_week=2, hour=9, timezone=timezone("America/Los_Angeles")
)
weekday_trigger = CronTrigger(
    day_of_week="mon-fri", hour=5, timezone=timezone("America/Los_Angeles")
)
monthly_trigger = CronTrigger(day=1, hour=10, timezone=timezone("America/Los_Angeles"))

# Add all jobs to scheduler
scheduler = BackgroundScheduler(timezone="America/Los_Angeles")

# 30 second triggers
scheduler.add_job(
    func=run_collect_and_generate_email_messaging_schedule_entries,
    trigger="interval",
    seconds=30,
)
scheduler.add_job(
    func=run_collect_and_send_email_messaging_schedule_entries,
    trigger="interval",
    seconds=30,
)
scheduler.add_job(func=process_queue, trigger="interval", seconds=30)
scheduler.add_job(
    func=run_find_and_run_queued_question_enrichment_row_job,
    trigger="interval",
    seconds=20,
)

# Minute triggers
scheduler.add_job(func=scrape_li_convos, trigger="interval", minutes=1)
scheduler.add_job(run_sales_navigator_launches, trigger="interval", minutes=1)
scheduler.add_job(func=generate_message_bumps, trigger="interval", minutes=2)
# scheduler.add_job(func=generate_email_bumps, trigger="interval", minutes=2)
scheduler.add_job(func=scrape_li_inboxes, trigger="interval", minutes=5)
scheduler.add_job(
    auto_mark_uninterested_bumped_prospects_job, trigger="interval", minutes=10
)

scheduler.add_job(func=auto_send_bumps, trigger="interval", minutes=15)

scheduler.add_job(func=run_queued_gm_jobs, trigger="interval", seconds=30)
scheduler.add_job(
    func=reset_phantom_buster_scrapes_and_launches_job, trigger="interval", minutes=15
)

# Hourly triggers
# scheduler.add_job(func=fill_in_daily_notifications, trigger="interval", hours=1)
# scheduler.add_job(func=clear_daily_notifications, trigger="interval", hours=1)
scheduler.add_job(
    func=update_all_phantom_buster_run_statuses_job, trigger="interval", hours=1
)
scheduler.add_job(auto_run_daily_revival_cleanup_job, trigger="interval", hours=1)
scheduler.add_job(
    func=run_collect_and_trigger_email_store_hunter_verify, trigger="interval", hours=1
)
scheduler.add_job(func=process_sdr_stats_job, trigger="interval", hours=3)
scheduler.add_job(func=run_hourly_email_finder_job, trigger="interval", hours=1)
scheduler.add_job(func=run_analytics_backfill_jobs, trigger="interval", hours=1)
scheduler.add_job(func=run_set_warmup_snapshots, trigger="interval", hours=3)
scheduler.add_job(
    func=run_auto_send_campaigns_and_send_approved_messages_job,
    trigger="interval",
    hours=1,
)

# Daily triggers
scheduler.add_job(run_sales_navigator_reset, trigger=daily_trigger)
scheduler.add_job(run_scrape_for_demos, trigger=daily_trigger)
scheduler.add_job(run_daily_editor_assignments, trigger=daily_trigger)
scheduler.add_job(run_daily_auto_notify_about_scheduling, trigger=daily_trigger)
scheduler.add_job(
    run_daily_collect_and_generate_campaigns_for_sdr, trigger=daily_trigger
)
scheduler.add_job(run_daily_drywall_notifications, trigger=daily_trigger)
scheduler.add_job(run_sync_all_campaign_leads, trigger=daily_trigger)
scheduler.add_job(run_daily_auto_send_report_email, trigger=mid_week_trigger)
scheduler.add_job(run_daily_trigger_runner, trigger=daily_trigger)
scheduler.add_job(run_daily_demo_reminders, trigger=daily_trigger)

# Weekly triggers
scheduler.add_job(run_auto_update_sdr_linkedin_sla_jobs, trigger=weekly_trigger)

# Weekday triggers
scheduler.add_job(run_weekday_phantom_buster_updater, trigger=weekday_trigger)

# Monthly triggers
scheduler.add_job(func=replenish_sdr_credits, trigger=monthly_trigger)


scheduler.start()

atexit.register(lambda: scheduler.shutdown())
