from datetime import datetime, timedelta, timezone
from flask import Blueprint, jsonify, request
from src.bump_framework.models import BumpFramework
from src.prospecting.services import send_to_purgatory
from src.utils.slack import URL_MAP, send_slack_message
from src.voyager.services import fetch_li_prospects_for_sdr, queue_withdraw_li_invites
from src.prospecting.models import Prospect, ProspectHiddenReason
from src.client.models import ClientSDR
from src.voyager.services import (
    update_linkedin_cookies,
    fetch_conversation,
    get_profile_urn_id,
    clear_linkedin_cookies,
    run_fast_analytics_backfill,  #  do not remove this import for celery to work
)
from src.authentication.decorators import require_user
from src.utils.request_helpers import get_request_parameter
from src.voyager.linkedin import LinkedIn
from app import db
import time
from src.message_generation.services import (
    add_generated_msg_queue,
    send_sent_by_sellscale_notification,
)
from src.voyager.services import reconnect_disconnected_linkedins

from src.merge_crm.services import add_contact_to_db # for celery task registration
from src.chatbot.campaign_builder_assistant import generate_followup # for celery task registration


VOYAGER_BLUEPRINT = Blueprint("voyager", __name__)


@VOYAGER_BLUEPRINT.route("/profile/self", methods=["GET"])
@require_user
def get_self_profile(client_sdr_id: int):
    """Get profile data for the SDR"""

    cookies = (
        get_request_parameter(
            "cookies", request, json=False, required=False, parameter_type=str
        )
        or None
    )
    cookies = cookies.replace(':""', ':"').replace('"",', '",') if cookies else None

    user_agent = (
        get_request_parameter(
            "user_agent", request, json=False, required=False, parameter_type=str
        )
        or None
    )

    if cookies:
        send_slack_message(
            message=f"<{client_sdr_id}> Passed in cookies: {cookies}",
            webhook_urls=[URL_MAP["operations-li-invalid-cookie"]],
        )

    api = LinkedIn(client_sdr_id=client_sdr_id, cookies=cookies, user_agent=user_agent)
    profile = api.get_user_profile(use_cache=False)

    send_slack_message(
        message=f"<{client_sdr_id}> Self profile: {profile}",
        webhook_urls=[URL_MAP["operations-li-invalid-cookie"]],
    )

    if not cookies and not api.is_valid():
        return jsonify({"message": "Invalid LinkedIn cookies"}), 403

    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)

    # If the SDR's profile img is expired, update it
    if profile and time.time() * 1000 > int(sdr.img_expire):
        sdr.img_url = profile.get("miniProfile", {}).get("picture", {}).get(
            "com.linkedin.common.VectorImage", {}
        ).get("rootUrl", "") + profile.get("miniProfile", {}).get("picture", {}).get(
            "com.linkedin.common.VectorImage", {}
        ).get(
            "artifacts", [{}, {}, {}]
        )[
            2
        ].get(
            "fileIdentifyingUrlPathSegment", ""
        )
        sdr.img_expire = (
            profile.get("miniProfile", {})
            .get("picture", {})
            .get("com.linkedin.common.V{ectorImage", {})
            .get("artifacts", [{}, {}, {}])[2]
            .get("expiresAt", 0)
        )
        db.session.add(sdr)
        db.session.commit()

    return jsonify({"message": "Success", "data": profile}), 200


@VOYAGER_BLUEPRINT.route("/profile", methods=["GET"])
@require_user
def get_profile(client_sdr_id: int):
    """Get profile data for a prospect"""

    public_id = get_request_parameter("public_id", request, json=False, required=False)
    urn_id = get_request_parameter("urn_id", request, json=False, required=False)

    api = LinkedIn(client_sdr_id)
    profile = api.get_profile(public_id=public_id, urn_id=urn_id)
    if not api.is_valid():
        return jsonify({"message": "Invalid LinkedIn cookies"}), 403

    return jsonify({"message": "Success", "data": profile}), 200


