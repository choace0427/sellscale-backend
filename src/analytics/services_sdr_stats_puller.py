from app import db, celery
from model_import import SDRHealthStats
from src.client.models import ClientSDR


def get_average_icp_fit_score(sdr_id):
    results = db.session.execute(
        """
        select 
            avg(prospect.icp_fit_score) "Avg. ICP Fit Score from Last 7 Days"
        from prospect
            join client_archetype on client_archetype.id = prospect.archetype_id
            join prospect_status_records on prospect_status_records.prospect_id = prospect.id 
                and prospect_status_records.to_status = 'SENT_OUTREACH'
                and prospect_status_records.created_at > NOW() - '7 days'::INTERVAL
        where prospect.overall_status <> 'REMOVED'
        and prospect.client_sdr_id = """
        + str(sdr_id)
        + """
        and prospect.icp_fit_score >= 0;
    """
    ).fetchall()[0][0]

    return results


def get_message_ops_stats(sdr_id):
    results = db.session.execute(
        """
        with linkedin_stats as (
            select
                prospect_id,
                min(prospect_status_records.created_at) filter (where prospect_status_records.to_status = 'ACCEPTED') acceptance_date,
                min(prospect_status_records.created_at) filter (where prospect_status_records.to_status = 'RESPONDED') bumped_date
            from prospect_status_records
                join prospect on prospect.id = prospect_status_records.prospect_id
                and prospect.client_sdr_id = """
        + str(sdr_id)
        + """
            group by 1
            having min(prospect_status_records.created_at) filter (where prospect_status_records.to_status = 'RESPONDED') is not null
        )
        select 
            count(distinct prospect.id) filter (where prospect_status_records.to_status = 'SENT_OUTREACH') "# Linkedins Sent in Last 7 Days",
            count(distinct prospect.id) filter (where prospect_email_status_records.to_status = 'SENT_OUTREACH') "# Emails Sent in Last 7 Days",
            extract('days' from avg(bumped_date - acceptance_date)) + cast(extract('hours' from avg(bumped_date - acceptance_date)) as float) / 24 "Avg. Time to First Bump",
            client_sdr.auto_bump "Auto Bumps Active"
        from prospect
            join client_sdr on client_sdr.id = prospect.client_sdr_id
            join prospect_status_records on prospect_status_records.prospect_id = prospect.id 
            left join linkedin_stats on linkedin_stats.prospect_id = prospect.id
            left join prospect_email_status_records on prospect_email_status_records.prospect_email_id = prospect.approved_prospect_email_id
        where prospect.client_sdr_id = """
        + str(sdr_id)
        + """
            and prospect_status_records.created_at > NOW() - '7 days'::INTERVAL
        group by 4;
    """
    ).fetchall()

    if len(results) == 0:
        return {
            "Linkedins Sent in Last 7 Days": 0,
            "Emails Sent in Last 7 Days": 0,
            "Avg. Time to First Bump": 0,
            "Auto Bumps Active": False,
        }

    results = results[0]

    return {
        "Linkedins Sent in Last 7 Days": results[0],
        "Emails Sent in Last 7 Days": results[1],
        "Avg. Time to First Bump": results[2],
        "Auto Bumps Active": results[3],
    }


def get_message_ops_targets(sdr_id):
    results = db.session.execute(
        """
            select 
                client_sdr.weekly_li_outbound_target "Linkedin Goal Volume",
                client_sdr.weekly_email_outbound_target "Email Goal Volume",
                3 "Speed to Lead",
                TRUE "Auto Bumps Enabled"
            from client_sdr 
            where client_sdr.id = """
        + str(sdr_id)
        + """
    """
    ).fetchall()[0]
    return {
        "Linkedin Goal Volume": results[0],
        "Email Goal Volume": results[1],
        "Speed to Lead": results[2],
        "Auto Bumps Enabled": results[3],
    }


