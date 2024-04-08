from app import db
from typing import Optional
import json

def get_active_campaign_data(client_id: int):
    query = f"""
        with d as (
            select 
                'active' "status",
                client_archetype.id "persona_id",
                concat(client_archetype.emoji, ' ', client_archetype.archetype) "campaign",
                client_sdr.img_url "rep_profile_picture",
                client_sdr.name "rep",
                
                client_archetype.linkedin_active,
                client_archetype.email_active,
                
                count(distinct prospect.id) filter (where prospect.approved_outreach_message_id is not null) num_used_linkedin,
                count(distinct prospect.id) num_total_linkedin,
                
                count(distinct prospect.id) filter (where prospect.approved_prospect_email_id is not null) num_used_email,
                count(distinct prospect.id) filter (where prospect.email is not null) num_total_email
                
            from
                client_sdr
                join client_archetype on client_archetype.client_sdr_id = client_sdr.id
                join prospect on prospect.archetype_id = client_archetype.id
                    and prospect.overall_status not in ('REMOVED')
            where
                client_sdr.active
                and client_archetype.active
                and (client_archetype.linkedin_active or client_archetype.email_active)
                and client_sdr.client_id = {{CLIENT_ID}}
            group by 1,2,3,4,5,6
        )
        select 
            *,
            (case when linkedin_active then num_used_linkedin else 0 end) + (case when email_active then num_used_email else 0 end) num_used_total,
            (case when linkedin_active then num_total_linkedin else 0 end) + (case when email_active then num_total_email else 0 end) num_total
        from d;
    """.format(
        CLIENT_ID=client_id
    )
    
    result = db.session.execute(query).fetchall()
    if result is not None:
        result = [dict(row) for row in result]

    return result

def get_rep_needed_campaign_data(client_id: int):
    query = f"""
        with d as (
            select 
                'rep action needed' "status",
                concat(client_archetype.emoji, ' ', client_archetype.archetype) "campaign",
                client_sdr.img_url "rep_profile_picture",
                client_sdr.name "rep",
                count(distinct operator_dashboard_entry.id) "num_open_tasks",
                array_agg(distinct operator_dashboard_entry.id) "open_task_ids",
                array_agg(distinct operator_dashboard_entry.title) "open_task_titles"
            from
                client_sdr
                join client_archetype on client_archetype.client_sdr_id = client_sdr.id
                join operator_dashboard_entry
                    on operator_dashboard_entry.status = 'PENDING'
                    and cast(operator_dashboard_entry.task_data->>'campaign_id' as integer) = client_archetype.id
            where
                client_sdr.active
                and client_sdr.client_id = {{client_id}}
            group by 1,2,3,4
        )
        select 
            *
        from d;
    """.format(
        client_id=client_id
    )
    
    result = db.session.execute(query).fetchall()
    if result is not None:
        result = [dict(row) for row in result]

    return result

