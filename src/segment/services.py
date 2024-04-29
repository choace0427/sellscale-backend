import yaml
from typing import Optional
from sqlalchemy import or_, and_

from regex import E
from app import db
from sqlalchemy.orm import attributes
from src.client.models import ClientArchetype, ClientSDR
from src.contacts.models import SavedApolloQuery
from src.ml.services import get_text_generation
from src.prospecting.icp_score.models import ICPScoringRuleset
from src.prospecting.icp_score.services import update_icp_filters
from src.prospecting.models import Prospect, ProspectOverallStatus, ProspectUploadHistory
from src.segment.models import Segment
from sqlalchemy import case
from sqlalchemy.orm.attributes import flag_modified


def create_new_segment(
    client_sdr_id: int, segment_title: str, filters: dict, parent_segment_id: int = None
) -> Segment or None:
    existing_segment = Segment.query.filter_by(
        client_sdr_id=client_sdr_id, segment_title=segment_title
    ).first()
    if existing_segment:
        return None
    
    parent_segment: Segment = Segment.query.get(parent_segment_id)
    saved_apollo_query_id = None
    if parent_segment:
        saved_apollo_query_id = parent_segment.saved_apollo_query_id

    new_segment = Segment(
        client_sdr_id=client_sdr_id,
        segment_title=segment_title,
        filters=filters,
        parent_segment_id=parent_segment_id,
        saved_apollo_query_id=saved_apollo_query_id,
    )

    db.session.add(new_segment)
    db.session.commit()

    return new_segment


def get_segments_for_sdr(sdr_id: int, include_all_in_client: bool = False) -> list[dict]:
    client_sdr: ClientSDR = ClientSDR.query.get(sdr_id)
    client_id: int = client_sdr.client_id
    client_sdrs: list[ClientSDR] = ClientSDR.query.filter_by(client_id=client_id).all()
    
    if not include_all_in_client:
        all_segments: list[Segment] = Segment.query.filter_by(client_sdr_id=sdr_id).all()
    else:
        all_segments: list[Segment] = Segment.query.filter(
            Segment.client_sdr_id.in_([sdr.id for sdr in client_sdrs])
        ).all()

    num_contacted_prospected_for_segments_query = """
        select 
            segment_id, 
            count(distinct prospect.id) num_prospected,
            count(distinct prospect.id) filter (where prospect.approved_prospect_email_id is not null or prospect.approved_outreach_message_id is not null) num_contacted
        from prospect
        where prospect.segment_id is not null
            and prospect.client_id = {client_id}
        group by 1;
    """

    num_prospected_for_segments = db.session.execute(
        num_contacted_prospected_for_segments_query.format(client_id=client_id)
    ).fetchall()
    retval = [segment.to_dict() for segment in all_segments]

    for segment_dict in retval:
        segment_id = segment_dict["id"]
        for row in num_prospected_for_segments:
            if row[0] == segment_id:
                segment_dict["num_prospected"] = row[1]
                segment_dict["num_contacted"] = row[2]

    # order by segment ID reverse order
    retval = sorted(retval, key=lambda x: x["id"], reverse=True)

    return retval


def get_base_segment_for_archetype(archetype_id: int) -> Segment:
    client_archetype: ClientArchetype = ClientArchetype.query.get(archetype_id)
    if not client_archetype:
        return None
    if not client_archetype.base_segment_id:
        segment: Segment = create_new_segment(
            client_sdr_id=client_archetype.client_sdr_id,
            segment_title=client_archetype.archetype,
            filters={},
        )
        client_archetype.base_segment_id = segment.id
        db.session.commit()

    return client_archetype.base_segment_id


def get_prospect_ids_for_segment(segment_id: int) -> list[int]:
    prospects: list[Prospect] = Prospect.query.filter_by(segment_id=segment_id).all()
    return [prospect.id for prospect in prospects]


def update_segment(
    client_sdr_id: int,
    segment_id: int,
    segment_title: str,
    filters: dict,
    client_archetype_id: Optional[int] = None,
) -> Segment:
    segment: Segment = Segment.query.filter_by(
        client_sdr_id=client_sdr_id, id=segment_id
    ).first()

    if not segment:
        return None

    if segment_title:
        segment.segment_title = segment_title

    if filters:
        segment.filters = filters

    if client_archetype_id:
        segment.client_archetype_id = client_archetype_id

    db.session.add(segment)
    db.session.commit()

    if client_archetype_id:
        # If we attached segement to campaign, add existing contacts to campaign
        success, msg = add_unused_prospects_in_segment_to_campaign(
            segment_id=segment_id, campaign_id=client_archetype_id
        )

    return segment


