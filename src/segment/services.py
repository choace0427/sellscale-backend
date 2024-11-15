import yaml
from typing import Optional
from sqlalchemy import or_, and_, desc
from sqlalchemy.exc import SQLAlchemyError

from regex import E
from app import db, celery
from sqlalchemy.orm import attributes
from src.client.models import ClientArchetype, ClientSDR
from src.contacts.models import SavedApolloQuery
from src.ml.services import get_text_generation
from src.prospecting.icp_score.models import ICPScoringRuleset
from src.prospecting.icp_score.services import update_icp_filters, update_icp_scoring_ruleset
from src.prospecting.models import (
    Prospect,
    ProspectOverallStatus,
    ProspectUploadHistory, ProspectStatus, ProspectStatusRecords,
)
from src.research.models import ResearchPointType
from src.segment.models import Segment
from src.segment.models import SegmentTags
from sqlalchemy import case
from sqlalchemy.orm.attributes import flag_modified


def create_new_segment(
    client_sdr_id: int, segment_title: str, filters: dict, campaign_id: int = None, saved_apollo_query_id: Optional[int] = None, attached_segment_tag_ids = [], is_market_map: bool = False
) -> Segment or None:
    existing_segment = Segment.query.filter_by(
        client_sdr_id=client_sdr_id, segment_title=segment_title
    ).first()
    if existing_segment:
        print("existing segment")
        return None

    if saved_apollo_query_id:
        saved_apollo_query_id = saved_apollo_query_id

    new_segment = Segment(
        client_sdr_id=client_sdr_id,
        segment_title=segment_title,
        filters=filters,
        saved_apollo_query_id=saved_apollo_query_id,
        attached_segment_tag_ids=attached_segment_tag_ids,
        is_market_map=is_market_map,
    )

    db.session.add(new_segment)
    db.session.commit()

    if campaign_id:
        update_segment(
            client_sdr_id=client_sdr_id,
            segment_id=new_segment.id,
            segment_title=segment_title,
            filters=filters,
            client_archetype_id=campaign_id,
            attached_segment_tag_ids=attached_segment_tag_ids,
            is_market_map=is_market_map,
        )

    return new_segment


def get_count_no_active_convo(
        segment_id: int
) -> dict:
    query = """
    with prospect_sale_status as (
        select 
	    p.id,
	    (count(distinct psr.id) filter (where psr.to_status = 'ACTIVE_CONVO') + count(distinct p.id) filter (where pesr.to_status = 'ACTIVE_CONVO')) = 0 should_reset
        from prospect p 
            left join prospect_status_records psr on p.id = psr.prospect_id
            left join prospect_email pe on pe.prospect_id = psr.prospect_id
            left join prospect_email_status_records pesr on pesr.prospect_email_id = pe.id
        where p.segment_id = :segment_id
        group by p.segment_id, p.id ) 
    select count(prospect_sale_status.id)
    from prospect_sale_status
    where should_reset = TRUE
    """

    count_not_in_active_convo = db.session.execute(query, {"segment_id": segment_id}).fetchone()[0]
    retval = {
        "count_not_in_active_convo": count_not_in_active_convo
    }

    return retval

def get_prospects_ids_no_active_convo(
        segment_id: int
):
    query = """
    with prospect_sale_status as (
        select 
	    p.id,
	    (count(distinct psr.id) filter (where psr.to_status = 'ACTIVE_CONVO') + count(distinct p.id) filter (where pesr.to_status = 'ACTIVE_CONVO')) = 0 should_reset
        from prospect p 
            left join prospect_status_records psr on p.id = psr.prospect_id
            left join prospect_email pe on pe.prospect_id = psr.prospect_id
            left join prospect_email_status_records pesr on pesr.prospect_email_id = pe.id
        where p.segment_id = :segment_id
        group by p.segment_id, p.id ) 
    select prospect_sale_status.id as prospect_id
    from prospect_sale_status
    where should_reset = TRUE
    """

    prospect_ids_not_in_active_convo = db.session.execute(query, {"segment_id": segment_id}).fetchall()
    retval = []
    for row in prospect_ids_not_in_active_convo:
        retval.append(row["prospect_id"])

    return retval


def reset_prospect_contacts(convo_reset_prospect_ids: list[int], new_segment_name: str):
    for prospect_id in convo_reset_prospect_ids:
        # reset_prospect_task(prospect_id)
        reset_prospect_task.delay(prospect_id, new_segment_name)


