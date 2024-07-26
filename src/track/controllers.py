from flask import Blueprint, jsonify, request
from src.authentication.decorators import require_user
from src.client.models import ClientSDR
from app import db
from src.prospecting.models import Prospect
from src.segment.models import Segment
from src.track.models import DeanonymizedContact, ICPRouting, TrackEvent
from src.track.services import create_track_event, deanonymized_contacts, get_client_track_source_metadata, get_most_recent_track_event, get_website_tracking_script, top_locations, track_event_history, verify_track_source, create_icp_route, update_icp_route, get_all_icp_routes, get_icp_route_details, categorize_prospect, categorize_deanonyomized_prospects
from src.track.services import find_company_from_orginfo

from src.utils.request_helpers import get_request_parameter

TRACK_BLUEPRINT = Blueprint("track", __name__)


@TRACK_BLUEPRINT.route("/webpage", methods=["POST"])
def create():
    ip = get_request_parameter("ip", request, json=True, required=True)
    page = get_request_parameter("page", request, json=True, required=True)
    track_key = get_request_parameter("track_key", request, json=True, required=True)

    success = create_track_event(ip=ip, page=page, track_key=track_key)


    if not success:
        return "ERROR", 400
    return "OK", 200

# def test_track_event():
#     page = "hunter test"
#     track_key = "X8492aa92JOIp2XXMV1382"
#     ips = [
#         "66.75.74.9",
#     ]
#     for ip in ips:
#         success = create_track_event(ip=ip, page=page, track_key=track_key, force_track_again=True)
#         print(f'success for IP {ip} is', success)
    
#     print('done')

@TRACK_BLUEPRINT.route("/get_script", methods=["GET"])
@require_user
def get_script(client_sdr_id: int):
    script = get_website_tracking_script(client_sdr_id)
    return jsonify({
        "script": script
    }), 200

@TRACK_BLUEPRINT.route("/verify_source", methods=["GET"])
@require_user
def verify_source(client_sdr_id: int):
    success, msg = verify_track_source(client_sdr_id)
    if not success:
        return msg, 400
    return msg, 200

@TRACK_BLUEPRINT.route("/most_recent_track_event", methods=["GET"])
@require_user
def most_recent_track_event(client_sdr_id: int):
    event = get_most_recent_track_event(client_sdr_id)
    return jsonify(event.to_dict()), 200

@TRACK_BLUEPRINT.route("/track_source_metadata", methods=["GET"])
@require_user
def track_source_metadata(client_sdr_id: int):
    metadata = get_client_track_source_metadata(client_sdr_id)
    return jsonify(metadata), 200

@TRACK_BLUEPRINT.route("/get_track_event_history", methods=["GET"])
@require_user
def get_track_event_history(client_sdr_id: int):
    days = get_request_parameter("days", request, json=False, required=False, default_value=14)
    
    history = track_event_history(client_sdr_id, days)
    locations = top_locations(client_sdr_id, days)
    return jsonify({
        "traffic": history,
        "locations": locations
    }), 200

@TRACK_BLUEPRINT.route("/get_deanonomized_contacts", methods=["GET"])
@require_user
def get_deanonomized_contacts(client_sdr_id: int):
    days = get_request_parameter("days", request, json=False, required=False, default_value=14)
    contacts = deanonymized_contacts(client_sdr_id, days)
    return jsonify({
        "contacts": contacts
    }), 200
    
@TRACK_BLUEPRINT.route("/create_icp_route", methods=["POST"])
@require_user
def create_icp_route_endpoint(client_sdr_id: int):
    title = get_request_parameter("title", request, json=True, required=True)
    description = get_request_parameter("description", request, json=True, required=True)
    filter_company = get_request_parameter("filter_company", request, json=True, required=True)
    ai_mode = get_request_parameter("ai_mode", request, json=True, required=True)
    rules = get_request_parameter("rules", request, json=True, required=False)
    filter_title = get_request_parameter("filter_title", request, json=True, required=True)
    filter_location = get_request_parameter("filter_location", request, json=True, required=True)
    filter_company_size = get_request_parameter("filter_company_size", request, json=True, required=True)
    segment_id = get_request_parameter("segment_id", request, json=True, required=False)
    send_slack = get_request_parameter("send_slack", request, json=True, required=False, default_value=False)

    icp_route = create_icp_route(
        client_sdr_id,
        title,
        description,
        filter_company,
        ai_mode,
        rules,
        filter_title,
        filter_location,
        filter_company_size,
        segment_id,
        send_slack
    )

    return jsonify(icp_route.to_dict()), 201

