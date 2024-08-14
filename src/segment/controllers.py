from flask import Blueprint, jsonify, request

from app import db
from src.ai_requests.services import create_ai_requests
from src.authentication.decorators import require_user
from src.client.controllers import create_archetype
from src.client.models import ClientArchetype, ClientSDR
from src.client.services import create_client_archetype
from src.prospecting.icp_score.models import ICPScoringRuleset
from src.prospecting.icp_score.services import update_icp_scoring_ruleset, \
    apply_segment_icp_scoring_ruleset_filters_task
from src.prospecting.models import Prospect, ProspectStatus, ProspectOverallStatus
from src.segment.models import Segment
from src.segment.services import (
    add_prospects_to_segment,
    add_unused_prospects_in_segment_to_campaign,
    connect_saved_apollo_query_to_segment,
    create_n_sub_batches_for_segment,
    create_new_segment,
    delete_segment,
    duplicate_segment,
    extract_data_from_sales_navigator_link,
    find_prospects_by_segment_filters,
    get_segment_predicted_prospects,
    get_segments_for_sdr,
    move_segment,
    remove_prospect_from_segment,
    run_n_scrapes_for_segment,
    set_current_scrape_page_for_segment,
    toggle_auto_scrape_for_segment,
    transfer_segment,
    update_segment,
    wipe_and_delete_segment,
    wipe_segment_ids_from_prospects_in_segment,
    get_unused_segments_for_sdr,
    scrape_all_enabled_segments,
    delete_tag_from_all_segments,
    remove_tag_from_segment,
    attach_tag_to_segment,
    get_segment_tags_for_sdr,
    create_and_add_tag_to_segment,
    get_count_no_active_convo, get_prospects_ids_no_active_convo,
    reset_prospect_contacts,
)
from src.segment.services_auto_segment import run_auto_segment
from src.utils.request_helpers import get_request_parameter
from src.segment.services import reset_prospect_task

SEGMENT_BLUEPRINT = Blueprint("segment", __name__)


@SEGMENT_BLUEPRINT.route("/")
def index():
    return "OK", 200


@SEGMENT_BLUEPRINT.route("/create", methods=["POST"])
@require_user
def create_segment(client_sdr_id: int):
    segment_title = get_request_parameter(
        "segment_title", request, json=True, required=True
    )
    filters = get_request_parameter("filters", request, json=True, required=True)

    is_market_map = get_request_parameter("is_market_map", request, json=True, required=False)

    campaign_id = get_request_parameter(
        "campaign_id", request, json=True, required=False
    )
    saved_apollo_query_id = get_request_parameter(
        "saved_apollo_query_id", request, json=True, required=False
    )

    segment: Segment = create_new_segment(
        client_sdr_id=client_sdr_id,
        segment_title=segment_title,
        filters=filters,
        campaign_id=campaign_id,
        saved_apollo_query_id=saved_apollo_query_id,
        is_market_map=is_market_map if is_market_map is not None else False,
    )

    # If is a market map, we want to create an icp ruleset, and have
    # it linked to the unassigned SDR
    unassigned_archetype: ClientArchetype = ClientArchetype.query.filter(
        ClientArchetype.client_sdr_id == client_sdr_id,
        ClientArchetype.is_unassigned_contact_archetype == True
    ).first()

    if unassigned_archetype:
        empty_icp_scoring_ruleset = ICPScoringRuleset(
            client_archetype_id=unassigned_archetype.id,
            segment_id=segment.id
        )
        db.session.add(empty_icp_scoring_ruleset)
        db.session.commit()

    if segment:
        return segment.to_dict(), 200
    else:
        return "Segment creation failed", 400


