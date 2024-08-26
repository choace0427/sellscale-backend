import random
from flask import Blueprint, request
from src.client.archetype.controllers import check_can_activate_email, check_can_activate_linkedin
from src.client.models import Client, ClientArchetype, ClientSDR
from src.email_sequencing.models import EmailSequenceStep, EmailSubjectLineTemplate
from src.message_generation.email.services import generate_magic_subject_line
from src.message_generation.services import generate_li_convo_init_msg
from src.prospecting.models import Prospect, ProspectOverallStatus

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
    show_task_list = get_request_parameter(
        "show_task_list", request, json=True, required=False, default=False
    )
    show_sample_prospect = get_request_parameter(
        "show_sample_prospect", request, json=True, required=False, default=False
    )
    show_sample_sequence = get_request_parameter(
        "show_sample_sequence", request, json=True, required=False, default=False
    )
    show_estimated_results = get_request_parameter(
        "show_estimated_results", request, json=True, required=False, default=False
    )
    show_action_item = get_request_parameter(
        "show_action_item", request, json=True, required=False, default=False
    )
    return handle_session_complete(
        session_id, 
        show_task_list, 
        show_sample_prospect, 
        show_sample_sequence, 
        show_estimated_results, 
        show_action_item
    )

def handle_session_complete(
    session_id: int, 
    show_task_list: bool = True, 
    show_sample_prospect: bool = True, 
    show_sample_sequence: bool = True, 
    show_estimated_results: bool = True, 
    show_action_item: bool = True
):
    try:
        selix_session: SelixSession = SelixSession.query.get(session_id)
        session_sdr: ClientSDR = ClientSDR.query.get(selix_session.client_sdr_id)
        company: Client = Client.query.get(session_sdr.client_id)
        tasks: list[SelixSessionTask] = SelixSessionTask.query.filter_by(selix_session_id=session_id).order_by(SelixSessionTask.order_number.is_(None).desc(), SelixSessionTask.order_number.asc()).all()

        webhook_url = company.pipeline_notifications_webhook_url

        session_memory = selix_session.memory
        archetype_name = ''

        prospect_name = ''
        propsect_company = ''
        prospect_image = ''
        prospect: Prospect = None

        if (session_memory and session_memory.get('campaign_id')):
            archetype_id = int(session_memory.get('campaign_id'))
            client_archetype : ClientArchetype = ClientArchetype.query.get(archetype_id)
            archetype_name = client_archetype.archetype

            random_prospect : Prospect = Prospect.query.filter_by(archetype_id=archetype_id).order_by(Prospect.id.desc()).first()
            if random_prospect:
                prospect_name = random_prospect.first_name + ' ' + random_prospect.last_name
                propsect_company = random_prospect.company
                prospect_image = random_prospect.img_url
                prospect = random_prospect

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

        if show_task_list:
            task_list = "\n".join([f"- {'✅' if task.status == SelixSessionTaskStatus.COMPLETE else '☑️'} {task.title}" for task in tasks])
            task_blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": task_list
                }
            })
        if show_sample_prospect and prospect_name != '':
            if prospect_image:
                task_blocks.append({
                    "type": "image",
                    "title": {
                        "type": "plain_text",
                        "text": f"Sample Prospect: {prospect_name} from {propsect_company}"
                    },
                    "block_id": "sample_prospect_image",
                    "image_url": prospect_image,
                    "alt_text": f"Image of {prospect_name} from {propsect_company}."
                })
            else:
                task_blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"Sample Prospect: {prospect_name} from {propsect_company}"
                    }
                })

        if show_sample_sequence and prospect:

            #generate initial message

            if (check_can_activate_linkedin(client_archetype, client_sdr_id=session_sdr.id)):
                
                message, _ = generate_li_convo_init_msg(prospect.id)

                task_blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*Initial Linkedin Message:*"
                    }
                })
                task_blocks.append({
                    "type": "rich_text",
                    "block_id": "Vrzsu",
                    "elements": [
                        {
                            "type": "rich_text_quote",
                            "elements": [
                                {
                                    "type": "text",
                                    "text": message
                                }
                            ]
                        },
                    ]
                })

            if (check_can_activate_email(client_archetype, client_sdr_id=session_sdr.id)):
                #get email template
                templates: list[EmailSequenceStep] = EmailSequenceStep.query.filter(
                EmailSequenceStep.client_archetype_id == prospect.archetype_id,
                EmailSequenceStep.overall_status == ProspectOverallStatus.PROSPECTED,
                EmailSequenceStep.active == True,).all()

                subjectline_template_id = None
                subjectline_strict = False  # Tracks if we need to use AI generate. [[ and {{ in template signify AI hence not strict
                subjectline_templates: list[
                    EmailSubjectLineTemplate
                ] = EmailSubjectLineTemplate.query.filter(
                    EmailSubjectLineTemplate.client_archetype_id == prospect.archetype_id,
                    EmailSubjectLineTemplate.active == True,
                ).all()
                subjectline_template: EmailSubjectLineTemplate = (
                    random.choice(subjectline_templates) if subjectline_templates else None
                )
                

                subjectline_template: EmailSubjectLineTemplate = (
                random.choice(subjectline_templates) if subjectline_templates else None
            )

                template: EmailSequenceStep = random.choice(templates) if templates else None

                #generate email template

                client_archetype : ClientArchetype = ClientArchetype.query.get(prospect.archetype_id)

                if client_archetype.is_ai_research_personalization_enabled:
                    magic_subject_line, personalized_email, ai_research_points = generate_magic_subject_line(
                        archetype_id,
                        prospect_id=prospect.id,
                        sequence_id=template.id,
                        should_generate_email=True,
                        room_id=None,
                        subject_line_id=subjectline_template.id
                    )

                    #add email results to slack message
                    task_blocks.append({
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "*Email Initial Message:*"
                        }
                    })
                    task_blocks.append({
                        "type": "rich_text",
                        "block_id": "Vrzsu",
                        "elements": [
                            {
                                "type": "rich_text_quote",
                                "elements": [
                                    {
                                        "type": "text",
                                        "text": f"Subject: {magic_subject_line}\n\n{personalized_email}"
                                    }
                                ]
                            },
                        ]
                    })
                

        if show_estimated_results:
            task_blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        "Estimated Results:\n"
                        ":incoming_envelope: # Contacts: 43 unique\n"
                        ":speech_balloon: Est. Conversations: 3 conversations\n"
                        ":calendar: Est. Demos: 1 demo\n"
                        ":moneybag: Est. Pipeline: $8,830"
                    )
                }
            })

        if show_action_item:
            task_blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "Review campaign and launch here:"
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

        # send_slack_message(
        #     message="New Selix Session Awaiting",
        #     #please advise correct webhook url
        #     webhook_urls=[webhook_url],
        #     blocks=task_blocks
        # )

        return task_blocks, 200
    except Exception as e:
        print('exception: ', e)
        return "NOT OK", 400