def merge_segment_filters(segment_id: int, segment_filters: dict):
    # Merge the segment filters to include the most out of both
    segment: Segment = Segment.query.get(segment_id)
    if segment:
        existing_filters = segment.filters or {}
        for key, value in segment_filters.items():
            if key in existing_filters:
                if existing_filters[key] is None:
                    existing_filters[key] = value
                elif isinstance(existing_filters[key], list) and isinstance(
                    value, list
                ):
                    existing_filters[key] = list(set(existing_filters[key] + value))
            else:
                existing_filters[key] = value
        segment.filters = existing_filters

        flag_modified(segment, "filters")
        db.session.add(segment)
        db.session.commit()


def delete_segment(client_sdr_id: int, segment_id: int) -> tuple[bool, str]:
    segment = Segment.query.filter_by(
        client_sdr_id=client_sdr_id, id=segment_id
    ).first()

    if not segment:
        return False, "Segment not found"

    prospects_with_segment: list[Prospect] = Prospect.query.filter_by(
        segment_id=segment_id
    ).all()
    if len(prospects_with_segment) > 0:
        return False, "Segment has prospects"
    
    # remove upload history records
    upload_history_records: list[ProspectUploadHistory] = ProspectUploadHistory.query.filter(
        ProspectUploadHistory.client_segment_id == segment_id
    ).all()
    for record in upload_history_records:
        record.client_segment_id = None
        db.session.add(record)
    db.session.commit()

    # any child segment should be moved to parent
    child_segments: list[Segment] = Segment.query.filter_by(
        parent_segment_id=segment_id
    ).all()
    for child_segment in child_segments:
        child_segment.parent_segment_id = None
        db.session.add(child_segment)
    db.session.commit()

    db.session.delete(segment)
    db.session.commit()

    return True, "Segment deleted"


def add_prospects_to_segment(prospect_ids: list[int], new_segment_id: int):
    batch_size = 50

    segment: Segment = Segment.query.get(new_segment_id)

    if segment.client_archetype_id:
        archetype: ClientArchetype = ClientArchetype.query.get(
            segment.client_archetype_id
        )

        for i in range(0, len(prospect_ids), batch_size):
            batch_prospect_ids = prospect_ids[i : i + batch_size]
            Prospect.query.filter(Prospect.id.in_(batch_prospect_ids)).update(
                {
                    Prospect.segment_id: new_segment_id,
                    Prospect.archetype_id: archetype.id,
                },
                synchronize_session=False,
            )
            db.session.commit()

    else:
        for i in range(0, len(prospect_ids), batch_size):
            batch_prospect_ids = prospect_ids[i : i + batch_size]
            Prospect.query.filter(Prospect.id.in_(batch_prospect_ids)).update(
                {
                    Prospect.segment_id: new_segment_id,
                },
                synchronize_session=False,
            )
            db.session.commit()

    return True, "Prospects added to segment"