@SEGMENT_BLUEPRINT.route("/<int:segment_id>/create-segment-from-market-map", methods=["POST"])
@require_user
def create_segment_from_market_map(client_sdr_id: int, segment_id: int):
    client_sdr = ClientSDR.query.get(client_sdr_id)

    if not client_sdr:
        return "Client SDR not found", 404

    client_archetype = ClientArchetype.query.filter(
        ClientArchetype.client_sdr_id == client_sdr_id,
        ClientArchetype.is_unassigned_contact_archetype == True,
    ).first()

    if not client_archetype:
        client_archetype_id = None
    else:
        client_archetype_id = client_archetype.id

    segment_title = get_request_parameter(
        "segment_title", request, json=True, required=True
    )

    prospects = get_request_parameter(
        "prospects", request, json=True, required=True
    )

    segment: Segment = create_new_segment(
        client_sdr_id=client_sdr_id,
        segment_title=segment_title,
        filters={},
        campaign_id=None,
        saved_apollo_query_id=None,
        is_market_map=False,
    )

    icp_ruleset = ICPScoringRuleset.query.filter(
        ICPScoringRuleset.segment_id == segment_id,
    ).first()

    if icp_ruleset:
        new_icp_ruleset = ICPScoringRuleset(
            client_archetype_id=client_archetype_id,
            included_individual_title_keywords=icp_ruleset.included_individual_title_keywords,
            excluded_individual_title_keywords=icp_ruleset.excluded_individual_title_keywords,
            included_individual_industry_keywords=icp_ruleset.included_individual_industry_keywords,
            excluded_individual_industry_keywords=icp_ruleset.excluded_individual_industry_keywords,
            individual_years_of_experience_start=icp_ruleset.individual_years_of_experience_start,
            individual_years_of_experience_end=icp_ruleset.individual_years_of_experience_end,
            included_individual_skills_keywords=icp_ruleset.included_individual_skills_keywords,
            excluded_individual_skills_keywords=icp_ruleset.excluded_individual_skills_keywords,
            included_individual_locations_keywords=icp_ruleset.included_individual_locations_keywords,
            excluded_individual_locations_keywords=icp_ruleset.excluded_individual_locations_keywords,
            included_individual_generalized_keywords=icp_ruleset.included_individual_generalized_keywords,
            excluded_individual_generalized_keywords=icp_ruleset.excluded_individual_generalized_keywords,
            included_company_name_keywords=icp_ruleset.included_company_name_keywords,
            excluded_company_name_keywords=icp_ruleset.excluded_company_name_keywords,
            included_company_locations_keywords=icp_ruleset.included_company_locations_keywords,
            excluded_company_locations_keywords=icp_ruleset.excluded_company_locations_keywords,
            company_size_start=icp_ruleset.company_size_start,
            company_size_end=icp_ruleset.company_size_end,
            included_company_industries_keywords=icp_ruleset.included_company_industries_keywords,
            excluded_company_industries_keywords=icp_ruleset.excluded_company_industries_keywords,
            included_company_generalized_keywords=icp_ruleset.included_company_generalized_keywords,
            excluded_company_generalized_keywords=icp_ruleset.excluded_company_generalized_keywords,
            included_individual_education_keywords=icp_ruleset.included_individual_education_keywords,
            excluded_individual_education_keywords=icp_ruleset.excluded_individual_education_keywords,
            included_individual_seniority_keywords=icp_ruleset.included_individual_seniority_keywords,
            excluded_individual_seniority_keywords=icp_ruleset.excluded_individual_seniority_keywords,
            individual_personalizers=icp_ruleset.individual_personalizers,
            company_personalizers=icp_ruleset.company_personalizers,
            dealbreakers=icp_ruleset.dealbreakers,
            individual_ai_filters=icp_ruleset.individual_ai_filters,
            company_ai_filters=icp_ruleset.company_ai_filters,
            segment_id=segment.id,
        )

        db.session.add(new_icp_ruleset)
        db.session.commit()

    add_prospects_to_segment(prospects, segment.id)

    if segment:
        return {"status": 200}, 200
    else:
        return "Segment creation failed", 400


@SEGMENT_BLUEPRINT.route("/<int:segment_id>/icp_ruleset", methods=["GET"])
@require_user
def get_icp_ruleset_by_segment(client_sdr_id: int, segment_id: int):
    client_archetype: ClientArchetype = ClientArchetype.query.filter(
        ClientArchetype.client_sdr_id == client_sdr_id,
        ClientArchetype.is_unassigned_contact_archetype == True,
    ).first()

    if not client_archetype:
        return "Cannot find unassigned client archetype", 400

    icp_scoring_ruleset: ICPScoringRuleset = ICPScoringRuleset.query.filter(
        ICPScoringRuleset.segment_id == segment_id,
    ).first()

    if not icp_scoring_ruleset:
        empty_icp_scoring_ruleset = ICPScoringRuleset(
            client_archetype_id=client_archetype.id,
            segment_id=segment_id
        )
        db.session.add(empty_icp_scoring_ruleset)
        db.session.commit()

        # Reset all score of prospects in the segment
        prospects = Prospect.query.filter(
            Prospect.segment_id == segment_id,
        ).all()

        for prospect in prospects:
            prospect.icp_fit_reason = ""
            prospect.icp_company_fit_score = 0
            prospect.icp_fit_reason_v2 = {}
            prospect.icp_fit_score = 0
            prospect.icp_company_fit_reason = 0

        return jsonify({"icp_ruleset": empty_icp_scoring_ruleset.to_dict()}), 200

    return jsonify({"icp_ruleset": icp_scoring_ruleset.to_dict()}), 200