def get_ai_is_setting_up_campaign_data(client_id: int):
    query = f"""
        with d as (
            select 
                'AI is Setting Up' "status",
                concat(client_archetype.emoji, ' ', client_archetype.archetype) "campaign",
                client_sdr.img_url "rep_profile_picture",
                client_sdr.name "rep",
                client_archetype.template_mode,
                
                count(distinct prospect_status_records.prospect_id) filter (where prospect_status_records.to_status = 'SENT_OUTREACH')
                    + count(distinct prospect_email_status_records.prospect_email_id) filter (where prospect_email_status_records.to_status = 'SENT_OUTREACH') "num_sent",
                
                
                count(distinct operator_dashboard_entry.id) "open_ops_cards",
                count(distinct prospect.id) "distinct_prospects",
                count(distinct linkedin_initial_message_template.id) "distinct_linkedin_templates",
                count(distinct generated_message_cta) "distinct_ctas",
                count(distinct bump_framework.id) "distinct_linkedin_followups",
                count(distinct email_sequence_step.id) "distinct_email_followups"
            from
                client_sdr
                join client_archetype on client_archetype.client_sdr_id = client_sdr.id
                left join prospect on prospect.archetype_id = client_archetype.id
                left join generated_message_cta on generated_message_cta.archetype_id = client_archetype.id and generated_message_cta.active
                left join linkedin_initial_message_template on linkedin_initial_message_template.client_archetype_id = client_archetype.id and linkedin_initial_message_template.active
                left join bump_framework on bump_framework.client_archetype_id = client_archetype.id and bump_framework.overall_status in ('ACCEPTED', 'BUMPED') and bump_framework.active and bump_framework.default
                left join email_sequence_step on email_sequence_step.client_archetype_id = client_archetype.id and email_sequence_step.active
                left join operator_dashboard_entry
                    on operator_dashboard_entry.status = 'PENDING'
                    and cast(operator_dashboard_entry.task_data->>'campaign_id' as integer) = client_archetype.id
                left join prospect_status_records on prospect_status_records.prospect_id = prospect.id 
                left join prospect_email on prospect_email.prospect_id = prospect.id
                left join prospect_email_status_records on prospect_email_status_records.prospect_email_id = prospect_email.id
            where
                client_sdr.active
                and client_sdr.client_id = {{client_id}}
                and client_archetype.active
                and not client_archetype.is_unassigned_contact_archetype
            group by 1,2,3,4,5
        )
        select 
            status,
            campaign,
            rep_profile_picture,
            rep,
            case
                when distinct_prospects > 0
                    then concat('✅ ', distinct_prospects, ' prospects found')
                else '🟡 Finding prospects'
            end prospects,
            case
                when template_mode
                    then 
                        case when distinct_linkedin_templates > 0 and distinct_linkedin_followups > 0
                            then concat('✅ ', distinct_linkedin_followups + 1, ' step LI sequence')
                            else '🟡 Writing LI sequence'
                        end
                else
                    case when distinct_ctas > 0 and distinct_linkedin_followups > 0
                            then concat('✅ ', distinct_linkedin_followups + 1, ' step LI sequence')
                        else '🟡 Writing LI sequence'
                    end
            end "linkedin_setup",
            case
                when distinct_email_followups > 0
                    then concat('✅ ', distinct_email_followups + 1, ' step Email sequence')
                    else '🟡 Writing Email sequence'
            end "email_setup"
        from d
        where 
            num_sent = 0
            and open_ops_cards = 0;
    """.format(
        client_id=client_id
    )
    
    result = db.session.execute(query).fetchall()
    if result is not None:
        result = [dict(row) for row in result]

    return result

def get_no_campaign_data(client_id: int):
    query = f"""
        with d as (
            select
                client.company "Company",
                client_sdr.img_url,
                client_sdr.name "Rep",
                concat(client_archetype.emoji, ' ', client_archetype.archetype) "Campaign",
                client_archetype.active "active",
                client_archetype.linkedin_active,
                client_archetype.email_active,
                segment.segment_title,
                case when client_archetype.template_mode = true then 'template-mode' else 'cta-mode' end "linkedin_mode",
                count(distinct segment_prospect.id) "prospects_in_segment",
                count(distinct operator_dashboard_entry.id) filter (where operator_dashboard_entry.status = 'COMPLETED') "num_complete_tasks",
                count(distinct operator_dashboard_entry.id) filter (where operator_dashboard_entry.status = 'PENDING') "num_open_tasks",
                count(distinct prospect.id) "num_prospects",
                count(distinct prospect.id) filter (where prospect.email is not null) "num_prospects_with_email",
                count(distinct linkedin_initial_message_template.id) "num_templates_active",
                count(distinct generated_message_cta.id) "num_templates_active",
                count(distinct bump_framework.id) "num_templates_active",
                count(distinct email_sequence_step.id) "num_templates_active",
                count(distinct prospect_status_records.prospect_id) filter (where prospect_status_records.to_status = 'SENT_OUTREACH') "num_linkedin_sent",
                count(distinct prospect_email.prospect_id) filter (where prospect_email_status_records.to_status = 'SENT_OUTREACH') "num_email_sent"
            from client_sdr
                join client on client.id = client_sdr.client_id and client_sdr.active
                left join client_archetype
                    on client_archetype.client_sdr_id = client_sdr.id and client_archetype.active and not client_archetype.is_unassigned_contact_archetype
                left join
                    operator_dashboard_entry on cast(operator_dashboard_entry.task_data->>'campaign_id' as integer) = client_archetype.id
                left join
                    prospect on prospect.archetype_id = client_archetype.id
                left join
                    linkedin_initial_message_template on linkedin_initial_message_template.client_archetype_id = client_archetype.id and linkedin_initial_message_template.active
                left join
                    generated_message_cta on generated_message_cta.archetype_id = client_archetype.id and generated_message_cta.active
                left join
                    bump_framework on bump_framework.client_archetype_id = client_archetype.id and bump_framework.overall_status in ('ACCEPTED', 'BUMPED') and bump_framework.active and bump_framework.default
                left join email_sequence_step on email_sequence_step.client_archetype_id = client_archetype.id and email_sequence_step.active and email_sequence_step.default
                left join prospect_status_records on prospect_status_records.prospect_id = prospect.id
                left join prospect_email on prospect_email.prospect_id = prospect.id
                left join prospect_email_status_records on prospect_email_status_records.prospect_email_id = prospect_email.id
                left join segment on segment.client_archetype_id = client_archetype.id
                left join prospect segment_prospect on segment_prospect.segment_id = segment.id
            where client.id = {{client_id}}
                and client_sdr.active
            group by 1,2,3,4,5,6,7,8,9
            order by 1 asc, 2 asc
        )
        select
            'no campaign found' status, 
            '' campaign,
            d."img_url" rep_profile_picture,
            d."Rep" rep,
            array_agg(d.segment_title) "recommended_segments"
        from d
        where 
            length(d."Campaign") = 1
        group by 
            1,2,3,4;
    """.format(
        client_id=client_id
    )

    result = db.session.execute(query).fetchall()
    if result is not None:
        result = [dict(row) for row in result]

    return result