@celery.task
def reset_prospect_task(prospect_id: int, new_segment_name: str):
    prospect = Prospect.query.get(prospect_id)
    prospect.approved_prospect_email_id = None
    prospect.approved_outreach_message_id = None
    prospect.status = ProspectStatus.PROSPECTED
    prospect.overall_status = ProspectOverallStatus.PROSPECTED

    latest_status_record = ProspectStatusRecords.query.filter_by(prospect_id=prospect_id).order_by(ProspectStatusRecords.created_at.desc()).first()

    if latest_status_record:
        new_status_record = ProspectStatusRecords(
            prospect_id=prospect_id,
            from_status=latest_status_record.to_status,
            to_status=ProspectStatus.PROSPECTED,
            additional_context="Resetting prospect to PROSPECTED status, to segment: " + new_segment_name
        )

        db.session.add(new_status_record)

    db.session.commit()


def get_segments_for_sdr(
    sdr_id: int, include_all_in_client: bool = False, tag_filter: int = None, archetype_id: int = None
) -> list[dict]:
    client_sdr: ClientSDR = ClientSDR.query.get(sdr_id)
    client_id: int = client_sdr.client_id

    sdr_ids = [sdr_id] if not include_all_in_client else [
        sdr.id for sdr in ClientSDR.query.filter_by(client_id=client_id).all()
    ]

    segments_query = """
        select
            s.id,
            s.client_sdr_id,
            csdr.client_id,
            csdr.name as client_sdr_name,
            csdr.img_url as client_sdr_img_url,
            archetype.archetype as client_archetype,
            archetype.emoji as client_archetype_emoji,
            saq.num_results,
            s.segment_title,
            s.filters,
            s.parent_segment_id,
            s.is_market_map,
            s.saved_apollo_query_id,
            count(distinct p.id) as num_prospected,
            count(distinct p.id) filter (where p.approved_prospect_email_id is not null or p.approved_outreach_message_id is not null) as num_contacted,
            count(distinct p.company) as unique_companies,
            s.attached_segment_tag_ids
        from segment s
        left join client_sdr csdr on s.client_sdr_id = csdr.id
        left join client_archetype archetype on s.client_archetype_id = archetype.id
        left join saved_apollo_query saq on s.saved_apollo_query_id = saq.id
        left join prospect p on s.id = p.segment_id and p.client_id = :client_id
        where s.client_sdr_id in :sdr_ids
        {archetype_filter}
        group by s.id, s.is_market_map, csdr.client_id, csdr.name, csdr.img_url, saq.num_results, archetype.archetype, archetype.emoji
    """

    archetype_filter = ""
    if archetype_id:
        archetype_filter = "and s.client_archetype_id = :archetype_id"

    segments_query = segments_query.format(archetype_filter=archetype_filter)

    query_params = {"client_id": client_id, "sdr_ids": tuple(sdr_ids)}
    if archetype_id:
        query_params["archetype_id"] = archetype_id

    segments_data = db.session.execute(segments_query, query_params).fetchall()

    retval = []
    for row in segments_data:
        segment_dict = {
            "id": row["id"],
            "segment_title": row["segment_title"],
            "is_market_map": row["is_market_map"],
            "filters": row["filters"],
            "parent_segment_id": row["parent_segment_id"],
            "saved_apollo_query_id": row["saved_apollo_query_id"],
            "num_prospected": row["num_prospected"],
            "num_contacted": row["num_contacted"],
            "unique_companies": row["unique_companies"],
            "apollo_query": {
                "num_results": row["num_results"],
            },
            "client_sdr": {
                "id": row["client_sdr_id"],
                "client_id": row["client_id"],
                "sdr_name": row["client_sdr_name"],
                "img_url": row["client_sdr_img_url"],
            },
            "client_archetype": {
                "archetype": row["client_archetype"],
                "emoji": row["client_archetype_emoji"],
            },
            "attached_segments": []
        }

        attached_segment_tag_ids = row["attached_segment_tag_ids"]
        segment_tags = (
            SegmentTags.query.filter(SegmentTags.id.in_(attached_segment_tag_ids)).all()
            if attached_segment_tag_ids
            else []
        )
        segment_dict["attached_segments"] = [tag.to_dict() for tag in segment_tags]
        retval.append(segment_dict)

    if tag_filter != "undefined" and tag_filter:
        retval = [
            segment
            for segment in retval
            if any(tag["id"] == int(tag_filter) for tag in segment["attached_segments"])
        ]

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

    #check to see if the base segment id exists in the segment table. It could have been deleted!
    segment: Segment = Segment.query.get(client_archetype.base_segment_id)
    if (segment is None):
        return None
    
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
    attached_segment_tag_ids: Optional[list[int]] = None,
    is_market_map: Optional[bool] = None,
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

    if attached_segment_tag_ids:
        segment.attached_segment_tag_ids = attached_segment_tag_ids

    if is_market_map is not None:
        segment.is_market_map = is_market_map

    db.session.add(segment)
    db.session.commit()

    if client_archetype_id:
        # If we attached segement to campaign, add existing contacts to campaign
        success, msg = add_unused_prospects_in_segment_to_campaign(
            segment_id=segment_id, campaign_id=client_archetype_id
        )
        # Connect icp_scoring_ruleset to the campaign
        icp_scoring_ruleset: ICPScoringRuleset = ICPScoringRuleset.query.filter(
            ICPScoringRuleset.segment_id == segment_id,
        ).first()

        current_icp_scoring_ruleset: ICPScoringRuleset = ICPScoringRuleset.query.filter(
            ICPScoringRuleset.client_archetype_id == client_archetype_id,
        ).first()

        # If there is already a icp_scoring_ruleset for the campaign, update it
        if current_icp_scoring_ruleset:
            update_icp_scoring_ruleset(
                client_archetype_id=client_archetype_id,
                included_individual_title_keywords=(icp_scoring_ruleset.included_individual_title_keywords if icp_scoring_ruleset.included_individual_title_keywords else []) + (current_icp_scoring_ruleset.included_individual_title_keywords if current_icp_scoring_ruleset.included_individual_title_keywords else []),
                excluded_individual_title_keywords=(icp_scoring_ruleset.excluded_individual_title_keywords if icp_scoring_ruleset.excluded_individual_title_keywords else []) + (current_icp_scoring_ruleset.excluded_individual_title_keywords if current_icp_scoring_ruleset.excluded_individual_title_keywords else []),
                included_individual_industry_keywords=(icp_scoring_ruleset.included_individual_industry_keywords if icp_scoring_ruleset.included_individual_industry_keywords else []) + (current_icp_scoring_ruleset.included_individual_industry_keywords if current_icp_scoring_ruleset.included_individual_industry_keywords else []),
                excluded_individual_industry_keywords=(icp_scoring_ruleset.excluded_individual_industry_keywords if icp_scoring_ruleset.excluded_individual_industry_keywords else []) + (current_icp_scoring_ruleset.excluded_individual_industry_keywords if current_icp_scoring_ruleset.excluded_individual_industry_keywords else []),
                individual_years_of_experience_start=icp_scoring_ruleset.individual_years_of_experience_start if icp_scoring_ruleset.individual_years_of_experience_start else 0,
                individual_years_of_experience_end=icp_scoring_ruleset.individual_years_of_experience_end if icp_scoring_ruleset.individual_years_of_experience_end else 0,
                included_individual_skills_keywords=(icp_scoring_ruleset.included_individual_skills_keywords if icp_scoring_ruleset.included_individual_skills_keywords else []) + (current_icp_scoring_ruleset.included_individual_skills_keywords if current_icp_scoring_ruleset.included_individual_skills_keywords else []),
                excluded_individual_skills_keywords=(icp_scoring_ruleset.excluded_individual_skills_keywords if icp_scoring_ruleset.excluded_individual_skills_keywords else []) + (current_icp_scoring_ruleset.excluded_individual_skills_keywords if current_icp_scoring_ruleset.excluded_individual_skills_keywords else []),
                included_individual_locations_keywords=(icp_scoring_ruleset.included_individual_locations_keywords if icp_scoring_ruleset.included_individual_locations_keywords else []) + (current_icp_scoring_ruleset.included_individual_locations_keywords if current_icp_scoring_ruleset.included_individual_locations_keywords else []),
                excluded_individual_locations_keywords=(icp_scoring_ruleset.excluded_individual_locations_keywords if icp_scoring_ruleset.excluded_individual_locations_keywords else []) + (current_icp_scoring_ruleset.excluded_individual_locations_keywords if current_icp_scoring_ruleset.excluded_individual_locations_keywords else []),
                included_individual_generalized_keywords=(icp_scoring_ruleset.included_individual_generalized_keywords if icp_scoring_ruleset.included_individual_generalized_keywords else []) + (current_icp_scoring_ruleset.included_individual_generalized_keywords if current_icp_scoring_ruleset.included_individual_generalized_keywords else []),
                excluded_individual_generalized_keywords=(icp_scoring_ruleset.excluded_individual_generalized_keywords if icp_scoring_ruleset.excluded_individual_generalized_keywords else []) + (current_icp_scoring_ruleset.excluded_individual_generalized_keywords if current_icp_scoring_ruleset.excluded_individual_generalized_keywords else []),
                included_company_name_keywords=(icp_scoring_ruleset.included_company_name_keywords if icp_scoring_ruleset.included_company_name_keywords else []) + (current_icp_scoring_ruleset.included_company_name_keywords if current_icp_scoring_ruleset.included_company_name_keywords else []),
                excluded_company_name_keywords=(icp_scoring_ruleset.excluded_company_name_keywords if icp_scoring_ruleset.excluded_company_name_keywords else []) + (current_icp_scoring_ruleset.excluded_company_name_keywords if current_icp_scoring_ruleset.excluded_company_name_keywords else []),
                included_company_locations_keywords=(icp_scoring_ruleset.included_company_locations_keywords if icp_scoring_ruleset.included_company_locations_keywords else []) + (current_icp_scoring_ruleset.included_company_locations_keywords if current_icp_scoring_ruleset.included_company_locations_keywords else []),
                excluded_company_locations_keywords=(icp_scoring_ruleset.excluded_company_locations_keywords if icp_scoring_ruleset.excluded_company_locations_keywords else []) + (current_icp_scoring_ruleset.excluded_company_locations_keywords if current_icp_scoring_ruleset.excluded_company_locations_keywords else []),
                company_size_start=icp_scoring_ruleset.company_size_start if icp_scoring_ruleset.company_size_start else 0,
                company_size_end=icp_scoring_ruleset.company_size_end if icp_scoring_ruleset.company_size_end else 0,
                included_company_industries_keywords=(icp_scoring_ruleset.included_company_industries_keywords if icp_scoring_ruleset.included_company_industries_keywords else []) + (current_icp_scoring_ruleset.included_company_industries_keywords if current_icp_scoring_ruleset.included_company_industries_keywords else []),
                excluded_company_industries_keywords=(icp_scoring_ruleset.excluded_company_industries_keywords if icp_scoring_ruleset.excluded_company_industries_keywords else []) + (current_icp_scoring_ruleset.excluded_company_industries_keywords if current_icp_scoring_ruleset.excluded_company_industries_keywords else []),
                included_company_generalized_keywords=(icp_scoring_ruleset.included_company_generalized_keywords if icp_scoring_ruleset.included_company_generalized_keywords else []) + (current_icp_scoring_ruleset.included_company_generalized_keywords if current_icp_scoring_ruleset.included_company_generalized_keywords else []),
                excluded_company_generalized_keywords=(icp_scoring_ruleset.excluded_company_generalized_keywords if icp_scoring_ruleset.excluded_company_generalized_keywords else []) + (current_icp_scoring_ruleset.excluded_company_generalized_keywords if current_icp_scoring_ruleset.excluded_company_generalized_keywords else []),
                included_individual_education_keywords=(icp_scoring_ruleset.included_individual_education_keywords if icp_scoring_ruleset.included_individual_education_keywords else []) + (current_icp_scoring_ruleset.included_individual_education_keywords if current_icp_scoring_ruleset.included_individual_education_keywords else []),
                excluded_individual_education_keywords=(icp_scoring_ruleset.excluded_individual_education_keywords if icp_scoring_ruleset.excluded_individual_education_keywords else []) + (current_icp_scoring_ruleset.excluded_individual_education_keywords if current_icp_scoring_ruleset.excluded_individual_education_keywords else []),
                included_individual_seniority_keywords=(icp_scoring_ruleset.included_individual_seniority_keywords if icp_scoring_ruleset.included_individual_seniority_keywords else []) + (current_icp_scoring_ruleset.included_individual_seniority_keywords if current_icp_scoring_ruleset.included_individual_seniority_keywords else []),
                excluded_individual_seniority_keywords=(icp_scoring_ruleset.excluded_individual_seniority_keywords if icp_scoring_ruleset.excluded_individual_seniority_keywords else []) + (current_icp_scoring_ruleset.excluded_individual_seniority_keywords if current_icp_scoring_ruleset.excluded_individual_seniority_keywords else []),
                individual_personalizers=(icp_scoring_ruleset.individual_personalizers if icp_scoring_ruleset.individual_personalizers else []) + (current_icp_scoring_ruleset.individual_personalizers if current_icp_scoring_ruleset.individual_personalizers else []),
                company_personalizers=(icp_scoring_ruleset.company_personalizers if icp_scoring_ruleset.company_personalizers else []) + (current_icp_scoring_ruleset.company_personalizers if current_icp_scoring_ruleset.company_personalizers else []),
                dealbreakers=(icp_scoring_ruleset.dealbreakers if icp_scoring_ruleset.dealbreakers else []) + (current_icp_scoring_ruleset.dealbreakers if current_icp_scoring_ruleset.dealbreakers else []),
                individual_ai_filters=(icp_scoring_ruleset.individual_ai_filters if icp_scoring_ruleset.individual_ai_filters else []) + (current_icp_scoring_ruleset.individual_ai_filters if current_icp_scoring_ruleset.individual_ai_filters else []),
                company_ai_filters=(icp_scoring_ruleset.company_ai_filters if icp_scoring_ruleset.company_ai_filters else []) + (current_icp_scoring_ruleset.company_ai_filters if current_icp_scoring_ruleset.company_ai_filters else []),
            )
        else:
            icp_scoring_ruleset.client_archetype_id = client_archetype_id

        # Update the research point types (if there exists any) to the new archetype
        research_point_types: ResearchPointType = ResearchPointType.query.filter(
            ResearchPointType.segment_id == segment_id
        ).all()

        for research_point_type in research_point_types:
            research_point_type.archetype_id = client_archetype_id

            db.session.add(research_point_type)

        db.session.add(icp_scoring_ruleset)
        db.session.add(current_icp_scoring_ruleset)
        db.session.commit()

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

    # If the segment has a campaign attached, update the campaign filters
    if segment.client_archetype_id:
        add_segment_filters_to_icp_scoring_ruleset_for_campaign(
            segment_id=segment_id, campaign_id=segment.client_archetype_id
        )


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
    upload_history_records: list[
        ProspectUploadHistory
    ] = ProspectUploadHistory.query.filter(
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

    # If have a icp_segment, delete that icp_segment_first
    icp_scoring_rulesets = ICPScoringRuleset.query.filter(
        ICPScoringRuleset.segment_id == segment.id,
    ).all()
    
    for icp_scoring_ruleset in icp_scoring_rulesets:
        db.session.delete(icp_scoring_ruleset)

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
                    Prospect.client_sdr_id: archetype.client_sdr_id
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

def add_apollo_filters_to_icp_scoring_ruleset_for_campaign(
    saved_apollo_query_id: int,
    campaign_id: int,
):
    saved_apollo_query: SavedApolloQuery = SavedApolloQuery.query.filter_by(
        id=saved_apollo_query_id
    ).first()
    if not saved_apollo_query:
        return False, "Apollo query not found"
    
    #delete the existing ruleset if it exists
    if campaign_id:
        ICPScoringRuleset.query.filter(ICPScoringRuleset.client_archetype_id == campaign_id).delete()
        db.session.commit()

    #extract filters from apollo query
    included_title_keywords = saved_apollo_query.data.get("person_titles")
    excluded_title_keywords = saved_apollo_query.data.get("person_not_titles")
    included_seniority_keywords = saved_apollo_query.data.get("person_seniorities")
    excluded_seniority_keywords = saved_apollo_query.data.get("person_not_seniorities")
    included_company_keywords = saved_apollo_query.data.get("organization_names")
    excluded_company_keywords = saved_apollo_query.data.get("organization_not_names")
    included_education_keywords = saved_apollo_query.data.get("education_keywords")
    excluded_education_keywords = saved_apollo_query.data.get("education_not_keywords")
    included_bio_keywords = saved_apollo_query.data.get("bio_keywords")
    excluded_bio_keywords = saved_apollo_query.data.get("bio_not_keywords")
    included_location_keywords = saved_apollo_query.data.get("person_locations")
    excluded_location_keywords = saved_apollo_query.data.get("person_not_locations")
    included_skills_keywords = saved_apollo_query.data.get("skills_keywords")
    excluded_skills_keywords = saved_apollo_query.data.get("skills_not_keywords")
    years_of_experience_start = saved_apollo_query.data.get("years_of_experience_start")
    years_of_experience_end = saved_apollo_query.data.get("years_of_experience_end")
    included_company_size = saved_apollo_query.data.get("organization_num_employees_ranges")
    included_industry_keywords = saved_apollo_query.data.get("organization_industry_tag_ids")
    excluded_industry_keywords = saved_apollo_query.data.get("organization_not_industry_tag_ids")
    filters = {
        "included_individual_title_keywords": included_title_keywords or [],
        "excluded_individual_title_keywords": excluded_title_keywords or [],
        "included_individual_seniority_keywords": included_seniority_keywords or [],
        "excluded_individual_seniority_keywords": excluded_seniority_keywords or [],
        "included_company_name_keywords": included_company_keywords or [],
        "excluded_company_name_keywords": excluded_company_keywords or [],
        "included_individual_education_keywords": included_education_keywords or [],
        "excluded_individual_education_keywords": excluded_education_keywords or [],
        "included_individual_generalized_keywords": included_bio_keywords or [],
        "excluded_individual_generalized_keywords": excluded_bio_keywords or [],
        "included_individual_locations_keywords": included_location_keywords or [],
        "excluded_individual_locations_keywords": excluded_location_keywords or [],
        "included_individual_skills_keywords": included_skills_keywords or [],
        "excluded_individual_skills_keywords": excluded_skills_keywords or [],
        "individual_years_of_experience_start": years_of_experience_start or 0,
        "individual_years_of_experience_end": years_of_experience_end or 0,
        "company_size_start": included_company_size or [],
        "included_individual_industry_keywords": included_industry_keywords or [],
        "excluded_individual_industry_keywords": excluded_industry_keywords or [],
    }
    
    print('filters are: ', filters)
    
    update_icp_scoring_ruleset(
        client_archetype_id=campaign_id,
        included_individual_title_keywords=filters["included_individual_title_keywords"],
        excluded_individual_title_keywords=filters["excluded_individual_title_keywords"],
        included_individual_industry_keywords=filters["included_individual_industry_keywords"],
        excluded_individual_industry_keywords=filters["excluded_individual_industry_keywords"],
        individual_years_of_experience_start=filters["individual_years_of_experience_start"],
        individual_years_of_experience_end=filters["individual_years_of_experience_end"],
        included_individual_skills_keywords=filters["included_individual_skills_keywords"],
        excluded_individual_skills_keywords=filters["excluded_individual_skills_keywords"],
        included_individual_locations_keywords=filters["included_individual_locations_keywords"],
        excluded_individual_locations_keywords=filters["excluded_individual_locations_keywords"],
        included_individual_generalized_keywords=filters["included_individual_generalized_keywords"],
        excluded_individual_generalized_keywords=filters["excluded_individual_generalized_keywords"],
        included_company_name_keywords=filters["included_company_name_keywords"],
        excluded_company_name_keywords=filters["excluded_company_name_keywords"],
        included_company_locations_keywords=[],  # Assuming this is not provided in the filters
        excluded_company_locations_keywords=[],  # Assuming this is not provided in the filters
        company_size_start=filters["company_size_start"][0] if filters["company_size_start"] else 0,
        company_size_end=filters["company_size_start"][1] if filters["company_size_start"] else 0,
        included_company_industries_keywords=filters["included_individual_industry_keywords"],
        excluded_company_industries_keywords=filters["excluded_individual_industry_keywords"],
        included_company_generalized_keywords=[],  # Assuming this is not provided in the filters
        excluded_company_generalized_keywords=[],  # Assuming this is not provided in the filters
        included_individual_education_keywords=filters["included_individual_education_keywords"],
        excluded_individual_education_keywords=filters["excluded_individual_education_keywords"],
        included_individual_seniority_keywords=filters["included_individual_seniority_keywords"],
        excluded_individual_seniority_keywords=filters["excluded_individual_seniority_keywords"],
    )

    return True, "Apollo filters added to campaign"


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
        Prospect.query.filter(
            Prospect.id.in_([prospect.id for prospect in prospects])
        ).update({"segment_id": None}, synchronize_session=False)
    else:
        Prospect.query.filter(
            Prospect.id.in_([prospect.id for prospect in prospects])
        ).update({"segment_id": to_segment_id}, synchronize_session=False)

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
            client_sdr_id=client_sdr_id, from_segment_id=segment_id, to_segment_id=0
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

    saved_apollo_query: SavedApolloQuery = SavedApolloQuery.query.get(
        saved_apollo_query_id
    )
    if not saved_apollo_query:
        return False, "Apollo query not found"

    if saved_apollo_query.client_sdr_id != segment.client_sdr_id:
        return False, "Apollo query and segment belong to different SDRs"

    segment.saved_apollo_query_id = saved_apollo_query_id
    db.session.add(segment)
    db.session.commit()

    # If the segment has a campaign attached, update the campaign filters
    if segment.client_archetype_id:
        add_segment_filters_to_icp_scoring_ruleset_for_campaign(
            segment_id=segment_id, campaign_id=segment.client_archetype_id
        )

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
    current_client_sdr_id: int, segment_id: int, new_client_sdr_id: int
):
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
    ).update(
        {
            Prospect.client_sdr_id: new_client_sdr_id,
            Prospect.archetype_id: unassigned_archetype.id,
        },
        synchronize_session=False,
    )
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


