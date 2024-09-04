from src.analytics.models import ActivityLog, FeatureFlag, RetentionActivityLogs
from app import db
from flask import jsonify
from src.campaigns.models import OutboundCampaign

from src.client.models import *
from src.message_generation.models import *
from src.prospecting.models import *
from src.email_outbound.models import *

from datetime import datetime, timedelta
from sqlalchemy import and_, or_, not_, func, distinct

from src.sockets.services import send_socket_message


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


def get_all_campaign_analytics_for_client(
    client_id: int, client_archetype_id: Optional[int] = None, start_date: Optional[str] = None, end_date: Optional[str] = None, verbose: bool = False, room_id: Optional[int] = None
):
    date_filter = ""
    if start_date and end_date:
        date_filter = f"and (prospect_status_records.created_at between '{start_date} 00:00:00' and '{end_date} 23:59:59' or prospect_email_status_records.created_at between '{start_date} 00:00:00' and '{end_date} 23:59:59')"

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
                        cast(prospect_email_status_records.to_status as varchar) ilike '%ACTIVE_CONVO_%'
                ) num_replies,
                count (distinct prospect.id) filter (
                    where prospect_status_records.to_status in ('ACTIVE_CONVO_SCHEDULING', 'ACTIVE_CONVO_QUESTION', 'ACTIVE_CONVO_NEXT_STEPS') or
                        prospect_email_status_records.to_status = 'DEMO_SET'
                ) positive_reply,
                count(distinct prospect.id) filter (
                    where prospect_status_records.to_status = 'DEMO_SET' or
                        prospect_email_status_records.to_status = 'DEMO_SET'
                ) num_demos,
                client_sdr.name,
                client_sdr.img_url,
                icp_scoring_ruleset.included_individual_title_keywords,
                icp_scoring_ruleset.included_individual_seniority_keywords,
                icp_scoring_ruleset.included_individual_locations_keywords,
                icp_scoring_ruleset.included_individual_industry_keywords,
                icp_scoring_ruleset.included_individual_generalized_keywords,
                icp_scoring_ruleset.included_individual_skills_keywords,
                icp_scoring_ruleset.included_company_name_keywords,
                icp_scoring_ruleset.included_company_locations_keywords,
                icp_scoring_ruleset.included_company_generalized_keywords,
                icp_scoring_ruleset.included_company_industries_keywords,
                icp_scoring_ruleset.company_size_start,
                icp_scoring_ruleset.company_size_end,
                client_archetype.id as id
            from client_archetype
                join client_sdr on client_sdr.id = client_archetype.client_sdr_id
                join prospect on prospect.client_sdr_id = client_sdr.id
                left join prospect_status_records on prospect_status_records.prospect_id = prospect.id and prospect_status_records.created_at > client_archetype.created_at
                left join prospect_email on prospect_email.id = prospect.approved_prospect_email_id
                left join prospect_email_status_records on prospect_email_status_records.prospect_email_id = prospect_email.id and prospect_email_status_records.created_at > client_archetype.created_at
                left join icp_scoring_ruleset on icp_scoring_ruleset.client_archetype_id = client_archetype.id
            where client_archetype.client_id = {client_id}
                and not client_archetype.is_unassigned_contact_archetype
                {client_archetype_id_filter}
                {date_filter}
            group by 1,2,3,4,5, client_archetype.updated_at, client_sdr.name, client_sdr.img_url, icp_scoring_ruleset.included_individual_title_keywords, icp_scoring_ruleset.included_individual_locations_keywords, icp_scoring_ruleset.included_individual_industry_keywords, icp_scoring_ruleset.included_company_name_keywords, icp_scoring_ruleset.included_company_locations_keywords, icp_scoring_ruleset.included_individual_generalized_keywords, icp_scoring_ruleset.included_individual_skills_keywords, icp_scoring_ruleset.included_company_generalized_keywords,icp_scoring_ruleset.included_company_industries_keywords, icp_scoring_ruleset.company_size_start, icp_scoring_ruleset.company_size_end, client_archetype.id, icp_scoring_ruleset.included_individual_seniority_keywords
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
        client_id=client_id,
        client_archetype_id_filter=(
            "and prospect.archetype_id = {} and client_archetype.id = {}".format(
                client_archetype_id,
                client_archetype_id,
            )
            if client_archetype_id
            else ""
        ),
        date_filter=date_filter
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
                "num_pos_replies": row[8],
                "num_demos": row[9],
                "name": row[10],
                "img_url": row[11],
                "included_individual_title_keywords": row[12],
                "included_individual_seniority_keywords": row[13],
                "included_individual_locations_keywords": row[14],
                "included_individual_industry_keywords": row[15],
                "included_individual_generalized_keywords": row[16],
                "included_individual_skills_keywords": row[17],
                "included_company_name_keywords": row[18],
                "included_company_locations_keywords": row[19],
                "included_company_generalized_keywords": row[20],
                "included_company_industries_keywords": row[21],
                "company_size_start": row[22],
                "company_size_end": row[23],
                "sent_percent": row[24],
                "open_percent": row[25],
                "reply_percent": row[26],
                "demo_percent": row[27],
                "id": client_archetype_id,
            }
        )

    if verbose and start_date and end_date:
        if room_id:
            print("Sending socket message")
            send_socket_message('+1', {"message": "+1", "room_id": room_id}, room_id)
        
        verbose_query = f"""
            with d as (
                select 
                    case 
                        when prospect_status_records.created_at is not null then to_char(prospect_status_records.created_at, 'YYYY-MM-DD')
                        when prospect_email_status_records.created_at is not null then to_char(prospect_email_status_records.created_at, 'YYYY-MM-DD')
                    end date,
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
                            cast(prospect_email_status_records.to_status as varchar) ilike '%ACTIVE_CONVO_%'
                    ) num_replies,
                    count (distinct prospect.id) filter (
                        where prospect_status_records.to_status in ('ACTIVE_CONVO_SCHEDULING', 'ACTIVE_CONVO_QUESTION', 'ACTIVE_CONVO_NEXT_STEPS') or
                            prospect_email_status_records.to_status = 'DEMO_SET'
                    ) positive_reply,
                    count(distinct prospect.id) filter (
                        where prospect_status_records.to_status = 'DEMO_SET' or
                            prospect_email_status_records.to_status = 'DEMO_SET'
                    ) num_demos,
                    array_agg (
                        concat(prospect.id, '###', prospect.full_name, '###', prospect_status_records.to_status, '###', case
                            when prospect.li_last_message_from_prospect is not null then prospect.li_last_message_from_prospect
                            when prospect.email_last_message_from_prospect is not null then prospect.email_last_message_from_prospect
                            else ''
                        end)
                    ) filter (
                        where prospect_status_records.to_status in ('ACTIVE_CONVO_SCHEDULING', 'ACTIVE_CONVO_QUESTION', 'ACTIVE_CONVO_NEXT_STEPS') or
                            prospect_email_status_records.to_status = 'DEMO_SET'
                    ) positive_reply_details,
                    array_agg(distinct client_archetype.id)
                from client_archetype
                    join client_sdr on client_sdr.id = client_archetype.client_sdr_id
                    join prospect on prospect.archetype_id = client_archetype.id
                    left join prospect_status_records on prospect_status_records.prospect_id = prospect.id
                    left join prospect_email on prospect_email.id = prospect.approved_prospect_email_id
                    left join prospect_email_status_records on prospect_email_status_records.prospect_email_id = prospect_email.id
                where client_archetype.id = {client_archetype_id}
                group by 1
                order by 1 desc
            )
            select 
                *
            from d;
        """


        top_icp_query = f"""
            select 
                prospect.id,
                prospect.full_name,
                prospect.icp_fit_score,
                prospect_status_records.created_at as status_created_at,
                prospect_email_status_records.created_at as email_status_created_at,
                prospect.company,
                prospect.title
            from prospect
                left join prospect_status_records on prospect_status_records.prospect_id = prospect.id
                left join prospect_email on prospect_email.prospect_id = prospect.id
                left join prospect_email_status_records on prospect_email_status_records.prospect_email_id = prospect_email.id    
            where prospect.icp_fit_score is not null
                and prospect.archetype_id = {client_archetype_id}
                and prospect.overall_status not in ('REMOVED')
            order by prospect.icp_fit_score desc
            limit 5;
        """
        top_icp_people = db.session.execute(top_icp_query).fetchall()
        top_icp_people_list = [
            {
                "id": row[0],
                "full_name": row[1],
                "icp_fit_score": row[2],
                "status_created_at": row[3],
                "email_status_created_at": row[4],
                "company": row[5],
                "title": row[6]
            } 
            for row in top_icp_people
        ]

        verbose_data = db.session.execute(verbose_query).fetchall()
        verbose_data_arr = []
        for row in verbose_data:
            start_date_obj = datetime.strptime(start_date, '%Y-%m-%d') if isinstance(start_date, str) else start_date
            end_date_obj = datetime.strptime(end_date, '%Y-%m-%d') if isinstance(end_date, str) else end_date
            row_date_obj = datetime.strptime(row[0], '%Y-%m-%d') if isinstance(row[0], str) else row[0]

            if start_date_obj and end_date_obj and row_date_obj and start_date_obj <= row_date_obj <= end_date_obj:
                verbose_data_arr.append(
                    {
                        "date": row[0],
                        "num_sent": row[1],
                        "num_opens": row[2],
                        "num_replies": row[3],
                        "num_pos_replies": row[4],
                        "num_demos": row[5],
                        "positive_reply_details": row[6]  # Ensure positive replies come in as an array
                    }
                )
        
        # Filter top_icp_people_list based on start_date and end_date
        filtered_top_icp_people_list = []
        for person in top_icp_people_list:
            status_date_obj = person['status_created_at'] if isinstance(person['status_created_at'], datetime) else datetime.strptime(person['status_created_at'], '%Y-%m-%d') if person['status_created_at'] else None
            email_status_date_obj = person['email_status_created_at'] if isinstance(person['email_status_created_at'], datetime) else datetime.strptime(person['email_status_created_at'], '%Y-%m-%d') if person['email_status_created_at'] else None

            if start_date_obj and end_date_obj:
                if (status_date_obj and start_date_obj <= status_date_obj <= end_date_obj) or (email_status_date_obj and start_date_obj <= email_status_date_obj <= end_date_obj):
                    filtered_top_icp_people_list.append(person)

        return {"summary": data_arr, "daily": verbose_data_arr, "top_icp_people": filtered_top_icp_people_list}

    return data_arr
