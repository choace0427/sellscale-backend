from flask import Blueprint, request
from src.client.models import Client, ClientArchetype, ClientSDR

from src.utils.request_helpers import get_request_parameter
from src.utils.slack import URL_MAP, send_slack_message
from src.chatbot.models import SelixSession, SelixSessionTask, SelixSessionTaskStatus

from .services import get_echo

ECHO_BLUEPRINT = Blueprint("echo", __name__)


@ECHO_BLUEPRINT.route("/")
def index():
    get_echo()
    return "OK", 200

@ECHO_BLUEPRINT.route("/send-slack-message", methods=["POST"])
def post_send_slack_message():
    message = get_request_parameter(
        "message", request, json=True, required=True
    )
    webhook_key = get_request_parameter(
        "webhook_key", request, json=True, required=True
    )
    send_slack_message(
        message=message,
        webhook_urls=[URL_MAP[webhook_key]],
    )

    return "OK", 200

@ECHO_BLUEPRINT.route("/session-complete", methods=["POST"])
def post_session_complete():
    session_id = get_request_parameter(
        "session_id", request, json=True, required=True
    )
    selix_session: SelixSession = SelixSession.query.get(session_id)
    session_sdr: ClientSDR = ClientSDR.query.get(selix_session.client_sdr_id)
    company: Client = Client.query.get(session_sdr.client_id)
    tasks: list[SelixSessionTask] = SelixSessionTask.query.filter_by(selix_session_id=session_id).order_by(SelixSessionTask.order_number.is_(None).desc(), SelixSessionTask.order_number.asc()).all()

    webhook_url = company.pipeline_notifications_webhook_url

    session_memory = selix_session.memory
    archetype_name = ''
    if (session_memory and session_memory.get('campaign_id')):
        archetype_id = int(session_memory.get('archetype_id'))
        client_archetype : ClientArchetype = ClientArchetype.query.get(archetype_id)
        archetype_name = client_archetype.archetype

    if not archetype_name or archetype_name == '':
        return "NOT OK", 400
    
    deep_link =  f"https://app.sellscale.com/authenticate?stytch_token_type=direct&token={session_sdr.auth_token}&redirect=selix&thread_id={selix_session.thread_id}&session_id={selix_session.id}"

    header = session_sdr.name + ', the "' + archetype_name + '" campaign is ready to review.'

    task_blocks = [
    {
        "type": "header",
        "text": {
            "type": "plain_text",
            "text": header,
            "emoji": True,
        },
    },
    {
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": f"{len(tasks)} tasks completed"
        }
    }
]

    task_list = "\n".join([f"- {'✅' if task.status == SelixSessionTaskStatus.COMPLETE else '☑️'} {task.title}" for task in tasks])
    task_blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": task_list
        }
    })

    task_blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": "View completed tasks here:"
        },
        "accessory": {
            "type": "button",
            "text": {
                "type": "plain_text",
                "text": "Review & Launch",
                "emoji": True
            },
            "url": deep_link,
            "action_id": "button-action"
        }
    })

    send_slack_message(
        message="New Selix Session Awaiting",
        #please advise correct webhook url
        webhook_urls=[webhook_url],
        blocks=task_blocks
    )

    return "OK", 200
    