def create_n_sub_batches_for_segment(segment_id: int, num_batches: int):
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
    num_prospects_per_batch = num_prospects // (num_batches + 1)

    current_count = 1

    for i in range(num_batches + 1):
        start_index = i * num_prospects_per_batch
        end_index = (i + 1) * num_prospects_per_batch
        if i == num_batches:
            end_index = num_prospects
        prospects_in_batch = unused_prospects[start_index:end_index]
        prospect_ids = [prospect.id for prospect in prospects_in_batch]

        if i != 0:
            new_title = f"Batch {current_count}: {original_segment.segment_title}"

            while Segment.query.filter_by(segment_title=new_title).first() is not None:
                current_count += 1
                new_title = f"Batch {current_count}: {original_segment.segment_title}"

            new_segment = create_new_segment(
                client_sdr_id=original_segment.client_sdr_id,
                segment_title=new_title,
                filters=original_segment.filters,
                attached_segment_tag_ids=original_segment.attached_segment_tag_ids,
            )

            add_prospects_to_segment(prospect_ids, new_segment.id)
        else:
            add_prospects_to_segment(prospect_ids, segment_id)

    return True, "Subsegments created"


def toggle_auto_scrape_for_segment(client_sdr_id: int, segment_id: int):
    segment: Segment = Segment.query.get(segment_id)
    if not segment:
        return False, "Segment not found"
    if segment.client_sdr_id != client_sdr_id:
        return False, "Segment does not belong to current SDR"

    segment.autoscrape_enabled = not segment.autoscrape_enabled
    db.session.add(segment)
    db.session.commit()

    return True, "Auto scrape toggled"