@TRACK_BLUEPRINT.route("/delete_icp_route/<int:icp_route_id>", methods=["DELETE"])
@require_user
def delete_icp_route_endpoint(client_sdr_id: int, icp_route_id: int):
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    icp_route: ICPRouting = ICPRouting.query.get(icp_route_id)
    #nullify any deanonymized contacts that were associated with this icp route
    deanonymized_contacts: list[DeanonymizedContact] = DeanonymizedContact.query.filter_by(icp_route_id=icp_route_id).all()
    for contact in deanonymized_contacts:
        contact.icp_route_id = None
        db.session.add(contact)
    db.session.commit()
    if not icp_route or icp_route.client_id != client_sdr.client_id:
        return "ICP Route not found", 404

    db.session.delete(icp_route)
    db.session.commit()

    return jsonify({"message": "ICP Route deleted successfully"}), 200


@TRACK_BLUEPRINT.route("/get_user_web_visits", methods=["GET"])
@require_user
def get_user_web_visits(client_sdr_id: int):
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if not client_sdr:
        return "Client not found", 404

    # Query to get distinct prospects and their visit counts
    prospects: list[Prospect] = db.session.query(
        Prospect.id,
        Prospect.full_name,
        Prospect.company,
        Prospect.title,
        Prospect.img_url,
        Prospect.linkedin_url,
        db.func.count(TrackEvent.id).label('num_visits'),
        db.func.array_agg(db.distinct(TrackEvent.window_location)).label('window_locations'),
        db.func.max(TrackEvent.created_at).label('most_recent_visit'),
        Segment.segment_title.label('segment_name')
    ).join(TrackEvent, TrackEvent.prospect_id == Prospect.id
    ).outerjoin(Segment, Segment.id == Prospect.segment_id
    ).filter(
        TrackEvent.prospect_id != None,
        Prospect.client_id == client_sdr.client_id
    ).group_by(
        Prospect.id,
        Segment.segment_title
    ).order_by(
        db.func.max(TrackEvent.created_at).desc()
    ).all()

    # Format the result
    formatted_prospects = []
    for prospect in prospects:
        formatted_prospects.append({
            "id": prospect.id,
            "full_name": prospect.full_name,
            "img_url": prospect.img_url,
            "company": prospect.company,
            "title": prospect.title,
            "linkedin_url": prospect.linkedin_url,
            "num_visits": prospect.num_visits,
            "window_locations": prospect.window_locations,
            "most_recent_visit": prospect.most_recent_visit,
            "segment_name": prospect.segment_name
        })

    return jsonify(formatted_prospects), 200


@TRACK_BLUEPRINT.route("/update_icp_route/<int:icp_route_id>", methods=["PUT"])
@require_user
def update_icp_route_endpoint(client_sdr_id: int, icp_route_id: int):
    title = get_request_parameter("title", request, json=True, required=False)
    description = get_request_parameter("description", request, json=True, required=False)
    filter_company = get_request_parameter("filter_company", request, json=True, required=False)
    filter_title = get_request_parameter("filter_title", request, json=True, required=False)
    filter_location = get_request_parameter("filter_location", request, json=True, required=False)
    filter_company_size = get_request_parameter("filter_company_size", request, json=True, required=False)
    segment_id = get_request_parameter("segment_id", request, json=True, required=False)
    send_slack = get_request_parameter("send_slack", request, json=True, required=False)
    active = get_request_parameter("active", request, json=True, required=False)
    rules = get_request_parameter("rules", request, json=True, required=False)
    ai_mode = get_request_parameter("ai_mode", request, json=True, required=False)

    icp_route = update_icp_route(
        client_sdr_id,
        icp_route_id,
        title,
        description,
        filter_company,
        ai_mode,
        rules,
        filter_title,
        filter_location,
        filter_company_size,
        segment_id,
        send_slack,
        active
    )

    if isinstance(icp_route, str):
        return icp_route, 404

    return jsonify(icp_route.to_dict()), 200

@TRACK_BLUEPRINT.route("/get_all_icp_routes", methods=["GET"])
@require_user
def get_all_icp_routes_endpoint(client_sdr_id: int):
    icp_routes: list[ICPRouting] = get_all_icp_routes(client_sdr_id)
    return jsonify([route for route in icp_routes]), 200


@TRACK_BLUEPRINT.route("/get_icp_route_details/<int:icp_route_id>", methods=["GET"])
@require_user
def get_icp_route_details_endpoint(client_sdr_id: int, icp_route_id: int):
    icp_route = get_icp_route_details(client_sdr_id, icp_route_id)
    
    if isinstance(icp_route, str):
        return icp_route, 404

    return jsonify(icp_route), 200

@TRACK_BLUEPRINT.route("/auto_classify_deanonymized_contacts", methods=["POST"])
@require_user
def auto_classify_deanonymized_contacts(client_sdr_id: int):
    #todo, change these to prospect ids.
    deanonymized_contact_ids = get_request_parameter("deanonymized_contact_ids", request, json=True, required=True)

    success = categorize_deanonyomized_prospects(deanonymized_contact_ids, True)

    if not success:
        return "ERROR", 400
    
    return "OK", 200