@SEGMENT_BLUEPRINT.route("/<int:segment_id>/prospects", methods=["GET"])
@require_user
def get_prospects_by_segment(client_sdr_id: int, segment_id: int):
    segment = Segment.query.filter(
        Segment.client_sdr_id == client_sdr_id,
        Segment.id == segment_id
    ).first()

    if not segment:
        return "Segment not found", 404

    prospects = Prospect.query.filter(
        Prospect.segment_id == segment_id,
    ).all()

    return jsonify({"prospects": [prospect.simple_to_dict() for prospect in prospects]}), 200


@SEGMENT_BLUEPRINT.route("/<int:segment_id>", methods=["GET"])
@require_user
def get_segment(client_sdr_id: int, segment_id: int):
    segment = Segment.query.filter_by(
        client_sdr_id=client_sdr_id, id=segment_id
    ).first()

    if segment:
        return segment.to_dict(), 200
    else:
        return "Segment not found", 404


@SEGMENT_BLUEPRINT.route("/<int:segment_id>/score", methods=["POST"])
@require_user
def post_score_segment_with_ruleset(client_sdr_id: int, segment_id: int):
    client_archetype: ClientArchetype = ClientArchetype.query.filter(
        ClientArchetype.client_sdr_id == client_sdr_id,
        ClientArchetype.is_unassigned_contact_archetype == True,
        ).first()

    if not client_archetype:
        return "Cannot find unassigned client archetype", 400

    included_individual_title_keywords = get_request_parameter(
        "included_individual_title_keywords", request, json=True, required=False
    )
    excluded_individual_title_keywords = get_request_parameter(
        "excluded_individual_title_keywords", request, json=True, required=False
    )
    included_individual_industry_keywords = get_request_parameter(
        "included_individual_industry_keywords", request, json=True, required=False
    )
    excluded_individual_industry_keywords = get_request_parameter(
        "excluded_individual_industry_keywords", request, json=True, required=False
    )
    individual_years_of_experience_start = get_request_parameter(
        "individual_years_of_experience_start", request, json=True, required=False
    )
    individual_years_of_experience_end = get_request_parameter(
        "individual_years_of_experience_end", request, json=True, required=False
    )
    included_individual_skills_keywords = get_request_parameter(
        "included_individual_skills_keywords", request, json=True, required=False
    )
    excluded_individual_skills_keywords = get_request_parameter(
        "excluded_individual_skills_keywords", request, json=True, required=False
    )
    included_individual_locations_keywords = get_request_parameter(
        "included_individual_locations_keywords", request, json=True, required=False
    )
    excluded_individual_locations_keywords = get_request_parameter(
        "excluded_individual_locations_keywords", request, json=True, required=False
    )
    included_individual_generalized_keywords = get_request_parameter(
        "included_individual_generalized_keywords", request, json=True, required=False
    )
    excluded_individual_generalized_keywords = get_request_parameter(
        "excluded_individual_generalized_keywords", request, json=True, required=False
    )
    included_individual_education_keywords = get_request_parameter(
        "included_individual_education_keywords", request, json=True, required=False
    )
    excluded_individual_education_keywords = get_request_parameter(
        "excluded_individual_education_keywords", request, json=True, required=False
    )
    included_individual_seniority_keywords = get_request_parameter(
        "included_individual_seniority_keywords", request, json=True, required=False
    )
    excluded_individual_seniority_keywords = get_request_parameter(
        "excluded_individual_seniority_keywords", request, json=True, required=False
    )
    included_company_name_keywords = get_request_parameter(
        "included_company_name_keywords", request, json=True, required=False
    )
    excluded_company_name_keywords = get_request_parameter(
        "excluded_company_name_keywords", request, json=True, required=False
    )
    included_company_locations_keywords = get_request_parameter(
        "included_company_locations_keywords", request, json=True, required=False
    )
    excluded_company_locations_keywords = get_request_parameter(
        "excluded_company_locations_keywords", request, json=True, required=False
    )
    company_size_start = get_request_parameter(
        "company_size_start", request, json=True, required=False
    )
    company_size_end = get_request_parameter(
        "company_size_end", request, json=True, required=False
    )
    included_company_industries_keywords = get_request_parameter(
        "included_company_industries_keywords", request, json=True, required=False
    )
    excluded_company_industries_keywords = get_request_parameter(
        "excluded_company_industries_keywords", request, json=True, required=False
    )
    included_company_generalized_keywords = get_request_parameter(
        "included_company_generalized_keywords", request, json=True, required=False
    )
    excluded_company_generalized_keywords = get_request_parameter(
        "excluded_company_generalized_keywords", request, json=True, required=False
    )
    individual_personalizers = get_request_parameter(
        "individual_personalizers", request, json=True, required=False
    )
    company_personalizers = get_request_parameter(
        "company_personalizers", request, json=True, required=False
    )
    dealbreakers = get_request_parameter(
        "dealbreakers", request, json=True, required=False
    )
    individual_ai_filters = get_request_parameter(
        "individual_ai_filters", request, json=True, required=False
    )
    company_ai_filters = get_request_parameter(
        "company_ai_filters", request, json=True, required=False
    )
    selected_contacts = get_request_parameter(
        "selectedContacts", request, json=True, required=False
    )

    segment = Segment.query.filter(
        Segment.client_sdr_id == client_sdr_id,
        Segment.id == segment_id
    ).first()

    if not segment:
        return "Segment not found", 404

    update_icp_scoring_ruleset(
        client_archetype_id=client_archetype.id,
        included_individual_title_keywords=included_individual_title_keywords,
        excluded_individual_title_keywords=excluded_individual_title_keywords,
        included_individual_industry_keywords=included_individual_industry_keywords,
        excluded_individual_industry_keywords=excluded_individual_industry_keywords,
        individual_years_of_experience_start=individual_years_of_experience_start,
        individual_years_of_experience_end=individual_years_of_experience_end,
        included_individual_skills_keywords=included_individual_skills_keywords,
        excluded_individual_skills_keywords=excluded_individual_skills_keywords,
        included_individual_locations_keywords=included_individual_locations_keywords,
        excluded_individual_locations_keywords=excluded_individual_locations_keywords,
        included_individual_generalized_keywords=included_individual_generalized_keywords,
        excluded_individual_generalized_keywords=excluded_individual_generalized_keywords,
        included_company_name_keywords=included_company_name_keywords,
        excluded_company_name_keywords=excluded_company_name_keywords,
        included_company_locations_keywords=included_company_locations_keywords,
        excluded_company_locations_keywords=excluded_company_locations_keywords,
        company_size_start=company_size_start,
        company_size_end=company_size_end,
        included_company_industries_keywords=included_company_industries_keywords,
        excluded_company_industries_keywords=excluded_company_industries_keywords,
        included_company_generalized_keywords=included_company_generalized_keywords,
        excluded_company_generalized_keywords=excluded_company_generalized_keywords,
        included_individual_education_keywords=included_individual_education_keywords,
        excluded_individual_education_keywords=excluded_individual_education_keywords,
        included_individual_seniority_keywords=included_individual_seniority_keywords,
        excluded_individual_seniority_keywords=excluded_individual_seniority_keywords,
        individual_personalizers=individual_personalizers,
        company_personalizers=company_personalizers,
        dealbreakers=dealbreakers,
        individual_ai_filters=individual_ai_filters,
        company_ai_filters=company_ai_filters,
        segment_id=segment_id,
    )

    # If selected contact is empty, we want to score all prospects in the segment
    if not selected_contacts or len(selected_contacts) == 0:
        prospects = Prospect.query.filter(
            Prospect.segment_id == segment_id,
        ).all()

        prospect_ids = [prospect.id for prospect in prospects]
    else:
        prospect_ids = selected_contacts

    success = apply_segment_icp_scoring_ruleset_filters_task(
        client_archetype_id=client_archetype.id,
        segment_id=segment_id,
        prospect_ids=prospect_ids,
    )

    if success:
        return {"message": "ok"}, 200

    return "Failed to apply ICP Scoring Ruleset", 500


