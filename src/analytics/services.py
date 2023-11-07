from src.analytics.models import FeatureFlag
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
                    not_(Prospect.hidden_until > datetime.utcnow()),
                )
            )
        else:
            query = query.filter(Prospect.hidden_until > datetime.utcnow())

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
                    not_(Prospect.hidden_until > datetime.utcnow()),
                )
            )
        else:
            query = query.filter(Prospect.hidden_until > datetime.utcnow())

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


def flag_enabled(feature: str) -> bool:
    """Checks if a feature is enabled

    Args:
        feature (str): The feature to check

    Returns:
        bool: Returns True if the feature is enabled, False otherwise
    """
    feature: FeatureFlag = FeatureFlag.query.filter(
        FeatureFlag.feature == feature
    ).first()
    if feature:
        return feature.value == 1
    return False


def flag_is_value(feature: str, value: int) -> bool:
    """Checks if a feature has a specific value

    Args:
        feature (str): The feature to check

    Returns:
        bool: Returns True if the feature has the value, False otherwise
    """
    feature: FeatureFlag = FeatureFlag.query.filter(
        FeatureFlag.feature == feature
    ).first()
    if feature:
        return feature.value == value
    return False


def get_all_campaign_analytics_for_client(client_id: int):
    query = """
        with d as (
            select 
                client_archetype.emoji,
                client_archetype.archetype,
                client_archetype.active,
                client_archetype.persona_fit_reason,
                client_sdr.auth_token,
                count(distinct prospect.id) filter (
                    where prospect_status_records.to_status = 'SENT_OUTREACH' or 
                        prospect_email_status_records.to_status = 'SENT_OUTREACH'
                ) num_sent,
                count(distinct prospect.id) filter (
                    where prospect_status_records.to_status = 'ACCEPTED' or 
                        prospect_email_status_records.to_status = 'EMAIL_OPENED'
                ) num_opens,
                count(distinct prospect.id) filter (
                    where prospect_status_records.to_status = 'ACTIVE_CONVO' or 
                        prospect_email_status_records.to_status = 'ACTIVE_CONVO'
                ) num_replies,
                count(distinct prospect.id) filter (
                    where prospect_status_records.to_status = 'DEMO_SET' or
                        prospect_email_status_records.to_status = 'DEMO_SET'
                ) num_demos,
                client_sdr.name,
                client_sdr.img_url,
                icp_scoring_ruleset.included_individual_title_keywords,
                icp_scoring_ruleset.included_individual_locations_keywords,
                icp_scoring_ruleset.included_individual_industry_keywords,
                icp_scoring_ruleset.included_individual_generalized_keywords,
                icp_scoring_ruleset.included_individual_skills_keywords,
                icp_scoring_ruleset.included_company_name_keywords,
                icp_scoring_ruleset.included_company_locations_keywords,
                icp_scoring_ruleset.included_company_generalized_keywords,
                icp_scoring_ruleset.included_company_industries_keywords,
                icp_scoring_ruleset.company_size_start,
                icp_scoring_ruleset.company_size_end
            from client_archetype
                join client_sdr on client_sdr.id = client_archetype.client_sdr_id
                join prospect on prospect.client_sdr_id = client_sdr.id
                left join prospect_status_records on prospect_status_records.prospect_id = prospect.id
                left join prospect_email on prospect_email.prospect_id = prospect.id
                left join prospect_email_status_records on prospect_email_status_records.prospect_email_id = prospect_email.id
                left join icp_scoring_ruleset on icp_scoring_ruleset.client_archetype_id = client_archetype.id
            where client_archetype.client_id = {client_id}
                and not client_archetype.is_unassigned_contact_archetype
            group by 1,2,3,4,5, client_archetype.updated_at, client_sdr.name, client_sdr.img_url, icp_scoring_ruleset.included_individual_title_keywords, icp_scoring_ruleset.included_individual_locations_keywords, icp_scoring_ruleset.included_individual_industry_keywords, icp_scoring_ruleset.included_company_name_keywords, icp_scoring_ruleset.included_company_locations_keywords, icp_scoring_ruleset.included_individual_generalized_keywords, icp_scoring_ruleset.included_individual_skills_keywords, icp_scoring_ruleset.included_company_generalized_keywords,icp_scoring_ruleset.included_company_industries_keywords, icp_scoring_ruleset.company_size_start, icp_scoring_ruleset.company_size_end
            order by client_archetype.updated_at desc
        )
        select 
            *,
            100 "sent_percent",
            num_opens / (0.0001 + cast(num_sent as float)) "open_percent",
            num_replies / (0.0001 + cast(num_sent as float)) "num_replies",
            num_demos / (0.0001 + cast(num_sent as float)) "num_demos"
        from d;
    """.format(
        client_id=client_id
    )

    data = db.session.execute(query).fetchall()

    data_arr = []
    for row in data:
        data_arr.append(
            {
                "emoji": row[0],
                "archetype": row[1],
                "active": row[2],
                "persona_fit_reason": row[3],
                "auth_token": row[4],
                "num_sent": row[5],
                "num_opens": row[6],
                "num_replies": row[7],
                "num_demos": row[8],
                "name": row[9],
                "img_url": row[10],
                "included_individual_title_keywords": row[11],
                "included_individual_locations_keywords": row[12],
                "included_individual_industry_keywords": row[13],
                "included_individual_generalized_keywords": row[14],
                "included_individual_skills_keywords": row[15],
                "included_company_name_keywords": row[16],
                "included_company_locations_keywords": row[17],
                "included_company_generalized_keywords": row[18],
                "included_company_industries_keywords": row[19],
                "company_size_start": row[20],
                "company_size_end": row[21],
                "sent_percent": row[22],
                "open_percent": row[23],
                "reply_percent": row[24],
                "demo_percent": row[25],
            }
        )

    return data_arr


