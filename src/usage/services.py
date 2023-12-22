from app import db
from src.prospecting.models import Prospect, ProspectStatusRecords
from src.research.models import ResearchPayload
from typing import Optional
import json


def get_response_prospecting_service(client_id: int):
    query = f"""
        select 
            count(distinct prospect.id) "prospect_created",
            count(distinct research_payload.prospect_id) "prospect_enriched",
            count(distinct prospect_status_records.prospect_id) filter (where prospect_status_records.to_status = 'SENT_OUTREACH') "total_outreach_sent",
            count(distinct prospect_status_records.prospect_id) filter (where prospect_status_records.to_status = 'RESPONDED') "ai_replies",
            count(distinct prospect_status_records.prospect_id) filter (where prospect_status_records.to_status = 'NOT_INTERESTED') "prospects_snoozed",
            count(distinct prospect_status_records.prospect_id) filter (where prospect_status_records.to_status = 'NOT_QUALIFIED') "prospects_removed",
            
            count(distinct prospect.id) filter (where prospect_status_records.to_status = 'SENT_OUTREACH' and prospect_status_records.created_at > NOW() - '30 days'::INTERVAL) "monthly_touchpoints_used"
        from prospect
            left join research_payload on research_payload.prospect_id = prospect.id
            left join prospect_status_records on prospect_status_records.prospect_id = prospect.id
        where prospect.client_id = :client_id;
    """
    result = db.session.execute(query, {"client_id": client_id}).fetchone()

    return result


def get_created_prospect(client_id: int):
    query = f"""
        select 
            to_char(prospect.created_at, 'YYYY-MM'),
            count(distinct prospect.id)
        from prospect
        where client_id = :client_id
            and prospect.created_at > NOW() - '365 days'::INTERVAL
        group by 1
        order by 1 asc;
    """
    result = db.session.execute(query, {"client_id": client_id}).fetchall()
    steps = []
    for id, step in result:
        step = {"date": id, "value": step}
        steps.append(step)

    return {"data": steps, "color": "blue"}


def get_touchsent_prospect(client_id: int):
    query = f"""
        select 
            to_char(prospect_status_records.created_at, 'YYYY-MM'),
            count(distinct prospect.id)
        from prospect
            left join prospect_status_records on prospect_status_records.prospect_id = prospect.id
        where client_id = :client_id
            and prospect_status_records.created_at > NOW() - '365 days'::INTERVAL
            and prospect_status_records.to_status = 'SENT_OUTREACH'
        group by 1
        order by 1 asc;
    """
    result = db.session.execute(query, {"client_id": client_id}).fetchall()
    steps = []
    for id, step in result:
        step = {"date": id, "value": step}
        steps.append(step)

    return {"data": steps, "color": "blue"}


def get_enriched_prospect(client_id: int):
    query = f"""
        select 
            to_char(prospect.created_at, 'YYYY-MM'),
            count(distinct prospect.id)
        from prospect
            join research_payload on research_payload.prospect_id = prospect.id
        where client_id = :client_id
            and prospect.created_at > NOW() - '365 days'::INTERVAL
        group by 1
        order by 1 asc;
    """
    result = db.session.execute(query, {"client_id": client_id}).fetchall()
    steps = []
    for id, step in result:
        step = {"date": id, "value": step}
        steps.append(step)
    return {"data": steps, "color": "pink"}


def get_followupsent_prospect(client_id: int):
    query = f"""
        select 
            to_char(prospect_status_records.created_at, 'YYYY-MM'),
            count(distinct prospect.id)
        from prospect
            left join prospect_status_records on prospect_status_records.prospect_id = prospect.id
        where client_id = :client_id
            and prospect_status_records.created_at > NOW() - '365 days'::INTERVAL
            and prospect_status_records.to_status = 'RESPONDED'
        group by 1
        order by 1 asc;
    """
    result = db.session.execute(query, {"client_id": client_id}).fetchall()
    steps = []
    for id, step in result:
        step = {"date": id, "value": step}
        steps.append(step)

    return {"data": steps, "color": "orange"}


def get_replies_prospect(client_id: int):
    query = f"""
        select 
            to_char(prospect_status_records.created_at, 'YYYY-MM'),
            count(distinct prospect.id)
        from prospect
            left join prospect_status_records on prospect_status_records.prospect_id = prospect.id
        where client_id = :client_id
            and prospect_status_records.created_at > NOW() - '365 days'::INTERVAL
            and prospect_status_records.to_status = 'ACTIVE_CONVO'
        group by 1
        order by 1 asc;
    """
    result = db.session.execute(query, {"client_id": client_id}).fetchall()
    steps = []
    for id, step in result:
        step = {"date": id, "value": step}
        steps.append(step)

    return {"data": steps, "color": "yellow"}


def get_nurture_prospect(client_id: int):
    query = f"""
       select 
            to_char(prospect_status_records.created_at, 'YYYY-MM'),
            count(distinct prospect.id)
        from prospect
            left join prospect_status_records on prospect_status_records.prospect_id = prospect.id
        where client_id = :client_id
            and prospect_status_records.created_at > NOW() - '365 days'::INTERVAL
            and prospect_status_records.to_status = 'NOT_INTERESTED'
        group by 1
        order by 1 asc;
    """
    result = db.session.execute(query, {"client_id": client_id}).fetchall()
    steps = []
    for id, step in result:
        step = {"date": id, "value": step}
        steps.append(step)

    return {"data": steps, "color": "red"}


def get_removed_prospect(client_id: int):
    query = f"""
       select 
            to_char(prospect_status_records.created_at, 'YYYY-MM'),
            count(distinct prospect.id)
        from prospect
            left join prospect_status_records on prospect_status_records.prospect_id = prospect.id
        where client_id = :client_id
            and prospect_status_records.created_at > NOW() - '365 days'::INTERVAL
            and prospect_status_records.to_status = 'NOT_QUALIFIED'
        group by 1
        order by 1 asc;
    """
    result = db.session.execute(query, {"client_id": client_id}).fetchall()
    steps = []
    for id, step in result:
        step = {"date": id, "value": step}
        steps.append(step)

    return {"data": steps, "color": "green"}