@SEGMENT_BLUEPRINT.route("/all", methods=["GET"])
@require_user
def get_segments(client_sdr_id: int):
    include_all_in_client: bool = get_request_parameter(
        "include_all_in_client", request, json=False, required=False
    )
    tag_filter: bool = get_request_parameter(
        "tag_filter", request, json=False, required=False
    )

    segments: list[dict] = get_segments_for_sdr(client_sdr_id, include_all_in_client=include_all_in_client,
                                                tag_filter=tag_filter)

    return {"segments": segments}, 200


@SEGMENT_BLUEPRINT.route("/<int:segment_id>/count_no_active_convo", methods=["GET"])
@require_user
def get_segment_count_no_active_convo(client_sdr_id: int, segment_id: int):
    segment = Segment.query.filter_by(
        client_sdr_id=client_sdr_id, id=segment_id
    ).first()

    if not segment:
        return "Segment not found", 404

    return get_count_no_active_convo(segment_id), 200


@SEGMENT_BLUEPRINT.route("/reset_segment", methods=["POST"])
@require_user
def post_reset_segment_convo_count(client_sdr_id: int):
    segment_id = get_request_parameter("segment_id", request, json=True, required=True)
    new_segment_title = get_request_parameter("new_segment_title", request, json=True, required=True)

    segment = Segment.query.filter_by(
        client_sdr_id=client_sdr_id, id=segment_id
    ).first()

    if not segment:
        return "Segment not found", 404

    # Get prospect Id From where we want to reset
    prospect_ids = get_prospects_ids_no_active_convo(segment_id)

    # Reset the prospect
    reset_prospect_contacts(prospect_ids, new_segment_title)

    # Create new Segment with new segment title
    new_segment = create_new_segment(
        client_sdr_id=client_sdr_id,
        segment_title=new_segment_title,
        filters=segment.filters,
        attached_segment_tag_ids=segment.attached_segment_tag_ids,
    )

    # Add those prospects to the new Segment
    add_prospects_to_segment(prospect_ids, new_segment_id=new_segment.id)

    return "Prospect reset", 200


