import base64
import json
from flask import Blueprint, request, jsonify, Response
import openai
from src.automation.models import PhantomBusterType
from src.automation.services import (
    create_phantom_buster_config,
    get_all_phantom_busters,
    create_new_auto_connect_phantom,
    process_pb_webhook_payload,
    schedule_process_queue_test,
    update_phantom_buster_li_at,
    create_pb_linkedin_invite_csv,
    update_pb_linkedin_send_status,
    reset_phantom_buster_scrapes_and_launches,
)
from src.automation.inbox_scraper import detect_demo # importing for celery task registration
from src.ml.openai_wrappers import (
    OPENAI_CHAT_GPT_4_MODEL,
    wrapped_chat_gpt_completion,
    wrapped_create_completion,
)
from src.utils.csv import send_csv
from src.utils.request_helpers import get_request_parameter
from src.automation.inbox_scraper import scrape_inbox
from src.utils.slack import (
    send_slack_message,
    CHANNEL_NAME_MAP,
    send_delayed_slack_message,
)
from src.authentication.decorators import require_user
from datetime import datetime

# Do not delete - registering Celery Task
from src.automation.orchestrator import process_queue

AUTOMATION_BLUEPRINT = Blueprint("automation", __name__)


@AUTOMATION_BLUEPRINT.route("/")
def index():
    return "OK", 200


@AUTOMATION_BLUEPRINT.route("/get-all-phantom-busters", methods=["GET"])
def get_all_phantom_busters_endpoint():
    resp = get_all_phantom_busters(
        pb_type=PhantomBusterType.OUTBOUND_ENGINE, search_term="Auto Connect"
    )
    return jsonify(resp)


@AUTOMATION_BLUEPRINT.route("/get-all-inbox-scrapers", methods=["GET"])
def get_all_inbox_scrapers_endpoint():
    resp = get_all_phantom_busters(
        pb_type=PhantomBusterType.INBOX_SCRAPER, search_term="Inbox Scraper"
    )
    return jsonify(resp)


@AUTOMATION_BLUEPRINT.route("/scrape_inbox", methods=["GET"])
def scrape_inbox_from_client_sdr_id():
    client_sdr_id = get_request_parameter(
        "client_sdr_id", request, json=False, required=True
    )
    resp = scrape_inbox(client_sdr_id=client_sdr_id)
    return jsonify(resp)


@AUTOMATION_BLUEPRINT.route("/configure_phantom_agents", methods=["POST"])
def configure_phantom_agents():
    client_sdr_id: int = get_request_parameter(
        "client_sdr_id", request, json=True, required=True
    )
    linkedin_session_cookie = get_request_parameter(
        "linkedin_session_cookie", request, json=True, required=True
    )

    auto_connect_pb_config = create_new_auto_connect_phantom(
        client_sdr_id=client_sdr_id, linkedin_session_cookie=linkedin_session_cookie
    )

    return jsonify(
        {
            "auto_connect_pb_config": auto_connect_pb_config,
        }
    )


@AUTOMATION_BLUEPRINT.route("/update_phantom_li_at", methods=["POST"])
def update_phantom_li_at():
    client_sdr_id: int = get_request_parameter(
        "client_sdr_id", request, json=True, required=True
    )
    linkedin_authentication_token: str = get_request_parameter(
        "linkedin_authentication_token", request, json=True, required=True
    )

    response = update_phantom_buster_li_at(
        client_sdr_id=client_sdr_id, li_at=linkedin_authentication_token
    )

    return jsonify(response)


@AUTOMATION_BLUEPRINT.route("/update_phantom_li_at_auth", methods=["POST"])
@require_user
def update_phantom_li_at_auth(client_sdr_id: int):
    linkedin_authentication_token: str = get_request_parameter(
        "linkedin_authentication_token", request, json=True, required=True
    )

    response = update_phantom_buster_li_at(
        client_sdr_id=client_sdr_id, li_at=linkedin_authentication_token
    )

    return jsonify(response)


@AUTOMATION_BLUEPRINT.route("/send_slack_message", methods=["POST"])
def post_send_slack_message():
    message = get_request_parameter("message", request, json=True, required=True)
    channel = get_request_parameter("channel", request, json=True, required=True)
    send_slack_message(message=message, webhook_urls=[channel])
    return "OK", 200


