

import json
import math

from psycopg2 import IntegrityError

from src.company.models import Company, CompanyRelation
from src.research.models import IScraperPayloadCache
from app import db
from src.utils.math import get_unique_int


def company_backfill(c_min: int, c_max: int):

    iscraper_cache = IScraperPayloadCache.query.filter(
        IScraperPayloadCache.payload_type == 'COMPANY'
    ).all()
    
    c_max = min(c_max, len(iscraper_cache)-1)
    print(f'Processing {c_min}/{c_max}...')

    c_count = 0
    for index in range(c_min, c_max):
        cache = iscraper_cache[index]
        processed = add_company_cache_to_db(cache)
        if processed:
            c_count += 1

    return c_count


def add_company_cache_to_db(cache) -> bool:
    result = json.loads(cache.payload)

    details = result.get('details', None)
    if not details:
        print(f'No details for company...')
        return False

    name = details.get('name', None)
    universal_name = details.get('universal_name', None)

    type = details.get('name', None)

    img_cover_url = (details.get('images') or {}).get('cover', None)
    img_logo_url = (details.get('images') or {}).get('logo', None)

    li_followers = details.get('followers', None)
    li_company_id = details.get('company_id', None)

    phone = (details.get('phone') or {}).get('number', None)

    websites = []
    urls = (details.get('urls') or {})
    for value in urls.values():
        websites.append(value)

    employees = details.get('staff', {}).get('total', None)

    founded_year = (details.get('founded') or {}).get('year', None)

    description = details.get('description', None)

    specialities = details.get('specialities', [])
    industries = details.get('industries', [])

    loc_head = (details.get('locations') or {}).get('headquarter', {})
    loc_others = (details.get('locations') or {}).get('other', [])

    if loc_head:
        loc_head['is_headquarter'] = True
        locations = [loc_head]
    else:
        locations = []
    
    for loc in loc_others:
        loc['is_headquarter'] = False
        locations.append(loc)

    career_page_url = (details.get('call_to_action') or {}).get('url', None)

    company: Company = Company.query.filter(
        Company.universal_name == universal_name).first()
    if company:
        print(f'Skipping existing company: {universal_name}')
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
        print(f'Added company: {universal_name}')

    # Add company relations
    if company:
        relations = result.get('related_companies') or []
        if len(relations) > 0:
            print(f'Found {len(relations)} company relations...')
        for relation in relations:
            other_company: Company = Company.query.filter(Company.universal_name == relation.get('universal_name')).first()
            if not other_company: 
                print(f'- No record of company found for: {relation.get("universal_name")}')
                continue

            id_pair = get_unique_int(company.id, other_company.id)
            company_relation: CompanyRelation = CompanyRelation.query.get(id_pair)
            if company_relation:
                print(f'- Skipping company relation: {company_relation.company_id_1} <-> {company_relation.company_id_2}')
            else:
                company_relation = CompanyRelation(
                    id_pair=id_pair,
                    company_id_1=company.id,
                    company_id_2=other_company.id,
                )
                db.session.add(company_relation)
                db.session.commit()
                print(f'- Added company relation: {company_relation.company_id_1} <-> {company_relation.company_id_2}')

    return True