@SEGMENT_BLUEPRINT.route("/<int:segment_id>", methods=["PATCH"])
@require_user
def update_segment_endpoint(client_sdr_id: int, segment_id: int):
    segment_title = get_request_parameter("segment_title", request, json=True)
    filters = get_request_parameter("filters", request, json=True)
    client_archetype_id = get_request_parameter(
        "client_archetype_id", request, json=True
    )

    segment: Segment = update_segment(
        client_sdr_id=client_sdr_id,
        segment_id=segment_id,
        segment_title=segment_title,
        filters=filters,
        client_archetype_id=client_archetype_id,
    )

    if segment:
        return segment.to_dict(), 200
    else:
        return "Segment update failed", 400


@SEGMENT_BLUEPRINT.route("/<int:segment_id>", methods=["DELETE"])
@require_user
def delete_segment_endpoint(client_sdr_id: int, segment_id: int):
    success, message = wipe_and_delete_segment(
        client_sdr_id=client_sdr_id, segment_id=segment_id
    )

    if success:
        return "Segment deleted", 200

    return message, 400


@SEGMENT_BLUEPRINT.route("/<int:segment_id>/prospects", methods=["POST"])
@require_user
def add_prospects_to_segment_endpoint(client_sdr_id: int, segment_id: int):
    prospect_ids = get_request_parameter(
        "prospect_ids", request, json=True, required=True
    )

    prospects_for_sdr_in_ids = Prospect.query.filter(
        Prospect.client_sdr_id == client_sdr_id, Prospect.id.in_(prospect_ids)
    ).all()
    filtered_ids = [prospect.id for prospect in prospects_for_sdr_in_ids]

    success, message = add_prospects_to_segment(
        prospect_ids=filtered_ids, new_segment_id=segment_id
    )

    if success:
        return "Prospects added to segment", 200

    return message, 400


