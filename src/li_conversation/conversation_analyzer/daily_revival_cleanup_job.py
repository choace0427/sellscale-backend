from app import db, celery
from model_import import Prospect, ProspectStatus
from src.prospecting.services import update_prospect_status_linkedin
from src.utils.slack import *


@celery.task
def run_daily_prospect_to_revival_status_cleanup_job():
    data = db.session.execute(
        """
        with d as (
            select 
                prospect.id,
                prospect.full_name,
                prospect.status,
                max(linkedin_conversation_entry.id) max_entry_id
            from prospect
                join linkedin_conversation_entry 
                    on linkedin_conversation_entry.thread_urn_id = prospect.li_conversation_urn_id
            where prospect.overall_status = 'ACTIVE_CONVO'
                    and cast(prospect.status as varchar) ilike '%ACTIVE_CONVO%'
                    and prospect.status <> 'ACTIVE_CONVO_REVIVAL'
            group by 1,2,3
        )
        select 
            d.id
        from d
            join linkedin_conversation_entry 
                on linkedin_conversation_entry.id = d.max_entry_id
        where 
            linkedin_conversation_entry.connection_degree = 'You' and 
            linkedin_conversation_entry.date < NOW() - '3 days'::INTERVAL
        limit 1;
    """
    ).fetchall()

    count = 0
    for row in data:
        prospect_id = row[0]
        update_prospect_status_linkedin(
            prospect_id=prospect_id,
            new_status=ProspectStatus.ACTIVE_CONVO_REVIVAL,
        )
        count += 1

    send_slack_message(
        message="Daily revival cleanup job ran. Updated " + str(count) + " prospects.",
        webhook_urls=[URL_MAP["eng-sandbox"]],
    )