@VOYAGER_BLUEPRINT.route("/send_message", methods=["POST"])
@require_user
def send_message(client_sdr_id: int):
    """Sends a LinkedIn message to a prospect"""
    from src.automation.orchestrator import add_process_for_future
    from src.utils.datetime.dateparse_utils import convert_string_to_datetime_or_none

    prospect_id = get_request_parameter(
        "prospect_id", request, json=True, required=True, parameter_type=int
    )
    msg = get_request_parameter(
        "message", request, json=True, required=True, parameter_type=str
    )
    ai_generated = (
        get_request_parameter(
            "ai_generated", request, json=True, required=False, parameter_type=bool
        )
        or False
    )

    purgatory = (
        get_request_parameter(
            "purgatory", request, json=True, required=False, parameter_type=bool
        )
        or True
    )
    purgatory_date = get_request_parameter(
        "purgatory_date", request, json=True, required=False, parameter_type=str
    )
    purgatory_date = (
        convert_string_to_datetime_or_none(purgatory_date) if purgatory_date else None
    )

    scheduled_send_date = get_request_parameter(
        "scheduled_send_date", request, json=True, required=False, parameter_type=str
    )
    scheduled_send_date = (
        convert_string_to_datetime_or_none(scheduled_send_date)
        if scheduled_send_date
        else None
    )

    bf_id = get_request_parameter(
        "bump_framework_id", request, json=True, required=False, parameter_type=int
    )
    bf_title = get_request_parameter(
        "bump_framework_title", request, json=True, required=False, parameter_type=str
    )
    bf_description = get_request_parameter(
        "bump_framework_description",
        request,
        json=True,
        required=False,
        parameter_type=str,
    )
    bf_length = get_request_parameter(
        "bump_framework_length", request, json=True, required=False, parameter_type=str
    )
    account_research_points = get_request_parameter(
        "account_research_points",
        request,
        json=True,
        required=False,
        parameter_type=list,
    )

    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if client_sdr.role == 'ADMIN':
        prospect = Prospect.query.get(prospect_id)
        client_sdr_id = prospect.client_sdr_id

    if scheduled_send_date:
        add_process_for_future(
            type="send_scheduled_linkedin_message",
            args={
                "client_sdr_id": client_sdr_id,
                "prospect_id": prospect_id,
                "message": msg,
                "send_sellscale_notification": True,
                "ai_generated": ai_generated,
                "bf_id": bf_id,
                "bf_title": bf_title,
                "bf_description": bf_description,
                "bf_length": bf_length,
                "account_research_points": account_research_points,
                "to_purgatory": purgatory,
                "purgatory_date": purgatory_date.isoformat(),
            },
            relative_time=scheduled_send_date,
        )

        prospect: Prospect = Prospect.query.get(prospect_id)
        prospect.hidden_until = scheduled_send_date + timedelta(days=1)
        db.session.add(prospect)
        db.session.commit()

        return jsonify({"message": "Scheduled message"}), 200

    send_sent_by_sellscale_notification(
        prospect_id=prospect_id,
        message=msg,
        bump_framework_id=bf_id,
    )

    api = LinkedIn(client_sdr_id)
    urn_id = get_profile_urn_id(prospect_id, api)
    msg_urn_id = api.send_message(msg, recipients=[urn_id])
    if isinstance(msg_urn_id, str):
        if ai_generated:
            add_generated_msg_queue(
                client_sdr_id=client_sdr_id,
                li_message_urn_id=msg_urn_id,
                bump_framework_id=bf_id,
                bump_framework_title=bf_title,
                bump_framework_description=bf_description,
                bump_framework_length=bf_length,
                account_research_points=account_research_points,
            )

        fetch_conversation(api=api, prospect_id=prospect_id, check_for_update=True)

    if purgatory:
        bump: BumpFramework = BumpFramework.query.get(bf_id)
        bump_delay = bump.bump_delay_days if bump and bump.bump_delay_days else 2
        aware_utc_now = datetime.utcnow().replace(tzinfo=timezone.utc)
        purgatory_delay = (
            (purgatory_date - aware_utc_now).days if purgatory_date else None
        )
        purgatory_delay = purgatory_delay or bump_delay
        send_to_purgatory(
            prospect_id, purgatory_delay, ProspectHiddenReason.RECENTLY_BUMPED
        )
    if not api.is_valid():
        return jsonify({"message": "Invalid LinkedIn cookies"}), 403

    return jsonify({"message": "Sent message"}), 200