def find_prospects_by_segment_filters(
    client_sdr_id: int,
    segment_ids: list[int] = [],
    included_title_keywords: list[str] = [],
    excluded_title_keywords: list[str] = [],
    included_seniority_keywords: list[str] = [],
    excluded_seniority_keywords: list[str] = [],
    included_company_keywords: list[str] = [],
    excluded_company_keywords: list[str] = [],
    included_education_keywords: list[str] = [],
    excluded_education_keywords: list[str] = [],
    included_bio_keywords: list[str] = [],
    excluded_bio_keywords: list[str] = [],
    included_location_keywords: list[str] = [],
    excluded_location_keywords: list[str] = [],
    included_skills_keywords: list[str] = [],
    excluded_skills_keywords: list[str] = [],
    years_of_experience_start: int = None,
    years_of_experience_end: int = None,
    archetype_ids: list[int] = [],
    included_industry_keywords: list[str] = [],
    excluded_industry_keywords: list[str] = [],
) -> list[dict]:
    # join prospect with segment and get segment_title
    # keep 'Uncategorized' if no segment present

    base_query = (
        Prospect.query.join(
            ClientArchetype, Prospect.archetype_id == ClientArchetype.id
        )
        .join(ClientSDR, Prospect.client_sdr_id == ClientSDR.id)
        .outerjoin(Segment, Prospect.segment_id == Segment.id)
        .with_entities(
            Prospect.id,
            Prospect.full_name,
            Prospect.title,
            Prospect.company,
            Prospect.linkedin_url,
            Prospect.industry,
            ClientArchetype.archetype,
            case(
                [(Segment.segment_title == None, "uncategorized")],  # type: ignore
                else_=Segment.segment_title,
            ).label("segment_title"),
        )
        .filter(ClientSDR.id == client_sdr_id)
    )

    if segment_ids:
        base_query = base_query.filter(Segment.id.in_(segment_ids))

    if archetype_ids:
        base_query = base_query.filter(Prospect.archetype_id.in_(archetype_ids))

    if included_title_keywords:
        or_addition = []
        for keyword in included_title_keywords:
            or_addition.append(Prospect.title.ilike(f"%{keyword}%"))
        if len(or_addition) > 1:
            base_query = base_query.filter(or_(*or_addition))
        else:
            base_query = base_query.filter(or_addition[0])

    if excluded_title_keywords:
        and_addition = []
        for keyword in excluded_title_keywords:
            and_addition.append(~Prospect.title.ilike(f"%{keyword}%"))
        if len(and_addition) > 1:
            base_query = base_query.filter(and_(*and_addition))
        else:
            base_query = base_query.filter(and_addition[0])

    if included_seniority_keywords:
        or_addition = []
        for keyword in included_seniority_keywords:
            or_addition.append(Prospect.title.ilike(f"%{keyword}%"))
        if len(or_addition) > 1:
            base_query = base_query.filter(or_(*or_addition))
        else:
            base_query = base_query.filter(or_addition[0])

    if excluded_seniority_keywords:
        and_addition = []
        for keyword in excluded_seniority_keywords:
            and_addition.append(~Prospect.title.ilike(f"%{keyword}%"))
        if len(and_addition) > 1:
            base_query = base_query.filter(and_(*and_addition))
        else:
            base_query = base_query.filter(and_addition[0])

    if included_company_keywords:
        or_addition = []
        for keyword in included_company_keywords:
            or_addition.append(Prospect.company.ilike(f"%{keyword}%"))
        if len(or_addition) > 1:
            base_query = base_query.filter(or_(*or_addition))
        else:
            base_query = base_query.filter(or_addition[0])

    if excluded_company_keywords:
        and_addition = []
        for keyword in excluded_company_keywords:
            and_addition.append(~Prospect.company.ilike(f"%{keyword}%"))
        if len(and_addition) > 1:
            base_query = base_query.filter(and_(*and_addition))
        else:
            base_query = base_query.filter(and_addition[0])

    if included_education_keywords:
        and_addition = []
        for keyword in included_education_keywords:
            and_addition.append(
                or_(
                    Prospect.education_1.ilike(f"%{keyword}%"),
                    Prospect.education_2.ilike(f"%{keyword}%"),
                )
            )
        if len(and_addition) > 1:
            base_query = base_query.filter(and_(*and_addition))
        else:
            base_query = base_query.filter(and_addition[0])

    if excluded_education_keywords:
        and_addition = []
        for keyword in excluded_education_keywords:
            and_addition.append(
                and_(
                    ~Prospect.education_1.ilike(f"%{keyword}%"),
                    ~Prospect.education_2.ilike(f"%{keyword}%"),
                )
            )
        if len(and_addition) > 1:
            base_query = base_query.filter(and_(*and_addition))
        else:
            base_query = base_query.filter(and_addition[0])

    if included_bio_keywords:
        or_addition = []
        for keyword in included_bio_keywords:
            or_addition.append(Prospect.linkedin_bio.ilike(f"%{keyword}%"))
        if len(or_addition) > 1:
            base_query = base_query.filter(or_(*or_addition))
        else:
            base_query = base_query.filter(or_addition[0])

    if excluded_bio_keywords:
        and_addition = []
        for keyword in excluded_bio_keywords:
            and_addition.append(~Prospect.linkedin_bio.ilike(f"%{keyword}%"))
        if len(and_addition) > 1:
            base_query = base_query.filter(and_(*and_addition))
        else:
            base_query = base_query.filter(and_addition[0])

    if included_industry_keywords:
        or_addition = []
        for keyword in included_industry_keywords:
            or_addition.append(Prospect.industry.ilike(f"%{keyword}%"))
        if len(or_addition) > 1:
            base_query = base_query.filter(or_(*or_addition))
        else:
            base_query = base_query.filter(or_addition[0])

    if excluded_industry_keywords:
        and_addition = []
        for keyword in excluded_industry_keywords:
            and_addition.append(~Prospect.industry.ilike(f"%{keyword}%"))
        if len(and_addition) > 1:
            base_query = base_query.filter(and_(*and_addition))
        else:
            base_query = base_query.filter(and_addition[0])

    if included_location_keywords:
        or_addition = []
        for keyword in included_location_keywords:
            or_addition.append(Prospect.prospect_location.ilike(f"%{keyword}%"))
        if len(or_addition) > 1:
            base_query = base_query.filter(or_(*or_addition))
        else:
            base_query = base_query.filter(or_addition[0])

    if excluded_location_keywords:
        and_addition = []
        for keyword in excluded_location_keywords:
            and_addition.append(~Prospect.prospect_location.ilike(f"%{keyword}%"))
        if len(and_addition) > 1:
            base_query = base_query.filter(and_(*and_addition))
        else:
            base_query = base_query.filter(and_addition[0])

    prospects = base_query.all()

    return [
        {
            "id": prospect.id,
            "name": prospect.full_name,
            "title": prospect.title,
            "company": prospect.company,
            "campaign": prospect.archetype,
            "segment": prospect.segment_title,
            "linkedin_url": prospect.linkedin_url,
            "industry": prospect.industry,
        }
        for prospect in prospects
    ]


