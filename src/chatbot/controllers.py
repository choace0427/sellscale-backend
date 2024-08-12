from concurrent.futures import thread
from flask import Blueprint, jsonify, request
import requests
from model_import import SelixSession
from src.analytics.services_chatbot import API_URL
from src.authentication.decorators import require_user
from src.chatbot.campaign_builder_assistant import add_message_to_thread, adjust_selix_task_order, bulk_create_selix_tasks, chat_with_assistant, delete_selix_task, delete_session, get_assistant_reply, get_last_n_messages, handle_run_thread, get_all_threads_with_tasks, handle_voice_instruction_enrichment_and_questions, update_session, create_selix_task, update_selix_task
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
    print("Creating session")
    room_id = get_request_parameter(
        "room_id", request, json=True, required=False
    )
    additional_context = get_request_parameter(
        "additional_context", request, json=True, required=False
    )
    session_name = get_request_parameter(
        "session_name", request, json=True, required=False
    )
    task_titles = get_request_parameter(
        "task_titles", request, json=True, required=False
    )
    chat_with_assistant(client_sdr_id=client_sdr_id, session_id=None, in_terminal=False, room_id=room_id, additional_context=additional_context, session_name=session_name, task_titles=task_titles)
    return "OK", 200

@SELIX_BLUEPRINT.route("/delete_session", methods=["DELETE"])
@require_user
def delete_session_endpoint(client_sdr_id: int):
    session_id = get_request_parameter(
        "session_id", request, json=True, required=True
    )

    success, message = delete_session(client_sdr_id=client_sdr_id, session_id=session_id)

    if not success:
        return jsonify({"error": message}), 400

    return jsonify({"message": message}), 200


#take note these are different functions, this one and the one below POST and GET
@SELIX_BLUEPRINT.route("/edit_session", methods=["PATCH"])
@require_user
def edit_session(client_sdr_id: int):
    session_id = get_request_parameter(
        "session_id", request, json=True, required=True
    )
    new_title = get_request_parameter(
        "new_title", request, json=True, required=False
    )
    new_status = get_request_parameter(
        "new_status", request, json=True, required=False
    )
    new_strategy_id = get_request_parameter(
        "new_strategy_id", request, json=True, required=False
    )
    new_campaign_id = get_request_parameter(
        "new_campaign_id", request, json=True, required=False
    )

    session: SelixSession = SelixSession.query.get(session_id)
    if not session:
        return jsonify({"error": "Session not found"}), 404

    success, message = update_session(session_id=session_id, client_sdr_id=client_sdr_id, new_title=new_title, new_status=new_status, new_strategy_id=new_strategy_id, new_campaign_id=new_campaign_id)

    if not success:
        return jsonify({"error": message}), 400
    
    return jsonify({"message": message}), 200


@SELIX_BLUEPRINT.route("/get_messages_in_thread", methods=["GET"])
@require_user
def get_messages_in_thread_old(client_sdr_id):
    thread_id = get_request_parameter(
        "thread_id", request, json=True, required=True
    )
    try:
        messages = get_last_n_messages(
            thread_id=thread_id
        )
    except Exception as e:
        return str(e), 400
    return jsonify(messages), 200

@SELIX_BLUEPRINT.route("/get_messages_in_thread", methods=["POST"])
@require_user
def get_messages_in_thread(client_sdr_id):
    thread_id = get_request_parameter(
        "thread_id", request, json=True, required=True
    )
    try:
        messages = get_last_n_messages(
            thread_id=thread_id
        )
    except Exception as e:
        return str(e), 400
    return jsonify(messages), 200

@SELIX_BLUEPRINT.route("/get_all_threads", methods=["GET"])
@require_user
def get_all_threads_route(client_sdr_id: int):
    threads = get_all_threads_with_tasks(client_sdr_id)
    return jsonify(threads), 200


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

    print("Adding message to thread")
    print(thread_id)

    add_message_to_thread(thread_id, message)
    
    handle_run_thread(thread_id, session_id)
    
    get_assistant_reply(thread_id)
        
    return "OK", 200

@SELIX_BLUEPRINT.route("/tasks", methods=["POST"])
@require_user
def create_task(client_sdr_id: int):
    session_id = get_request_parameter(
        "session_id", request, json=True, required=True
    )
    task_titles = get_request_parameter(
        "task_titles", request, json=True, required=True
    )

    success, message = bulk_create_selix_tasks(
        client_sdr_id=client_sdr_id,
        session_id=session_id,
        task_titles=task_titles
    )

    if not success:
        return jsonify({"error": message}), 400
    
    return jsonify({"message": message}), 200

@SELIX_BLUEPRINT.route("/task", methods=["PATCH"])
@require_user
def update_task(client_sdr_id: int):
    task_id = get_request_parameter(
        "task_id", request, json=True, required=True
    )
    new_title = get_request_parameter(
        "new_title", request, json=True, required=False
    )
    new_status = get_request_parameter(
        "new_status", request, json=True, required=False
    )
    new_proof_of_work = get_request_parameter(
        "new_proof_of_work", request, json=True, required=False
    )
    new_description = get_request_parameter(
        "new_description", request, json=True, required=False
    )
    internal_notes = get_request_parameter(
        "internal_notes", request, json=True, required=False
    )
    internal_review_needed = get_request_parameter(
        "internal_review_needed", request, json=True, required=False
    )

    success, message = update_selix_task(
        client_sdr_id=client_sdr_id,
        task_id=task_id,
        new_title=new_title,
        new_status=new_status,
        new_proof_of_work=new_proof_of_work,
        new_description=new_description,
        internal_notes=internal_notes,
        internal_review_needed=internal_review_needed
    )

    if not success:
        return jsonify({"error": message}), 400
    
    return jsonify({"message": message}), 200

@SELIX_BLUEPRINT.route("/task/order", methods=["PATCH"])
@require_user
def update_task_order(client_sdr_id: int):
    task_id = get_request_parameter(
        "task_id", request, json=True, required=True
    )
    new_order = get_request_parameter(
        "new_order", request, json=True, required=True
    )

    success, message = adjust_selix_task_order(
        client_sdr_id=client_sdr_id,
        task_id=task_id,
        new_order=new_order
    )

    if not success:
        return jsonify({"error": message}), 400
    
    return jsonify({"message": message}), 200

@SELIX_BLUEPRINT.route("/task", methods=["DELETE"])
@require_user
def delete_task(client_sdr_id: int):
    task_id = get_request_parameter(
        "task_id", request, json=True, required=True
    )

    success, message, status_code = delete_selix_task(client_sdr_id, task_id)
    if not success:
        return jsonify({"error": message}), status_code
    return jsonify({"message": message}), 200


@SELIX_BLUEPRINT.route("/question_prompter", methods=["POST"])
@require_user
def sanitize_transcript(client_sdr_id: int):
    session_id = get_request_parameter(
        "session_id", request, json=True, required=True
    )

    sanitized_transcript = handle_voice_instruction_enrichment_and_questions(
        session_id=session_id
    )

    return jsonify({'transcript': sanitized_transcript}), 200