@AUTOMATION_BLUEPRINT.route("/send_delayed_slack_message", methods=["POST"])
def post_send_delayed_slack_message():
    message = get_request_parameter("message", request, json=True, required=True)
    channel = get_request_parameter("channel_name", request, json=True, required=True)
    delay_date = get_request_parameter("delay_date", request, json=True, required=True)
    date = datetime.fromisoformat(delay_date[:-1])

    send_delayed_slack_message(
        message=message,
        channel_name=CHANNEL_NAME_MAP[channel],
        delay_date=date,
    )
    return "OK", 200


@AUTOMATION_BLUEPRINT.route(
    "/phantombuster/auto_connect_csv/<int:client_sdr_id>", methods=["GET"]
)
def get_phantombuster_autoconnect_csv(client_sdr_id: int):
    """Creates a CSV file with the data to be used by the phantombuster auto connect script"""
    data = create_pb_linkedin_invite_csv(client_sdr_id)
    if not data:
        empty_data = [{"Linkedin": "", "Message": ""}]
        return send_csv(
            empty_data, filename="empty_data.csv", fields=["Linkedin", "Message"]
        )

    return send_csv(data, filename="data.csv", fields=["Linkedin", "Message"])


@AUTOMATION_BLUEPRINT.route(
    "/phantombuster/auto_connect_webhook/<int:client_sdr_id>", methods=["POST"]
)
def post_phantombuster_autoconnect_webhook(client_sdr_id: int):
    """Webhook to be called by phantombuster after the auto connect script finishes"""
    pb_payload = request.get_json()

    success = process_pb_webhook_payload(client_sdr_id, pb_payload)

    # Since this is a webhook, we need to return a response that PB won't flag
    return "OK", 200


@AUTOMATION_BLUEPRINT.route("/whisper_transcribe", methods=["POST"])
def whisper_transcribe():
    """Webhook to be called by whisper after the transcription is finished"""
    base_64_audio = get_request_parameter(
        "base_64_audio", request, json=True, required=True
    )

    with open("audio.webm", "wb") as fh:
        fh.write(base64.decodebytes(base_64_audio.encode()))
        fh.close()

    with open("audio.webm", "rb") as fh:
        response = openai.Audio.transcribe("whisper-1", fh)

    return jsonify(response)


@AUTOMATION_BLUEPRINT.route("/whisper_diarization", methods=["POST"])
def whisper_diarization():
    raw_transcript = get_request_parameter(
        "raw_transcript", request, json=True, required=True
    )

    response = wrapped_create_completion(
        model=OPENAI_CHAT_GPT_4_MODEL,
        prompt="This is a raw speaker transcript. Convert it into a conversion between persons. Label people as Person A, Person B, and Person C. Mark people changes as you would in a transcript (i.e. with colons and line breaks). Use markdown formatting style.:"
        + raw_transcript,
        max_tokens=int(len(raw_transcript) / 4 + 100),
    )

    return jsonify(
        {
            "diarized_transcript": response,
        }
    )


@AUTOMATION_BLUEPRINT.route("/whisper_analysis", methods=["POST"])
def whisper_analysis():
    raw_transcript = get_request_parameter(
        "raw_transcript", request, json=True, required=True
    )

    response = wrapped_create_completion(
        model=OPENAI_CHAT_GPT_4_MODEL,
        prompt="Analyze this conversation and create three sections using markdown formatting: 1. Summary of the conversation. 2. General sentiment (very positive, positive, neutral, negative, very negative). 3. A list of the main topics discussed."
        + raw_transcript,
        max_tokens=int(len(raw_transcript) / 4 + 100),
    )

    return jsonify(
        {
            "analyzed_transcript": response,
        }
    )


@AUTOMATION_BLUEPRINT.route("/send_resend_email", methods=["POST"])
def send_resend_email():
    from src.automation.resend import send_email

    html = get_request_parameter("html", request, json=True, required=True)

    send_email(html=html)
    return "OK", 200


@AUTOMATION_BLUEPRINT.route("/schedule_process_queue_test", methods=["POST"])
def post_schedule_process_queue_test():
    size = get_request_parameter("size", request, json=True, required=True)
    wait = get_request_parameter("wait", request, json=True, required=True)

    schedule_process_queue_test(size, wait)

    return "OK", 200
