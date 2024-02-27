import json
from sqlalchemy import or_, and_

from regex import E
from app import db
from sqlalchemy.orm import attributes
from src.client.models import ClientArchetype, ClientSDR
from src.ml.services import get_text_generation
from src.prospecting.icp_score.models import ICPScoringRuleset
from src.prospecting.icp_score.services import update_icp_filters
from src.prospecting.models import Prospect, ProspectOverallStatus
from src.segment.models import Segment
from sqlalchemy import case


def create_new_segment(
    client_sdr_id: int, segment_title: str, filters: dict, parent_segment_id: int = None
) -> Segment or None:
    existing_segment = Segment.query.filter_by(
        client_sdr_id=client_sdr_id, segment_title=segment_title
    ).first()
    if existing_segment:
        return None

    new_segment = Segment(
        client_sdr_id=client_sdr_id,
        segment_title=segment_title,
        filters=filters,
        parent_segment_id=parent_segment_id,
    )

    db.session.add(new_segment)
    db.session.commit()

    return new_segment


def get_segments_for_sdr(sdr_id: int) -> list[dict]:
    all_segments: list[Segment] = Segment.query.filter_by(client_sdr_id=sdr_id).all()
    return [segment.to_dict() for segment in all_segments]


def get_prospect_ids_for_segment(segment_id: int) -> list[int]:
    prospects: list[Prospect] = Prospect.query.filter_by(segment_id=segment_id).all()
    return [prospect.id for prospect in prospects]


def update_segment(
    client_sdr_id: int, segment_id: int, segment_title: str, filters: dict
) -> Segment:
    segment = Segment.query.filter_by(
        client_sdr_id=client_sdr_id, id=segment_id
    ).first()

    if not segment:
        return None

    if segment_title:
        segment.segment_title = segment_title

    if filters:
        segment.filters = filters

    db.session.add(segment)
    db.session.commit()

    return segment


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

    db.session.delete(segment)
    db.session.commit()

    return True, "Segment deleted"


def add_prospects_to_segment(prospect_ids: list[int], new_segment_id: int):
    batch_size = 50
    for i in range(0, len(prospect_ids), batch_size):
        batch_prospect_ids = prospect_ids[i : i + batch_size]
        Prospect.query.filter(Prospect.id.in_(batch_prospect_ids)).update(
            {Prospect.segment_id: new_segment_id}, synchronize_session=False
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
        data: dict = json.loads(response)
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


def wipe_and_delete_segment(client_sdr_id: int, segment_id: int):
    wipe_segment_ids_from_prospects_in_segment(segment_id)
    delete_segment(client_sdr_id, segment_id)
    return True, "Segment wiped and deleted"