def extract_data_from_sales_navigator_link(
    sales_nav_url: str,
):
    response = get_text_generation(
        [
            {
                "role": "user",
                "content": f"""
Using this Sales Navigator URL:
```
{sales_nav_url}
```

Return a list of the job titles by parsing the URL above and return in a valid JSON formatted as {{data: [titles array]}}

Respond with only the JSON.

JSON:""",
            },
        ],
        max_tokens=600,
        model="gpt-4",
        type="ICP_CLASSIFY",
    )

    titles = []
    try:
        data: dict = yaml.safe_load(response)
        titles = data.get("data", [])
    except:
        return {}

    return {
        "titles": titles,
    }


def wipe_segment_ids_from_prospects_in_segment(segment_id: int):
    Prospect.query.filter(Prospect.segment_id == segment_id).update(
        {Prospect.segment_id: None}, synchronize_session=False
    )
    db.session.commit()

    return True, "Prospects removed from segment"


def add_segment_filters_to_icp_scoring_ruleset_for_campaign(
    segment_id: int,
    campaign_id: int,
):
    segment: Segment = Segment.query.filter_by(id=segment_id).first()
    if not segment:
        return False, "Segment not found"

    MAP_SEGMENT_FILTER_TO_ICP_FILTER = {
        "included_title_keywords": "included_individual_title_keywords",
        "excluded_title_keywords": "excluded_individual_title_keywords",
        "included_seniority_keywords": "included_individual_seniority_keywords",
        "excluded_seniority_keywords": "excluded_individual_seniority_keywords",
        "included_company_keywords": "included_company_name_keywords",
        "excluded_company_keywords": "excluded_company_name_keywords",
        "included_education_keywords": "included_individual_education_keywords",
        "excluded_education_keywords": "excluded_individual_education_keywords",
        "included_bio_keywords": "included_individual_generalized_keywords",
        "excluded_bio_keywords": "excluded_individual_generalized_keywords",
        "included_location_keywords": "included_individual_locations_keywords",
        "excluded_location_keywords": "excluded_individual_locations_keywords",
        "included_skills_keywords": "included_individual_skills_keywords",
        "excluded_skills_keywords": "excluded_individual_skills_keywords",
        "years_of_experience_start": "individual_years_of_experience_start",
        "years_of_experience_end": "individual_years_of_experience_end",
        "included_company_size": "company_size_start",
        "included_industry_keywords": "included_individual_industry_keywords",
        "excluded_industry_keywords": "excluded_individual_industry_keywords",
    }

    updated_filters = {}
    for segment_filter, icp_filter in MAP_SEGMENT_FILTER_TO_ICP_FILTER.items():
        if segment_filter in segment.filters:
            updated_filters[icp_filter] = segment.filters[segment_filter]

    update_icp_filters(
        client_archetype_id=campaign_id, filters=updated_filters, merge=True
    )


