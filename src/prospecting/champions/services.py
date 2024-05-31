from model_import import Prospect
from app import db
from src.research.linkedin.services import get_research_payload_new
from datetime import datetime
from dateutil.relativedelta import relativedelta

def mark_prospects_as_champion(client_id: int, prospect_ids: list, is_champion: bool):
    """
    Marks the given prospects as champions or not champions.

    Args:
        client_id (int): the client id
        prospect_ids (list): the list of prospect ids
        is_champion (bool): the value to set for is_champion
    """
    Prospect.query.filter(Prospect.id.in_(prospect_ids), Prospect.client_id == client_id).update(
        {
            Prospect.is_champion: is_champion,
            Prospect.overall_status: 'REMOVED',
            Prospect.status: 'NOT_QUALIFIED',
        }, synchronize_session=False
    )
    db.session.commit()

    return True

def get_champion_detection_stats(client_id: int):
    """
    Gets the champion detection stats for the given client.

    Args:
        client_id (int): the client id

    Returns:
        dict: {
            num_companies: int,
            num_contacts: int,
            num_changed_last_60_days: int,
        }
    """

    last_three_months = []
    for i in range(3):
        last_three_months.append((datetime.now() - relativedelta(months=i)).strftime('%Y-%m'))
    last_three_months_str = "'" + "', '".join(last_three_months) + "'"

    query = """
        with d as (
            with t as (
                select 
                    prospect.id prospect_id,
                    max(research_payload.id) max_rp_id
                from prospect
                    join research_payload on prospect.id = research_payload.prospect_id
                where prospect.client_id = {client_id}
                    and prospect.is_champion
                    and research_payload.research_type = 'LINKEDIN_ISCRAPER'
                group by 1
            )
            select 
                prospect.id prospect_id,
                prospect.company,
                research_payload.id,
                prospect.linkedin_url,
                research_payload.payload->'personal'->'position_groups'->0->'profile_positions'->-1->>'company' "new_company_name",
                concat(
                    research_payload.payload->'personal'->'position_groups'->0->'profile_positions'->-1->'date'->'start'->>'year',
                    '-',
                    case 
                        when cast(research_payload.payload->'personal'->'position_groups'->0->'profile_positions'->-1->'date'->'start'->>'month' as integer) < 10
                            then concat('0', research_payload.payload->'personal'->'position_groups'->0->'profile_positions'->-1->'date'->'start'->>'month')
                            else research_payload.payload->'personal'->'position_groups'->0->'profile_positions'->-1->'date'->'start'->>'month'
                    end
                    
                ) "new_company_start_date",
                
                research_payload.payload->'personal'->'position_groups'->1->'profile_positions'->0->>'company' "last_company_name",
                concat(
                    research_payload.payload->'personal'->'position_groups'->1->'profile_positions'->0->'date'->'start'->>'year',
                    '-',
                    case 
                        when cast(research_payload.payload->'personal'->'position_groups'->1->'profile_positions'->0->'date'->'start'->>'month' as integer) < 10
                            then concat('0', research_payload.payload->'personal'->'position_groups'->1->'profile_positions'->0->'date'->'start'->>'month')
                            else research_payload.payload->'personal'->'position_groups'->1->'profile_positions'->0->'date'->'start'->>'month'
                    end
                ) "last_company_start_date",
                research_payload.research_type
            from prospect
                join research_payload on research_payload.prospect_id = prospect.id 
                    and research_payload.research_type = 'LINKEDIN_ISCRAPER'
                join t on t.max_rp_id = research_payload.id and t.prospect_id = prospect.id
            where prospect.client_id = {client_id}
                and prospect.is_champion = True
        )
        select 
            count(distinct company) num_companies,
            count(distinct prospect_id) num_contacts,
            count(distinct prospect_id) filter (where new_company_start_date in ({last_three_months_str}) and new_company_name is not null)
        from d;
    """

    result = db.session.execute(query.format(client_id=client_id, last_three_months_str=last_three_months_str)).fetchone()

    return {
        "num_companies": result[0],
        "num_contacts": result[1],
        "num_changed_last_60_days": result[2],
    }

def refresh_job_data_for_all_champions(
    client_id: int,
):
    """
    Refreshes Linkedin cached data for all champions of the given client.
    """
    champion_prospect_ids: list[int] = [
        p.id
        for p in Prospect.query.filter(Prospect.client_id == client_id, Prospect.is_champion == True).all()
    ]

    for prospect_id in champion_prospect_ids:
        get_research_payload_new.delay(
            prospect_id, False
        )

    return True