@SEGMENT_BLUEPRINT.route("/find_prospects", methods=["POST"])
@require_user
def find_prospects_by_segment_filters_endpoint(client_sdr_id: int):
    segment_ids = get_request_parameter("segment_ids", request, json=True)
    archetype_ids = get_request_parameter("archetype_ids", request, json=True)
    included_title_keywords = get_request_parameter(
        "included_title_keywords", request, json=True
    )
    excluded_title_keywords = get_request_parameter(
        "excluded_title_keywords", request, json=True
    )
    included_seniority_keywords = get_request_parameter(
        "included_seniority_keywords", request, json=True
    )
    excluded_seniority_keywords = get_request_parameter(
        "excluded_seniority_keywords", request, json=True
    )
    included_company_keywords = get_request_parameter(
        "included_company_keywords", request, json=True
    )
    excluded_company_keywords = get_request_parameter(
        "excluded_company_keywords", request, json=True
    )
    included_education_keywords = get_request_parameter(
        "included_education_keywords", request, json=True
    )
    excluded_education_keywords = get_request_parameter(
        "excluded_education_keywords", request, json=True
    )
    included_bio_keywords = get_request_parameter(
        "included_bio_keywords", request, json=True
    )
    excluded_bio_keywords = get_request_parameter(
        "excluded_bio_keywords", request, json=True
    )
    included_location_keywords = get_request_parameter(
        "included_location_keywords", request, json=True
    )
    excluded_location_keywords = get_request_parameter(
        "excluded_location_keywords", request, json=True
    )
    included_skills_keywords = get_request_parameter(
        "included_skills_keywords", request, json=True
    )
    excluded_skills_keywords = get_request_parameter(
        "excluded_skills_keywords", request, json=True
    )
    years_of_experience_start = get_request_parameter(
        "years_of_experience_start", request, json=True
    )
    years_of_experience_end = get_request_parameter(
        "years_of_experience_end", request, json=True
    )
    included_industry_keywords = get_request_parameter(
        "included_industry_keywords", request, json=True
    )
    excluded_industry_keywords = get_request_parameter(
        "excluded_industry_keywords", request, json=True
    )

    prospects: list[dict] = find_prospects_by_segment_filters(
        client_sdr_id=client_sdr_id,
        segment_ids=segment_ids,
        included_title_keywords=included_title_keywords,
        excluded_title_keywords=excluded_title_keywords,
        included_seniority_keywords=included_seniority_keywords,
        excluded_seniority_keywords=excluded_seniority_keywords,
        included_company_keywords=included_company_keywords,
        excluded_company_keywords=excluded_company_keywords,
        included_education_keywords=included_education_keywords,
        excluded_education_keywords=excluded_education_keywords,
        included_bio_keywords=included_bio_keywords,
        excluded_bio_keywords=excluded_bio_keywords,
        included_location_keywords=included_location_keywords,
        excluded_location_keywords=excluded_location_keywords,
        included_skills_keywords=included_skills_keywords,
        excluded_skills_keywords=excluded_skills_keywords,
        years_of_experience_start=years_of_experience_start,
        years_of_experience_end=years_of_experience_end,
        archetype_ids=archetype_ids,
        included_industry_keywords=included_industry_keywords,
        excluded_industry_keywords=excluded_industry_keywords,
    )

    return jsonify({"prospects": prospects, "num_prospects": len(prospects)}), 200


@SEGMENT_BLUEPRINT.route("/extract_sales_nav_titles", methods=["POST"])
@require_user
def extract_sales_nav_titles(client_sdr_id: int):
    sales_nav_url = get_request_parameter(
        "sales_nav_url", request, json=True, required=True
    )

    data: dict = extract_data_from_sales_navigator_link(
        sales_nav_url=sales_nav_url,
    )

    return jsonify(data), 200


@SEGMENT_BLUEPRINT.route("/wipe_segment", methods=["POST"])
@require_user
def wipe_segment(client_sdr_id: int):
    segment_id = get_request_parameter("segment_id", request, json=True, required=True)

    segment: Segment = Segment.query.filter_by(
        client_sdr_id=client_sdr_id, id=segment_id
    ).first()
    if not segment:
        return "Segment not found", 404

    success, msg = wipe_segment_ids_from_prospects_in_segment(segment_id=segment_id)
    if success:
        return msg, 200

    return "Failed", 400


@SEGMENT_BLUEPRINT.route(
    "/add_unused_prospects_in_segment_to_campaign", methods=["POST"]
)
@require_user
def add_unused_prospects_in_segment_to_campaign_endpoint(client_sdr_id: int):
    segment_id = get_request_parameter("segment_id", request, json=True, required=True)
    campaign_id = get_request_parameter(
        "campaign_id", request, json=True, required=True
    )

    segment: Segment = Segment.query.filter_by(
        client_sdr_id=client_sdr_id, id=segment_id
    ).first()
    if not segment:
        return "Segment not found", 404

    client_archetype: ClientArchetype = ClientArchetype.query.filter_by(
        client_sdr_id=client_sdr_id, id=campaign_id
    ).first()
    if not client_archetype:
        return "Client archetype not found", 404

    success, msg = add_unused_prospects_in_segment_to_campaign(
        segment_id=segment_id, campaign_id=campaign_id
    )
    if success:
        return msg, 200

    return "Failed", 400


@SEGMENT_BLUEPRINT.route("/remove_prospects_from_segment", methods=["POST"])
@require_user
def post_remove_prospects_from_segment(client_sdr_id: int):
    prospect_ids = get_request_parameter(
        "prospect_ids", request, json=True, required=True
    )

    success, msg = remove_prospect_from_segment(
        client_sdr_id=client_sdr_id, prospect_ids=prospect_ids
    )

    if success:
        return msg, 200

    return "Failed to remove prospects", 400


@SEGMENT_BLUEPRINT.route("/auto_split_segment", methods=["POST"])
@require_user
def post_auto_split_segment_endpoint(client_sdr_id: int):
    segment_id = get_request_parameter("segment_id", request, json=True, required=True)

    auto_filters = get_request_parameter(
        "auto_filters", request, json=True, required=True
    )

    success = run_auto_segment(segment_id=segment_id, auto_filters=auto_filters)

    if success:
        return "Segment split", 200

    return "Failed to remove prospects", 400