def run_new_scrape_for_segment(segment_id: int):
    from src.contacts.services import upload_prospects_from_apollo_page_to_segment

    segment: Segment = Segment.query.get(segment_id)
    if not segment:
        return False, "Segment not found"
    if not segment.autoscrape_enabled:
        return False, "Auto scrape not enabled for segment"

    saved_apollo_query: SavedApolloQuery = SavedApolloQuery.query.get(
        segment.saved_apollo_query_id
    )
    if not saved_apollo_query:
        return False, "Apollo query not found for segment"

    max_pages = saved_apollo_query.num_results // 100 + 1

    if not segment.current_scrape_page:
        segment.current_scrape_page = 1

    if segment.current_scrape_page > max_pages:
        return False, "All pages scraped"

    # todo(Aakash) run scrape here with celery
    upload_prospects_from_apollo_page_to_segment(
        client_sdr_id=segment.client_sdr_id,
        saved_apollo_query_id=segment.saved_apollo_query_id,
        page=segment.current_scrape_page,
        segment_id=segment_id,
    )

    segment.current_scrape_page = segment.current_scrape_page + 1
    db.session.add(segment)
    db.session.commit()

    return True, "Scrape initiated"


@celery.task
def run_n_scrapes_for_segment(client_sdr_id: int, segment_id: int, num_scrapes: int):
    segment: Segment = Segment.query.get(segment_id)
    if not segment or segment.client_sdr_id != client_sdr_id:
        return False, "Segment not found"

    for i in range(num_scrapes):
        success, msg = run_new_scrape_for_segment(segment_id)
        if not success:
            return False, msg
    return True, "Scrapes initiated"