def get_champion_detection_changes(
    client_id: int,
    search_term: str = ''
):
    last_three_months = []
    for i in range(3):
        last_three_months.append((datetime.now() - relativedelta(months=i)).strftime('%Y-%m'))
    last_three_months_str = "'" + "', '".join(last_three_months) + "'"

    query = """
    with d as (
        with t as (
            select 
                prospect.id prospect_id,
                max(research_payload.id) max_rp_id
            from prospect
                join research_payload on prospect.id = research_payload.prospect_id
            where prospect.client_id = {client_id}
                and prospect.is_champion
                and research_payload.research_type = 'LINKEDIN_ISCRAPER'
            group by 1
        )
        select 
            prospect.id prospect_id,
            prospect.company,
            prospect.full_name,
            research_payload.id,
            prospect.linkedin_url,
            research_payload.payload->'personal'->'position_groups'->0->'company'->>'logo' "new_company_logo",
            research_payload.payload->'personal'->'position_groups'->0->'profile_positions'->-1->>'company' "new_company_name",
            research_payload.payload->'personal'->'position_groups'->0->'profile_positions'->-1->>'title' "new_title",
            concat(
                research_payload.payload->'personal'->'position_groups'->0->'profile_positions'->-1->'date'->'start'->>'year',
                '-',
                case 
                    when cast(research_payload.payload->'personal'->'position_groups'->0->'profile_positions'->-1->'date'->'start'->>'month' as integer) < 10
                        then concat('0', research_payload.payload->'personal'->'position_groups'->0->'profile_positions'->-1->'date'->'start'->>'month')
                        else research_payload.payload->'personal'->'position_groups'->0->'profile_positions'->-1->'date'->'start'->>'month'
                end
                
            ) "new_company_start_date",
            research_payload.payload->'personal'->'position_groups'->1->'profile_positions'->0->>'title' "old_title",
            research_payload.payload->'personal'->'position_groups'->1->'company'->>'logo' "old_company_logo",
            
            research_payload.payload->'personal'->'position_groups'->1->'profile_positions'->0->>'company' "last_company_name",
            concat(
                research_payload.payload->'personal'->'position_groups'->1->'profile_positions'->0->'date'->'start'->>'year',
                '-',
                case 
                    when cast(research_payload.payload->'personal'->'position_groups'->1->'profile_positions'->0->'date'->'start'->>'month' as integer) < 10
                        then concat('0', research_payload.payload->'personal'->'position_groups'->1->'profile_positions'->0->'date'->'start'->>'month')
                        else research_payload.payload->'personal'->'position_groups'->1->'profile_positions'->0->'date'->'start'->>'month'
                end
            ) "last_company_start_date",
            research_payload.research_type
        from prospect
            join research_payload on research_payload.prospect_id = prospect.id 
                and research_payload.research_type = 'LINKEDIN_ISCRAPER'
            join t on t.max_rp_id = research_payload.id and t.prospect_id = prospect.id
        where prospect.client_id = {client_id}
            and prospect.is_champion = True
            {search_filter}
    )
    select 
        case when
            new_company_start_date in ({last_three_months_str}) then true
            else false
        end "change_detected",
        *
    from d
    where new_company_name is not null
    order by change_detected desc, new_company_start_date desc;
    """

    search_filter = ""
    if search_term:
        search_filter = f"and (prospect.company ilike '%{search_term}%' or prospect.full_name ilike '%{search_term}%')"

    query = query.format(client_id=client_id, last_three_months_str=last_three_months_str, search_filter=search_filter)

    result = db.session.execute(query.format(client_id=client_id, last_three_months_str=last_three_months_str)).fetchall()

    results = []
    for row in result:
        results.append({
            "change_detected": row[0],
            "prospect_id": row[1],
            "company": row[2],
            "full_name": row[3],
            "research_payload_id": row[4],
            "linkedin_url": row[5],
            "new_company_logo": row[6],
            "new_company_name": row[7],
            "new_title": row[8],
            "new_company_start_date": row[9],
            "old_title": row[10],
            "old_company_logo": row[11],
            "last_company_name": row[12],
            "last_company_start_date": row[13],
            "research_type": row[14],
        })
    
    return results