def add_unused_prospects_in_segment_to_campaign(segment_id: int, campaign_id: int):
    prospects: list[Prospect] = Prospect.query.filter(
        and_(
            Prospect.segment_id == segment_id,
            Prospect.overall_status == ProspectOverallStatus.PROSPECTED,
            Prospect.approved_outreach_message_id == None,
            Prospect.approved_prospect_email_id == None,
        )
    ).all()

    prospect_ids: list[int] = [prospect.id for prospect in prospects]

    Prospect.query.filter(Prospect.id.in_(prospect_ids)).update(
        {Prospect.archetype_id: campaign_id}, synchronize_session=False
    )
    db.session.commit()

    add_segment_filters_to_icp_scoring_ruleset_for_campaign(
        segment_id=segment_id, campaign_id=campaign_id
    )

    return True, "Prospects added to campaign"


def remove_prospect_from_segment(client_sdr_id: int, prospect_ids: list[int]):
    prospects: list[Prospect] = Prospect.query.filter(
        and_(Prospect.client_sdr_id == client_sdr_id, Prospect.id.in_(prospect_ids))
    ).all()

    for prospect in prospects:
        prospect.segment_id = None
        db.session.add(prospect)

    db.session.commit()
    return True, "Prospects removed from segment"


def move_segment_prospects(
    client_sdr_id: int, from_segment_id: int, to_segment_id: int
):
    prospects: list[Prospect] = Prospect.query.filter(
        and_(
            Prospect.segment_id == from_segment_id,
        )
    ).all()

    if to_segment_id == 0:
        Prospect.query.filter(Prospect.id.in_([prospect.id for prospect in prospects])).update(
            {"segment_id": None}, synchronize_session=False
        )
    else:
        Prospect.query.filter(Prospect.id.in_([prospect.id for prospect in prospects])).update(
            {"segment_id": to_segment_id}, synchronize_session=False
        )

    db.session.commit()
    return True, "Prospects moved to segment"


def wipe_and_delete_segment(client_sdr_id: int, segment_id: int):
    segment: Segment = Segment.query.filter_by(id=segment_id).first()

    # If segment is child, move to parent else move to segment 0
    if segment and segment.parent_segment_id:
        move_segment_prospects(
            client_sdr_id=client_sdr_id,
            from_segment_id=segment_id,
            to_segment_id=segment.parent_segment_id,
        )
    else:
        move_segment_prospects(
            client_sdr_id=client_sdr_id,
            from_segment_id=segment_id,
            to_segment_id=0
        )

    # wipe_segment_ids_from_prospects_in_segment(segment_id)
    success, msg = delete_segment(client_sdr_id, segment_id)
    if not success:
        return False, msg
    return True, "Segment wiped and deleted"