def get_outreach_over_time(
    client_id: int,
    num_days: int = 365,
):
    query = """
        select 
            to_char(prospect_status_records.created_at, 'YYYY-MM-DD'),
            count(distinct prospect.id) filter (
                where prospect_status_records.to_status = 'SENT_OUTREACH' or 
                    prospect_email_status_records.to_status = 'SENT_OUTREACH'
            ) sent_outreach,
            count(distinct prospect.id) filter (
                where prospect_status_records.to_status = 'ACCEPTED' or 
                    prospect_email_status_records.to_status = 'EMAIL_OPENED'
            ) opened,
            count(distinct prospect.id) filter (
                where prospect_status_records.to_status = 'ACTIVE_CONVO' or 
                    prospect_email_status_records.to_status = 'ACTIVE_CONVO'
            ) active_convo,
            count(distinct prospect.id) filter (
                where prospect_status_records.to_status = 'DEMO_SET' or
                    prospect_email_status_records.to_status = 'DEMO_SET'
            ) demo_set
        from client_archetype
            join client_sdr on client_sdr.id = client_archetype.client_sdr_id
            join prospect on prospect.client_sdr_id = client_sdr.id
            left join prospect_status_records on prospect_status_records.prospect_id = prospect.id
            left join prospect_email on prospect_email.prospect_id = prospect.id
            left join prospect_email_status_records on prospect_email_status_records.prospect_email_id = prospect_email.id
        where prospect_status_records.created_at > NOW() - '{days} days'::INTERVAL
            and prospect.client_id = {client_id}
        group by 1
        order by 1 asc;
    """.format(
        client_id=client_id, days=num_days
    )

    data = db.session.execute(query).fetchall()

    dates = []
    sent_outreach = []
    opened = []
    active_convo = []
    demos = []

    for row in data:
        dates.append(row[0])
        sent_outreach.append(row[1])
        opened.append(row[2])
        active_convo.append(row[3])
        demos.append(row[4])

    modes = {
        "week": {
            "labels": dates[len(dates) - 7 :],
            "data": {
                # get last 7
                "outbound": sent_outreach[len(sent_outreach) - 7 :],
                "acceptances": opened[len(opened) - 7 :],
                "replies": active_convo[len(active_convo) - 7 :],
                "demos": demos[len(demos) - 7 :],
            },
        },
        "month": {
            "labels": dates[len(dates) - 30 :],
            "data": {
                "outbound": sent_outreach[len(sent_outreach) - 30 :],
                "acceptances": opened[len(opened) - 30 :],
                "replies": active_convo[len(active_convo) - 30 :],
                "demos": demos[len(demos) - 30 :],
            },
        },
        "year": {
            "labels": dates,
            "data": {
                "outbound": sent_outreach,
                "acceptances": opened,
                "replies": active_convo,
                "demos": demos,
            },
        },
    }

    return modes

