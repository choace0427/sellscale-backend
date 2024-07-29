import datetime
from app import db
from src.automation.resend import send_email
from src.client.models import ClientArchetype, ClientSDR, Client
from src.onboarding.services import is_onboarding_complete
from src.weekly_report.email_template import (
    generate_weekly_update_email,
)

from src.weekly_report.models import *
from tests.research import linkedin


def generate_weekly_report_data_payload(client_sdr_id: int) -> WeeklyReportData:
    # Raw Data Computation
    warmup_query = """
        select 
            max(sla_schedule.linkedin_volume) filter (where NOW() < sla_schedule.end_date) linkedin_warming,
            max(sla_schedule.email_volume) filter (where NOW() < sla_schedule.end_date) email_warming,
            max(sla_schedule.linkedin_volume) filter (where NOW() < sla_schedule.end_date + '7 days'::INTERVAL) linkedin_warming_next_week,
            max(sla_schedule.email_volume) filter (where NOW() < sla_schedule.end_date + '7 days'::INTERVAL) email_warming_next_week
        from client_sdr
            join sla_schedule on sla_schedule.client_sdr_id = client_sdr.id
        where client_sdr.id = {client_sdr_id}
    """.format(
        client_sdr_id=client_sdr_id
    )
    warmup_data = db.engine.execute(warmup_query).fetchone()

    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)

    linkedin_token_valid = (
        client_sdr.li_at_token and client_sdr.li_at_token != "INVALID"
    )

    client_id = client_sdr.client_id
    cumulative_and_last_week_pipeline_query = """
    select 
        count(distinct prospect.id) filter (where prospect_status_records.to_status = 'SENT_OUTREACH' or prospect_email_status_records.to_status = 'SENT_OUTREACH') num_sent_all_time,
        count(distinct prospect.id) filter (where prospect_status_records.to_status = 'ACCEPTED' or prospect_email_status_records.to_status = 'EMAIL_OPENED') num_opened_all_time,
        count(distinct prospect.id) filter (where prospect_status_records.to_status = 'ACTIVE_CONVO' or cast(prospect_email_status_records.to_status as varchar) ilike '%ACTIVE_CONVO_%') num_replied_all_time,
        count(distinct prospect.id) filter (where prospect_status_records.to_status in ('ACTIVE_CONVO_SCHEDULING', 'ACTIVE_CONVO_QUESTION', 'ACTIVE_CONVO_NEXT_STEPS') or prospect_email_status_records.to_status = 'DEMO_SET') num_positive_reply_all_time,
            count(distinct prospect.id) filter (where prospect_status_records.to_status = 'DEMO_SET' or prospect_email_status_records.to_status = 'DEMO_SET') num_demos_all_time,
        
        count(distinct prospect.id) filter (where (prospect_status_records.to_status = 'SENT_OUTREACH' and prospect_status_records.created_at > NOW() - '7 days'::INTERVAL) or (prospect_email_status_records.to_status = 'SENT_OUTREACH' and prospect_email_status_records.created_at > NOW() - '7 days'::INTERVAL)) num_sent_last_week,
        count(distinct prospect.id) filter (where (prospect_status_records.to_status = 'ACCEPTED' and prospect_status_records.created_at > NOW() - '7 days'::INTERVAL) or (prospect_email_status_records.to_status = 'EMAIL_OPENED' and prospect_email_status_records.created_at > NOW() - '7 days'::INTERVAL)) num_opened_last_week,
            count(distinct prospect.id) filter (where (prospect_status_records.to_status = 'ACTIVE_CONVO' and prospect_status_records.created_at > NOW() - '7 days'::INTERVAL) or (prospect_email_status_records.to_status = 'ACTIVE_CONVO' and prospect_email_status_records.created_at > NOW() - '7 days'::INTERVAL)) num_replied_last_week,
            count(distinct prospect.id) filter (where (prospect_status_records.to_status in ('ACTIVE_CONVO_SCHEDULING', 'ACTIVE_CONVO_QUESTION', 'ACTIVE_CONVO_NEXT_STEPS') and prospect_status_records.created_at > NOW() - '7 days'::INTERVAL) or (prospect_email_status_records.to_status = 'DEMO_SET' and prospect_email_status_records.created_at > NOW() - '7 days'::INTERVAL)) num_positive_reply_last_week,
            count(distinct prospect.id) filter (where (prospect_status_records.to_status = 'DEMO_SET' and prospect_status_records.created_at > NOW() - '7 days'::INTERVAL) or (prospect_email_status_records.to_status = 'DEMO_SET' and prospect_email_status_records.created_at > NOW() - '7 days'::INTERVAL)) num_demos_last_week
    from prospect
        join client_sdr on client_sdr.id = prospect.client_sdr_id
        join prospect_status_records on prospect_status_records.prospect_id = prospect.id
        left join prospect_email on prospect_email.prospect_id = prospect.id
        left join prospect_email_status_records on prospect_email_status_records.prospect_email_id = prospect_email.id
    where 
        client_sdr.client_id = {client_id}
    """.format(
        client_id=client_id
    )
    cumulative_and_last_week_pipeline_data = db.engine.execute(
        cumulative_and_last_week_pipeline_query
    ).fetchone()

    active_campaigns_query = """
    select 
        client_archetype.emoji,
        client_archetype.archetype "name",
        client_archetype.id,
        case 
            when client_archetype.linkedin_active then 'LINKEDIN'
            when client_archetype.email_active then 'EMAIL'
            else 'LINKEDIN'
        end channel,
        round(
            cast(count(distinct prospect.id) filter (where prospect.approved_outreach_message_id is not null or prospect.approved_prospect_email_id is not null) as float) / count(distinct prospect.id) * 1000
        ) / 10 completion_percent,
        count(distinct prospect.id) filter (where prospect.overall_status = 'PROSPECTED') prospects_left,
        count(distinct prospect.id) filter (where prospect_status_records.to_status = 'SENT_OUTREACH' or prospect_email_status_records.to_status = 'SENT_OUTREACH') num_sent_all_time,
        count(distinct prospect.id) filter (where prospect_status_records.to_status = 'ACCEPTED' or prospect_email_status_records.to_status = 'EMAIL_OPENED') num_opened_all_time,
        count(distinct prospect.id) filter (where prospect_status_records.to_status = 'ACTIVE_CONVO' or cast(prospect_email_status_records.to_status as varchar) ilike '%ACTIVE_CONVO_%') num_replied_all_time,
        count(distinct prospect.id) filter (where prospect_status_records.to_status in ('ACTIVE_CONVO_SCHEDULING', 'ACTIVE_CONVO_QUESTION', 'ACTIVE_CONVO_NEXT_STEPS') or prospect_email_status_records.to_status = 'DEMO_SET') num_positive_reply_all_time,
        count(distinct prospect.id) filter (where prospect_status_records.to_status = 'DEMO_SET' or prospect_email_status_records.to_status = 'DEMO_SET') num_demo_all_time
            
    from client_archetype
        join prospect on prospect.archetype_id = client_archetype.id
        left join prospect_status_records on prospect_status_records.prospect_id = prospect.id
        left join prospect_email on prospect_email.prospect_id = prospect.approved_prospect_email_id
        left join prospect_email_status_records on prospect_email_status_records.prospect_email_id = prospect_email.id
    where client_archetype.active and client_archetype.client_sdr_id = {client_sdr_id}
    group by 1,2,3,4;
    """.format(
        client_sdr_id=client_sdr_id
    )
    active_campaigns_data = db.engine.execute(active_campaigns_query).fetchall()

    demo_responses_query = """
    select 
        prospect.full_name,
        prospect.company,
        client_sdr.name user_name,
        max(prospect.li_last_message_from_prospect)
    from prospect
        join prospect_status_records on prospect_status_records.prospect_id = prospect.id
        join client_sdr on client_sdr.id = prospect.client_sdr_id
    where prospect_status_records.to_status in ('DEMO_SET')
        and prospect_status_records.created_at > NOW() - '7 days'::INTERVAL
        and prospect.client_sdr_id = {client_sdr_id}
    group by 1,2,3;
    """.format(
        client_sdr_id=client_sdr_id
    )
    demo_responses_data = db.engine.execute(demo_responses_query).fetchall()

    prospect_responses_query = """
    select 
        prospect.full_name,
        prospect.company,
        client_sdr.name user_name,
        max(prospect.li_last_message_from_prospect)
    from prospect
        join prospect_status_records on prospect_status_records.prospect_id = prospect.id
        join client_sdr on client_sdr.id = prospect.client_sdr_id
    where prospect_status_records.to_status in ('ACTIVE_CONVO_SCHEDULING', 'ACTIVE_CONVO_QUESTION')
        and prospect_status_records.created_at > NOW() - '7 days'::INTERVAL
        and prospect.client_sdr_id = {client_sdr_id}
    group by 1,2,3;
    """.format(
        client_sdr_id=client_sdr_id
    )
    prospect_responses_data = db.engine.execute(prospect_responses_query).fetchall()

    next_week_sample_prospects_query = """
        select 
            prospect.full_name,
            case 
                when prospect.icp_fit_score = 0 then '<span style="color: red;">🟥 Very Low</span>'
                when prospect.icp_fit_score = 1 then '<span style="color: orange;">🟧 Low</span>'
                when prospect.icp_fit_score = 2 then '<span style="color: yellow;">🟨 Medium</span>'
                when prospect.icp_fit_score = 3 then '<span style="color: blue;">🟦 High</span>'
                when prospect.icp_fit_score = 4 then '<span style="color: green;">🟩 Very High</span>'
                else '<span style="color: green;">🟪 No Score</span>'
            end icp_fit_score_label,
            prospect.title,
            prospect.company
        from prospect
            join client_archetype on prospect.archetype_id = client_archetype.id
        where prospect.archetype_id = {archetype_id}
            and client_archetype.active
            and prospect.status = 'PROSPECTED'
        order by icp_fit_score > 0 desc, icp_fit_score desc
        limit 3;
    """
    next_week_sample_prospects_data = [
        {
            "sample_prospects": db.engine.execute(
                next_week_sample_prospects_query.format(archetype_id=archetype.id)
            ).fetchall(),
            "campaign_id": archetype.id,
            "campaign_emoji": archetype.emoji,
            "campaign_name": archetype.name,
            "prospects_left": archetype.prospects_left,
        }
        for archetype in active_campaigns_data
    ]

    prospects_removed_query = """
        select count(distinct prospect.id)
        from prospect
        where prospect.client_sdr_id = {client_sdr_id}
            and prospect.created_at > NOW() - '7 days'::INTERVAL
    """.format(
        client_sdr_id=client_sdr_id
    )
    num_prospects_added_data = db.engine.execute(prospects_removed_query).fetchone()

    email_str_query = """
        select 
            string_agg(
                concat(
                    case when reputation = 100 then '🟢' else '🟡' end,
                    ' ',
                    account_name
                ),
                ', '
            ) email_str
        from warmup_snapshot
        where warmup_snapshot.client_sdr_id = {client_sdr_id}
            and channel_type = 'EMAIL';
    """.format(
        client_sdr_id=client_sdr_id
    )
    email_str = db.engine.execute(email_str_query).fetchone().email_str

    # Create Structured Data
    warmup_payload = WeeklyReportWarmupPayload(
        linkedin_outbound_per_week=warmup_data.linkedin_warming,
        email_outbound_per_week=warmup_data.email_warming,
        linkedin_outbound_per_week_next_week=warmup_data.linkedin_warming_next_week,
        email_outbound_per_week_next_week=warmup_data.email_warming_next_week,
        active_emails_str=email_str,
    )
    cumulative_client_pipeline = WeeklyReportPipelineData(
        num_sent=cumulative_and_last_week_pipeline_data.num_sent_all_time,
        num_opens=cumulative_and_last_week_pipeline_data.num_opened_all_time,
        num_replies=cumulative_and_last_week_pipeline_data.num_replied_all_time,
        num_positive_response=cumulative_and_last_week_pipeline_data.num_positive_reply_all_time,
        num_demos=cumulative_and_last_week_pipeline_data.num_demos_all_time,
    )
    last_week_client_pipeline = WeeklyReportPipelineData(
        num_sent=cumulative_and_last_week_pipeline_data.num_sent_last_week,
        num_opens=cumulative_and_last_week_pipeline_data.num_opened_last_week,
        num_replies=cumulative_and_last_week_pipeline_data.num_replied_last_week,
        num_positive_response=cumulative_and_last_week_pipeline_data.num_positive_reply_last_week,
        num_demos=cumulative_and_last_week_pipeline_data.num_demos_last_week,
    )
    active_campaigns = [
        WeeklyReportActiveCampaign(
            campaign_emoji=campaign.emoji,
            campaign_name=campaign.name,
            campaign_id=campaign.id,
            campaign_completion_percent=campaign.completion_percent,
            campaign_channel=campaign.channel,
            num_sent=campaign.num_sent_all_time,
            num_opens=campaign.num_opened_all_time,
            num_replies=campaign.num_replied_all_time,
            num_positive_replies=campaign.num_positive_reply_all_time,
            num_demos=campaign.num_demo_all_time,
        )
        for campaign in active_campaigns_data
    ]
    demo_responses = [
        ProspectResponse(
            prospect_name=prospect.full_name,
            prospect_company=prospect.company,
            user_name=prospect.user_name,
            message=prospect.max,
        )
        for prospect in demo_responses_data
        if len(prospect.max) > 5
    ]
    prospect_responses = [
        ProspectResponse(
            prospect_name=prospect.full_name,
            prospect_company=prospect.company,
            user_name=prospect.user_name,
            message=prospect.max,
        )
        for prospect in prospect_responses_data
        if len(prospect.max) > 5
    ]
    next_week_sample_prospects = [
        NextWeekSampleProspects(
            campaign_emoji=entry["campaign_emoji"],
            campaign_name=entry["campaign_name"],
            campaign_id=entry["campaign_id"],
            prospects_left=entry["prospects_left"],
            sample_prospects=[
                SampleProspect(
                    prospect_name=data.full_name,
                    prospect_icp_fit=data.icp_fit_score_label,
                    prospect_title=data.title,
                    prospect_company=data.company,
                )
                for data in entry["sample_prospects"]
            ],
        )
        for entry in next_week_sample_prospects_data
    ]
    num_prospects_added = num_prospects_added_data.count

    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    user_name = client_sdr.name
    client: Client = Client.query.get(client_sdr.client_id)
    company: str = client.company

    # Format date like November 3rd, 2023 from 7 days ago to today
    date_start = (datetime.datetime.now() - datetime.timedelta(days=7)).strftime(
        "%B %-d, %Y"
    )
    date_end = datetime.datetime.now().strftime("%B %-d, %Y")

    # Return Structured Data in a WeeklyReportData object
    return WeeklyReportData(
        warmup_payload=warmup_payload,
        cumulative_client_pipeline=cumulative_client_pipeline,
        last_week_client_pipeline=last_week_client_pipeline,
        active_campaigns=active_campaigns,
        demo_responses=demo_responses,
        prospect_responses=prospect_responses,
        next_week_sample_prospects=next_week_sample_prospects,
        num_prospects_added=num_prospects_added,
        auth_token=client_sdr.auth_token,
        user_name=user_name,
        date_start=date_start,
        date_end=date_end,
        company=company,
        linkedin_token_valid=linkedin_token_valid,
    )