@VOYAGER_BLUEPRINT.route("/send_message_generic", methods=["POST"])
@require_user
def send_message_generic(client_sdr_id: int):
    """Sends a LinkedIn message to a profile"""

    li_urn_id = get_request_parameter(
        "li_urn_id", request, json=True, required=True, parameter_type=str
    )
    msg = get_request_parameter(
        "message", request, json=True, required=True, parameter_type=str
    )

    api = LinkedIn(client_sdr_id)
    api.send_message(msg, recipients=[li_urn_id])

    return jsonify({"message": "Success", "data": None}), 200


@VOYAGER_BLUEPRINT.route("/raw_conversation", methods=["GET"])
@require_user
def get_raw_conversation(client_sdr_id: int):
    """Gets a conversation with a prospect in raw li data"""

    convo_urn_id = get_request_parameter(
        "convo_urn_id", request, json=False, required=True
    )
    limit = get_request_parameter("limit", request, json=False, required=False)
    if limit is None:
        limit = 20

    api = LinkedIn(client_sdr_id)
    convo = api.get_conversation(convo_urn_id, int(limit))
    if not api.is_valid():
        return jsonify({"message": "Invalid LinkedIn cookies"}), 403

    return jsonify({"message": "Success", "data": convo}), 200


@VOYAGER_BLUEPRINT.route("/raw_conversation_details", methods=["GET"])
@require_user
def get_raw_conversation_details(client_sdr_id: int):
    """Gets a conversation details with a prospect in raw li data"""

    prospect_urn_id = get_request_parameter(
        "prospect_urn_id", request, json=False, required=True
    )

    api = LinkedIn(client_sdr_id)
    details = api.get_conversation_details(prospect_urn_id)
    if not api.is_valid():
        return jsonify({"message": "Invalid LinkedIn cookies"}), 403

    return jsonify({"message": "Success", "data": details}), 200


@VOYAGER_BLUEPRINT.route("/conversation", methods=["GET"])
@require_user
def get_conversation(client_sdr_id: int):
    """Gets a conversation with a prospect"""

    prospect_id = get_request_parameter(
        "prospect_id", request, json=False, required=True, parameter_type=int
    )
    check_for_update = get_request_parameter(
        "check_for_update", request, json=False, required=False, parameter_type=bool
    )

    if check_for_update is None:
        check_for_update = True
    else:
        check_for_update = bool(check_for_update)

    api = LinkedIn(client_sdr_id) if check_for_update else None
    convo, status_text = fetch_conversation(api, prospect_id, check_for_update)
    if api and not api.is_valid():
        return jsonify({"message": "Invalid LinkedIn cookies"}), 403

    prospect: Prospect = Prospect.query.get(prospect_id)

    return (
        jsonify(
            {
                "message": "Success",
                "data": convo,
                "prospect": prospect.to_dict(),
                "data_status": status_text,
            }
        ),
        200,
    )