def set_current_scrape_page_for_segment(client_sdr_id: int, segment_id: int, page: int):
    segment: Segment = Segment.query.get(segment_id)
    if not segment or segment.client_sdr_id != client_sdr_id:
        return False, "Segment not found"

    segment.current_scrape_page = page
    db.session.add(segment)
    db.session.commit()

    return True, "Current scrape page set"


@celery.task
def scrape_all_enabled_segments():
    segments: list[Segment] = Segment.query.filter(
        and_(Segment.autoscrape_enabled == True)
    ).all()

    for segment in segments:
        print(segment.segment_title)
        # run_n_scrapes_for_segment.delay(client_sdr_id, segment.id, 1)

    return True, "Scrapes initiated for all enabled segments"


def create_and_add_tag_to_segment(
    segment_id: int, client_sdr_id: int, name: str, color: str
) -> tuple[bool, Segment]:
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if not client_sdr:
        return False, "Client SDR not found"
    client_id = client_sdr.client_id
    new_tag = SegmentTags(client_id=client_id, name=name, color=color)
    db.session.add(new_tag)
    db.session.flush()  # Ensure new_tag.id is available immediately after addition
    segment = Segment.query.get(segment_id)
    if not segment:
        return False, None
    if segment.attached_segment_tag_ids is None:
        segment.attached_segment_tag_ids = []
    print(f"Before adding: {segment.attached_segment_tag_ids}")
    if new_tag.id not in segment.attached_segment_tag_ids:
        segment.attached_segment_tag_ids.append(new_tag.id)
        flag_modified(
            segment, "attached_segment_tag_ids"
        )  # Explicitly mark as modified
        db.session.add(segment)
        try:
            db.session.commit()
            print(f"After adding: {segment.attached_segment_tag_ids}")
            return True, new_tag
        except SQLAlchemyError as e:
            db.session.rollback()
            return False, f"Failed to add tag to segment: {str(e)}"
    else:
        return False, None


