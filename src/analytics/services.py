from app import db
from flask import jsonify

from src.client.models import *
from src.message_generation.models import *
from src.prospecting.models import *
from src.email_outbound.models import *

from datetime import datetime, timedelta
from sqlalchemy import and_, or_, not_


def get_weekly_client_sdr_outbound_goal_map():
    results = db.session.execute(
        """
        select client_sdr.client_id, sum(client_sdr.weekly_li_outbound_target) from client_sdr group by 1;
    """
    ).fetchall()

    outbound_goal_map = {}
    for res in results:
        outbound_goal_map[res[0]] = res[1]

    return outbound_goal_map


def get_sdr_pipeline_all_details(
    client_sdr_id: int, include_purgatory: bool = False
) -> dict:
    """Gets a holistic view of ProspectStatus details for a given ClientSDR

    Args:
        client_sdr_id (int): The ClientSDR id

    Returns:
        dict: Returns a dict of ProspectStatus details for a given ClientSDR
    """
    all_pipeline_details = {}

    # Get LinkedIn Statuses
    li_statuses_count = {}
    for li_status in ProspectStatus.all_statuses():

        query = Prospect.query.filter(
            Prospect.client_sdr_id == client_sdr_id,
            Prospect.status == li_status,
        )
        if not include_purgatory:
            query = query.filter(
                or_(
                    Prospect.hidden_until == None,
                    not_(Prospect.hidden_until < datetime.utcnow()),
                )
            )
        else:
            query = query.filter(or_(Prospect.hidden_until >= datetime.utcnow()))

        li_statuses_count[li_status.value.lower()] = query.count()
    all_pipeline_details.update(li_statuses_count)  # TODO REMOVE THIS
    all_pipeline_details[ProspectChannels.LINKEDIN.value] = li_statuses_count

    # Get Overall Statuses
    overall_statuses_count = {}
    for overall_status in ProspectOverallStatus.all_statuses():
        query = Prospect.query.filter(
            Prospect.client_sdr_id == client_sdr_id,
            Prospect.overall_status == overall_status,
        )
        if not include_purgatory:
            query = query.filter(
                or_(
                    Prospect.hidden_until == None,
                    not_(Prospect.hidden_until < datetime.utcnow()),
                )
            )
        else:
            query = query.filter(or_(Prospect.hidden_until >= datetime.utcnow()))

        overall_statuses_count[overall_status.value] = query.count()
    all_pipeline_details[ProspectChannels.SELLSCALE.value] = overall_statuses_count

    # Get Email Statuses
    email_statuses_count = {}
    prospect_ids = [
        p.id
        for p in Prospect.query.filter(Prospect.client_sdr_id == client_sdr_id).all()
    ]
    for email_status in ProspectEmailOutreachStatus.all_statuses():
        email_statuses_count[email_status.value] = ProspectEmail.query.filter(
            ProspectEmail.prospect_id.in_(prospect_ids),
            ProspectEmail.outreach_status == email_status,
        ).count()
    all_pipeline_details[ProspectChannels.EMAIL.value] = email_statuses_count

    return all_pipeline_details