def get_segment_predicted_prospects(
    client_sdr_id: int,
    prospect_industries: list[str] = [],
    prospect_seniorities: list[str] = [],
    prospect_education: list[str] = [],
    prospect_titles: list[str] = [],
    companies: list[str] = [],
    company_sizes: list[tuple[int, int]] = [],
):
    prospect_industries = prospect_industries + [""]
    prospect_seniorities = prospect_seniorities + [""]
    prospect_titles = prospect_titles + [""]
    prospect_education = prospect_education + [""]
    companies = companies + [""]
    company_size = company_sizes + [None]
    permutations = []
    index_to_permutation_map = {}
    index = 0
    index_to_summary_map = {}
    for industry in prospect_industries:
        for seniority in prospect_seniorities:
            for education in prospect_education:
                for title in prospect_titles:
                    for company in companies:
                        for size in company_size:
                            print("size: " + str(size))
                            summary = ""
                            if industry:
                                summary += "(✅ industry: {industry}) ".format(
                                    industry=industry
                                )
                            if seniority:
                                summary += "(✅ seniority: {seniority}) ".format(
                                    seniority=seniority
                                )
                            if title:
                                summary += "(✅ title: {title}) ".format(title=title)
                            if education:
                                summary += "(✅ education: {education}) ".format(
                                    education=education
                                )
                            if company:
                                summary += "(✅ company: {company}) ".format(
                                    company=company
                                )
                            if size:
                                summary += "(✅ size: {size}) ".format(
                                    size=(
                                        str(size[0]) + " - " + str(size[1])
                                        if size
                                        else "any"
                                    )
                                )
                            if not summary:
                                summary = "any"

                            size_query = "1=1"
                            if size:
                                size_query = f"prospect.company_size >= {size[0]} and prospect.company_size <= {size[1]}"

                            permutation = {
                                "industry": industry,
                                "seniority": seniority,
                                "title": title,
                                "education": education,
                                "company": company,
                                "size": size,
                                "sql_query": "prospect.industry ilike '%{industry}%' and prospect.title ilike '%{title}%' and prospect.title ilike '%{seniority}%' and prospect.company ilike '%{company}%' and (prospect.education_1 ilike '%{education}%' or prospect.education_2 ilike '%{education}%') and {size_query}".format(
                                    industry=industry,
                                    title=title,
                                    education=education,
                                    seniority=seniority,
                                    company=company,
                                    size_query=size_query,
                                ),
                                "summary": summary,
                                "index": index,
                            }
                            permutations.append(permutation)
                            index_to_permutation_map[index] = permutation
                            index_to_summary_map[index] = summary

                            index += 1

    columns = []
    for i, permutation in enumerate(permutations):
        columns.append(
            'array_agg(distinct prospect.id) filter (where {sql_query}) as "{index}"'.format(
                sql_query=permutation["sql_query"], index=permutation["index"]
            )
        )
    columns = ",\n".join(columns)

    query = """
        select
            {columns}
        from prospect
        where prospect.client_sdr_id = {client_sdr_id}
            and prospect.segment_id is null
    """.format(
        columns=columns, client_sdr_id=client_sdr_id
    )

    print(query)

    result = db.session.execute(query).fetchall()
    data = []
    for row in result:
        for i, column in enumerate(row.keys()):
            if row[i] == 0:
                continue
            data.append(
                {
                    "summary": index_to_summary_map[int(column)],
                    "num_prospects": len(row[i]) if row[i] else 0,
                    "prospect_ids": row[i],
                    # "permutation": index_to_permutation_map[int(column)],
                }
            )

    order_data_by_num_prospects = sorted(
        data, key=lambda x: x["num_prospects"], reverse=True
    )

    return order_data_by_num_prospects


def get_unused_segments_for_sdr(client_sdr_id: int):
    query = """
        select
            segment.segment_title,
            segment_id,
            count(distinct prospect.id),
            array_agg(distinct client_archetype.archetype)
        from
            prospect
            join segment on segment.id = prospect.segment_id
            join client_archetype on client_archetype.id = prospect.archetype_id
        where
            prospect.client_sdr_id = {client_sdr_id}
        group by 1, 2
        having count(distinct prospect.id) filter (where client_archetype.is_unassigned_contact_archetype) = count(distinct prospect.id);
    """

    result = db.session.execute(query.format(client_sdr_id=client_sdr_id)).fetchall()

    data = []
    for row in result:
        data.append(
            {
                "segment_title": row[0],
                "segment_id": row[1],
                "num_prospects": row[2],
                "distinct_archetypes": row[3],
            }
        )

    return data

def connect_saved_apollo_query_to_segment(segment_id: int, saved_apollo_query_id: int):
    segment: Segment = Segment.query.get(segment_id)
    if not segment:
        return False, "Segment not found"
    
    saved_apollo_query: SavedApolloQuery = SavedApolloQuery.query.get(saved_apollo_query_id)
    if not saved_apollo_query:
        return False, "Apollo query not found"
    
    if saved_apollo_query.client_sdr_id != segment.client_sdr_id:
        return False, "Apollo query and segment belong to different SDRs"

    segment.saved_apollo_query_id = saved_apollo_query_id
    db.session.add(segment)
    db.session.commit()

    return True, "Apollo query connected to segment"

def duplicate_segment(
    segment_id: int,
):
    """
    Creates a duplicate of the segment with the same filters and title for the same SDR
    """

    segment: Segment = Segment.query.get(segment_id)
    if not segment:
        return False, "Segment not found"

    new_segment = Segment(
        client_sdr_id=segment.client_sdr_id,
        segment_title="[Duplicate] " + segment.segment_title,
        filters=segment.filters,
        parent_segment_id=segment.parent_segment_id,
        saved_apollo_query_id=segment.saved_apollo_query_id,
    )

    db.session.add(new_segment)
    db.session.commit()

    return True, "Segment duplicated"

