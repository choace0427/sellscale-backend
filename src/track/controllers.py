import datetime
import os
from flask import Blueprint, jsonify, request, current_app
from src.authentication.decorators import require_user
from src.client.models import ClientSDR
from app import app, db
from src.prospecting.models import Prospect
from src.prospecting.services import add_prospect, get_linkedin_slug_from_url, get_navigator_slug_from_url
from src.research.linkedin.services import research_personal_profile_details
from src.segment.models import Segment
from src.track.models import DeanonymizedContact, ICPRouting, TrackEvent
from src.track.services import categorize_via_gpt_direct, categorize_via_rules_direct, create_track_event, deanonymized_contacts, get_client_track_source_metadata, get_most_recent_track_event, get_website_tracking_script, top_locations, track_event_history, verify_track_source, create_icp_route, update_icp_route, get_all_icp_routes, get_icp_route_details, categorize_prospect, categorize_deanonyomized_prospects
from src.track.services import find_company_from_orginfo
from src.utils.abstract.attr_utils import deep_get

from src.utils.request_helpers import get_request_parameter

TRACK_BLUEPRINT = Blueprint("track", __name__)
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    storage_uri=os.environ.get("CELERY_REDIS_URL"),
)
limiter.init_app(app)

@TRACK_BLUEPRINT.route("/webpage", methods=["POST"])
@limiter.limit("1 per 3 seconds")
def create():
    ip = get_request_parameter("ip", request, json=True, required=True)
    page = get_request_parameter("page", request, json=True, required=True)
    track_key = get_request_parameter("track_key", request, json=True, required=True)

    if track_key != 'X8492aa92JOIp2XXMV1382':
        return "ERROR", 400

    success = create_track_event(ip=ip, page=page, track_key=track_key)

    if not success:
        return "ERROR", 400
    return "OK", 200

@TRACK_BLUEPRINT.route("/simulate_linkedin_bucketing", methods=["POST"])
@require_user
def simulate_linkedin_bucketing(client_sdr_id: int):
    # get the linkedin url from the request
    linkedin_url = get_request_parameter("linkedin_url", request, json=True, required=True)

    visited_page = get_request_parameter("visited_page", request, json=True, parameter_type=str, required=False) or ''

    slug = None
    if "/in/" in linkedin_url:
        slug = get_linkedin_slug_from_url(linkedin_url)
    elif "/lead/" in linkedin_url:
        slug = get_navigator_slug_from_url(linkedin_url)
    # could optionally use iscraper payload cache.
    if not slug:
        return "ERROR", 400
    print('simulating linkedin lookup with slug', slug)
    payload = research_personal_profile_details(profile_id=slug)
    
    # Assign variables to relevant data about this person
    first_name = payload.get("first_name")
    last_name = payload.get("last_name")
    profile_picture = payload.get("profile_picture")
    industry = payload.get("industry")
    location = payload.get("location", {}).get("default")
    connections_count = payload.get("network_info", {}).get("connections_count")
    skills = payload.get("skills", [])
    position_groups = payload.get("position_groups", [])
    
    # Add prospect using the extracted data
    company_name = deep_get(payload, "position_groups.0.company.name")
    company_url = deep_get(payload, "position_groups.0.company.url")
    employee_count = (
        str(deep_get(payload, "position_groups.0.company.employees.start"))
        + "-"
        + str(deep_get(payload, "position_groups.0.company.employees.end"))
    )
    full_name = f"{first_name} {last_name}"
    linkedin_url = f"linkedin.com/in/{slug}"
    linkedin_bio = deep_get(payload, "summary")
    title = deep_get(payload, "sub_title")
    twitter_url = None

    education_1 = deep_get(payload, "education.0.school.name")
    education_2 = deep_get(payload, "education.1.school.name")

    prospect_location = "{}, {}, {}".format(
        deep_get(payload, "location.city", default="") or "",
        deep_get(payload, "location.state", default="") or "",
        deep_get(payload, "location.country", default="") or "",
    )
    company_location = deep_get(
        payload, "position_groups.0.profile_positions.0.location", default=""
    )

    # Health Check fields
    followers_count = deep_get(payload, "network_info.followers_count") or 0

    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if not client_sdr:
        return "ClientSDR not found", 404
    client_id = client_sdr.client_id

    rule_based_icp_routes: list[ICPRouting] = ICPRouting.query.filter(
        ICPRouting.client_id == client_id,
        ICPRouting.active == True,
        ICPRouting.ai_mode == False
    ).all()

    met_conditions = None
    for rule in rule_based_icp_routes: 
        route, met_conditions = categorize_via_rules_direct(
            prospect_name=full_name,
            prospect_company=company_name,
            prospect_title=title,
            webpage_click=visited_page,
            icp_route_id=rule.id
        )
        if route != -1:
            route : ICPRouting = ICPRouting.query.get(route)
            return jsonify({
                "icp_route": route.to_dict(),
                "prospect": {
                    "first_name": first_name,
                    "last_name": last_name,
                    "full_name": full_name,
                    "profile_picture": profile_picture,
                    "industry": industry,
                    "location": location,
                    "connections_count": connections_count,
                    "skills": skills,
                    "position_groups": position_groups,
                    "company_name": company_name,
                    "company_url": company_url,
                    "employee_count": employee_count,
                    "linkedin_url": linkedin_url,
                    "linkedin_bio": linkedin_bio,
                    "title": title,
                    "twitter_url": twitter_url,
                    "education_1": education_1,
                    "education_2": education_2,
                    "prospect_location": prospect_location,
                    "company_location": company_location,
                    "followers_count": followers_count
                },
                "met_conditions": met_conditions
            }), 200

    #look up if there are active ai icp routes

    ai_icp_routes: list[ICPRouting] = ICPRouting.query.filter(
        ICPRouting.client_id == client_id,
        ICPRouting.active == True,
        ICPRouting.ai_mode == True
    ).all()

    if not ai_icp_routes:
        return "No active ICP routes found", 404

    gpt_route_id = categorize_via_gpt_direct(
        prospect_name=full_name,
        prospect_company=company_name,
        prospect_title=title,
        prospect_linkedin=linkedin_url,
        prospect_email='Not available',
        prospect_location=prospect_location,
        prospect_company_size=employee_count,
        track_event_created_at=datetime.datetime.now(),
        client_id=client_id
    )

    if gpt_route_id != -1:
        route : ICPRouting = ICPRouting.query.get(gpt_route_id)
        return jsonify({
            "icp_route": route.to_dict(),
            "prospect": {
                "first_name": first_name,
                "last_name": last_name,
                "full_name": full_name,
                "profile_picture": profile_picture,
                "industry": industry,
                "location": location,
                "connections_count": connections_count,
                "skills": skills,
                "position_groups": position_groups,
                "company_name": company_name,
                "company_url": company_url,
                "employee_count": employee_count,
                "linkedin_url": linkedin_url,
                "linkedin_bio": linkedin_bio,
                "title": title,
                "twitter_url": twitter_url,
                "education_1": education_1,
                "education_2": education_2,
                "prospect_location": prospect_location,
                "company_location": company_location,
                "followers_count": followers_count
            }
        }), 200

    return "Route not found", 404





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

