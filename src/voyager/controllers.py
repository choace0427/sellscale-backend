from flask import Blueprint, jsonify, request
from src.voyager.services import fetch_li_prospects_for_sdr
from src.prospecting.models import Prospect
from src.client.models import ClientSDR
from src.voyager.services import update_linkedin_cookies, fetch_conversation, get_profile_urn_id, clear_linkedin_cookies
from src.authentication.decorators import require_user
from src.utils.request_helpers import get_request_parameter
from src.voyager.linkedin import LinkedIn
from app import db
import time

VOYAGER_BLUEPRINT = Blueprint("voyager", __name__)


@VOYAGER_BLUEPRINT.route("/profile/self", methods=["GET"])
@require_user
def get_self_profile(client_sdr_id: int):
    """Get profile data for the SDR"""

    api = LinkedIn(client_sdr_id)
    profile = api.get_user_profile(use_cache=False)
    if(not api.is_valid()):
      return jsonify({"message": "Invalid LinkedIn cookies"}), 403
    
    # If the SDR's profile img is expired, update it
    if profile and time.time()*1000 > int(api.client_sdr.img_expire):
      api.client_sdr.img_url = profile.get("miniProfile", {}).get("picture", {}).get("com.linkedin.common.VectorImage", {}).get("rootUrl", "")+profile.get("miniProfile", {}).get("picture", {}).get("com.linkedin.common.VectorImage", {}).get("artifacts", [])[2].get("fileIdentifyingUrlPathSegment", "")
      api.client_sdr.img_expire = profile.get("miniProfile", {}).get("picture", {}).get("com.linkedin.common.VectorImage", {}).get("artifacts", [])[2].get("expiresAt", 0)
      db.session.add(api.client_sdr)
      db.session.commit()

    return jsonify({"message": "Success", "data": profile}), 200


@VOYAGER_BLUEPRINT.route("/profile", methods=["GET"])
@require_user
def get_profile(client_sdr_id: int):
    """Get profile data for a prospect"""

    public_id = get_request_parameter("public_id", request, json=False, required=True)

    api = LinkedIn(client_sdr_id)
    profile = api.get_profile(public_id)
    if(not api.is_valid()):
      return jsonify({"message": "Invalid LinkedIn cookies"}), 403

    return jsonify({"message": "Success", "data": profile}), 200


@VOYAGER_BLUEPRINT.route("/send_message", methods=["POST"])
@require_user
def send_message(client_sdr_id: int):
    """Sends a LinkedIn message to a prospect"""

    prospect_id = get_request_parameter("prospect_id", request, json=True, required=True, parameter_type=int)
    msg = get_request_parameter("message", request, json=True, required=True)

    api = LinkedIn(client_sdr_id)
    urn_id = get_profile_urn_id(prospect_id, api)
    api.send_message(msg, recipients=[urn_id])
    if(not api.is_valid()):
      return jsonify({"message": "Invalid LinkedIn cookies"}), 403

    return jsonify({"message": "Sent message"}), 200


@VOYAGER_BLUEPRINT.route("/raw_conversation", methods=["GET"])
@require_user
def get_raw_conversation(client_sdr_id: int):
    """Gets a conversation with a prospect in raw li data"""

    convo_urn_id = get_request_parameter("convo_urn_id", request, json=False, required=True)
    limit = get_request_parameter("limit", request, json=False, required=False)
    if limit is None: limit = 20

    api = LinkedIn(client_sdr_id)
    convo = api.get_conversation(convo_urn_id, int(limit))
    if(not api.is_valid()):
      return jsonify({"message": "Invalid LinkedIn cookies"}), 403

    return jsonify({"message": "Success", "data": convo}), 200


@VOYAGER_BLUEPRINT.route("/raw_conversation_details", methods=["GET"])
@require_user
def get_raw_conversation_details(client_sdr_id: int):
    """Gets a conversation details with a prospect in raw li data"""

    prospect_urn_id = get_request_parameter("prospect_urn_id", request, json=False, required=True)

    api = LinkedIn(client_sdr_id)
    details = api.get_conversation_details(prospect_urn_id)
    if(not api.is_valid()):
      return jsonify({"message": "Invalid LinkedIn cookies"}), 403

    return jsonify({"message": "Success", "data": details}), 200


@VOYAGER_BLUEPRINT.route("/conversation", methods=["GET"])
@require_user
def get_conversation(client_sdr_id: int):
    """Gets a conversation with a prospect"""

    prospect_id = get_request_parameter("prospect_id", request, json=False, required=True)
    check_for_update = get_request_parameter("check_for_update", request, json=False, required=False)

    if check_for_update is None:
      check_for_update = True
    else:
      check_for_update = bool(check_for_update)

    api = LinkedIn(client_sdr_id)
    convo, status_text = fetch_conversation(api, prospect_id, check_for_update)
    if(not api.is_valid()):
      return jsonify({"message": "Invalid LinkedIn cookies"}), 403

    prospect: Prospect = Prospect.query.get(prospect_id)

    return jsonify({"message": "Success", "data": convo, "prospect": prospect.to_dict(), "data_status": status_text}), 200


@VOYAGER_BLUEPRINT.route("/recent_conversations", methods=["GET"])
@require_user
def get_recent_conversations(client_sdr_id: int):
    """Gets recent conversation data with filters"""

    timestamp = get_request_parameter("timestamp", request, json=False, required=False)
    read = get_request_parameter("read", request, json=False, required=False)
    starred = get_request_parameter("starred", request, json=False, required=False)
    with_connection = get_request_parameter("with_connection", request, json=False, required=False)
    limit = get_request_parameter("limit", request, json=False, required=False)
    if limit is None: limit = 20

    api = LinkedIn(client_sdr_id)

    convos = api.get_conversations(int(limit))
    if(not api.is_valid()):
      return jsonify({"message": "Invalid LinkedIn cookies"}), 403
    
    if not convos:
      convos = []

    if timestamp:
      convos = filter(lambda x: x['lastActivityAt'] > int(timestamp), convos)
    if read:
      convos = filter(lambda x: x['read'] == bool(read), convos)
    if starred:
      convos = filter(lambda x: x['starred'] == bool(starred), convos)
    if with_connection:
      convos = filter(lambda x: x['withNonConnection'] != bool(with_connection), convos)

    return jsonify({"message": "Success", "data": list(convos)}), 200


@VOYAGER_BLUEPRINT.route("/auth_tokens", methods=["POST"])
@require_user
def update_auth_tokens(client_sdr_id: int):
    """Updates the LinkedIn auth tokens for a SDR"""

    cookies = get_request_parameter("cookies", request, json=True, required=True, parameter_type=str)

    status_text, status = update_linkedin_cookies(client_sdr_id, cookies)

    return jsonify({"message": status_text}), status


@VOYAGER_BLUEPRINT.route("/auth_tokens", methods=["DELETE"])
@require_user
def clear_auth_tokens(client_sdr_id: int):
    """Clears the LinkedIn auth tokens for a SDR"""

    status_text, status = clear_linkedin_cookies(client_sdr_id)

    return jsonify({"message": status_text}), status


@VOYAGER_BLUEPRINT.route("/refetch_all_convos", methods=["GET"])
@require_user
def get_refetch_all_convos(client_sdr_id: int):
    """Refetches all convos for the SDR"""

    fetch_li_prospects_for_sdr(client_sdr_id)

    return jsonify({"message": 'Success'}), 200