@VOYAGER_BLUEPRINT.route("/recent_conversations", methods=["GET"])
@require_user
def get_recent_conversations(client_sdr_id: int):
    """Gets recent conversation data with filters"""

    timestamp = get_request_parameter("timestamp", request, json=False, required=False)
    read = get_request_parameter("read", request, json=False, required=False)
    starred = get_request_parameter("starred", request, json=False, required=False)
    with_connection = get_request_parameter(
        "with_connection", request, json=False, required=False
    )
    limit = get_request_parameter("limit", request, json=False, required=False)
    if limit is None:
        limit = 20

    api = LinkedIn(client_sdr_id)

    convos = api.get_conversations(int(limit))
    if not api.is_valid():
        return jsonify({"message": "Invalid LinkedIn cookies"}), 403

    if not convos:
        convos = []

    if timestamp:
        convos = filter(lambda x: x["lastActivityAt"] > int(timestamp), convos)
    if read:
        convos = filter(lambda x: x["read"] == bool(read), convos)
    if starred:
        convos = filter(lambda x: x["starred"] == bool(starred), convos)
    if with_connection:
        convos = filter(
            lambda x: x["withNonConnection"] != bool(with_connection), convos
        )

    return jsonify({"message": "Success", "data": list(convos)}), 200


@VOYAGER_BLUEPRINT.route("/auth_tokens", methods=["POST"])
@require_user
def update_auth_tokens(client_sdr_id: int):
    """Updates the LinkedIn auth tokens for a SDR"""

    cookies = get_request_parameter(
        "cookies", request, json=True, required=True, parameter_type=str
    )
    user_agent = get_request_parameter(
        "user_agent", request, json=True, required=True, parameter_type=str
    )

    status_text, status = update_linkedin_cookies(client_sdr_id, cookies, user_agent)

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

    return jsonify({"message": "Success"}), 200


@VOYAGER_BLUEPRINT.route("/connections", methods=["GET"])
@require_user
def get_connections(client_sdr_id: int):
    """Gets all linkedin connections for a SDR"""

    limit = get_request_parameter("limit", request, json=False, required=False)
    if limit is None:
        limit = 20

    api = LinkedIn(client_sdr_id)
    profile = api.get_user_profile(use_cache=False)
    if not api.is_valid():
        return jsonify({"message": "Invalid LinkedIn cookies"}), 403
    sdr_urn_id = (
        profile.get("miniProfile", {})
        .get("entityUrn", "")
        .replace("urn:li:fs_miniProfile:", "")
    )
    if not sdr_urn_id:
        return jsonify({"message": "Failed to find URN ID for SDR"}), 403

    connections = api.graphql_get_connections(10, 0)
    print(connections)

    return jsonify({"message": "Success", "data": []}), 200


@VOYAGER_BLUEPRINT.route("/sales-nav", methods=["GET"])
@require_user
def get_sales_nav(client_sdr_id: int):
    """."""

    keyword = get_request_parameter("keyword", request, json=False, required=True)
    yoe = get_request_parameter("yoe", request, json=False, required=True)

    api = LinkedIn(client_sdr_id)
    # profile = api.get_user_profile(use_cache=False)
    if not api.is_valid():
        return jsonify({"message": "Invalid LinkedIn cookies"}), 403

    result = api.graphql_get_sales_nav(keyword, yoe)

    return jsonify({"message": "Success", "data": result}), 200


@VOYAGER_BLUEPRINT.route("/raw_company", methods=["GET"])
@require_user
def get_raw_company(client_sdr_id: int):
    company_public_id = get_request_parameter(
        "company_public_id", request, json=False, required=True
    )

    api = LinkedIn(client_sdr_id)
    company = api.get_company(company_public_id)
    if not api.is_valid():
        return jsonify({"message": "Invalid LinkedIn cookies"}), 403

    return jsonify({"message": "Success", "data": company}), 200


@VOYAGER_BLUEPRINT.route("/raw_company_updates", methods=["GET"])
@require_user
def get_raw_company_updates(client_sdr_id: int):
    company_public_id = get_request_parameter(
        "company_public_id", request, json=False, required=True
    )

    api = LinkedIn(client_sdr_id)
    updates = api.get_company_updates(public_id=company_public_id)
    if not api.is_valid():
        return jsonify({"message": "Invalid LinkedIn cookies"}), 403

    return jsonify({"message": "Success", "data": updates}), 200