def get_outreach_over_time(
    client_id: int,
    num_days: int = 365,
):
    query = """
        select 
            case 
                when prospect_status_records.created_at is not null 
                    then to_char(prospect_status_records.created_at, 'YYYY-MM-DD')
                when prospect_email_status_records.created_at is not null
                    then to_char(prospect_email_status_records.created_at, 'YYYY-MM-DD')
            end date,
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
                    cast(prospect_email_status_records.to_status as varchar) ilike '%ACTIVE_CONVO_%'
            ) active_convo,
            count(distinct prospect.id) filter (
                where prospect_status_records.to_status in ('ACTIVE_CONVO_SCHEDULING', 'ACTIVE_CONVO_QUESTION', 'ACTIVE_CONVO_NEXT_STEPS') or
                    prospect_email_status_records.to_status = 'DEMO_SET'
            ) positive_reply,
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
        where (
                prospect_status_records.created_at > NOW() - '{days} days'::INTERVAL
                or 
                prospect_email_status_records.created_at > NOW() - '{days} days'::INTERVAL
            )
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
    positive_reply = []
    demos = []

    for row in data:
        dates.append(row[0])
        sent_outreach.append(row[1])
        opened.append(row[2])
        active_convo.append(row[3])
        positive_reply.append(row[4])
        demos.append(row[5])

    modes = {
        "week": {
            "labels": dates[len(dates) - 7 :],
            "data": {
                # get last 7
                "outbound": sent_outreach[len(sent_outreach) - 7 :],
                "acceptances": opened[len(opened) - 7 :],
                "replies": active_convo[len(active_convo) - 7 :],
                "positive_replies": positive_reply[len(positive_reply) - 7 :],
                "demos": demos[len(demos) - 7 :],
            },
        },
        "month": {
            "labels": dates[len(dates) - 30 :],
            "data": {
                "outbound": sent_outreach[len(sent_outreach) - 30 :],
                "acceptances": opened[len(opened) - 30 :],
                "replies": active_convo[len(active_convo) - 30 :],
                "positive_replies": positive_reply[len(positive_reply) - 30 :],
                "demos": demos[len(demos) - 30 :],
            },
        },
        "year": {
            "labels": dates,
            "data": {
                "outbound": sent_outreach,
                "acceptances": opened,
                "replies": active_convo,
                "positive_replies": positive_reply,
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
                "channel": row[9],
            }
        )

    return data_arr


def get_upload_analytics_for_client(client_id):
    # Initialize response dictionary
    analytics = {
        "top_line_scraped": 0,
        "top_line_uploaded": 0,
        "top_line_scored": 0,
        "contacts_over_time": [],
        "uploads": [],
    }

    # Query for analytics
    prospects = Prospect.query.filter_by(client_id=client_id).all()
    archetypes = ClientArchetype.query.filter_by(client_id=client_id).all()

    # Count top line metrics
    analytics["top_line_scraped"] = len(prospects)
    analytics["top_line_uploaded"] = len(prospects)  # Assuming scraped equals uploaded
    analytics["top_line_scored"] = len(
        [p for p in prospects if p.icp_fit_score is not None and p.icp_fit_score >= 0]
    )

    # Contacts over time (cumulative)
    start_date = min(
        [p.created_at.date() for p in prospects if p.created_at],
        default=datetime.now().date(),
    )
    end_date = datetime.now().date()
    week = timedelta(days=7)
    cumulative_count = 0

    while start_date <= end_date:
        week_end = start_date + week
        count = len(
            [
                p
                for p in prospects
                if p.created_at and start_date <= p.created_at.date() < week_end
            ]
        )
        cumulative_count += count
        analytics["contacts_over_time"].append(
            {"x": start_date.strftime("%Y-%m-%d"), "y": cumulative_count}
        )
        start_date += week

    # Aggregate uploads by creation date
    for archetype in archetypes:
        archetype_prospects = [p for p in prospects if p.archetype_id == archetype.id]
        upload_dates = {
            p.created_at.date() for p in archetype_prospects if p.created_at
        }
        client_sdr: ClientSDR = ClientSDR.query.get(archetype.client_sdr_id)
        for upload_date in upload_dates:
            upload_data = {
                "upload name": archetype.emoji + " " + archetype.archetype,
                "account": client_sdr.name,
                "scraped": len(
                    [
                        p
                        for p in archetype_prospects
                        if p.created_at and p.created_at.date() == upload_date
                    ]
                ),
                "status": "Complete",  # Assuming all uploads are complete
                "upload date": upload_date.strftime("%Y-%m-%d"),
                "account_title": client_sdr.title,
                "account_img": client_sdr.img_url,
            }
            analytics["uploads"].append(upload_data)

    return analytics


def add_activity_log(client_sdr_id: int, type: str, name: str, description: str):
    """Adds an activity log for a given ClientSDR

    Args:
        client_sdr_id (int): The ClientSDR id
        type (str): The type of activity
        name (str): The name of the activity
        description (str): The description of the activity
    """
    activity_log = ActivityLog(
        client_sdr_id=client_sdr_id,
        type=type,
        name=name,
        description=description,
    )
    db.session.add(activity_log)
    db.session.commit()

    return activity_log.id


def get_activity_logs(client_sdr_id: int) -> list[dict]:
    """Gets all activity logs for a given ClientSDR

    Args:
        client_sdr_id (int): The ClientSDR id

    Returns:
        List[dict]: Returns a list of activity logs for a given ClientSDR
    """
    activity_logs: list[ActivityLog] = ActivityLog.query.filter(
        ActivityLog.client_sdr_id == client_sdr_id
    ).all()
    return [activity_log.to_dict() for activity_log in activity_logs]

def get_overview_pipeline_activity(client_sdr_id: int) -> dict:
    """
    Gets the following stats for the Client that the ClientSDR is associated with:
    - Opportunities created: # of opportunities created in the Client's CRM
    - Pipeline Generated: $ of pipeline generated in the Client's CRM
    - New Leads this Quarter: # of prospects added to the Client's CRM this quarter
    - Activities this Quarter: # of activities logged in the Client's CRM this quarter

    Args:
        client_sdr_id (int): _description_

    Returns:
        list[dict]: _description_
    """
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client_id = client_sdr.client_id

    opps_pipeline_leads_stats_query = """
        select 
            count(distinct prospect.id) filter (where prospect.merge_opportunity_id is not null) "num_opportunities_all_time",
            sum(prospect.contract_size) filter (where prospect.merge_opportunity_id is not null) "pipeline_generated_all_time",
            count(distinct prospect.id) filter (where prospect.created_at > NOW() - '3 month'::INTERVAL) "leads_created_last_3_month",
            count(distinct prospect.id) filter (where prospect.created_at > NOW() - '1 month'::INTERVAL) "leads_created_last_1_month"
        from prospect
        where prospect.client_id = {client_id};
    """

    distinct_activity_stats = """
    select 
        count(distinct prospect.id) filter (where 
            (prospect_status_records.to_status = 'SENT_OUTREACH' and prospect_status_records.created_at > NOW() - '3 month'::INTERVAL) or 
            (prospect_email_status_records.to_status = 'SENT_OUTREACH' and prospect_email_status_records.created_at > NOW() - '3 month'::INTERVAL)
        ) "activity_3_mon",
        count(distinct prospect.id) filter (where 
            (prospect_status_records.to_status = 'SENT_OUTREACH' and prospect_status_records.created_at > NOW() - '24 hours'::INTERVAL) or 
            (prospect_email_status_records.to_status = 'SENT_OUTREACH' and prospect_email_status_records.created_at > NOW() - '24 hours'::INTERVAL)
        ) "activity_1_day"
    from prospect
        left join prospect_status_records on prospect_status_records.prospect_id = prospect.id 
        left join prospect_email on prospect_email.prospect_id = prospect.id 
        left join prospect_email_status_records on prospect_email_status_records.prospect_email_id = prospect_email.id
    where prospect.client_id = {client_id};
    """

    opps_pipeline_leads_stats = db.session.execute(opps_pipeline_leads_stats_query.format(client_id=client_id)).fetchone()
    distinct_activity_stats = db.session.execute(distinct_activity_stats.format(client_id=client_id)).fetchone()

    return {
        "opportunities_created": opps_pipeline_leads_stats[0],
        "pipeline_generated": opps_pipeline_leads_stats[1],
        "leads_created_last_3_month": opps_pipeline_leads_stats[2],
        "leads_created_last_1_month": opps_pipeline_leads_stats[3],
        "activity_3_mon": distinct_activity_stats[0],
        "activity_1_day": distinct_activity_stats[1],
    }


def get_cycle_dates_for_campaign(client_sdr_id: int, campaign_id: Optional[int] = None) -> list[dict]:
    """
    Fetches the cycle dates for all outbound campaigns attached to the given campaign ID or client SDR ID.

    Args:
        client_sdr_id (int): The Client SDR ID.
        campaign_id (Optional[int]): The Campaign ID. If None, fetches campaigns for the client SDR ID.

    Returns:
        list[dict]: A list of dictionaries containing the start and end dates of the cycles.
    """
    from datetime import datetime, timedelta

    def get_monday(date):
        return date - timedelta(days=date.weekday()) if date.weekday() > 0 else date

    def get_sunday(date):
        return date + timedelta(days=(6 - date.weekday())) if date.weekday() < 6 else date

    if campaign_id is not None:
        client_archetype: ClientArchetype = ClientArchetype.query.filter_by(id=campaign_id).first()
        if not client_archetype:
            return []

        # Fetching all outbound campaigns attached to the given campaign ID
        outbound_campaigns: list[OutboundCampaign] = OutboundCampaign.query.filter_by(client_archetype_id=client_archetype.id).all()
        if not outbound_campaigns:
            return []
    else:
        # Fetching all outbound campaigns for the given client SDR ID
        outbound_campaigns: list[OutboundCampaign] = OutboundCampaign.query.join(ClientArchetype).filter(
            ClientArchetype.client_sdr_id == client_sdr_id
        ).all()
        if not outbound_campaigns:
            return []

    # Fetching cycle dates from all outbound campaigns
    cycle_dates = {}
    for outbound_campaign in outbound_campaigns:
        start_date = outbound_campaign.campaign_start_date + timedelta(days=1)
        end_date = outbound_campaign.campaign_end_date + timedelta(days=1)

        current_date = start_date
        while current_date <= end_date:
            monday = get_monday(current_date).date()
            sunday = get_sunday(current_date).date()

            date_tuple = (monday, sunday)
            if date_tuple not in cycle_dates:
                cycle_dates[date_tuple] = {"start": date_tuple[0].isoformat(), "end": date_tuple[1].isoformat()}

            current_date += timedelta(days=7)  # Move to the next week

    return sorted(cycle_dates.values(), key=lambda x: x['start'], reverse=True)

    # return sorted(cycle_dates, key=lambda x: x['start'], reverse=True)

#template analytics endpoint

def get_template_analytics_for_archetype(archetype_id: int, start_date: Optional[str] = None):
    from sqlalchemy import text
    from datetime import datetime

    if start_date is None:
        start_date = datetime.now().strftime('%Y-%m-%d')

    # CTA Analytics
    cta_analytics_query = text("""
        select 
            generated_message_cta.text_value,
            count(distinct prospect.id) filter (where prospect_status_records.to_status = 'SENT_OUTREACH') as num_sent,
            count(distinct prospect.id) filter (where prospect_status_records.to_status = 'ACCEPTED') as num_open,
            count(distinct prospect.id) filter (where prospect_status_records.to_status = 'ACTIVE_CONVO') as num_reply
        from prospect
            left join generated_message on generated_message.id = prospect.approved_outreach_message_id
            left join generated_message_cta on generated_message_cta.id = generated_message.message_cta
            left join prospect_status_records on prospect_status_records.prospect_id = prospect.id
        where prospect.icp_fit_score is not null and
            (
                prospect_status_records.created_at >= :start_date
            )
            and prospect.archetype_id = :archetype_id
            and generated_message_cta.text_value is not null
        group by generated_message_cta.text_value
        limit 5;
    """)
    print('params are', {'archetype_id': archetype_id, 'start_date': start_date})
    cta_analytics = db.session.execute(cta_analytics_query, {'archetype_id': archetype_id, 'start_date': start_date}).fetchall()

    print('cta_analytics', cta_analytics)

    # Linkedin Template Analytics
    linkedin_template_analytics_query = text("""
        select 
            linkedin_initial_message_template.message,
            count(distinct prospect.id) filter (where prospect_status_records.to_status = 'SENT_OUTREACH') as num_sent,
            count(distinct prospect.id) filter (where prospect_status_records.to_status = 'ACCEPTED') as num_open,
            count(distinct prospect.id) filter (where prospect_status_records.to_status = 'ACTIVE_CONVO') as num_reply
        from prospect
            left join generated_message on generated_message.id = prospect.approved_outreach_message_id
            left join linkedin_initial_message_template on linkedin_initial_message_template.id = generated_message.li_init_template_id
            left join prospect_status_records on prospect_status_records.prospect_id = prospect.id
        where 
            (
                prospect_status_records.created_at >= :start_date
            )
            and prospect.archetype_id = :archetype_id
            and linkedin_initial_message_template.message is not null
        group by linkedin_initial_message_template.message
        limit 5;
    """)
    linkedin_template_analytics = db.session.execute(linkedin_template_analytics_query, {'archetype_id': archetype_id, 'start_date': start_date}).fetchall()

    print('linkedin_template_analytics', linkedin_template_analytics)

    # Subject Lines
    subject_lines_analytics_query = text("""
        select 
            email_subject_line_template.subject_line,
            count(distinct prospect_email.prospect_id) filter (where prospect_email_status_records.to_status = 'SENT_OUTREACH') as num_sent,
            count(distinct prospect_email.prospect_id) filter (where prospect_email_status_records.to_status = 'EMAIL_OPENED') as num_open,
            count(distinct prospect_email.prospect_id) filter (where prospect_email_status_records.to_status = 'ACTIVE_CONVO') as num_reply
        from prospect
            left join prospect_email on prospect_email.prospect_id = prospect.id
            left join prospect_email_status_records on prospect_email_status_records.prospect_email_id = prospect_email.id
            left join generated_message on generated_message.id = prospect_email.personalized_subject_line
            left join email_subject_line_template on generated_message.email_subject_line_template_id = email_subject_line_template.id
        where 
            email_subject_line_template.subject_line is not null and
            (
                prospect_email_status_records.created_at >= :start_date
            )
            and prospect.archetype_id = :archetype_id
            and email_subject_line_template.subject_line is not null
        group by email_subject_line_template.subject_line
        limit 5;
    """)
    subject_lines_analytics = db.session.execute(subject_lines_analytics_query, {'archetype_id': archetype_id, 'start_date': start_date}).fetchall()

    print('subject_lines_analytics', subject_lines_analytics)

    # Email Templates
    email_templates_analytics_query = text("""
        select 
            email_sequence_step.title,
            count(distinct prospect_email.prospect_id) filter (where prospect_email_status_records.to_status = 'SENT_OUTREACH') as num_sent,
            count(distinct prospect_email.prospect_id) filter (where prospect_email_status_records.to_status = 'EMAIL_OPENED') as num_open,
            count(distinct prospect_email.prospect_id) filter (where prospect_email_status_records.to_status = 'ACTIVE_CONVO') as num_reply
        from prospect
            left join prospect_email on prospect_email.prospect_id = prospect.id
            left join prospect_email_status_records on prospect_email_status_records.prospect_email_id = prospect_email.id
            left join generated_message on generated_message.id = prospect_email.personalized_body
            left join email_sequence_step on email_sequence_step.id = generated_message.email_sequence_step_template_id
        where 
            email_sequence_step.title is not null and
            (
                prospect_email_status_records.created_at >= :start_date
            )
            and prospect.archetype_id = :archetype_id
        group by 1;
    """)
    email_templates_analytics = db.session.execute(email_templates_analytics_query, {'archetype_id': archetype_id, 'start_date': start_date}).fetchall()

    print('email_templates_analytics', email_templates_analytics)

    return {
        "cta_analytics": [dict(row) for row in cta_analytics],
        "linkedin_template_analytics": [dict(row) for row in linkedin_template_analytics],
        "subject_lines_analytics": [dict(row) for row in subject_lines_analytics],
        "email_templates_analytics": [dict(row) for row in email_templates_analytics]
    }

def process_cycle_data_and_generate_report(client_sdr_id: int, cycle_data: dict) -> dict:
    """
    Process the cycle data and generate a report using the LLM model.
    
    Args:
        client_sdr_id (int): The ID of the client SDR.
        cycle_data (dict): The cycle data to be processed.
    
    Returns:
        dict: The generated report.
    """
    from src.ml.openai_wrappers import wrapped_chat_gpt_completion
    import traceback
    import sys

    def print_error_with_line_number(e):
        exc_type, exc_value, exc_tb = sys.exc_info()
        tb = traceback.extract_tb(exc_tb)
        line_number = tb[-1].lineno
        print(f"Error: {e} at line {line_number}")

    try:
        # Extracting relevant data from cycle_data
        analytics_data = cycle_data.get("analyticsData", [])
        
        # Combining daily data and summary data into a narrative form
        compiled_data = []
        for item in analytics_data:
            summary = item.get("summary", [{}])
            summary = summary[0] if summary else {}
            campaign_id = summary.get("id", -1)
            if (campaign_id != -1):
                # Determine start and end dates based on daily data
                daily_data = item.get("daily", [])
                if daily_data:
                    start_date = min(d['date'] for d in daily_data)
                    end_date = max(d['date'] for d in daily_data)
                else:
                    start_date = None
                    end_date = None

                # Get one of the generated messages for the campaign
                outbound_campaign = None
                if start_date and end_date:
                    outbound_campaign = OutboundCampaign.query.filter(
                        OutboundCampaign.client_archetype_id == campaign_id,
                        OutboundCampaign.created_at.between(start_date, end_date)
                    ).order_by(OutboundCampaign.created_at.asc()).first()

                # the outbound campaign has an array prospect_ids which we can get some prospect information from
                prospect_ids = outbound_campaign.prospect_ids if outbound_campaign else []

                # get the prospects
                prospects: list[Prospect] = (
                    Prospect.query.filter(Prospect.id.in_(prospect_ids))
                    .order_by(Prospect.icp_fit_score.desc())
                    .limit(3)
                    .all()
                )
                prospect_blurbs = []
                for prospect in prospects:
                    blurb = (
                        f"Prospect Name: {prospect.full_name}, "
                        f"Title: {prospect.title}, "
                        f"Company: {prospect.company}, "
                    )
                    prospect_blurbs.append(blurb)
                prospect_blurbs_str = "\n".join(prospect_blurbs)

                generated_message_text = ""
                if outbound_campaign:
                    generated_message = GeneratedMessage.query.filter(
                        GeneratedMessage.outbound_campaign_id == outbound_campaign.id,
                        GeneratedMessage.completion.isnot(None),
                        GeneratedMessage.date_sent.between(start_date, end_date)
                    ).order_by(GeneratedMessage.date_sent.asc()).first()
                    generated_message_text = generated_message.completion if generated_message else ""
            archetype = summary.get("archetype")
            if not archetype:
                continue
            daily_data = item.get("daily", [])
            
            narrative = (
                f"Campaign '{archetype}':\n"
                f"Total messages sent: {sum(d['num_sent'] for d in daily_data)}\n"
                f"Total opens: {sum(d['num_opens'] for d in daily_data)}\n"
                f"Total replies: {sum(d['num_replies'] for d in daily_data)}\n"
                f"Total positive replies: {sum(d['num_pos_replies'] for d in daily_data)}\n"
                f"Prospect information:\n {prospect_blurbs_str}\n"
                f"Total demos: {sum(d['num_demos'] for d in daily_data)}\n"
                f"Sample outreach message from this campaign: {generated_message_text}\n"
                f"Daily breakdown:\n"
            )
            
            for daily in daily_data:
                narrative += (
                    f"  - Date: {daily.get('date')}, "
                    f"Sent: {daily.get('num_sent')}, "
                    f"Opens: {daily.get('num_opens')}, "
                    f"Replies: {daily.get('num_replies')}, "
                    f"Positive Replies: {daily.get('num_pos_replies')}, "
                    f"Demos: {daily.get('num_demos')}\n"
                )
            
            compiled_data.append(narrative.strip())

        
        compiled_data_str = "\n\n".join(compiled_data)

        compiled_data_str += '''\n\nThe report should be generated and organized in HTML format, use tables to illustrate as well. appropriately formatted 
        with various colors such as #BE4BDB (purple), and #A9E34B (green) to highlight table headers or footers. and tables. Text should be normal colors such as black or white depending on the background color.
        Make sure not to use global styling for the output as it may accidentally affect the overall design of the report.
        '''

        print('compiled_data_str', compiled_data_str)

        # Preparing the input for the LLM
        user_prompt = (
            f"Cycle Data Summary:\n"
            f"Summary Data: {compiled_data_str}\n"
        )

        system_prompt = '''You are a sales analytics expert delivering feedback for an array of different sales outreach campaigns that ran that week.
        You have access to the daily data and summary data for each campaign. Make sure to mention any insights based on the prospect information provided if applicable.
        Please generate a report detailing across all outreach campaigns:
        0. A 3-4 sentence general summary of everything, be specific about things.
        1. What went well -> in this section, even if nothing went well, try to find something that did. Do not mention anything that went poorly.
        2. What didn't go well
        3. Interesting/unusual learnings
        4. A hypothesis

        Please mention the name of the campaign when generating your research. Do not precede your response with any greetings, salutations, or introduction to the report.
        Make sure the report is detailed and points out specific campaigns by name.
        '''

        # Generating the report
        report_response = wrapped_chat_gpt_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=2500,
            model="gpt-4o"
        )

        report_response = report_response.replace('```html', '').replace('```', '').strip()

        # Returning the report as a dictionary
        result = {
            "report": report_response
        }
    except Exception as e:
        print_error_with_line_number(e)
        result = {"report": "An error occurred while generating the report."}

    return result

def update_retention_analytics():
    try:
        # Delete all activity
        print("Deleting all activity from retention_activity_logs")
        db.session.execute("DELETE FROM retention_activity_logs;")
        db.session.commit()
        
        # Add Selix Sessions to Activity
        print("Adding Selix Sessions to Activity")
        db.session.execute("""
            INSERT INTO retention_activity_logs (created_at, updated_at, client_sdr_id, client_id, activity_date, activity_tag)
            SELECT 
                NOW() created_at,
                NOW() updated_at,
                client_sdr.id AS client_sdr_id,
                client.id AS client_id,
                selix_session.created_at AS activity_date,
                'selix_session_created' AS activity_tag
            FROM
                client 
            JOIN client_sdr ON client.id = client_sdr.client_id
            JOIN selix_session on selix_session.client_sdr_id = client_sdr.id
            GROUP BY client_sdr.id, client.id, selix_session.id;
        """)
        db.session.commit()
        
        # Add Campaign Activated
        print("Adding Campaign Activated to Activity")
        db.session.execute("""
            INSERT INTO retention_activity_logs (created_at, updated_at, client_sdr_id, client_id, activity_date, activity_tag)
            SELECT 
                NOW() created_at,
                NOW() updated_at,
                client_sdr.id AS client_sdr_id,
                client.id AS client_id,
                min(CASE 
                        WHEN prospect_status_records.created_at IS NOT NULL THEN prospect_status_records.created_at 
                        ELSE prospect_email_status_records.created_at 
                    END) AS activity_date,
                'campaign_activated' AS activity_tag
            FROM
                client 
            JOIN client_sdr ON client.id = client_sdr.client_id
            JOIN client_archetype ON client_archetype.client_sdr_id = client_sdr.id
            JOIN prospect ON prospect.archetype_id = client_archetype.id
            LEFT JOIN prospect_status_records ON prospect_status_records.prospect_id = prospect.id 
            LEFT JOIN prospect_email ON prospect_email.prospect_id = prospect.id
            LEFT JOIN prospect_email_status_records ON prospect_email_status_records.prospect_email_id = prospect_email.id
            WHERE
                prospect_email_status_records.to_status = 'SENT_OUTREACH' 
                OR prospect_status_records.to_status = 'SENT_OUTREACH'
            GROUP BY client_sdr.id, client.id, client_archetype.id;
        """)
        db.session.commit()
        
        # Add Demo Sets
        print("Adding Demo Sets to Activity")
        db.session.execute("""
            INSERT INTO retention_activity_logs (created_at, updated_at, client_sdr_id, client_id, activity_date, activity_tag)
            SELECT 
                NOW() created_at,
                NOW() updated_at,
                client_sdr.id AS client_sdr_id,
                client.id AS client_id,
                min(CASE 
                        WHEN prospect_status_records.created_at IS NOT NULL THEN prospect_status_records.created_at 
                        ELSE prospect_email_status_records.created_at 
                    END) filter (
                        where prospect_status_records.to_status = 'DEMO_SET' or prospect_email_status_records.to_status = 'DEMO_SET'
                    ) AS activity_date,
                concat('demo_set_detected_', prospect.id) AS activity_tag
            FROM
                client 
            JOIN client_sdr ON client.id = client_sdr.client_id
            JOIN client_archetype ON client_archetype.client_sdr_id = client_sdr.id
            JOIN prospect ON prospect.archetype_id = client_archetype.id
            LEFT JOIN prospect_status_records ON prospect_status_records.prospect_id = prospect.id 
            LEFT JOIN prospect_email ON prospect_email.prospect_id = prospect.id
            LEFT JOIN prospect_email_status_records ON prospect_email_status_records.prospect_email_id = prospect_email.id
            WHERE
                prospect_email_status_records.to_status = 'DEMO_SET' 
                OR prospect_status_records.to_status = 'DEMO_SET'
            GROUP BY client_sdr.id, client.id, prospect.id;
        """)
        db.session.commit()
        
        # Add Active Convo (Positive response)
        print("Adding Active Convo (Positive response) to Activity")
        db.session.execute("""
            INSERT INTO retention_activity_logs (created_at, updated_at, client_sdr_id, client_id, activity_date, activity_tag)
            SELECT 
                NOW() created_at,
                NOW() updated_at,
                client_sdr.id AS client_sdr_id,
                client.id AS client_id,
                min(CASE 
                        WHEN prospect_status_records.created_at IS NOT NULL THEN prospect_status_records.created_at 
                        ELSE prospect_email_status_records.created_at 
                    END) filter (
                        where prospect_status_records.to_status in ('ACTIVE_CONVO_SCHEDULING', 'ACTIVE_CONVO_QUESTION', 'ACTIVE_CONVO_NEXT_STEPS') or prospect_email_status_records.to_status in ('ACTIVE_CONVO_SCHEDULING', 'ACTIVE_CONVO_QUESTION', 'ACTIVE_CONVO_NEXT_STEPS')
                    ) AS activity_date,
                concat('positive_response_detected_', prospect.id) AS activity_tag
            FROM
                client 
            JOIN client_sdr ON client.id = client_sdr.client_id
            JOIN client_archetype ON client_archetype.client_sdr_id = client_sdr.id
            JOIN prospect ON prospect.archetype_id = client_archetype.id
            LEFT JOIN prospect_status_records ON prospect_status_records.prospect_id = prospect.id 
            LEFT JOIN prospect_email ON prospect_email.prospect_id = prospect.id
            LEFT JOIN prospect_email_status_records ON prospect_email_status_records.prospect_email_id = prospect_email.id
            WHERE
                prospect_email_status_records.to_status in ('ACTIVE_CONVO_SCHEDULING', 'ACTIVE_CONVO_QUESTION', 'ACTIVE_CONVO_NEXT_STEPS') 
                OR prospect_status_records.to_status in ('ACTIVE_CONVO_SCHEDULING', 'ACTIVE_CONVO_QUESTION', 'ACTIVE_CONVO_NEXT_STEPS')
            GROUP BY client_sdr.id, client.id, prospect.id;
        """)
        db.session.commit()

        return True
    except Exception as e:
        print("An error occurred, rolling back the transaction")
        db.session.rollback()

        return False


def get_retention_analytics(units: str = "weeks" or "months", allowed_tags: list[str] = []):
    all_clients: list[Client] = Client.query.all()

    retention_data = []
    id_to_client_name_map = {}
    for client in all_clients:
        client_id = client.id
        client_name = client.company
        id_to_client_name_map[client_id] = client_name
        client_created_at = client.created_at

        if units == "weeks":
            logs = {
                (client_created_at + timedelta(weeks=i)).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=(client_created_at + timedelta(weeks=i)).weekday()): {
                    'count': 0,
                    'activity_tags': []
                }
                for i in range((datetime.now() - client_created_at).days // 7 + 1)
            }
        elif units == "months":
            logs = {
                (client_created_at + timedelta(days=i)).replace(day=1, hour=0, minute=0, second=0, microsecond=0): {
                    'count': 0,
                    'activity_tags': []
                }
                for i in range(0, (datetime.now() - client_created_at).days, 30)
            }

        retention_data.append({
            "client_id": client_id,
            "client_name": client_name,
            "client_created_at": client_created_at,
            "retention_logs": logs
        })

    retention_logs: list[RetentionActivityLogs] = RetentionActivityLogs.query.all()

    if allowed_tags:
        updated_retention_logs = []
        for log_entry in retention_logs:
            for tag in allowed_tags:
                if tag in log_entry.activity_tag:
                    updated_retention_logs.append(log_entry)
                    break
        retention_logs = updated_retention_logs

    for log_entry in retention_logs:
        client_id = log_entry.client_id
        client_sdr_id = log_entry.client_sdr_id
        activity_date = log_entry.activity_date
        activity_tag = log_entry.activity_tag

        # Find the corresponding client retention data
        for client_data in retention_data:
            if client_data["client_id"] == client_id:
                # Find the corresponding week start date
                if units == "weeks":
                    start_date = activity_date.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=activity_date.weekday())
                elif units == "months":
                    start_date = activity_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

                if start_date in client_data["retention_logs"]:
                    if client_data['client_name'] not in client_data['retention_logs'][start_date]['activity_tags']:
                        client_data["retention_logs"][start_date]["count"] += 1
                        client_data["retention_logs"][start_date]["activity_tags"].append(client_data['client_name'])
                break
        
    retention_graphs = [
        {
            "cohort_num": i,
            "companies": [],
            "unit_over_unit_activity": [{"count": 0, "activity_users": []} for _ in range(12)]
        }
        for i in range(1,13)
    ]
    for client_data in retention_data:
        days = 365 if units == 'months' else 84
        if client_data['client_created_at'] < datetime.now() - timedelta(days=days):
            continue

        start_date = datetime.now() - (timedelta(days=days))
        cohort_num = (client_data["client_created_at"] - start_date).days // (7 if units == "weeks" else 30) + 1


        for log_date, log_data in client_data["retention_logs"].items():
            if log_date < start_date:
                continue

            client_created_date = client_data["client_created_at"]

            if units == "weeks":
                unit_num = (log_date - client_created_date).days // 7 + 1
            elif units == "months":
                unit_num = (log_date - client_created_date).days // 30 + 1

            print("Client Name: ", client_data["client_name"], "Cohort Number: ", cohort_num, "Unit Number: ", unit_num)
            print("Activity Date: ", log_date, "Activity Count: ", log_data["count"], "Activity Tags: ", log_data["activity_tags"])
            print("\n")

            if cohort_num > 11 or unit_num > 11:
                continue

            retention_graphs[cohort_num]["unit_over_unit_activity"][unit_num]["count"] += log_data["count"]
            if client_data["client_name"] not in retention_graphs[cohort_num]["companies"] and client_data['client_created_at'] >= start_date:
                retention_graphs[cohort_num]["companies"].append(client_data["client_name"])
            if log_data['count'] > 0:
                retention_graphs[cohort_num]["unit_over_unit_activity"][unit_num]["activity_users"].extend([client_data["client_name"]])

    retval = {
        'retention_data': retention_data,
        'retention_graphs': retention_graphs
    }

    def convert_datetimes_to_strings(data):
        if isinstance(data, dict):
            return {convert_datetimes_to_strings(k): convert_datetimes_to_strings(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [convert_datetimes_to_strings(item) for item in data]
        elif isinstance(data, datetime):
            return data.isoformat()
        return data

    retval = convert_datetimes_to_strings(retval)

    return retval

def get_retention_analytics_new(units: str = "weeks" or "months", allowed_tags: list[str] = []):
    all_clients: list[Client] = Client.query.filter(Client.include_in_analytics == True).all()
    
    first_client_created_at = min([client.created_at for client in all_clients])
    if units == "weeks":
        start_date = first_client_created_at.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=first_client_created_at.weekday())
    elif units == "months":
        start_date = first_client_created_at.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    cohort_data = [
        {
            "cohort_num": i,
            "start_date": start_date + timedelta(weeks=(i - 1) * 7) if units == "weeks" else start_date + timedelta(days=(i - 1) * 30),
            "end_date": start_date + timedelta(weeks=i * 7) if units == "weeks" else start_date + timedelta(days=i * 30),
            "companies": [],
            "unit_1": {"count": 0, "activity_users": []},
            "unit_2": {"count": 0, "activity_users": []},
            "unit_3": {"count": 0, "activity_users": []},
            "unit_4": {"count": 0, "activity_users": []},
            "unit_5": {"count": 0, "activity_users": []},
            "unit_6": {"count": 0, "activity_users": []},
            "unit_7": {"count": 0, "activity_users": []},
            "unit_8": {"count": 0, "activity_users": []},
            "unit_9": {"count": 0, "activity_users": []},
            "unit_10": {"count": 0, "activity_users": []},
            "unit_11": {"count": 0, "activity_users": []},
            "unit_12": {"count": 0, "activity_users": []},
        }
        for i in range(1, (((datetime.now() - start_date).days // 7 + 1) if units == "weeks" else (datetime.now() - start_date).days // 30 + 1) + 1)
    ]
    for client in all_clients:
        client_created_date = client.created_at
        if units == "weeks":
            cohort_num = (client_created_date - start_date).days // 7 + 1
        elif units == "months":
            cohort_num = (client_created_date - start_date).days // 30 + 1

        cohort_start = start_date + timedelta(weeks=(cohort_num - 1) * 7) if units == "weeks" else start_date + timedelta(days=(cohort_num - 1) * 30)
        cohort_end = cohort_start + timedelta(weeks=1) if units == "weeks" else cohort_start + timedelta(days=30)

        cohort_index = cohort_num - 1
        try:
            cohort_data[cohort_index]["companies"].append({
                'company': client.company,
                'id': client.id,
            })
        except Exception as e:
            import pdb; pdb.set_trace()
            print(e)

    id_to_client_map = {client.id: client for client in all_clients}

    retention_logs: list[RetentionActivityLogs] = RetentionActivityLogs.query.all()

    if allowed_tags:
        updated_retention_logs = []
        for log_entry in retention_logs:
            for tag in allowed_tags:
                if tag in log_entry.activity_tag:
                    updated_retention_logs.append(log_entry)
                    break
        retention_logs = updated_retention_logs

    for log in retention_logs:
        client_id = log.client_id
        activity_date = log.activity_date
        activity_tag = log.activity_tag

        client = id_to_client_map.get(client_id)
        if not client:
            continue

        # Determine the cohort number for the client
        client_created_date = client.created_at
        if units == "weeks":
            cohort_num = (client_created_date - start_date).days // 7 + 1
        elif units == "months":
            cohort_num = (client_created_date - start_date).days // 30 + 1


        key = (activity_date - client_created_date).days // (7 if units == "weeks" else 30) + 1
        if key > 12:
            continue
        unit_key = f"unit_{key}"

        cohort_index = cohort_num - 1

        # Update the corresponding unit in the cohort
        if unit_key in cohort_data[cohort_index]:
            if any(company['id'] == client_id for company in cohort_data[cohort_index]["companies"]):
                if client_id not in [activity_user['client_id'] for activity_user in cohort_data[cohort_index][unit_key]["activity_users"]]:
                    cohort_data[cohort_index][unit_key]["count"] += 1
                cohort_data[cohort_index][unit_key]["activity_users"].append({
                    'client_id': client_id,
                    'activity_tag': activity_tag,
                    "company": client.company,
                })
    
    retval = {
        'cohort_data': cohort_data
    }

    def convert_datetimes_to_strings(data):
        if isinstance(data, dict):
            return {convert_datetimes_to_strings(k): convert_datetimes_to_strings(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [convert_datetimes_to_strings(item) for item in data]
        elif isinstance(data, datetime):
            return data.isoformat()
        return data
    
    retval = convert_datetimes_to_strings(retval)

    return cohort_data