def get_active_sdr_id() -> list[int]:
    query = """
    select 
        client_sdr.id
    from client_sdr
        join client on client.id = client_sdr.client_id
    where 
        client_sdr.active and client.active and client.id <> 1;
    """

    return [row.id for row in db.engine.execute(query).fetchall()]


def send_email_with_data(
    client_sdr_id: int,
    test_mode: bool = True,
    to_emails: list[str] = [],
    cc_emails: list[str] = [],
    bcc_emails: list[str] = [],
) -> bool:
    data = generate_weekly_report_data_payload(client_sdr_id)
    html = generate_weekly_update_email(data)

    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    first_name = client_sdr.name.split(" ")[0]
    # title is like `Hristina's Report: Week of Nov 22`
    # date should be today but structured like above
    date_in_title = datetime.datetime.now().strftime("%B %-d")
    title = "{first_name}'s Report: Week of {date}".format(
        first_name=first_name, date=date_in_title
    )

    send_email(
        html=html,
        title=title,
        to_emails=to_emails,
        cc_emails=cc_emails,
        bcc_emails=bcc_emails,
    )

    return True


def send_all_emails(test_mode: bool = True, to_emails: list[str] = []) -> bool:
    client_sdr_ids = get_active_sdr_id()
    for client_sdr_id in client_sdr_ids:
        client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)

        if client_sdr.is_onboarding:
            continue

        name = client_sdr.name

        cc_emails = []
        bcc_emails = []

        if not test_mode:
            to_emails = [client_sdr.email]
            cc_emails = client_sdr.weekly_report_cc_emails or []
            bcc_emails = client_sdr.weekly_report_bcc_emails or []

        if "team@sellscale.com" not in bcc_emails and not test_mode:
            bcc_emails.append("team@sellscale.com")

        print("Sending email to {name}...".format(name=name))
        print("To: {to_emails}".format(to_emails=to_emails))
        print("CC: {cc_emails}".format(cc_emails=cc_emails))
        print("BCC: {bcc_emails}".format(bcc_emails=bcc_emails))
        print("")

        # todo(Aakash) Update this
        send_email_with_data(client_sdr_id, test_mode, to_emails, cc_emails, bcc_emails)
    return True