@SEGMENT_BLUEPRINT.route("/segment_predictions", methods=["POST"])
@require_user
def get_segment_predictions(client_sdr_id: int):
    prospect_industries = get_request_parameter(
        "prospect_industries", request, json=True, required=True
    )
    prospect_seniorities = get_request_parameter(
        "prospect_seniorities", request, json=True, required=True
    )
    prospect_titles = get_request_parameter(
        "prospect_titles", request, json=True, required=True
    )
    prospect_education = get_request_parameter(
        "prospect_education", request, json=True, required=True
    )
    companies = get_request_parameter("companies", request, json=True, required=True)
    company_sizes = get_request_parameter(
        "company_sizes", request, json=True, required=True
    )

    predictions: list = get_segment_predicted_prospects(
        client_sdr_id=client_sdr_id,
        prospect_industries=prospect_industries,
        prospect_seniorities=prospect_seniorities,
        prospect_education=prospect_education,
        prospect_titles=prospect_titles,
        companies=companies,
        company_sizes=company_sizes,
    )

    return jsonify(predictions), 200


@SEGMENT_BLUEPRINT.route("/get_unused_segments", methods=["GET"])
@require_user
def get_unused_segments(client_sdr_id: int):
    """
    Get all unused segments for a given client_sdr.
    Unused segments are segments where all the prospects are not assigned to any campaign.

    Args:
        client_sdr_id (int): _description_

    Returns:
        _type_: _description_
    """

    segments: list[dict] = get_unused_segments_for_sdr(client_sdr_id)
    return jsonify(segments), 200


@SEGMENT_BLUEPRINT.route(
    "/<int:segment_id>/request_campaign_and_move_prospects", methods=["POST"]
)
@require_user
def request_campaign_and_move_prospects(client_sdr_id: int, segment_id: int):
    client_sdr: ClientSDR = ClientSDR.query.filter_by(id=client_sdr_id).first()
    client_id = client_sdr.client_id

    segment: Segment = Segment.query.filter_by(
        client_sdr_id=client_sdr_id, id=segment_id
    ).first()

    # Create archetype
    archetype_dict = create_client_archetype(
        client_id=client_id,
        client_sdr_id=client_sdr_id,
        archetype=segment.segment_title,
        filters={},
    )
    archetype_id = archetype_dict and archetype_dict["client_archetype_id"]

    if not archetype_id:
        return "Failed to create archetype", 400

    # Add Unusued Prospects from Segment into Campaign
    success, msg = add_unused_prospects_in_segment_to_campaign(
        segment_id=segment_id, campaign_id=archetype_id
    )

    # Create AI Request
    create_ai_requests(
        client_sdr_id=client_sdr_id,
        title="Requesting Campaign From Segment: " + segment.segment_title,
        description="Can you please create a campaign for the prospects in this segment: "
                    + segment.segment_title
                    + "?",
    )

    if success:
        return msg, 200

    return "Failed", 400


@SEGMENT_BLUEPRINT.route("/connect_apollo_query", methods=['POST'])
@require_user
def post_connect_saved_apollo_query_to_segment(client_sdr_id: int):
    segment_id = get_request_parameter("segment_id", request, json=True, required=True)
    saved_apollo_query_id = get_request_parameter("saved_apollo_query_id", request, json=True, required=True)

    success, msg = connect_saved_apollo_query_to_segment(
        segment_id=segment_id,
        saved_apollo_query_id=saved_apollo_query_id
    )

    if success:
        return msg, 200

    return "Failed", 400


@SEGMENT_BLUEPRINT.route("/transfer_segment", methods=['POST'])
@require_user
def post_transfer_segment(client_sdr_id: int):
    segment_id = get_request_parameter("segment_id", request, json=True, required=True)
    new_client_sdr_id = get_request_parameter("new_client_sdr_id", request, json=True, required=True)

    success, msg = transfer_segment(
        current_client_sdr_id=client_sdr_id,
        segment_id=segment_id,
        new_client_sdr_id=new_client_sdr_id
    )

    if not success:
        return msg, 400

    return msg, 200


@SEGMENT_BLUEPRINT.route("/duplicate_segment", methods=['POST'])
@require_user
def post_duplicate_segment(client_sdr_id: int):
    segment_id = get_request_parameter("segment_id", request, json=True, required=True)

    success, msg = duplicate_segment(
        segment_id=segment_id
    )

    if not success:
        return msg, 400

    return msg, 200


