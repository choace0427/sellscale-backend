import json
from app import db


def get_campaign_drilldown_data(archetype_id):
    sql = """
    select 
        prospect.id "prospect_id",
        prospect.full_name "prospect_name",
        case 
            when  prospect_status_records.to_status in ('ACTIVE_CONVO_SCHEDULING', 'ACTIVE_CONVO_NEXT_STEPS', 'ACTIVE_CONVO_QUESTION') 
                then 'ACTIVE_CONVO_SCHEDULING'
            when prospect_email_status_records.to_status = 'ACTIVE_CONVO'
            	then 'ACTIVE_CONVO_SCHEDULING'
            when prospect_email_status_records.to_status is not null
            	then cast(prospect_email_status_records.to_status as VARCHAR)
            else cast(prospect_status_records.to_status as VARCHAR)
        end "to_status",
        case 
            when prospect.icp_fit_score = 4 then 'VERY HIGH'
            when prospect.icp_fit_score = 3 then 'HIGH'
            when prospect.icp_fit_score = 2 then 'MEDIUM'
            when prospect.icp_fit_score = 1 then 'LOW'
            when prospect.icp_fit_score = 0 then 'VERY LOW'
            else 'UNKNOWN'
        end "prospect_icp_fit_score",
        prospect.title "prospect_title",
        prospect.company "prospect_company",
        client_archetype.archetype "prospect_archetype",
        prospect.img_url "img_url",
        max(case 
        	when prospect.li_last_message_from_prospect is not null
            	then prospect.li_last_message_from_prospect
			when prospect_email.id is not null and prospect_email.outreach_status not in ('SENT_OUTREACH', 'EMAIL_OPENED')
				then 'Responded to an email'
            else 'no response yet.'
        end) "li_last_message_from_prospect",
        max(prospect.li_last_message_timestamp) "li_last_message_timestamp"
    from prospect
    	join client_archetype on client_archetype.id = prospect.archetype_id
        left join prospect_status_records on prospect_status_records.prospect_id = prospect.id
        left join prospect_email on prospect_email.prospect_id = prospect.id
        left join prospect_email_status_records on prospect_email_status_records.prospect_email_id = prospect_email.id
    where 
        (
        	prospect_status_records.to_status in ('SENT_OUTREACH', 'ACCEPTED', 'ACTIVE_CONVO', 'DEMO_SET', 'ACTIVE_CONVO_SCHEDULING', 'ACTIVE_CONVO_NEXT_STEPS', 'ACTIVE_CONVO_QUESTION')
        	or
        	prospect_email_status_records.to_status in ('SENT_OUTREACH', 'EMAIL_OPENED', 'ACTIVE_CONVO', 'DEMO_SET')
        )
        and prospect.archetype_id = :archetype_id
    group by 1,2,3,4,5,6,7,8
    order by 
        case when prospect.li_last_message_timestamp is null then 1 else 0 end,
        li_last_message_timestamp desc;
    """

    # Execute Query with parameters
    result = db.session.execute(sql, {"archetype_id": archetype_id})

    # Convert to list of dictionaries
    data = [dict(row) for row in result]

    return data
