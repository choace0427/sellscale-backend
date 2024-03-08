import json
import math
from typing import Optional

from psycopg2 import IntegrityError
from src.prospecting.models import Prospect
from sqlalchemy import or_

from src.company.models import Company, CompanyRelation
from src.research.models import IScraperPayloadCache
from src.client.models import ClientSDR, Client
from app import db, celery
from src.utils.math import get_unique_int
from src.utils.slack import send_slack_message, URL_MAP


def company_backfill(c_min: int, c_max: int):
    iscraper_cache = IScraperPayloadCache.query.filter(
        IScraperPayloadCache.payload_type == "COMPANY"
    ).all()

    c_max = min(c_max, len(iscraper_cache) - 1)

    send_slack_message(
        message=f"Backfilling Companies: {c_min}/{c_max}...",
        webhook_urls=[URL_MAP["eng-sandbox"]],
    )

    print(f"Processing {c_min}/{c_max}...")

    c_count = 0
    for index in range(c_min, c_max):
        cache = iscraper_cache[index]
        result = json.loads(cache.payload)
        processed = add_company_cache_to_db.delay(result)
        if processed:
            c_count += 1

    return c_count


@celery.task
def add_company_cache_to_db(json_data) -> bool:
    details = json_data.get("details", None)
    if not details:
        print(f"No details for company...")
        return False

    name = details.get("name", None)
    universal_name = details.get("universal_name", None)

    type = details.get("name", None)

    img_cover_url = (details.get("images") or {}).get("cover", None)
    img_logo_url = (details.get("images") or {}).get("logo", None)

    li_followers = details.get("followers", None)
    li_company_id = details.get("company_id", None)

    phone = details.get("phone")

    websites = []
    urls = details.get("urls") or {}
    for value in urls.values():
        websites.append(value)

    employees = details.get("staff", {}).get("total", None)

    founded_year = (details.get("founded") or {}).get("year", None)

    description = details.get("description", None)

    specialities = details.get("specialities", [])
    industries = details.get("industries", [])

    loc_head = (details.get("locations") or {}).get("headquarter", {})
    loc_others = (details.get("locations") or {}).get("other", [])

    if loc_head:
        loc_head["is_headquarter"] = True
        locations = [loc_head]
    else:
        locations = []

    for loc in loc_others:
        loc["is_headquarter"] = False
        locations.append(loc)

    career_page_url = (details.get("call_to_action") or {}).get("url", None)

    company: Company = Company.query.filter(
        Company.universal_name == universal_name
    ).first()
    if company:
        print(f"Skipping existing company: {universal_name}")
    else:
        company = Company(
            name=name,
            universal_name=universal_name,
            type=type,
            img_cover_url=img_cover_url,
            img_logo_url=img_logo_url,
            li_followers=li_followers,
            li_company_id=li_company_id,
            phone=phone,
            websites=websites,
            employees=employees,
            founded_year=founded_year,
            description=description,
            specialities=specialities,
            industries=industries,
            locations=locations,
            career_page_url=career_page_url,
        )

        db.session.add(company)
        db.session.commit()
        print(f"Added company: {universal_name}")

    # Add company relations
    if company:
        relations = json_data.get("related_companies") or []
        if len(relations) > 0:
            print(f"Found {len(relations)} company relations...")
        for relation in relations:
            other_company: Company = Company.query.filter(
                Company.universal_name == relation.get("universal_name")
            ).first()
            if not other_company:
                print(
                    f'- No record of company found for: {relation.get("universal_name")}'
                )
                continue

            id_pair = get_unique_int(company.id, other_company.id)
            company_relation: CompanyRelation = CompanyRelation.query.get(id_pair)
            if company_relation:
                print(
                    f"- Skipping company relation: {company_relation.company_id_1} <-> {company_relation.company_id_2}"
                )
            else:
                company_relation = CompanyRelation(
                    id_pair=id_pair,
                    company_id_1=company.id,
                    company_id_2=other_company.id,
                )
                db.session.add(company_relation)
                db.session.commit()
                print(
                    f"- Added company relation: {company_relation.company_id_1} <-> {company_relation.company_id_2}"
                )

    return True


def company_backfill_prospects(client_sdr_id: int):
    prospects = Prospect.query.filter(
        Prospect.client_sdr_id == client_sdr_id,
        Prospect.company_id == None,
    ).all()

    print(f"Processing {len(prospects)} prospects...")

    c_count = 0
    for prospect in prospects:
        success = find_company_for_prospect.delay(prospect.id)
        if success:
            c_count += 1

    return c_count