@TRACK_BLUEPRINT.route("/fetch_user_buckets", methods=["GET"])
@require_user
def fetch_user_buckets(client_sdr_id: int):
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if not client_sdr:
        return "ClientSDR not found", 404

    client_id = client_sdr.client_id
    buckets = ICPRouting.query.filter_by(client_id=client_id).all()
    return jsonify([bucket.to_dict() for bucket in buckets]), 200



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
        Prospect.icp_routing_id,
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
    from collections import defaultdict

    grouped_prospects = defaultdict(lambda: {
        "id": None,
        "full_name": None,
        "img_url": None,
        "company": None,
        "icp_routing_id": None,
        "title": None,
        "linkedin_url": None,
        "num_visits": 0,
        "window_locations": set(),
        "most_recent_visit": None,
        "segment_name": None
    })

    for prospect in prospects:

        full_name = prospect.full_name
        grouped = grouped_prospects[full_name]

        if grouped["id"] is None:
            grouped["id"] = prospect.id
        if grouped["full_name"] is None:
            grouped["full_name"] = full_name
        if grouped["img_url"] is None:
            grouped["img_url"] = prospect.img_url
        if grouped["company"] is None:
            grouped["company"] = prospect.company
        if grouped["icp_routing_id"] is None:
            grouped["icp_routing_id"] = prospect.icp_routing_id
        if grouped["title"] is None:
            grouped["title"] = prospect.title
        if grouped["linkedin_url"] is None:
            grouped["linkedin_url"] = prospect.linkedin_url

        grouped["num_visits"] += prospect.num_visits
        grouped["window_locations"].update(prospect.window_locations)
        
        if not grouped["most_recent_visit"] or prospect.most_recent_visit > grouped["most_recent_visit"]:
            grouped["most_recent_visit"] = prospect.most_recent_visit
        
        if prospect.segment_name and grouped["segment_name"] is None:
            grouped["segment_name"] = prospect.segment_name


    formatted_prospects = [
        {
            "id": value["id"],
            "full_name": value["full_name"],
            "img_url": value["img_url"],
            "company": value["company"],
            "icp_routing_id": value["icp_routing_id"],
            "title": value["title"],
            "linkedin_url": value["linkedin_url"],
            "num_visits": value["num_visits"],
            "window_locations": list(value["window_locations"]),
            "most_recent_visit": value["most_recent_visit"],
            "segment_name": value["segment_name"]
        }
        for value in grouped_prospects.values()
    ]

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