def move_segment(
    client_sdr_id: int,
    segment_id: int,
    new_parent_segment_id: Optional[int],
):
    """
    Moves the segment to a new parent segment or to the root level
    """
    segment: Segment = Segment.query.get(segment_id)
    if not segment:
        return False, "Segment not found"
    if segment.client_sdr_id != client_sdr_id:
        return False, "Segment does not belong to current SDR"

    if new_parent_segment_id:
        new_parent_segment: Segment = Segment.query.get(new_parent_segment_id)
        if not new_parent_segment:
            return False, "New parent segment not found"
        if new_parent_segment.client_sdr_id != segment.client_sdr_id:
            return False, "New parent segment belongs to a different SDR"
    
    segment.parent_segment_id = new_parent_segment_id
    db.session.add(segment)
    db.session.commit()

    return True, "Segment moved"

def transfer_segment(
        current_client_sdr_id: int,
        segment_id: int, 
        new_client_sdr_id: int):
    """
    Transfers a segment to a new SDR which means that all prospected prospects in the segment will be transferred to the new SDR
    (i.e. folks who do not have any outreach message or email approved will be transferred to the new SDR)
    """
    # verify that current SDR has access to the segment
    segment: Segment = Segment.query.get(segment_id)
    if not segment:
        return False, "Segment not found"
    if segment.client_sdr_id != current_client_sdr_id:
        return False, "Segment does not belong to current SDR"

    prospects: list[Prospect] = Prospect.query.filter(
        and_(
            Prospect.segment_id == segment_id,
            Prospect.overall_status == ProspectOverallStatus.PROSPECTED,
            Prospect.approved_outreach_message_id == None,
            Prospect.approved_prospect_email_id == None,
        )
    ).all()

    unassigned_archetype: ClientArchetype = ClientArchetype.query.filter_by(
        client_sdr_id=new_client_sdr_id, is_unassigned_contact_archetype=True
    ).first()
    if not unassigned_archetype:
        return False, "Unassigned archetype not found for new SDR"
    
    Prospect.query.filter(
        Prospect.id.in_([prospect.id for prospect in prospects])
    ).update({
        Prospect.client_sdr_id: new_client_sdr_id,
        Prospect.archetype_id: unassigned_archetype.id
    }, synchronize_session=False)
    db.session.commit()

    saved_apollo_query: SavedApolloQuery = SavedApolloQuery.query.filter_by(
        id=segment.saved_apollo_query_id
    ).first()
    if saved_apollo_query:
        saved_apollo_query.client_sdr_id = new_client_sdr_id
        db.session.add(saved_apollo_query)
        db.session.commit()


    segment: Segment = Segment.query.get(segment_id)
    segment.client_sdr_id = new_client_sdr_id
    segment.client_archetype_id = None
    db.session.add(segment)
    db.session.commit()

    return True, "Segment transferred to new SDR"

def create_n_sub_batches_for_segment(
    segment_id: int,
    num_batches: int
):
    """
    Finds all unused prospects in the current segment and creates `num_batches` subsegments as 
    child segments of the current segment. Each subsegment will have an equal number of prospects
    added to it.
    """
    original_segment: Segment = Segment.query.get(segment_id)
    unused_prospects = Prospect.query.filter(
        Prospect.segment_id == segment_id,
        Prospect.approved_outreach_message_id == None,
        Prospect.approved_prospect_email_id == None,
    ).all()

    num_prospects = len(unused_prospects)
    num_prospects_per_batch = num_prospects // num_batches

    for i in range(num_batches):
        start_index = i * num_prospects_per_batch
        end_index = (i + 1) * num_prospects_per_batch
        if i == num_batches - 1:
            end_index = num_prospects
        prospects_in_batch = unused_prospects[start_index:end_index]
        prospect_ids = [prospect.id for prospect in prospects_in_batch]

        new_segment = create_new_segment(
            client_sdr_id=original_segment.client_sdr_id,
            segment_title=f"Batch {i + 1}: {original_segment.segment_title}",
            filters=original_segment.filters,
            parent_segment_id=segment_id,
        )

        add_prospects_to_segment(prospect_ids, new_segment.id)

    return True, "Subsegments created"