def get_cta_results(sdr_id):
    results = db.session.execute(
        """
     select 
        generated_message_cta.text_value,
        ARRAY_AGG(distinct client_sdr.name) "SDRs with CTA",
        count(distinct prospect_status_records.prospect_id) filter (where prospect_status_records.to_status = 'SENT_OUTREACH') "# Sent Outreach",
        count(distinct prospect_status_records.prospect_id) filter (where prospect_status_records.to_status = 'ACCEPTED') "# Accepted",
        count(distinct prospect_status_records.prospect_id) filter (where prospect_status_records.to_status = 'ACTIVE_CONVO') "# Active Convo",
        cast(count(distinct prospect_status_records.prospect_id) filter (where prospect_status_records.to_status = 'ACCEPTED') as float) / (0.000001 + count(distinct prospect_status_records.prospect_id) filter (where prospect_status_records.to_status = 'SENT_OUTREACH')) "% Acceptance Rate",
        cast(count(distinct prospect_status_records.prospect_id) filter (where prospect_status_records.to_status = 'ACTIVE_CONVO') as float) / (0.000001 + count(distinct prospect_status_records.prospect_id) filter (where prospect_status_records.to_status = 'SENT_OUTREACH')) "% Conversation Rate"
        from client_sdr   
        join client_archetype
            on client_archetype.client_sdr_id = client_sdr.id
        join generated_message_cta
            on generated_message_cta.archetype_id = client_archetype.id
            join generated_message on generated_message.message_cta = generated_message_cta.id
            join prospect_status_records on prospect_status_records.prospect_id = generated_message.prospect_id
        where generated_message_cta.active
        and client_sdr.id = """
        + str(sdr_id)
        + """
        and generated_message_cta.active
        group by 1
        order by 7 desc;
    """
    ).fetchall()
    return results


def inbox_slas(sdr_id):
    results = db.session.execute(
        """
        select 
        client_sdr.name,
        client_sdr.auto_bump,
        concat('https://app.sellscale.com/authenticate?stytch_token_type=direct&token=', client_sdr.auth_token, '&redirect=all/inboxes') "Direct Link",
        count(distinct prospect.id) filter (where prospect.status = 'ACCEPTED' and prospect.hidden_until < NOW()) "Accepted Inbox (AI-handles)",
        count(distinct prospect.id) filter (where prospect.status = 'RESPONDED' and prospect.hidden_until < NOW()) "Bumped Inbox (AI-handles)",
        count(distinct prospect.id) filter (where prospect.overall_status = 'ACTIVE_CONVO' and prospect.hidden_until < NOW()) "# Active Convos Needing Attention (SS-handles)",
        count(distinct prospect.id) filter (where prospect.status = 'ACTIVE_CONVO_SCHEDULING' and prospect.hidden_until < NOW()) "# Scheduling (SS)"
        from client_sdr
        join prospect on prospect.client_sdr_id = client_sdr.id
        where client_sdr.id = """
        + str(sdr_id)
        + """
        and client_sdr.active
        group by 1,2,3
        order by 6 desc;
    """
    ).fetchall()

    if len(results) == 0:
        return {
            "Name": "",
            "Auto Bumps Enabled": False,
            "Direct Link": "",
            "Accepted Inbox (AI-handles)": 0,
            "Bumped Inbox (AI-handles)": 0,
            "# Active Convos Needing Attention (SS-handles)": 0,
            "# Scheduling (SS)": 0,
        }

    results = results[0]
    return {
        "Name": results[0],
        "Auto Bumps Enabled": results[1],
        "Direct Link": results[2],
        "Accepted Inbox (AI-handles)": results[3],
        "Bumped Inbox (AI-handles)": results[4],
        "# Active Convos Needing Attention (SS-handles)": results[5],
        "# Scheduling (SS)": results[6],
    }