def delete_tag_from_all_segments(client_sdr_id: int, tag_id: int) -> tuple[bool, str]:
    # First, find and delete the tag from the SegmentTags table
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if not client_sdr:
        return False, "Client SDR not found"
    client_id = client_sdr.client_id
    tag = SegmentTags.query.get(tag_id)
    if not tag or tag.client_id != client_id:
        return False, "Tag not found or does not belong to client"

    try:
        # Remove the tag from all segments where it is attached
        segments = Segment.query.filter(
            Segment.attached_segment_tag_ids.any(tag_id)
        ).all()
        for segment in segments:
            if tag_id in segment.attached_segment_tag_ids:
                segment.attached_segment_tag_ids.remove(tag_id)
                flag_modified(
                    segment, "attached_segment_tag_ids"
                )  # Mark the list as modified
                db.session.add(segment)

        # Delete the tag from the SegmentTags table
        db.session.delete(tag)
        db.session.commit()
        return True, "Tag deleted from all segments and SegmentTags table"
    except SQLAlchemyError as e:
        db.session.rollback()
        return False, f"Failed to delete tag: {str(e)}"


def attach_tag_to_segment(
    segment_id: int, client_sdr_id: int, tag_id: int
) -> tuple[bool, str]:
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if not client_sdr:
        return False, "Client SDR not found"
    client_id = client_sdr.client_id
    print("got params", segment_id, client_id, tag_id)
    if not segment_id:
        raise ValueError("Invalid request. Required parameter `segment_id` missing.")

    segment = Segment.query.get(segment_id)
    if not segment:
        return False, "Segment not found"

    tag = SegmentTags.query.get(tag_id)
    if not tag or tag.client_id != client_id:
        return False, "Tag not found or does not belong to client"

    if segment.attached_segment_tag_ids is None:
        segment.attached_segment_tag_ids = []

    print(f"Before adding: {segment.attached_segment_tag_ids}")
    if tag_id not in segment.attached_segment_tag_ids:
        segment.attached_segment_tag_ids.append(tag_id)
        flag_modified(
            segment, "attached_segment_tag_ids"
        )  # Explicitly mark as modified
        db.session.add(segment)
        try:
            db.session.commit()
            print(f"After adding: {segment.attached_segment_tag_ids}")
            return True, "Tag added to segment successfully"
        except SQLAlchemyError as e:
            db.session.rollback()
            return False, f"Failed to add tag to segment: {str(e)}"
    else:
        return False, "Tag already attached to segment"


