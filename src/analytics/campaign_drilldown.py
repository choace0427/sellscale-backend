import json
from app import db


def get_campaign_drilldown_data(archetype_id):
    sql = """
    select 
        prospect.id "prospect_id",
        prospect.full_name "prospect_name",
        prospect_status_records.to_status,
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
        max(case when prospect.li_last_message_from_prospect is not null
            then prospect.li_last_message_from_prospect
            else 'no response yet.'
        end) "li_last_message_from_prospect",
        max(prospect.li_last_message_timestamp) "li_last_message_timestamp"
    from prospect
        join prospect_status_records on prospect_status_records.prospect_id = prospect.id
        join client_archetype on client_archetype.id = prospect.archetype_id
    where 
        prospect_status_records.to_status in ('SENT_OUTREACH', 'ACCEPTED', 'ACTIVE_CONVO', 'DEMO_SET')
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