def get_completed_campaign_data(client_id: int):
    query = f"""
        with d as (
            select 
                'Complete' "status",
                concat(client_archetype.emoji, ' ', client_archetype.archetype) "campaign",
                client_sdr.img_url "rep_profile_picture",
                client_sdr.name "rep",
                
                client_archetype.linkedin_active,
                client_archetype.email_active,
                
                count(distinct prospect.id) filter (where prospect.approved_outreach_message_id is not null) num_used_linkedin,
                count(distinct prospect.id) num_total_linkedin,
                
                count(distinct prospect.id) filter (where prospect.approved_prospect_email_id is not null) num_used_email,
                count(distinct prospect.id) filter (where prospect.email is not null) num_total_email,
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
                ) num_demos
                
            from
                client_sdr
                join client_archetype on client_archetype.client_sdr_id = client_sdr.id
                join prospect on prospect.archetype_id = client_archetype.id
                    and prospect.overall_status not in ('REMOVED')
                left join prospect_status_records on prospect_status_records.prospect_id = prospect.id 
                left join prospect_email on prospect_email.prospect_id = prospect.id
                left join prospect_email_status_records on prospect_email_status_records.prospect_email_id = prospect_email.id
            where
                client_sdr.active
                and not client_archetype.active
                and client_sdr.client_id = {{client_id}}
                and not client_archetype.is_unassigned_contact_archetype
            group by 1,2,3,4,5,6
        )
        select 
            *,
            (case when d.num_used_linkedin > 0 then num_used_linkedin else 0 end) + (case when d.num_used_email > 0 then num_used_email else 0 end) num_used_total,
            (case when d.num_used_linkedin > 0 then num_total_linkedin else 0 end) + (case when d.num_used_email > 0 then num_total_email else 0 end) num_total
        from d
        where (d.num_used_linkedin > 0 or d.num_used_email > 0)
        order by 1 asc, 2 asc, 3 asc;
    """.format(
        client_id=client_id
    )

    result = db.session.execute(query).fetchall()
    if result is not None:
        result = [dict(row) for row in result]

    return result

def get_seat_utilization_data(client_id: int):
    query = f"""
        select 
            client_sdr.img_url "rep_image",
            client_sdr.name "rep",
            count(distinct client_archetype.id) filter (where client_archetype.active and (client_archetype.linkedin_active or client_archetype.email_active)) num_campaigns
        from client_sdr
            left join client on client.id = client_sdr.client_id
            left join client_archetype on client_archetype.client_sdr_id = client_sdr.id
        where
            client.active and client_sdr.active
            and client.id = {{client_id}}
        group by 1,2
        order by 3 desc;
    """.format(
        client_id=client_id
    )

    result = db.session.execute(query).fetchall()
    if result is not None:
        result = [dict(row) for row in result]

    return result