def remove_tag_from_segment(segment_id: int, tag_id: int) -> tuple[bool, str]:
    segment = Segment.query.get(segment_id)
    if not segment:
        return False, "Segment not found"

    if tag_id in segment.attached_segment_tag_ids:
        segment.attached_segment_tag_ids.remove(tag_id)
        flag_modified(
            segment, "attached_segment_tag_ids"
        )  # Explicitly mark as modified
        db.session.add(segment)

        try:
            db.session.commit()
            return True, "Tag removed from segment"
        except SQLAlchemyError as e:
            db.session.rollback()
            return False, f"Failed to remove tag from segment: {str(e)}"
    else:
        return False, "Tag not attached to segment"


def get_segment_tags_for_sdr(client_sdr_id: int) -> tuple[bool, list[SegmentTags]]:
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if not client_sdr:
        return False, "Client SDR not found"
    client_id = client_sdr.client_id
    tags = SegmentTags.query.filter_by(client_id=client_id).all()
    if not tags:
        return False, "No tags found for SDR"
    return True, tags


# Update tags for a segment
def update_segment_tags(segment_id: int, new_tag_ids: list[int]) -> tuple[bool, str]:
    segment = Segment.query.get(segment_id)
    if not segment:
        return False, "Segment not found"

    # Validate all new tag IDs
    valid_tags = SegmentTags.query.filter(SegmentTags.id.in_(new_tag_ids)).all()
    if len(valid_tags) != len(new_tag_ids):
        return False, "One or more tags are invalid"

    segment.attached_segment_tag_ids = new_tag_ids
    db.session.add(segment)
    db.session.commit()
    return True, "Segment tags updated successfully"
