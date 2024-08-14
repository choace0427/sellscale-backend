from typing import Optional
from app import db
from flask import Blueprint, jsonify, request
import requests

from src.apollo.services import save_apollo_cookies, get_apollo_cookies, get_fuzzy_company_list
from src.authentication.decorators import require_user
from src.client.models import ClientSDR
from src.contacts.models import SavedApolloQuery
from src.prospecting.models import Prospect
from src.segment.models import Segment
from src.utils.request_helpers import get_request_parameter
from src.apollo.models import ApolloCookies


APOLLO_REQUESTS = Blueprint("apollo", __name__)


@APOLLO_REQUESTS.route("/cookies", methods=["GET"])
def get_get_apollo_cookies():
    """
    Gets Apollo cookies.
    """
    cookies, csrf_token = get_apollo_cookies()

    if not cookies:
        return (
            jsonify({"status": "error", "message": "Error getting Apollo cookies."}),
            500,
        )

    return (
        jsonify(
            {
                "status": "success",
                "data": {"cookies": cookies, "csrf_token": csrf_token},
            }
        ),
        200,
    )


@APOLLO_REQUESTS.route("/cookies", methods=["POST"])
def post_save_apollo_cookies():
    """
    Saves Apollo cookies.
    """
    cookies = get_request_parameter(
        "cookies", request, json=True, required=True, parameter_type=str
    )
    csrf_token = get_request_parameter(
        "csrf_token", request, json=True, required=True, parameter_type=str
    )

    if not save_apollo_cookies(cookies=cookies, csrf_token=csrf_token):
        return (
            jsonify({"status": "error", "message": "Error saving Apollo cookies."}),
            500,
        )

    return jsonify({"status": "success", "message": "Apollo cookies saved."}), 200

def fetch_tags(q_tag_fuzzy_name, cookies: Optional[tuple] = None):
    if not cookies:
        cookies, csrf_token = get_apollo_cookies()
    else:
        csrf_token = cookies[1]
        cookies = cookies[0]

    headers = {
        "x-csrf-token": csrf_token,
        "cookie": cookies,
    }
    params = {
        "q_tag_fuzzy_name": q_tag_fuzzy_name,
        "kind": "linkedin_industry",
        "display_mode": "fuzzy_select_mode",
        "cacheKey": 1708721393701,
    }
    response = requests.get(
        "https://app.apollo.io/api/v1/tags/search", headers=headers, params=params
    )
    if response.status_code != 200:
        return {"status": "error", "message": "Error searching tags."}, response.status_code

    return {"status": "success", "data": response.json()}, 200

@APOLLO_REQUESTS.route("/tags/search", methods=["GET"])
def search_tags():
    """
    Searches for tags on Apollo.
    """
    q_tag_fuzzy_name = get_request_parameter(
        "q_tag_fuzzy_name", request, json=False, required=True, parameter_type=str
    )
    result, status_code = fetch_tags(q_tag_fuzzy_name)
    return jsonify(result), status_code

@APOLLO_REQUESTS.route("/tags/searchTechnology", methods=["GET"])
def search_technology_tags():
    """
    Searches for technology tags on Apollo.
    """
    q_tag_fuzzy_name = get_request_parameter(
        "q_tag_fuzzy_name", request, json=False, required=True, parameter_type=str
    )

    response = get_fuzzy_company_list(q_tag_fuzzy_name)

    if response.status_code != 200:
        return (
            jsonify({"status": "error", "message": "Error searching technology tags."}),
            response.status_code,
        )
    return jsonify({"status": "success", "data": response.json()}), 200

@APOLLO_REQUESTS.route("/save_query", methods=["POST"])
@require_user
def save_query(client_sdr_id):
    """
    Saves a query on Apollo.
    """
    data = request.get_json()
    current_saved_query_id = data.get("currentSavedQueryId")
    editing_query_id = data.get("editingQuery")
    filter_name = data.get("name")

    client_sdr: ClientSDR = ClientSDR.query.filter_by(id=client_sdr_id).first()
    current_query: SavedApolloQuery = SavedApolloQuery.query.filter_by(id=current_saved_query_id).first()

    current_query_client_sdr_id = current_query.client_sdr_id
    current_query_client_sdr: ClientSDR = ClientSDR.query.filter_by(id=current_query_client_sdr_id).first()

    if not current_query or current_query_client_sdr.client_id != client_sdr.client_id:
        return jsonify({"status": "error", "message": "Current query not found."}), 404

    if editing_query_id:
        editing_query: SavedApolloQuery = SavedApolloQuery.query.filter_by(id=editing_query_id).first()
        if not editing_query:
            return jsonify({"status": "error", "message": "Editing query not found."}), 404

        # Copy data from current_query to editing_query
        editing_query.data = current_query.data
        editing_query.results = current_query.results
        editing_query.num_results = current_query.num_results
        editing_query.custom_name = filter_name
    else:
        current_query.custom_name = filter_name

    db.session.commit()
    return jsonify({"status": "success", "data": 'success'}), 200