@celery.task
def find_company_for_prospect(prospect_id: int) -> Company:
    prospect: Prospect = Prospect.query.get(prospect_id)
    if prospect.company_id:
        return Company.query.get(prospect.company_id)

    company: Company = Company.query.filter(
        or_(
            Company.name == prospect.company,
            Company.universal_name == prospect.company,
            Company.websites.any(prospect.company_url),
        ),
    ).first()

    if company:
        prospect.company_id = company.id
        prospect.company = company.name
        prospect.company_url = (
            company.websites[0] if len(company.websites) > 0 else None
        )
        prospect.employee_count = company.employees
        db.session.commit()
        return company
    else:
        return None


def find_company(company_name: str, company_url: str = "") -> Optional[int]:
    company: Company = Company.query.filter(
        or_(
            Company.name == company_name,
            Company.universal_name == company_name,
            Company.websites.any(company_url),
        ),
    ).first()

    return company.id if company else None


def find_sdr_from_slack(user_name: str, user_id: str, team_domain: str):
    sdr: ClientSDR = ClientSDR.query.filter(
        ClientSDR.slack_user_id == user_id,
    ).first()

    return (sdr.to_dict(), sdr.auth_token) if sdr else (None, None)


def authorize_slack_user(client_sdr_id: int, user_id: str):
    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)

    if sdr:
        sdr.slack_user_id = user_id
        db.session.commit()
        return True

    return False


def company_detail(company_id: int, client_sdr_id: int):
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client_id = client_sdr.client_id

    query = """
        select
            company.name "name",
            company.websites "websites",
            company.description "description",
            company.industries "industries",
            company.locations "locations",
            company.specialities "specialties",
            company.employees "num_employees",
            company.founded_year "founded_year"
        from company
            join prospect on prospect.company_id = company.id
        where company.id = {COMPANY_ID}
            and prospect.client_id = {CLIENT_ID}
    """.format(
        COMPANY_ID=company_id, CLIENT_ID=client_id
    )

    result = db.session.execute(query).fetchone()
    if result is not None:
        result = dict(result)

    return result


def get_timeline(company_id: int, client_sdr_id: int):
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client_id = client_sdr.client_id

    query = """
        with d as (
            select 
                prospect.first_name,
                prospect.full_name,
                prospect.title,
                prospect.company,
                case
                    when prospect_status_records.to_status is not null
                        then prospect_status_records.created_at
                    else
                        prospect_email_status_records.created_at
                end created_at,
                case
                    when prospect_status_records.to_status is not null
                        then 'LinkedIn'
                    else
                        'Email'
                end channel,
                case
                    when prospect_status_records.to_status is not null
                        then cast(prospect_status_records.to_status as varchar)
                    else
                        cast(prospect_email_status_records.to_status as varchar)
                end status,
                client_sdr.name "rep"
            from prospect
                join client_sdr on client_sdr.id = prospect.client_sdr_id
                left join prospect_status_records on prospect_status_records.prospect_id = prospect.id 
                left join prospect_email on prospect_email.prospect_id = prospect.id
                left join prospect_email_status_records on prospect_email_status_records.prospect_email_id = prospect_email.id
            where 
                prospect.client_id = {CLIENT_ID} and
                (
                    prospect_email_status_records.to_status in ('ACTIVE_CONVO', 'DEMO_SET', 'EMAIL_OPENED')
                    or prospect_status_records.to_status in ('ACCEPTED', 'ACTIVE_CONVO', 'DEMO_SET')
                ) and 
                prospect.company_id = {COMPANY_ID}
            group by 1,2,3,4,5,6,7,8
            order by case
                when prospect_status_records.to_status is not null
                    then prospect_status_records.created_at
                else
                    prospect_email_status_records.created_at
            end desc
        )
        select 
            concat(
                d.first_name, ' moved to `', lower(replace(d.status, '_', ' ')), '` on ', d.channel, ' - ', to_char(d.created_at, 'MM/DD/YYYY')
            ) title,
            concat(
                d.full_name, ' is ', d.rep, ' contact and is currently the ', d.title, ' at ', d.company
            ) subtitle
        from d;
    """.format(
        COMPANY_ID = company_id,
        CLIENT_ID= client_id
    )

    result = db.session.execute(query).fetchall()
    if result is not None:
        result = [dict(row) for row in result]

    return result


def prospect_engagement(company_id: int, client_sdr_id: int):
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client_id = client_sdr.client_id

    query = """
        select 
            prospect.full_name "contact",
            prospect.title "title",
            client_sdr.name "rep_name",
            case 
                when prospect.approved_outreach_message_id is not null or prospect.approved_prospect_email_id is not null
                    then 'engaged'
                else 'sourced'
            end status
        from prospect
            join client_sdr on client_sdr.id = prospect.client_sdr_id
        where 
            prospect.company_id = {COMPANY_ID}
            and prospect.client_id = {CLIENT_ID}
    """.format(
        COMPANY_ID = company_id,
        CLIENT_ID = client_id
    )

    result = db.session.execute(query).fetchall()
    if result is not None:
        result = [dict(row) for row in result]

    return result
