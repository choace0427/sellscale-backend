from app import db
from src.prospecting.models import Prospect, ProspectStatusRecords
from src.research.models import ResearchPayload
from typing import Optional
import json


def get_response_prospecting_service(client_id: int):
    query = f"""
        WITH combined_values AS (
            SELECT
                'linkedin' AS source,
                prospect.id AS prospect_id,
                rp.prospect_id AS enriched_prospect_id,
                CASE WHEN psr.to_status = 'SENT_OUTREACH' THEN psr.prospect_id ELSE NULL END AS outreach_sent_prospect_id,
                CASE WHEN psr.to_status = 'RESPONDED' THEN psr.prospect_id ELSE NULL END AS responded_prospect_id,
                CASE WHEN psr.to_status = 'NOT_INTERESTED' THEN psr.prospect_id ELSE NULL END AS snoozed_prospect_id,
                CASE WHEN psr.to_status = 'NOT_QUALIFIED' THEN psr.prospect_id ELSE NULL END AS removed_prospect_id,
                CASE WHEN psr.to_status = 'SENT_OUTREACH' AND psr.created_at > NOW() - INTERVAL '30 days' THEN prospect.id ELSE NULL END AS monthly_touchpoints_id
            FROM
                prospect
                LEFT JOIN research_payload rp ON rp.prospect_id = prospect.id
                LEFT JOIN prospect_status_records psr ON psr.prospect_id = prospect.id
            WHERE
                prospect.client_id = :client_id
            UNION ALL
            SELECT
                'email' AS source,
                prospect.id AS prospect_id,
                NULL AS enriched_prospect_id,
                CASE WHEN pesr.to_status = 'SENT_OUTREACH' THEN pesr.prospect_email_id ELSE NULL END AS outreach_sent_prospect_id,
                CASE WHEN pesr.to_status = 'BUMPED' THEN pesr.prospect_email_id ELSE NULL END AS responded_prospect_id,
                CASE WHEN pesr.to_status = 'NOT_INTERESTED' THEN pesr.prospect_email_id ELSE NULL END AS snoozed_prospect_id,
                CASE WHEN pesr.to_status = 'NOT_QUALIFIED' THEN pesr.prospect_email_id ELSE NULL END AS removed_prospect_id,
                CASE WHEN pesr.to_status = 'SENT_OUTREACH' AND pesr.created_at > NOW() - INTERVAL '30 days' THEN prospect.id ELSE NULL END AS monthly_touchpoints_id
            FROM
                prospect
                LEFT JOIN prospect_email pe ON pe.prospect_id = prospect.id
                LEFT JOIN prospect_email_status_records pesr ON pesr.prospect_email_id = pe.id
            WHERE
                prospect.client_id = :client_id
        )
        SELECT
            COUNT(DISTINCT prospect_id) AS prospect_created,
            COUNT(DISTINCT enriched_prospect_id) AS prospect_enriched,
            COUNT(DISTINCT outreach_sent_prospect_id) AS total_outreach_sent,
            COUNT(DISTINCT responded_prospect_id) AS ai_replies,
            COUNT(DISTINCT snoozed_prospect_id) AS prospects_snoozed,
            COUNT(DISTINCT removed_prospect_id) AS prospects_removed,
            COUNT(DISTINCT monthly_touchpoints_id) AS monthly_touchpoints_used
        FROM
            combined_values;
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