@APOLLO_REQUESTS.route("/get_all_saved_queries", methods=["GET"])
@require_user
def get_all_saved_queries(client_sdr_id):
    """
    Gets all saved Apollo queries for a client SDR where custom_name is not null,
    ordered by updated_at.
    """
    #1. get all client_sdr_id attached to the client

    client_sdr: ClientSDR = ClientSDR.query.filter_by(id=client_sdr_id).first()
    client_sdrs: list[ClientSDR] = ClientSDR.query.filter_by(client_id=client_sdr.client_id).all()

    client_sdr_ids = [client_sdr.id for client_sdr in client_sdrs]

    queries: list[SavedApolloQuery] = SavedApolloQuery.query.filter(
        SavedApolloQuery.client_sdr_id.in_(client_sdr_ids),
        SavedApolloQuery.custom_name.isnot(None),
        # SavedApolloQuery.value_proposition.isnot(None),
        # SavedApolloQuery.segment_description.isnot(None),
        SavedApolloQuery.is_icp_filter.isnot(True)
    ).order_by(SavedApolloQuery.updated_at.desc()).all()

    result = [
        query.to_dict()
        for query in queries
    ]

    return jsonify({"status": "success", "data": result}), 200

@APOLLO_REQUESTS.route("/update_segment_description/<int:prefilter_id>", methods=["PUT"])
@require_user
def update_segment_description(client_sdr_id, prefilter_id):
    """
    Updates the segment_description of the prefilter given the ID.
    """
    data = request.get_json()
    new_segment_description = data.get("segment_description")

    if not new_segment_description:
        return jsonify({"status": "error", "message": "Segment description is required."}), 400

    prefilter: SavedApolloQuery = SavedApolloQuery.query.filter_by(id=prefilter_id, is_prefilter=True).first()

    if not prefilter:
        return jsonify({"status": "error", "message": "Prefilter not found."}), 404

    if prefilter.client_sdr_id != client_sdr_id:
        return jsonify({"status": "error", "message": "You are not authorized to update this prefilter."}), 403

    prefilter.segment_description = new_segment_description
    db.session.commit()

    return jsonify({"status": "success", "message": "Segment description updated successfully."}), 200


@APOLLO_REQUESTS.route("/get_all_icp_queries", methods=["GET"])
@require_user
def get_all_icp_queries(client_sdr_id):
    """
    Gets all saved Apollo queries for a client SDR where custom_name is not null,
    ordered by updated_at.
    """
    client_sdr: ClientSDR = ClientSDR.query.filter_by(id=client_sdr_id).first()
    client_sdrs: list[ClientSDR] = ClientSDR.query.filter_by(client_id=client_sdr.client_id).all()

    client_sdr_ids = [client_sdr.id for client_sdr in client_sdrs]

    queries: list[SavedApolloQuery] = SavedApolloQuery.query.filter(
        SavedApolloQuery.client_sdr_id.in_(client_sdr_ids),
        SavedApolloQuery.custom_name.isnot(None),
        SavedApolloQuery.is_icp_filter==True
    ).order_by(SavedApolloQuery.updated_at.desc()).all()

    result = [
        query.to_dict()
        for query in queries
    ]

    return jsonify({"status": "success", "data": result}), 200