def get_all_campaign_analytics_for_client_campaigns_page(client_id: int):
    query = """
        select 
            concat(client_archetype.emoji, ' ', client_archetype.archetype) "Campaign",
            client_sdr.name "Account",
            count(distinct prospect.id) "Sourced",
            round(100 * cast(count(distinct prospect.id) filter (where (
                prospect_email_status_records.to_status = 'SENT_OUTREACH' or 
                prospect_status_records.to_status = 'SENT_OUTREACH'
            )) as float) / (count(distinct prospect.id) + 0.001)) "Contacted%",
            round(100 * cast(count(distinct prospect.id) filter (where (
                prospect_email_status_records.to_status = 'EMAIL_OPENED' or 
                prospect_status_records.to_status = 'ACCEPTED'
            )) as float) / (count(distinct prospect.id) + 0.001)) "Open%",
            round(100 * cast(count(distinct prospect.id) filter (where (
                prospect_email_status_records.to_status = 'ACTIVE_CONVO' or 
                prospect_status_records.to_status = 'ACTIVE_CONVO'
            )) as float) / (count(distinct prospect.id) + 0.001)) "Reply%",
            count(distinct prospect.id) filter (where (
                prospect_email_status_records.to_status = 'DEMO_SET' or 
                prospect_status_records.to_status = 'DEMO_SET'
            )) "Demo Set",
            case 
                when 
                    count(distinct prospect.id) filter (where (
                        prospect_email_status_records.to_status = 'SENT_OUTREACH' or 
                        prospect_status_records.to_status = 'SENT_OUTREACH'
                    )) < 10
                    and client_archetype.active = False
                    then 'Setup'
                when 
                    count(distinct prospect.id) filter (where (
                        prospect_email_status_records.to_status = 'SENT_OUTREACH' or 
                        prospect_status_records.to_status = 'SENT_OUTREACH'
                    )) >= 10 
                    and client_archetype.active = False
                    then 'Complete'
                else
                    'Active'
            end "Status",
            client_sdr.img_url "img_url",
            array_agg(distinct generated_message.message_type) filter (where generated_message.message_type is not null) "Channel"
        from 
            client_archetype
            join prospect on prospect.archetype_id = client_archetype.id
            join client_sdr on client_sdr.id = client_archetype.client_sdr_id
            left join prospect_status_records on prospect_status_records.prospect_id = prospect.id
            left join prospect_email on prospect_email.id = prospect.approved_prospect_email_id
            left join prospect_email_status_records on prospect_email_status_records.prospect_email_id = prospect_email.id
            left join generated_message on generated_message.prospect_id = prospect.id and generated_message.message_status = 'SENT'
        where client_archetype.client_id = {client_id}
        group by 1,2, client_archetype.active, client_sdr.img_url
    """.format(
        client_id=client_id
    )

    data = db.session.execute(query).fetchall()

    data_arr = []
    for row in data:
        data_arr.append(
            {
                "campaign": row[0],
                "account": row[1],
                "sourced": row[2],
                "contacted": row[3],
                "open": row[4],
                "reply": row[5],
                "demo_set": row[6],
                "status": row[7],
                "img_url": row[8],
                "channel": row[9]
            }
        )

    return data_arr