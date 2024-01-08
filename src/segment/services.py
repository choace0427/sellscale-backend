from app import db
from sqlalchemy.orm import attributes
from src.client.models import ClientArchetype, ClientSDR
from src.prospecting.models import Prospect
from src.segment.models import Segment


def create_new_segment(
    client_sdr_id: int, segment_title: str, filters: dict
) -> Segment or None:
    # dulicate check
    existing_segment = Segment.query.filter_by(
        client_sdr_id=client_sdr_id, segment_title=segment_title
    ).first()
    if existing_segment:
        return None

    new_segment = Segment(
        client_sdr_id=client_sdr_id,
        segment_title=segment_title,
        filters=filters,
    )

    db.session.add(new_segment)
    db.session.commit()

    return new_segment


def get_segments_for_sdr(sdr_id: int) -> list[dict]:
    all_segments: list[Segment] = Segment.query.filter_by(client_sdr_id=sdr_id).all()
    return [segment.to_dict() for segment in all_segments]


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
    Prospect.query.filter(Prospect.id.in_(prospect_ids)).update(
        {Prospect.segment_id: new_segment_id}, synchronize_session=False
    )
    db.session.commit()

    return True, "Prospects added to segment"


def find_prospects_by_segment_filters(
    client_sdr_id: int,
    included_title_keywords: list[str] = [],
    excluded_title_keywords: list[str] = [],
    included_seniority_keywords: list[str] = [],
    excluded_seniority_keywords: list[str] = [],
    included_company_keywords: list[str] = [],
    excluded_company_keywords: list[str] = [],
) -> list[dict]:
    base_query = (
        Prospect.query.join(ClientArchetype)
        .join(ClientSDR)
        .filter(ClientSDR.id == client_sdr_id)
    )

    if included_title_keywords:
        for keyword in included_title_keywords:
            base_query = base_query.filter(Prospect.title.ilike(f"%{keyword}%"))

    if excluded_title_keywords:
        for keyword in excluded_title_keywords:
            base_query = base_query.filter(~Prospect.title.ilike(f"%{keyword}%"))

    if included_seniority_keywords:
        for keyword in included_seniority_keywords:
            base_query = base_query.filter(Prospect.title.ilike(f"%{keyword}%"))

    if excluded_seniority_keywords:
        for keyword in excluded_seniority_keywords:
            base_query = base_query.filter(~Prospect.title.ilike(f"%{keyword}%"))

    if included_company_keywords:
        for keyword in included_company_keywords:
            base_query = base_query.filter(Prospect.company.ilike(f"%{keyword}%"))

    if excluded_company_keywords:
        for keyword in excluded_company_keywords:
            base_query = base_query.filter(~Prospect.company.ilike(f"%{keyword}%"))

    # extract just the columns I need:
    #             prospect.id,
    #     prospect.full_name "Name",
    #   prospect.title "Title",
    #   prospect.company "Company",
    #   client_archetype.archetype "Campaign",
    #   case
    #     when segment.segment_title is null then 'Uncategorized'
    #     else segment.segment_title
    #   end "Segment"

    prospects = base_query.with_entities(
        Prospect.id,
        Prospect.full_name,
        Prospect.title,
        Prospect.company,
        ClientArchetype.archetype,
        Segment.segment_title,
    ).all()

    return [
        {
            "id": prospect.id,
            "name": prospect.full_name,
            "title": prospect.title,
            "company": prospect.company,
            "campaign": prospect.archetype,
            "segment": prospect.segment_title,
        }
        for prospect in prospects
    ]