def feedback_sla(sdr_id):
    results = db.session.execute(
        """
        select 
        client_sdr.name "SDR Name",
        prospect.full_name "Prospect Name",
        prospect.company "Company",
        prospect.title "Title",
        prospect.demo_date "Demo Date",
        case when
            prospect.demo_date < NOW() then 'Feedback needed!' 
            else 'Demo happening soon...'
        end message
        from prospect
        join client_sdr on client_sdr.id = prospect.client_sdr_id
        left join demo_feedback on demo_feedback.prospect_id = prospect.id
        where prospect.status in ('DEMO_SET')
        and demo_feedback.id is null
        and prospect.client_sdr_id = """
        + str(sdr_id)
        + """
        and client_sdr.active
        order by prospect.demo_date asc;
    """
    ).fetchall()
    return results


def get_icp_fit_status(sdr_id):
    score = get_average_icp_fit_score(sdr_id)
    if not score:
        return "🔴"
    good_status = score >= 3
    if good_status:
        return "🟢"
    else:
        return "🔴"


def get_message_ops_status(sdr_id):
    stats = get_message_ops_stats(sdr_id)
    targets = get_message_ops_targets(sdr_id)

    if (
        stats["Linkedins Sent in Last 7 Days"] >= targets["Linkedin Goal Volume"]
        and stats["Emails Sent in Last 7 Days"] >= targets["Email Goal Volume"]
        and stats["Avg. Time to First Bump"] <= targets["Speed to Lead"]
        and stats["Auto Bumps Active"] == targets["Auto Bumps Enabled"]
    ):
        return "🟢"
    else:
        return "🔴"


def get_cta_status(sdr_id):
    stats = get_cta_results(sdr_id)
    for entry in stats:
        if entry[5] <= 0.2:
            return "🔴"
    return "🟢"


def sdr_slas_status(sdr_id):
    inbox_stats = inbox_slas(sdr_id)
    feedback_stats = feedback_sla(sdr_id)

    ai_handles = inbox_stats["Accepted Inbox (AI-handles)"] < 3
    bumped_handles = inbox_stats["Bumped Inbox (AI-handles)"] < 3
    active_convos = inbox_stats["# Active Convos Needing Attention (SS-handles)"] < 3

    num_feedbacks_needed = 0
    for entry in feedback_stats:
        if entry[5] == "Feedback needed!":
            num_feedbacks_needed += 1
    feedback_needed = num_feedbacks_needed == 0

    if ai_handles and bumped_handles and active_convos and feedback_needed:
        return "🟢"
    else:
        return "🔴"


@celery.task
def process_sdr_stats():
    sdrs = ClientSDR.query.filter_by(active=True).all()
    for sdr in sdrs:
        pull_and_save_sdr_stats.delay(sdr.id)


@celery.task
def pull_and_save_sdr_stats(sdr_id):
    sdr: ClientSDR = ClientSDR.query.filter_by(id=sdr_id).first()
    if not sdr or not sdr.active:
        return False

    print("Pulling stats for SDR: " + sdr.name)

    prospect_fit: str = get_icp_fit_status(sdr_id)
    message_volume: str = get_message_ops_status(sdr_id)
    cta_status: str = get_cta_status(sdr_id)
    sdr_slas = sdr_slas_status(sdr_id)

    health_stats_exist: SDRHealthStats = SDRHealthStats.query.filter_by(
        sdr_id=sdr_id
    ).first()
    if health_stats_exist:
        health_stats_exist.prospect_fit = prospect_fit
        health_stats_exist.message_volume = message_volume
        health_stats_exist.message_quality = cta_status
        health_stats_exist.sdr_action_items = sdr_slas
        db.session.add(health_stats_exist)
        db.session.commit()
    else:
        new_stats: SDRHealthStats = SDRHealthStats(
            sdr_id=sdr_id,
            prospect_fit=prospect_fit,
            message_volume=message_volume,
            message_quality=cta_status,
            sdr_action_items=sdr_slas,
        )
        db.session.add(new_stats)
        db.session.commit()

    return True