@SEGMENT_BLUEPRINT.route("/create_n_subsegments", methods=['POST'])
@require_user
def post_create_n_subsegments(client_sdr_id: int):
    segment_id = get_request_parameter("segment_id", request, json=True, required=True)
    num_batches = get_request_parameter("num_batches", request, json=True, required=True)

    success, msg = create_n_sub_batches_for_segment(
        segment_id=segment_id,
        num_batches=num_batches
    )

    if not success:
        return msg, 400

    return msg, 200


@SEGMENT_BLUEPRINT.route("/move_segment", methods=['POST'])
@require_user
def post_move_segment(client_sdr_id: int):
    segment_id = get_request_parameter("segment_id", request, json=True, required=True)
    new_parent_segment_id = get_request_parameter("new_parent_segment_id", request, json=True, required=False)

    success, msg = move_segment(
        client_sdr_id=client_sdr_id,
        segment_id=segment_id,
        new_parent_segment_id=new_parent_segment_id
    )

    if not success:
        return msg, 400

    return msg, 200


@SEGMENT_BLUEPRINT.route("/toggle_segment_auto_scrape", methods=['POST'])
@require_user
def post_toggle_segment_auto_scrape(client_sdr_id: int):
    segment_id = get_request_parameter("segment_id", request, json=True, required=True)

    success, msg = toggle_auto_scrape_for_segment(client_sdr_id, segment_id)

    if success:
        return msg, 200

    return msg, 400


@SEGMENT_BLUEPRINT.route("/run_scrapes", methods=['POST'])
@require_user
def post_run_scrapes(client_sdr_id: int):
    segment_id = get_request_parameter("segment_id", request, json=True, required=True)
    num_scrapes = get_request_parameter("num_scrapes", request, json=True, required=True)

    success, msg = run_n_scrapes_for_segment(client_sdr_id, segment_id, num_scrapes)

    if success:
        return msg, 200

    return msg, 400


@SEGMENT_BLUEPRINT.route("/set_current_scrape_page", methods=['POST'])
@require_user
def post_set_current_scrape_page(client_sdr_id: int):
    segment_id = get_request_parameter("segment_id", request, json=True, required=True)
    current_scrape_page = get_request_parameter("current_scrape_page", request, json=True, required=True)

    success, msg = set_current_scrape_page_for_segment(client_sdr_id, segment_id, current_scrape_page)

    if success:
        return msg, 200

    return msg, 400


@SEGMENT_BLUEPRINT.route("/tags/create", methods=["POST"])
@require_user
def create_segment_tag_endpoint(client_sdr_id: int):
    segment_id = get_request_parameter("segment_id", request, json=True, required=True)
    name = get_request_parameter("name", request, json=True, required=True)
    color = get_request_parameter("color", request, json=True, required=True)

    success, tag = create_and_add_tag_to_segment(segment_id, client_sdr_id, name, color)
    if success:
        return jsonify(tag.to_dict()), 201
    else:
        return jsonify({"error": "Failed to create or add tag"}), 400


@SEGMENT_BLUEPRINT.route("/tags/add", methods=["POST"])
@require_user
def add_tag_to_segment(client_sdr_id: int):
    tag_id = get_request_parameter("tag_id", request, json=True, required=True)
    segment_id = get_request_parameter("segment_id", request, json=True, required=True)

    result, message = attach_tag_to_segment(segment_id, client_sdr_id, tag_id)
    if result:
        return jsonify({"message": message}), 200
    else:
        return jsonify({"error": message}), 400


@SEGMENT_BLUEPRINT.route("/tags/<int:tag_id>", methods=['DELETE'])
@require_user
def delete_tag_from_segment(client_sdr_id: int, tag_id: int):
    print('params are', client_sdr_id, tag_id)
    success, message = delete_tag_from_all_segments(client_sdr_id, tag_id)
    if success:
        return jsonify({"message": message}), 200
    else:
        return jsonify({"error": message}), 400


@SEGMENT_BLUEPRINT.route("/tags/remove", methods=["POST"])
@require_user
def remove_tag_from_segment_endpoint(client_sdr_id: int):
    tag_id = get_request_parameter("tag_id", request, json=True, required=True)
    segment_id = get_request_parameter("segment_id", request, json=True, required=True)
    success, message = remove_tag_from_segment(segment_id, tag_id)
    if success:
        return "Tag removed from segment", 200
    else:
        return message, 400


@SEGMENT_BLUEPRINT.route("/tags", methods=["GET"])
@require_user
def get_segment_tags(client_sdr_id: int):
    success, tags = get_segment_tags_for_sdr(client_sdr_id)
    if success:
        return jsonify([tag.to_dict() for tag in tags]), 200
    else:
        return jsonify([]), 200