@APOLLO_REQUESTS.route("/get_saved_query/<int:saved_query_id>", methods=["GET"])
@require_user
def get_saved_query(client_sdr_id, saved_query_id):
    """
    Gets a specific saved Apollo query by ID for a client SDR.
    """
    client_sdr: ClientSDR = ClientSDR.query.filter_by(id=client_sdr_id).first()
    query: SavedApolloQuery = SavedApolloQuery.query.filter_by(id=saved_query_id).first()

    company_breadcrumbs = [breadcrumb for breadcrumb in query.results['breadcrumbs'] if breadcrumb.get('label') == 'Companies']
    if company_breadcrumbs and len(company_breadcrumbs) == 1 and not isinstance(company_breadcrumbs[0].get('value'), str):
        from src.company.models import Company
        company_ids = [id for sublist in [breadcrumb['value'] for breadcrumb in company_breadcrumbs] for id in sublist]
        #query all companies with the company_ids and filter out companies with empty names 
        #sorry TWITTER
        companies: list[Company] = Company.query.filter(Company.apollo_uuid.in_(company_ids), db.func.length(Company.name) > 1).all()
        company_map = {company.apollo_uuid: company for company in companies}

        # Remove the 'Companies' breadcrumb and construct new breadcrumbs in one pass
        new_breadcrumbs = [
            {
                'label': 'Companies',
                'value': company.apollo_uuid,
                'display_name': company.name,
                'logo_url': company.img_logo_url or ""
            }
            for company_id in company_ids if (company := company_map.get(company_id))
        ]

        query.results['breadcrumbs'] = [
            breadcrumb for breadcrumb in query.results['breadcrumbs'] if breadcrumb.get('label') != 'Companies'
        ] + new_breadcrumbs

    query_client_sdr_id = query.client_sdr_id
    query_client_sdr: ClientSDR = ClientSDR.query.filter_by(id=query_client_sdr_id).first()
    
    if not query or query_client_sdr.client_id != client_sdr.client_id:
        return jsonify({"status": "error", "message": "Query not found."}), 404

    return jsonify({"status": "success", "data": query.to_dict()}), 200

@APOLLO_REQUESTS.route("/<int:saved_query_id>", methods=["DELETE"])
@require_user
def delete_saved_query(client_sdr_id, saved_query_id):
    """
    Deletes a specific saved Apollo query by ID for a client SDR.
    """
    query: SavedApolloQuery = SavedApolloQuery.query.filter_by(id=saved_query_id).first()
    #check if the query belongs under the client
    client_sdr: ClientSDR = ClientSDR.query.filter_by(id=client_sdr_id).first()

    query_client_sdr_id = query.client_sdr_id
    query_client_sdr: ClientSDR = ClientSDR.query.filter_by(id=query_client_sdr_id).first()

    if not query or query_client_sdr.client_id != client_sdr.client_id:
        return jsonify({"status": "error", "message": "Query not found."}), 404

    db.session.delete(query)
    db.session.commit()

    return jsonify({"status": "success", "message": "Pre-filter deleted successfully"}), 200


#this is not a good name for this route, it should be something like update_apollo_query
@APOLLO_REQUESTS.route("/update_segment", methods=["PUT"])
@require_user
def update_segment(client_sdr_id):
    """
    Updates a specific field of an existing segment for a client SDR.
    """
    data = request.get_json()
    segment_id = data.get("id")
    field = data.get("field")
    value = data.get("value")

    print('updating field data', value, 'for field', field)   

    if not segment_id or not field:
        return jsonify({"status": "error", "message": "Segment ID and field are required."}), 400
    
    #check if the segment belongs under the client

    client_sdr: ClientSDR = ClientSDR.query.filter_by(id=client_sdr_id).first()
    query: SavedApolloQuery = SavedApolloQuery.query.filter_by(id=segment_id).first()

    query_client_sdr_id = query.client_sdr_id
    query_client_sdr: ClientSDR = ClientSDR.query.filter_by(id=query_client_sdr_id).first()

    if not query or query_client_sdr.client_id != client_sdr.client_id:
        return jsonify({"status": "error", "message": "Segment not found."}), 404

    setattr(query, field, value)

    db.session.commit()

    return jsonify({"status": "success", "message": "Segment updated successfully."}), 200


@APOLLO_REQUESTS.route("/segments", methods=["GET"])
@require_user
def get_segments(client_sdr_id: int):
    """
    Retrieves segments and their associated prospect counts for a client SDR.
    """
    segments = db.session.query(
        Segment.id,
        Segment.segment_title,
        db.func.count(db.distinct(Prospect.id))
    ).join(
        ClientSDR, ClientSDR.id == Segment.client_sdr_id
    ).outerjoin(
        Prospect, Prospect.segment_id == Segment.id
    ).filter(
        Segment.client_sdr_id == client_sdr_id
    ).group_by(
        Segment.id, Segment.segment_title
    ).order_by(
        Segment.segment_title
    ).all()

    result = [
        {
            "id": segment,
            "segment_title": segment_title,
            "prospect_count": prospect_count
        }
        for segment, segment_title, prospect_count in segments
    ]

    return jsonify({"status": "success", "data": result}), 200
