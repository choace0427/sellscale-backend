from concurrent.futures import thread
from flask import Blueprint, jsonify, request
import requests
from model_import import SelixSession
from src.analytics.services_chatbot import API_URL
from src.authentication.decorators import require_user
from src.chatbot.campaign_builder_assistant import add_message_to_thread, chat_with_assistant, get_assistant_reply, get_last_n_messages, handle_run_thread
from src.utils.request_helpers import get_request_parameter

SELIX_BLUEPRINT = Blueprint("selix", __name__)

@SELIX_BLUEPRINT.route("/get_sessions", methods=["GET"])
@require_user
def get_sessions(client_sdr_id: int):
    sessions = SelixSession.query.filter_by(client_sdr_id=client_sdr_id).all()
    return jsonify([session.to_dict() for session in sessions]), 200


@SELIX_BLUEPRINT.route("/create_session", methods=["POST"])
@require_user
def create_session(client_sdr_id: int):
    room_id = get_request_parameter(
        "room_id", request, json=True, required=False
    )
    additional_context = get_request_parameter(
        "additional_context", request, json=True, required=False
    )
    chat_with_assistant(client_sdr_id=client_sdr_id, session_id=None, in_terminal=False, room_id=room_id, additional_context=additional_context)
    return "OK", 200

@SELIX_BLUEPRINT.route("/get_messages_in_thread", methods=["GET"])
@require_user
def get_messages_in_thread(client_sdr_id):
    thread_id = get_request_parameter(
        "thread_id", request, json=True, required=True
    )
    messages = get_last_n_messages(
        thread_id=thread_id
    )
    return jsonify(messages), 200

@SELIX_BLUEPRINT.route("/create_message", methods=["POST"])
@require_user
def create_message(client_sdr_id):
    session_id = get_request_parameter(
        "session_id", request, json=True, required=True
    )
    message = get_request_parameter(
        "message", request, json=True, required=True
    )

    session: SelixSession = SelixSession.query.get(session_id)
    thread_id = session.thread_id

    add_message_to_thread(thread_id, message)
    handle_run_thread(thread_id, session_id)
    get_assistant_reply(thread_id)
        
    return "OK", 200
