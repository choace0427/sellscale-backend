import datetime
from http import client
import json
from operator import is_
from tracemalloc import start
from typing import Optional
from numpy import add
import requests
import os
import time
from app import db, celery

from model_import import SelixSession, SelixSessionTask, SelixSessionStatus, SelixSessionTaskStatus, SelixActionCall
from src.client.models import ClientSDR, Client
from src.contacts.models import SavedApolloQuery

from src.contacts.services import get_contacts_from_predicted_query_filters, handle_chat_icp
from src.ml.openai_wrappers import wrapped_chat_gpt_completion
from src.ml.services import generate_strategy_copilot_response, simple_perplexity_response
from src.strategies.models import Strategies, StrategyStatuses
from src.strategies.services import create_task_list_from_strategy
from src.utils.abstract.attr_utils import deep_get
from src.utils.slack import URL_MAP, send_slack_message
from src.sockets.services import send_socket_message

# Some information about the user you're speaking with:
# Name: Rishi Bhanderjee
# Title: Sales Rep at Athelas
# Company: Athelas
# Company Tagline: AI-Powered Operations for Healthcare
# Company Description: At Athelas we're bringing simple, life-changing health care products and medical billing services to patients and providers around the globe.

OPENAI_API_KEY = "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"

# Setup
API_URL = "https://api.openai.com/v1"
HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {OPENAI_API_KEY}",
    "OpenAI-Beta": "assistants=v1",
}


# ACTIONS
def increment_session_counter(session_id: int):
    selix_session: SelixSession = SelixSession.query.get(session_id)
    selix_session.memory["counter"] = selix_session.memory.get("counter", 0) + 1
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(selix_session, "memory")
    db.session.add(selix_session)
    db.session.commit()

    thread_id = selix_session.thread_id
    if (thread_id):
        session_dict = selix_session.to_dict()
        #loop through the task and see if things need to be converted to serializable
        for key, value in session_dict.items():
            if isinstance(value, datetime.datetime):
                session_dict[key] = value.isoformat()
        send_socket_message('update-session', {'session': session_dict, 'thread_id': thread_id}, thread_id)

def adjust_selix_task_order(client_sdr_id: int, task_id: int, new_order: int) -> tuple[bool, str]:
    task: SelixSessionTask = SelixSessionTask.query.get(task_id)
    session: SelixSession = SelixSession.query.get(task.selix_session_id)
    if not task:
        return False, "Task not found"
    if session.client_sdr_id != client_sdr_id:
        return False, "Unauthorized to update this task"

    task.order_number = new_order
    db.session.add(task)
    db.session.commit()
    return True, "Task order updated successfully"

def create_selix_task(client_sdr_id: int, session_id: int, task_title: str, widget_type: Optional[str] = None) -> tuple[bool, str]:
    order_number = SelixSessionTask.query.filter_by(selix_session_id=session_id).count() + 1
    task = SelixSessionTask(
        selix_session_id=session_id,
        actual_completion_time=None,
        title=task_title,
        description="",
        status=SelixSessionTaskStatus.QUEUED,
        order_number=order_number,
        widget_type=widget_type
    )

    session: SelixSession = SelixSession.query.get(session_id)
    if not session or session.client_sdr_id != client_sdr_id:
        return False, "Unauthorized to create task"

    db.session.add(task)
    db.session.commit()
    return True, "Task created successfully"

def bulk_create_selix_tasks(client_sdr_id: int, session_id: int, task_titles: list[str], widget_type: Optional[str] = None) -> tuple[bool, str]:
    total_success = False
    total_message = ""
    for task_title in task_titles:
        success, message = create_selix_task(client_sdr_id, session_id, task_title, widget_type)

        if not success:
            total_success = False
            total_message = message
            break
        else:
            total_success = True
            total_message = message

    return total_success, total_message

def update_selix_task(
        client_sdr_id: int, 
        task_id: int, 
        new_title: Optional[str] = None, 
        new_status: Optional[str] = None, 
        new_proof_of_work: Optional[str] = None, 
        new_description: Optional[str] = None, 
        internal_notes: Optional[str] = None,
        internal_review_needed: Optional[bool] = None,
        widget_type: Optional[str] = None,
        rewind_img: Optional[str] = None
) -> tuple[bool, str]:
    task: SelixSessionTask = SelixSessionTask.query.get(task_id)
    session: SelixSession = SelixSession.query.get(task.selix_session_id)
    if not task:
        return False, "Task not found"
    if session.client_sdr_id != client_sdr_id:
        return False, "Unauthorized to update this task"

    if new_title:
        task.title = new_title
    if new_status:
        task.status = new_status
    if new_proof_of_work:
        task.proof_of_work_img = new_proof_of_work
    if new_description:
        task.description = new_description
    if internal_notes:
        task.internal_notes = internal_notes
    if internal_review_needed is not None:
        task.requires_review = internal_review_needed
    task.widget_type = widget_type if widget_type else None
    if rewind_img:
        task.rewind_img = rewind_img

    db.session.add(task)
    db.session.commit()
    
    #send socket message to update the task
    thread_id = session.thread_id
    if thread_id:
        task_dict = task.to_dict()
        for key, value in task.to_dict().items():
            if isinstance(value, datetime.datetime):
                task_dict[key] = value.isoformat()
        send_socket_message('update-task', {'task': task_dict, 'thread_id': thread_id}, thread_id)

    return True, "Task updated successfully"

def delete_selix_task(client_sdr_id: int, task_id: int) -> tuple[bool, str, int]:
    try:
        task = SelixSessionTask.query.get(task_id)
        session: SelixSession = SelixSession.query.get(task.selix_session_id)
        if not task or session.client_sdr_id != client_sdr_id:
            return False, "Unauthorized to delete this task", 403
        if not task:
            return False, "Task not found", 404

        db.session.delete(task)
        db.session.commit()
        return True, "Task deleted successfully", 200
    except Exception as e:
        return False, str(e), 500


def set_session_tab(
    selix_session_id: int,
    tab_name: str,
):
    selix_session: SelixSession = SelixSession.query.get(selix_session_id)
    selix_session.memory["tab"] = tab_name
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(selix_session, "memory")
    db.session.add(selix_session)
    db.session.commit()

    #send message to change tab
    thread_id = selix_session.thread_id
    if thread_id:
        send_socket_message('change-tab', {'tab': tab_name, 'thread_id': thread_id}, thread_id)
    return True, "Session tab updated successfully"

def create_selix_action_call_entry(
    selix_session_id: int, 
    action_title: str,
    action_description: str,
    action_function: str,
    action_params: dict
) -> int:
    selix_action_call = SelixActionCall(
        selix_session_id=selix_session_id,
        action_title=action_title,
        action_description=action_description,
        action_function=action_function,
        action_params=action_params
    )
    db.session.add(selix_action_call)
    db.session.commit()
    thread_id = SelixSession.query.get(selix_session_id).thread_id
    if thread_id:
        action_dict = selix_action_call.to_dict()
        if 'file' in action_dict.get('action_params', {}):
            del action_dict['action_params']['file'] #remove the file from the action params as it is not serializable and will cause an error when sending to the frontend
        for key, value in action_dict.items():
            if isinstance(value, datetime.datetime):
                action_dict[key] = value.isoformat()
        send_socket_message('incoming-message', {'action': action_dict, 'thread_id': thread_id}, thread_id)
    return selix_action_call.id

def selix_campaign_enabled_handler(campaign_id: int):
    """
    If called, check if there are any sessions with the given campaign_id and automatically:
    - mark the session as complete
    - mark all the tasks in the session as complete

    This is a handler function that is called when a campaign is enabled.
    """

    try:
        query = """
            select selix_session.id
            from selix_session
            where cast(selix_session.memory->>'campaign_id' as integer) = {}
        """.format(campaign_id)

        result = db.session.execute(query).fetchall()
        session_ids = [row[0] for row in result]

        for session_id in session_ids:
            session: SelixSession = SelixSession.query.get(session_id)
            session.status = SelixSessionStatus.COMPLETE
            db.session.add(session)
            db.session.commit()

            session_tasks = SelixSessionTask.query.filter_by(selix_session_id=session_id).all()
            for task in session_tasks:
                task.status = SelixSessionTaskStatus.COMPLETE
                db.session.add(task)
            db.session.commit()
    except Exception as e:
        print("Error in campaign_enabled_handler: ", e)

def mark_action_complete(selix_action_call_id: int):
    selix_action_call: SelixActionCall = SelixActionCall.query.get(selix_action_call_id)
    #look up selix task from the action
    selix_task: SelixSessionTask = None
    if selix_action_call.action_params.get("title"):
        selix_task = SelixSessionTask.query.filter_by(selix_session_id=selix_action_call.selix_session_id, title=selix_action_call.action_params.get("title")).first()
    else:
        print("Task not found for action: ", selix_action_call_id)
        return
    # selix_task.status = SelixSessionTaskStatus.COMPLETE
    selix_action_call.actual_completion_time = datetime.datetime.now()
    # db.session.add(selix_task)
    db.session.add(selix_action_call)
    db.session.commit()

    #send message to update the task as complete
    thread_id = SelixSession.query.get(selix_action_call.selix_session_id).thread_id
    if thread_id:
        action_dict = selix_action_call.to_dict()
        #loop through the action and see if things need to be converted to serializable
        for key, value in action_dict.items():
            if isinstance(value, datetime.datetime):
                action_dict[key] = value.isoformat()
        print("Sending message to update task with payload: ", action_dict)
        send_socket_message('update-task', {'action': action_dict, 'thread_id': thread_id}, thread_id)

def create_campaign(campaign_name: str):
    print("⚡️ AUTO ACTION: create_campaign('{}')".format(campaign_name))
    return {"success": True}


def find_prospects(query_description: str):
    print("⚡️ AUTO ACTION: find_prospects('{}')".format(query_description))
    contacts = get_contacts_from_predicted_query_filters(query_description)
    sample_prospects_to_show = [
        {
            "company": people["organization"]["name"],
            "title": people["title"],
            "full_name": people["name"],
            "linkedin_url": people["linkedin_url"],
        }
        for people in contacts["people"][0:4]
    ]

    breadcrumbs = contacts["breadcrumbs"]
    num_prospects = contacts["pagination"]["total_entries"]

    return {
        "num_prospects": num_prospects,
        "sample_prospects_to_show": sample_prospects_to_show,
        "breadcrumbs": breadcrumbs,
    }

@celery.task
def edit_strategy(
    edit_description: str,
    session_id: int,
    should_create_action: bool = True
):
    print('editing strategy')
    print("⚡️ AUTO ACTION: edit_strategy('{}')".format(edit_description))
    
    selix_action_id = None
    if should_create_action:
        selix_action_id = create_selix_action_call_entry(
        selix_session_id=session_id,
        action_title="Adjusting the strategy",
        action_description="Edit the strategy based on the description provided: {}".format(edit_description),
        action_function="edit_strategy",
        action_params={"edit_description": edit_description}
        )

    strategy_id: int = SelixSession.query.get(session_id).memory.get("strategy_id", None)
    if not strategy_id:
        return {"error": "No strategy found."}
    
    strategy: Strategies = Strategies.query.get(strategy_id)
    title = strategy.title
    description = strategy.description

    messages = get_last_n_messages(SelixSession.query.get(session_id).thread_id)
    last_message_from_user = None
    if messages:
        last_message_from_user = messages[-1].get('message', None)
    
    if last_message_from_user:
        edit_description = last_message_from_user

    changes_needed = wrapped_chat_gpt_completion(
        messages=[
            {
                "role": "system",
                "content": """
                You are a strategy editor. I will provide you with both a title and an 'edit description'. 
                Based on the edit description, tell me what adjustments I need to make to the strategy title and description.
                Only make changes if REQUIRED and do not alter more than needed.

                Original Title: {}
                Original Description: {}

                Edit Description: {}

                Changes Needed:""".format(
                    title, description, edit_description
                ),
            }
        ],
        model="gpt-4o",
        max_tokens=1000,
        response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "changes_needed_schema",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "title_changes_needed": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "change_description": { "type": "string" },
                                    },
                                    "required": ["change_description"],
                                    "additionalProperties": False
                                }
                            },
                            "description_changes_needed": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "change_description": { "type": "string" },
                                    },
                                    "required": ["change_description"],
                                    "additionalProperties": False
                                }
                            }
                        },
                        "required": ["title_changes_needed", "description_changes_needed"],
                        "additionalProperties": False
                    },
                    "strict": True
                }
            }
    )
    
    changes_needed = json.loads(changes_needed)

    title_changes_needed = changes_needed.get("title_changes_needed", [])
    description_changes_needed = changes_needed.get("description_changes_needed", [])

    title_changes_needed_str = "\n".join([f"- {change['change_description']}" for change in title_changes_needed])
    description_changes_needed_str = "\n".join([f"- {change['change_description']}" for change in description_changes_needed])

    updated_title = wrapped_chat_gpt_completion(
        messages=[
            {
                "role": "system",
                "content": """
                You are a strategy title editor. I will provide you with both a title and an 'edit description'. 
                Based on the edit description, you will need to update the strategy title. If the edit description does not require a change in the title, simply respond with the original title.

                Do NOT make any other changes to the title. Only update the title if the edit description requires it.
                ONLY respond with the updated title. No extra text.

                Original Title: {}
                Edit Description: {}

                New Title:""".format(
                    title, title_changes_needed_str
                ),
            }
        ],
        model="gpt-4o",
        max_tokens=50
    )

    updated_description = wrapped_chat_gpt_completion(
        messages=[
            {
                "role": "system",
                "content": """
                You are a strategy description editor. I will provide you with both a description and an 'edit description'.
                Based on the edit description, you will need to update the strategy description. If the edit description does not require a change in the description, simply respond with the original description.

                Do NOT make any other changes to the description. Only update the description if the edit description requires it.
                MAKE SURE YOU maintain the same structure and format of the original description.
                ONLY respond with the updated description. No extra text.

                Original Description: '''
                {}
                '''

                Edit Description: {}

                New Description:""".format(
                    description, description_changes_needed_str
                ),
            }
        ],
        model="gpt-4o",
        max_tokens=1000
    )

    strategy.title = updated_title
    strategy.description = updated_description
    db.session.add(strategy)
    db.session.commit()

    if selix_action_id:
        mark_action_complete(selix_action_id)
    set_session_tab(
        session_id, 
        "STRATEGY_CREATOR"
    )

    #trigger an update to the session
    session = SelixSession.query.get(session_id)
    thread_id = session.thread_id

    if thread_id:
        session_dict = session.to_dict()
        #loop through the task and see if things need to be converted to serializable
        for key, value in session_dict.items():
            if isinstance(value, datetime.datetime):
                session_dict[key] = value.isoformat()
        send_socket_message('update-session', {'session': session_dict, 'thread_id': thread_id}, thread_id)

    # Three cases
    num_queued_tasks = SelixSessionTask.query.filter_by(selix_session_id=session_id, status=SelixSessionTaskStatus.QUEUED).count()
    num_total_tasks = SelixSessionTask.query.filter_by(selix_session_id=session_id).count()
    session_status_is_active = session.status == SelixSessionStatus.ACTIVE
    # 1. If no tasks in Queued and session status is ACTIVE
    if num_queued_tasks == 0 and session_status_is_active:
        pass
    # 2. If there are tasks in Queued, then clear all those tasks and generate new tasks from strategy and move to pending operator
    elif num_queued_tasks > 0:
        queued_tasks = SelixSessionTask.query.filter_by(selix_session_id=session_id, status=SelixSessionTaskStatus.QUEUED).all()
        for task in queued_tasks:
            task.status = SelixSessionTaskStatus.CANCELLED
            db.session.add(task)
            db.session.commit()
            task_dict = task.to_dict()
            for key, value in task_dict.items():
                if isinstance(value, datetime.datetime):
                    task_dict[key] = value.isoformat()
            send_socket_message('update-task', {'task': task_dict, 'thread_id': thread_id}, thread_id)
        
        session.status = SelixSessionStatus.PENDING_OPERATOR
        db.session.add(session)
        db.session.commit()
        send_socket_message('update-session', {'session': session_dict, 'thread_id': thread_id}, thread_id)

        create_tasks_from_strategy(session_id=session_id)
    # 3. If there are zero tasks in Queued and session status is not ACTIVE, mark all non complete tasks as canceled and make new adjustment tasks and a new notify & review task
    elif num_queued_tasks == 0 and not session_status_is_active:
        for change in title_changes_needed:
            create_task(
                title="Adjust: {}".format(change["change_description"]),
                description="Adjust based on title change: {}".format(change["change_description"]),
                session_id=session_id,
                create_action=True
            )
        for change in description_changes_needed:
            create_task(
                title="Adjust: {}".format(change["change_description"]),
                description="Adjust based on description change: {}".format(change["change_description"]),
                session_id=session_id,
                create_action=True
            )
        
        sdr_name = ClientSDR.query.get(session.client_sdr_id).name
        first_name = sdr_name.split(" ")[0]

        create_task(
            title="Notify {} for review & launch".format(first_name),
            description="Notify {} and review the changes made to the strategy.".format(first_name),
            session_id=session_id,
            create_action=True
        )

        session.status = SelixSessionStatus.PENDING_OPERATOR
        db.session.add(session)
        db.session.commit()
        send_socket_message('update-session', {'session': session_dict, 'thread_id': thread_id}, thread_id)

    return {"success": True}


def generate_sequence(channel: str, steps: list):
    print("⚡️ AUTO ACTION: generate_sequence('{}', {})".format(channel, steps))
    return {"channel": channel, "num_steps": 1, "steps": steps}

def search_internet(query: str, session_id: int):
    print("⚡️ AUTO ACTION: search_internet('{}')".format(query))
    
    selix_action_id = create_selix_action_call_entry(
        selix_session_id=session_id,
        action_title="Searching Internet",
        action_description="Searching the internet for information related to the query: {}".format(query),
        action_function="search_internet",
        action_params={"query": query}
    )

    import concurrent.futures

    def check_citation(citation):
        try:
            from bs4 import BeautifulSoup
            import requests
            if 'reddit' in citation:
                print(f"⚠️ Citation blocked or not accessible: {citation}")
                return None

            response = requests.get(citation, timeout=2)
            if response.status_code == 200:
                x_frame_options = response.headers.get('X-Frame-Options', '').lower()
                if x_frame_options != '' and ('sameorigin' or 'deny' in x_frame_options):
                    print('x frame options for this url are: ', x_frame_options)
                    print(f"⚠️ Citation blocked due to X-Frame-Options: {citation}")
                    return None

                print('xframe options were as follows: ', x_frame_options, 'for url ', citation)
                content_security_policy = response.headers.get('Content-Security-Policy', '').lower()
                if "frame-ancestors 'self'" in content_security_policy:
                    print(f"⚠️ Citation blocked due to Content-Security-Policy frame-ancestors directive: {citation}")
                    return None

                iframe_html = f'<iframe src="{citation}" style="display:none;"></iframe>'
                soup = BeautifulSoup(iframe_html, 'html.parser')
                iframe = soup.find('iframe')
                
                if iframe and iframe.get('src'):
                    iframe_response = requests.get(iframe.get('src'), timeout=2)
                    if iframe_response.status_code == 200:
                        print('this is a valid citation: ', citation)
                        return citation
                    else:
                        print(f"⚠️ Citation iframe source refused to connect or not accessible: {iframe.get('src')}")
                        return None
                else:
                    print(f"⚠️ Citation blocked or not accessible: {citation}")
                    return None
            else:
                print(f"⚠️ Citation blocked or not accessible: {citation}")
                return None
        except Exception as e:
            print(f"⚠️ Error checking citation {citation}: {e}")
            return None

    def get_perplexity_response(query):
        import random
        prompt_endings = [
            "\nReturn your response in a maximum of 1-2 engaging paragraphs.",
            "\nPlease provide a concise and insightful answer in no more than two paragraphs.",
            "\nSummarize your response in 1-2 short, impactful paragraphs.",
            "\nCraft your response in 1-2 paragraphs, ensuring it is both clear and compelling.",
            "\nDeliver your answer in 1-2 paragraphs, focusing on clarity and brevity.",
            "\nProvide a succinct and informative response in no more than two paragraphs."
        ]
        return simple_perplexity_response(
            model="llama-3-sonar-large-32k-online",
            prompt = query + random.choice(prompt_endings)
        )

    with concurrent.futures.ThreadPoolExecutor() as executor:
        # Get 3 responses to the same query
        # This is to ensure we get the best response
        # as the perplexity model can sometimes give
        # different responses for the same query
        future_responses = [executor.submit(get_perplexity_response, query) for _ in range(3)]
        responses = [future.result() for future in concurrent.futures.as_completed(future_responses)]

    best_response = None
    max_valid_citations = 0
    best_valid_citations = []

    for response_data in responses:
        response, citations, images = response_data
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future_to_citation = {executor.submit(check_citation, citation): citation for citation in citations}
            valid_citations = [future.result() for future in concurrent.futures.as_completed(future_to_citation) if future.result() is not None]
            print('valid citations: ', valid_citations)
        if len(valid_citations) > max_valid_citations:
            max_valid_citations = len(valid_citations)
            best_response = (response, valid_citations, images)
            best_valid_citations = valid_citations

    if best_response:
        response, citations, images = best_response
        citations = best_valid_citations
    else:
        response, citations, images = None, [], []

    session: SelixSession = SelixSession.query.get(session_id)
    session.memory["search"] = [{
        "query": query,
        "response": response,
        "citations": citations,
        "images": images
    }]
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(session, "memory")
    db.session.add(session)
    db.session.commit()

    thread_id = session.thread_id
    if (thread_id):
        session_dict = session.to_dict()
        #loop through the task and see if things need to be converted to serializable
        for key, value in session_dict.items():
            if isinstance(value, datetime.datetime):
                session_dict[key] = value.isoformat()
        send_socket_message('update-session', {'session': session_dict, 'thread_id': thread_id}, thread_id)

    mark_action_complete(selix_action_id)
    set_session_tab(session_id, "BROWSER")
    return {"response": response}

def create_review_card(campaign_id: dict):
    print("⚡️ AUTO ACTION: create_review_card({})".format(campaign_id))
    return {"success": True}

def create_strategy(angle: str, prospects: str, offer: str, channel: str, timing: str, specific_copy: str, personalizers: str, links: str, session_id: int):
    # description = (
    #     f"Angle: {angle}\n"
    #     f"Prospects: {prospects}\n"
    #     f"Offer: {offer}\n"
    #     f"Channel: {channel}\n"
    #     f"Timing: {timing}\n"
    #     f"Specific Copy: {specific_copy}\n"
    #     f"Customizations: {personalizers}\n"
    #     f"Links: {links}"
    # )

    description = ''
    # Fetch the whole transcript from the conversation
    session: SelixSession = SelixSession.query.get(session_id)
    thread_id = session.thread_id
    messages = get_last_n_messages(thread_id)
    description = ""
    for message in messages:
        if 'message' in message:
            description += f"{message['role']}:\n{message['message']}\n\n"

    print("⚡️ AUTO ACTION: create_strategy('{}')".format(description))

    selix_action_id = create_selix_action_call_entry(
        selix_session_id=session_id,
        action_title="Create Strategy for `{}`".format(description[:20] + "..."),
        action_description="Create a strategy based on the description provided: {}".format(description),
        action_function="create_strategy",
        action_params={"description": description, "title" : "Create Strategy"}
    )

    title = wrapped_chat_gpt_completion(
        messages=[
            {
                "role": "system",
                "content": """
                Based on the description, give me a 3-5 word strategy title.

                Examples:
                Input: "Expand market reach through social media campaigns."
                Output: "Social Media Market Expansion"

                Input: "Increase customer retention by improving support services."
                Output: "Enhanced Customer Support Retention"

                Important:
                - Only return the strategy title. No Yapping.
                - No quotations or special characters. Just the simple 3-5 word title.
                
                Description: {}
                Strategy Title:""".format(
                    description
                ),
            }
        ],
        model="gpt-4o",
    )

    chat_content = [
        {"sender": "user", "query": description, "id": 1}
    ]
    strategy_response = generate_strategy_copilot_response(chat_content, client_sdr_id=session.client_sdr_id)
    strategy_description = strategy_response.get("response", "").replace("html", "").replace("`", "").strip()

    session: SelixSession = SelixSession.query.get(session_id)
    client_sdr: ClientSDR = ClientSDR.query.get(session.client_sdr_id)

    strategy: Strategies = Strategies(
        title=title,
        description=strategy_description,
        tagged_campaigns=None,
        status=StrategyStatuses.NOT_STARTED,
        start_date=datetime.datetime.today(),
        end_date=datetime.datetime.today() + datetime.timedelta(days=30),
        client_id=client_sdr.client_id,
        created_by=session.client_sdr_id
    )
    db.session.add(strategy)
    db.session.commit()

    from sqlalchemy.orm.attributes import flag_modified
    
    session: SelixSession = SelixSession.query.get(session_id)
    session.memory["strategy_id"] = strategy.id
    flag_modified(session, "memory")
    db.session.add(session)
    db.session.commit()

    thread_id = session.thread_id
    if (thread_id):
        session_dict = session.to_dict()
        #loop through the task and see if things need to be converted to serializable
        for key, value in session_dict.items():
            if isinstance(value, datetime.datetime):
                session_dict[key] = value.isoformat()
        send_socket_message('update-session', {'session': session_dict, 'thread_id': thread_id}, thread_id)

    selix_task = SelixSessionTask(
        selix_session_id=session_id,
        actual_completion_time=datetime.datetime.now(),
        title="Create Strategy",
        description="Create a strategy based on the description provided: {}".format(description),
        status=SelixSessionTaskStatus.COMPLETE
    )
    db.session.add(selix_task)
    db.session.commit()

    thread_id = session.thread_id
    if thread_id:
        task_dict = selix_task.to_dict()
        for key, value in task_dict.items():
            if isinstance(value, datetime.datetime):
                task_dict[key] = value.isoformat()
        send_socket_message('add-task-to-session', {'task': task_dict, 'thread_id': thread_id}, thread_id)

    

    # Mark all previous tasks in the session as complete
    previous_tasks: list[SelixSessionTask] = SelixSessionTask.query.filter(
        SelixSessionTask.selix_session_id == session_id,
        SelixSessionTask.status != SelixSessionTaskStatus.COMPLETE
    ).all()
    
    for task in previous_tasks:
        task.status = SelixSessionTaskStatus.COMPLETE
        task.actual_completion_time = datetime.datetime.now()
        db.session.add(task)
    
    db.session.commit()

    #send socket to update all these tasks after commit
    if thread_id:
        for task in previous_tasks:
            task_dict = task.to_dict()
            for key, value in task_dict.items():
                if isinstance(value, datetime.datetime):
                    task_dict[key] = value.isoformat()
            send_socket_message('update-task', {'task': task_dict, 'thread_id': thread_id}, thread_id)

    mark_action_complete(selix_action_id)
    set_session_tab(session_id, "STRATEGY_CREATOR")
    return {"success": True}

def create_task(title: str, description: str, session_id: int, create_action=True, widget_type=None):
    print("⚡️ AUTO ACTION: create_task('{}', '{}')".format(title, description))
    
    selix_action_id = None
    if create_action:
        selix_action_id = create_selix_action_call_entry(
            selix_session_id=session_id,
            action_title="Adding task: {}".format(title),
            action_description="Create a task with the title: {} and description: {}".format(title, description),
            action_function="create_task",
            action_params={"title": title, "description": description},
        )

    order_number = SelixSessionTask.query.filter_by(selix_session_id=session_id).count() + 1

    task = SelixSessionTask(
        selix_session_id=session_id,
        actual_completion_time=None,
        title=title,
        description=description,
        status=SelixSessionTaskStatus.QUEUED,
        order_number=order_number,
        widget_type=widget_type if widget_type != 'NULL' else None
    )
    db.session.add(task)
    db.session.commit()


    thread_id = SelixSession.query.get(session_id).thread_id
    if thread_id:
        task_dict = task.to_dict()
        for key, value in task_dict.items():
            if isinstance(value, datetime.datetime):
                task_dict[key] = value.isoformat()
        send_socket_message('add-task-to-session', {'task': task_dict, 'thread_id': thread_id}, thread_id)

    if selix_action_id:
        mark_action_complete(selix_action_id)
    set_session_tab(session_id, "PLANNER")
    return {"success": True, "action_id": selix_action_id, "task_id": task.id}

def wait_for_ai_execution(session_id: int):
    print("⚡️ AUTO ACTION: wait_for_ai_execution()")
    
    selix_action_id = create_selix_action_call_entry(
        selix_session_id=session_id,
        action_title="Start working on tasks",
        action_description="Wait for AI Execution to complete.",
        action_function="wait_for_ai_execution",
        action_params={'title': 'Awaiting AI Completion'}
    )

    session: SelixSession = SelixSession.query.get(session_id)
    session.estimated_completion_time = datetime.datetime.now() + datetime.timedelta(hours=24)
    session.status = SelixSessionStatus.PENDING_OPERATOR
    
    send_slack_message(
        message="Selix Session is waiting for operator: {}".format(session.id),
        webhook_urls=[URL_MAP['eng-sandbox']]
    )

    send_socket_message(
        'increment-counter',
        {'message': 'increment', 'thread_id': session.thread_id},
        session.thread_id
    )

    #take first queued task and mark it as in progress
    task = SelixSessionTask.query.filter_by(selix_session_id=session_id, status=SelixSessionTaskStatus.QUEUED).order_by(SelixSessionTask.order_number.asc()).first()

    if task:
        task.status = SelixSessionTaskStatus.IN_PROGRESS
        db.session.add(task)
        db.session.commit()

        thread_id = session.thread_id
        if thread_id:
            task_dict = task.to_dict()
            for key, value in task_dict.items():
                if isinstance(value, datetime.datetime):
                    task_dict[key] = value.isoformat()
            send_socket_message('update-task', {'task': task_dict, 'thread_id': thread_id}, thread_id)

    session_sdr: ClientSDR = ClientSDR.query.get(session.client_sdr_id)
    company: Client = Client.query.get(session_sdr.client_id)
    tasks: list[SelixSessionTask] = SelixSessionTask.query.filter_by(selix_session_id=session_id).order_by(SelixSessionTask.order_number.is_(None).desc(), SelixSessionTask.order_number.asc()).all()

    deep_link =  f"https://app.sellscale.com/authenticate?stytch_token_type=direct&token={session_sdr.auth_token}&redirect=selix&thread_id={session.thread_id}&session_id={session.id}"
    
    task_blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"🎉🤖 New Selix Session Complete: {session_sdr.name} from {company.company} 🎉",
                "emoji": True,
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"{len(tasks)} tasks created"
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
            "text": "View the session here:"
        },
        "accessory": {
            "type": "button",
            "text": {
                "type": "plain_text",
                "text": "Deep Link",
                "emoji": True
            },
            "url": deep_link,
            "action_id": "button-action"
        }
    })

    task_blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": "Internal Tool"
        },
        "accessory": {
            "type": "button",
            "text": {
                "type": "plain_text",
                "text": "Internal Tool",
                "emoji": True
            },
            "url": "https://sellscale.retool.com/apps/d844610e-5523-11ef-8ac7-4fac094b8e83/Selix%20MVP/Selix%20AI%20-%20Internal%20Operations%20View?_releaseVersion=latest",
            "action_id": "button-action-internal-tool"
        }
    })

    send_slack_message(
        message="New Selix Session Awaiting",
        webhook_urls=[URL_MAP['selix-sessions']],
        blocks=task_blocks
    )
    
    mark_action_complete(selix_action_id)
    set_session_tab(session_id, "PLANNER")
    return {"success": True}

def create_tasks_from_strategy(session_id: int):
    print("⚡️ AUTO ACTION: create_tasks_from_strategy()")
    set_session_tab(session_id, "PLANNER")

    selix_action_id = create_selix_action_call_entry(
        selix_session_id=session_id,
        action_title="Creating task list from strategy",
        action_description="Create tasks based on the strategy",
        action_function="create_tasks_from_strategy",
        action_params={}
    )
    
    tasks: list[dict[str, str]] = create_task_list_from_strategy(
        selix_session_id=session_id
    )
    
    for task in tasks:
        create_task(
            title=task["title"],
            description=task["description"],
            session_id=session_id,
            create_action=True,
            widget_type=task['widget_type']
        )

    mark_action_complete(selix_action_id)
    
    return {"success": True}

def create_icp(
    icp_description: str,
    session_id: int,
    should_create_action: bool = True
):
    
    #create the action call

    selix_action_id = None
    if should_create_action:
        selix_action_id = create_selix_action_call_entry(
            selix_session_id=session_id,
            action_title="Creating new ICP",
            action_description="Create an ICP based on the description provided: {}".format(icp_description),
            action_function="create_icp",
            action_params={"icp_description": icp_description}
        )

    print('parameters are', icp_description, session_id, should_create_action)
    
    selix_session: SelixSession = SelixSession.query.get(session_id)

    #idk maybe we should populate chat_content with the previous messages
    handle_chat_icp(client_sdr_id=selix_session.client_sdr_id, chat_content=[], prompt=icp_description)

    #change tab to ICP
    set_session_tab(session_id, "ICP")

    if selix_action_id:
        mark_action_complete(selix_action_id)

    return {"success": True}


def update_and_receive_memory(session_id):
    messages = get_last_n_messages(SelixSession.query.get(session_id).thread_id)
    memory_state = SelixSession.query.get(session_id).memory.get('memory_state') or ''

    messages = [msg for msg in messages if 'message' in msg]

    last_message_from_assistant = messages[-1]['message'] if messages else ''
    last_message_from_user = messages[-2]['message'] if len(messages) > 1 else ''

    response = wrapped_chat_gpt_completion(
        messages=[
            {
                "role": "user",
                "content": """You are a memory editor. I will provide you with the current memory state and the last few messages from the user and from the assistant.

Based on the last message, make adjustments to the memory state. Things to add in the memory should be 'action items' such as:
- "Remember to ask the user which channel they want to reach out on."
- "Ask the user to provide you with a CSV file of their prospects."
- "Ask if the user if they have a booth at the event."
and other items. 

IMPORTANT:
- Only add action items to the memory state if they have not already been added
- Do not add general information or context to the memory state. Only add action items if the user indicated they will provide something but have not yet done so.
- Do not add information that is already present in the memory state. Only add new action items
- Remove any action items that have been completed. ONLY remove if the action item has a 100-percent certainty of completion.
- The memory state must be stored as a bullet-point list.

User: {last_message_from_user}
Assistant: {last_message_from_assistant}
        
Current Memory State:
{memory_state}

Only respond with the updated memory state. If there's nothing new to mention, just write "- None"

Updated Memory State:""".format(
            last_message_from_assistant=last_message_from_assistant,
            last_message_from_user=last_message_from_user,
            memory_state=memory_state
        )
            }
        ],
        model="gpt-4o",
        max_tokens=1000
    )

    session = SelixSession.query.get(session_id)
    session.memory['memory_state'] = response
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(session, "memory")

    db.session.add(session)
    db.session.commit()

    return {"updated_memory": response}

ACTION_MAP = {
    "create_campaign": create_campaign,
    "find_prospects": find_prospects,
    "generate_sequence": generate_sequence,
    "create_review_card": create_review_card,
    "create_strategy": create_strategy,
    "create_task": create_task,
    "wait_for_ai_execution": wait_for_ai_execution,
    "search_internet": search_internet,
    "edit_strategy": edit_strategy,
    "create_tasks_from_strategy": create_tasks_from_strategy,
    "create_icp": create_icp
}


def run_action(action_name, params, session_id):
    return ACTION_MAP[action_name](**params, session_id=session_id)

# ACTIONS - END


def create_thread():
    response = requests.post(f"{API_URL}/threads", headers=HEADERS, json={})
    print("✨ Created thread: ", response.json()["id"], "\n")
    return response.json()["id"]


def add_message_to_thread(thread_id, content, role="user", device_id=None):
    data = {"role": role, "content": content}

    #send socket message to other chats in case it's open
    
    if device_id:
        print("Sending message to device_id: ", device_id)
        send_socket_message('incoming-message', {'message': content, 'thread_id': thread_id, 'role': 'user', 'device_id': device_id}, thread_id)

    requests.post(f"{API_URL}/threads/{thread_id}/messages", headers=HEADERS, json=data)

    if role == "user":
        session = SelixSession.query.filter_by(thread_id=thread_id).first()
        update_and_receive_memory(session.id)


def run_thread(thread_id, assistant_id):
    data = {
        "assistant_id": assistant_id,
    }
    response = requests.post(
        f"{API_URL}/threads/{thread_id}/runs", headers=HEADERS, json=data
    )

    session_id = SelixSession.query.filter_by(thread_id=thread_id).first().id
    increment_session_counter(session_id)

    send_socket_message('increment-counter', {'message' : 'increment', 'thread_id': thread_id}, thread_id)
    
    error_msg = deep_get(response.json(),'error.message')

    max_attempts = 10
    attempts = 0
    while error_msg and 'already has an active run' in error_msg and attempts < max_attempts:
        time.sleep(1)
        print('re-fetching')
        response = requests.post(
            f"{API_URL}/threads/{thread_id}/runs", headers=HEADERS, json=data
        )
        error_msg = deep_get(response.json(),'error.message')
        attempts += 1
        
    return response.json()["id"]

def stringStartsWith(string, prefix):
    return string[:len(prefix)] == prefix


def get_assistant_reply(thread_id):
    try:
        response = requests.get(
            f"{API_URL}/threads/{thread_id}/messages", headers=HEADERS
        )
        last_message = response.json()["data"][0]["content"][0]["text"]["value"]
        if last_message and last_message != "Acknowledged." and 'Here is some additional context about me,' not in last_message:
            send_socket_message('incoming-message', {'message': last_message, 'thread_id': thread_id, 'role': 'assistant'}, thread_id)
        return last_message
    except:
        return ""

def get_all_threads_with_tasks(client_sdr_id: int) -> list[dict]:
    query = """
    SELECT 
        ss.*, 
        json_agg(json_build_object(
            'id', sst.id,
            'selix_session_id', sst.selix_session_id,
            'title', sst.title,
            'status', sst.status,
            'created_at', sst.created_at,
            'updated_at', sst.updated_at,
            'widget_type', sst.widget_type,
            'description', sst.description,
            'order_number', sst.order_number,
            'proof_of_work_img', sst.proof_of_work_img,
            'rewind_img', sst.rewind_img
        )) AS tasks
    FROM selix_session ss
    LEFT JOIN selix_session_task sst ON ss.id = sst.selix_session_id
    WHERE ss.client_sdr_id = :client_sdr_id
    and ss.status != 'CANCELLED'
    GROUP BY ss.id
    ORDER BY ss.created_at DESC
    """
    result = db.session.execute(query, {'client_sdr_id': client_sdr_id}).fetchall()
    return [dict(row) for row in result]

def get_action_calls(selix_session_id):
    action_calls = SelixActionCall.query.filter_by(selix_session_id=selix_session_id).all()
    return [
        {
            **action_call.to_dict(),
            "created_at": action_call.created_at.replace(tzinfo=datetime.timezone.utc)
        }
        for action_call in action_calls
    ]

def get_last_n_messages(thread_id):
    import time
    from requests.exceptions import RequestException

    all_messages = []
    params = {
        "limit": 100,
        "order": "desc",
    }

    def fetch_messages_with_retry(url, headers, params, retries=3, timeout=2):
        for attempt in range(retries):
            try:
                response = requests.get(url, headers=headers, params=params)
                response.raise_for_status()
                return response
            except RequestException as e:
                if attempt < retries - 1:
                    time.sleep(timeout)
                else:
                    raise e

    while True:
        response = fetch_messages_with_retry(
            f"{API_URL}/threads/{thread_id}/messages", headers=HEADERS, params=params
        )
        
        messages = response.json().get("data", [])
        
        all_messages.extend([
            {
                "type": "message",
                "role": message["role"],
                "message": message["content"][0]["text"]["value"] if message["content"] else "",
                "created_time": datetime.datetime.utcfromtimestamp(message["created_at"])
            }
            for message in messages
        ])

        has_more = response.json().get("has_more", False)
        if not has_more:
            break

        # Update the 'before' parameter to fetch the next set of messages
        params["before"] = messages[-1]["created_at"]


    # Pull all actions
    selix_session_id = SelixSession.query.filter_by(thread_id=thread_id).first().id
    action_calls = get_action_calls(selix_session_id)
    
    # Combine messages and action calls and sort by created time
    all_messages.extend(action_calls)

    all_messages.sort(key=lambda x: x["created_time"])

    selix_session: SelixSession = SelixSession.query.filter_by(thread_id=thread_id).first()

    if len(all_messages) > 6:
        transcript_str = "\n".join([f"{message['role']}: {message['message']}" for message in all_messages if message["type"] == "message"])
        if selix_session.session_name == "New Session":
            rename_session(selix_session.id, transcript_str)

    # Filter out messages based on the given criteria
    filtered_messages = [
        message for message in all_messages
        if message["type"] == 'action' or (message["message"].strip() != "Acknowledged." and 'Here is some additional context about me,' not in message["message"])
    ]
    # Ensure the first message is always the assistant's greeting
    first_message = {
        "created_time": datetime.datetime.utcfromtimestamp(selix_session.created_at.timestamp()),
        "message": "Hello! How can I assist you today? Please provide some information about your campaign or what you would like to achieve. \n \n Chat below, or try clicking the 🎙️ to talk to me!",
        "role": "assistant",
        "type": "message",
    }
    
    # Insert the first message at the beginning of the filtered messages
    filtered_messages.insert(0, first_message)
    all_messages = filtered_messages

    return all_messages

def rename_session(session_id, transcript_str):
    title = wrapped_chat_gpt_completion(
        messages=[
            {
                "role": "system",
                "content": """
                Based on the transcript, give me a 2-4 word session title.

                Examples:
                Input: "User: How do I reset my password? Assistant: You can reset your password by going to the settings page."
                Output: "Password Reset Help"

                Input: "User: What are your business hours? Assistant: We are open from 9 AM to 5 PM, Monday to Friday."
                Output: "Business Hours Info"

                Important:
                - Only return the session title. No extra text.
                - No quotations or special characters. Just the simple 2-4 word title.
                
                Transcript: {}
                Session Title:""".format(
                    transcript_str
                ),
            }
        ],
        model="gpt-4o",
        max_tokens=50
    )

    selix_session = SelixSession.query.get(session_id)
    selix_session.session_name = title
    selix_session.memory["session_name"] = title
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(selix_session, "memory")
    db.session.add(selix_session)
    db.session.commit()


    thread_id = selix_session.thread_id
    if (thread_id):
        session_dict = selix_session.to_dict()
        #loop through the task and see if things need to be converted to serializable
        for key, value in session_dict.items():
            if isinstance(value, datetime.datetime):
                session_dict[key] = value.isoformat()
        send_socket_message('update-session', {'session': session_dict, 'thread_id': thread_id}, thread_id)

    return title


def retrieve_actions_needed(thread_id, run_id, session_id):
    response = requests.get(
        f"{API_URL}/threads/{thread_id}/runs/{run_id}", headers=HEADERS
    )

    function_calls = response.json()["required_action"]["submit_tool_outputs"][
        "tool_calls"
    ]

    responses = []
    for function_call in function_calls:
        tool_call_id = function_call["id"]
        function_name = function_call["function"]["name"]
        args_str = function_call["function"]["arguments"]

        print("Executing: ", function_name, args_str)

        func_args = json.loads(args_str)
        output = run_action(function_name, func_args, session_id=session_id)

        responses.append(
            {
                "tool_call_id": tool_call_id,
                "output": output,
            }
        )

    submit_tool_outputs(
        thread_id,
        run_id,
        [
            {
                "tool_call_id": response["tool_call_id"],
                "output": json.dumps(response["output"]),
            }
            for response in responses
        ],
    )

    return response.json()


def submit_tool_outputs(thread_id, run_id, tool_outputs):
    data = {"tool_outputs": tool_outputs}
    response = requests.post(
        f"{API_URL}/threads/{thread_id}/runs/{run_id}/submit_tool_outputs",
        headers=HEADERS,
        json=data,
    )
    return response.json()

def update_session(
    client_sdr_id: int, 
    session_id: int, 
    new_title: Optional[str], 
    new_status: Optional[str], 
    new_strategy_id: Optional[int],
    new_campaign_id: Optional[int],
    is_draft: Optional[bool] = None,
    new_name: Optional[str] = None
) -> tuple[bool, str]:
    session: SelixSession = SelixSession.query.get(session_id)
    if not session:
        return False, "Session not found."
    if session.client_sdr_id != client_sdr_id:
        return False, "Unauthorized to update this session."
    
    if new_title:
        session.session_name = new_title
    if new_status:
        session.status = new_status
    if new_strategy_id:
        session.memory["strategy_id"] = new_strategy_id
    if new_campaign_id:
        session.memory["campaign_id"] = new_campaign_id
    if is_draft is not None:
        session.draft_session = is_draft
    if new_name:
        session.session_name = new_name
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(session, "session_name")
    flag_modified(session, "status")
    flag_modified(session, "memory")
    flag_modified(session, "draft_session")
    db.session.add(session)
    db.session.commit()

    thread_id = session.thread_id
    if (thread_id):
        session_dict = session.to_dict()
        #loop through the task and see if things need to be converted to serializable
        for key, value in session_dict.items():
            if isinstance(value, datetime.datetime):
                session_dict[key] = value.isoformat()
        send_socket_message('update-session', {'session': session_dict, 'thread_id': thread_id}, thread_id)

    return True, "Session updated successfully"

def delete_session(client_sdr_id: int, session_id: int):
    """
    If session exists and is owned by the client SDR, delete it and all associated tasks and action calls.
    """
    session: SelixSession = SelixSession.query.get(session_id)
    if not session:
        return False, "Session not found."
    if session.client_sdr_id != client_sdr_id:
        return False, "Unauthorized to delete this session."

    # Delete all tasks associated with the session
    tasks: list[SelixSessionTask]= SelixSessionTask.query.filter_by(selix_session_id=session_id).all()
    for task in tasks:
        task.status = SelixSessionTaskStatus.CANCELLED
        db.session.delete(task)

    # Delete all action calls associated with the session
    # action_calls: list[SelixActionCall] = SelixActionCall.query.filter_by(selix_session_id=session_id).all()
    # for action_call in action_calls:
    #     db.session.delete(action_call)

    session.status = SelixSessionStatus.CANCELLED

    db.session.add(session)
    db.session.commit()

    return True, "Session deleted successfully"


def chat_with_assistant(
        client_sdr_id: int, 
        session_id: Optional[int] = None, 
        in_terminal: Optional[bool] = True, 
        room_id: Optional[int] = None,
        additional_context: Optional[str] = None,
        session_name: Optional[str] = None,
        task_titles: Optional[list[str]] = None
):
    print("Starting conversation with the assistant. Type 'quit' to end.")
    assistant_id = "asst_uJJtKPGaVeVYQjgqCquTL3Bq" # Selix AI OpenAI Assistant ID

    thread_id = None
    selix_session = None

    is_draft_session = False
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if client_sdr.role == 'FREE':
        is_draft_session = True

    if session_id:
        selix_session: SelixSession = SelixSession.query.get(session_id)
        thread_id = selix_session.thread_id

        # get the last N messages and print them out
        messages = get_last_n_messages(thread_id)
        print("\n\n#############\n\n")
        for message in messages:
            print(f"{message['role']}: {message['message']}\n")

    if not session_id:
        thread_id = create_thread()
        selix_session: SelixSession = SelixSession(
            client_sdr_id=client_sdr_id,
            session_name=session_name or "New Session",
            status=SelixSessionStatus.ACTIVE,
            memory={},
            estimated_completion_time=None,
            actual_completion_time=None,
            assistant_id=assistant_id,
            thread_id=thread_id,
            draft_session=is_draft_session
        )
        db.session.add(selix_session)
        db.session.commit()
        if thread_id:
            session_dict = selix_session.to_dict()
            session_dict['estimated_completion_time'] = session_dict.get('estimated_completion_time').isoformat() if session_dict.get('estimated_completion_time') else None
            session_dict['actual_completion_time'] = session_dict.get('actual_completion_time').isoformat() if session_dict.get('actual_completion_time') else None
            send_socket_message('new-session', {'session': session_dict, thread_id: room_id}, room_id)

            #create one task for the session
            create_task("Collaborate with the user to gather campaign information", "Chat with Selix on the left to get started.", selix_session.id, create_action=False)

    if task_titles:
        total_success, total_message = bulk_create_selix_tasks(client_sdr_id, selix_session.id, task_titles)
        if not total_success:
            print(total_message)
            return
            
    if not additional_context:
        client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
        client: Client = Client.query.get(client_sdr.client_id)
        client_sdrs: list[ClientSDR] = ClientSDR.query.filter_by(client_id=client.id).all()
        pre_filters: SavedApolloQuery = SavedApolloQuery.query.filter(
            SavedApolloQuery.segment_description.isnot(None),
            SavedApolloQuery.client_sdr_id.in_([client_sdr.id for client_sdr in client_sdrs])
        ).order_by(SavedApolloQuery.id.desc()).first()
        icp_description = ""
        if pre_filters:
            icp_description = pre_filters.segment_description
        additional_context = """
Here is some additional context about me, the person you're speaking with, my company, and other relevant information:
- Name: {name}
- Title: {title}
- Company: {company}
- Company Tagline: {tagline}
- Company Description: {description}
- Ideal Customer Profile Description: {icp_description}

Reference this information as needed during our conversation. Simply respond with one word after this messaying saying "Acknowledged".""".format(
            name=client_sdr.name,
            title=client_sdr.title,
            company=client.company,
            tagline=client.tagline,
            description=client.description,
            icp_description=icp_description
        )

        add_message_to_thread(
            thread_id, 
            additional_context, 
            role="user"
        )
    else:
        additional_context = """
Here is some additional context about me, the person you're speaking with, my company, and other relevant information:
{additional_context}

Reference this information as needed during our conversation. Simply respond with one word after this messaying saying "Acknowledged".""".format(
            additional_context=additional_context
        )
        add_message_to_thread(
            thread_id, 
            additional_context,
            role="user"
        )

    handle_run_thread(thread_id, session_id)
    reply = get_assistant_reply(thread_id)

    selix_session.memory["additional_context"] = additional_context
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(selix_session, "memory")
    db.session.add(selix_session)
    db.session.commit()

    while True and in_terminal:
        user_input = input("\n\n#############\n\n😎 You: ")
        if user_input.lower() == "quit":
            break

        add_message_to_thread(thread_id, user_input)
        handle_run_thread(thread_id, session_id)
        reply = get_assistant_reply(thread_id)

        print("🤖 Assistant:", reply)

def handle_run_thread(thread_id, session_id):
    run_id = run_thread(thread_id, 'asst_uJJtKPGaVeVYQjgqCquTL3Bq')

    # Simple polling mechanism
    while True:
        run_status = requests.get(
            f"{API_URL}/threads/{thread_id}/runs/{run_id}", headers=HEADERS
        ).json()["status"]
        # print(run_status)
        if run_status in ["completed", "failed"]:
            break
        if run_status == "requires_action":
            print("🧩 Requires action")
            retrieve_actions_needed(thread_id, run_id, session_id)
        time.sleep(1)  # Sleep to avoid hitting the API rate limits too hard

def handle_voice_instruction_enrichment_and_questions(
    session_id: int
):
    session: SelixSession = SelixSession.query.get(session_id)
    if not session:
        return False, "Session not found."
    
    client_sdr: ClientSDR = ClientSDR.query.get(session.client_sdr_id)
    client: Client = Client.query.get(client_sdr.client_id)
    client_sdrs: list[ClientSDR] = ClientSDR.query.filter_by(client_id=client.id).all()
    pre_filters: SavedApolloQuery = SavedApolloQuery.query.filter(
        SavedApolloQuery.segment_description.isnot(None),
        SavedApolloQuery.client_sdr_id.in_([client_sdr.id for client_sdr in client_sdrs])
    ).order_by(SavedApolloQuery.id.desc()).first()
    icp_description = ""
    if pre_filters:
        icp_description = pre_filters.segment_description

    past_conversations = get_last_n_messages(session.thread_id)[0:10]

    additional_context = """
Here is some additional context about me, the person you're speaking with, my company, and other relevant information:
- Name: {name}
- Title: {title}
- Company: {company}
- Company Tagline: {tagline}
- Company Description: {description}
- Ideal Customer Profile Description: {icp_description}
- Past Conversations: {past_conversations}

Reference this information as needed""".format(
        name=client_sdr.name,
        title=client_sdr.title,
        company=client.company,
        tagline=client.tagline,
        description=client.description,
        icp_description=icp_description,
        past_conversations=past_conversations
    )

    text = wrapped_chat_gpt_completion(
        messages=[
            {
                "role": "system",
                "content": """
You are the Selix voice assistant question prompter.
I am going to provide you an unsanitized transcript of a voice instruction from the user for a given conversation. Here's some additional context about the user and the conversation:

Context: {additional_context}

Based on the voice instruction, ask the user follow-up questions in the form of 6-7 word brief questions to collect more data. Make sure to reference the additional context provided above in your questions.
Bullet point each question in a list format, use 1,2,3 etc. for each question.

Follow-up Questions:""".format(
                    additional_context=additional_context
                ),
            }
        ],
        model="gpt-4o",
        max_tokens=500
    )

    return text

@celery.task
def generate_followup(client_sdr_id: int, device_id: str, prompt: str, chat_messages: list, room_id: str, previous_follow_up: str):

    # Compile the message transcript
    compiled_message_transcript = [
        f"{message.get('role')}: {message.get('content')}" for message in chat_messages
    ]

    compiled_message_transcript = "\n".join(compiled_message_transcript)
    compiled_message_transcript += '\n' + 'the users partially typed response is: ' + prompt

    # Prepare the system message
    system_message = {
        "role": "system",
        "content": f"""
        You are a Selix AI assistant. Selix has a few functionalities: campaign creation, strategy creation, task creation, and campaign curation.
        Your purpose is to come up with additional question to pose to the user- - you are like a though partner. 

        Here are some example questions--

        Why are you targeting (specific audience)? i.e. "Why are you targeting specialty marketing leaders?"
        Which booth is your company at the event? 
        Do you have an account list?
        Why is (product) the best option?
        Which feature resonates the most with (target audience)?

    
        In general, ask questions that will help you understand the user's needs and preferences better. Keep it short.

        NOTE: Don't ask question about analytics / metrics / budget

        I am going to provide you with a compiled message transcript of the conversation between you and the user. 
        In as little text as possible, generate a VERY brief question from the assistant based on the compiled message transcript. Make sure it 
        is not the same as the previous follow-up question which is: {previous_follow_up} 
        
        Followup Question:"""
    }
    print(system_message)
    # print('messages are', compiled_message_transcript)

    # Get the follow-up message from the assistant
    followup_message = wrapped_chat_gpt_completion(
        messages=[system_message, {"role": "user", "content": compiled_message_transcript}],
        model="gpt-4o",
        max_tokens=50
    )

    send_socket_message('suggestion', {'message': followup_message, 'thread_id': room_id, 'device_id': device_id}, room_id)

    return followup_message

def add_file_to_thread(thread_id: str, file: str, file_name: str, description: str):
    # Create a Selix action call entry
    selix_session_id = SelixSession.query.filter_by(thread_id=thread_id).first().id
    
    create_selix_action_call_entry(
        selix_session_id=selix_session_id,
        action_title="Analyzing File",
        action_description="Analyze file with name: {} and description: '{}'".format(file_name, description),
        action_function="analyze_file",
        action_params={"file": file, "description": description, "file_name": file_name, 'title': 'Analyze File'}
    )        
    analyze_file(file, description, file_name, selix_session_id)

    #send socket message to add the file to the thread
    thread_id = SelixSession.query.get(selix_session_id).thread_id
    if thread_id:
        send_socket_message('incoming-message', {'message': f"Thanks for the file! I'm taking a look now.", 'thread_id': thread_id}, thread_id)

    # Log the action
    print(f"File added to thread {thread_id} with description: {description}")

def analyze_file(file:str, description:str, file_name: str, session_id: int ):
    #create a task for the user to review the analysis

    order_number = SelixSessionTask.query.filter_by(selix_session_id=session_id).count() + 1
    selix_task = SelixSessionTask(
        selix_session_id=session_id,
        actual_completion_time=None,
        title="Analyze File",
        description="Analyze file: {} with description: {}".format(file_name, description),
        status=SelixSessionTaskStatus.QUEUED,
        order_number=order_number
    )

    db.session.add(selix_task)
    db.session.commit()

    thread_id = SelixSession.query.get(session_id).thread_id
    if thread_id:
        task_dict = selix_task.to_dict()
        for key, value in task_dict.items():
            if isinstance(value, datetime.datetime):
                task_dict[key] = value.isoformat()
        send_socket_message('add-task-to-session', {'task': task_dict, 'thread_id': thread_id}, thread_id)

    return {"success": True}

@celery.task
def get_suggested_first_message(client_sdr_id: int, room_id: str):
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client: Client = Client.query.get(client_sdr.client_id)

    latest_segment_description: SavedApolloQuery = SavedApolloQuery.query.filter(
        SavedApolloQuery.segment_description.isnot(None),
        SavedApolloQuery.client_sdr_id == client_sdr_id
    ).order_by(SavedApolloQuery.id.desc()).first()
    
    prompt = f"""
You are a campaign angle suggestor for a chatbot that helps clients create sales campaigns. Based on the following client information, 
suggest three different short campaign angles (1 sentence each) for the campaign that are creative and are ultra specific. 

Company: {client.company} Tagline: {client.tagline} Description: {client.description} Segment Description: {latest_segment_description}

All angles should stem on things that we can reasonably search from the internet. 
Make it specific to the comapny and the persona. 

Examples of angles you can take
1. Company-level angles
    -job postings
    -published articles
2. Person-level angles
    -Have XYZ written on their linkedin profiles
    -recent news about XYZ

 BE CREATIVE. No messages should exceed 70 characters.

Example Good Angle 1: 'Write a campaign targeting series a founders who recently posted for an SDR.' 
Example Good Angle 2: 'Write a campaign targeting recently hired founding sales individuals'' 

"""
    
    print('hello test')

    
    response_schema = {
        "name": "response_schema",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "message_1": {"type": "string"},
                "message_2": {"type": "string"},
                "message_3": {"type": "string"},
            },
            "required": ["message_1", "message_2", "message_3"],
            "additionalProperties": False
        }
    }

    response = wrapped_chat_gpt_completion(
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ],
        model="gpt-4o-2024-08-06",
        max_tokens=300,
        response_format={"type": "json_schema", "json_schema": response_schema}
    )

    response = json.loads(response)
    response = [response.get(f"message_{i+1}").replace('"', '').replace("'", '') for i in range(3)]

    if room_id:
        send_socket_message('first-message-suggestion', {'messages': response, 'room_id': room_id}, room_id)
    
    return response

@celery.task
def generate_corrected_transcript(client_sdr_id: int, device_id: str, sentence_to_correct: str, thread_id: int):

    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)

    client: Client = client_sdr.client
    client_company: str = client.company

    client_description: str = client.description
    client_sdr_name: str = client_sdr.name
    client_sdr_title: str = client_sdr.title

    all_sdrs_in_company: list[ClientSDR] = ClientSDR.query.filter_by(client_id=client.id).all()
    #make a string comma separated list of all the sdrs in the company
    all_sdrs_in_company = ', '.join([sdr.name for sdr in all_sdrs_in_company])
    
    system_prompt = """

    Here is some client information for context:
    - Company: {client_company}
    - SDR Name: {client_sdr_name}
    - Other SDRs in the company: {all_sdrs_in_company}

    You are a helpful assistant for the company SellScale and their chatbot Selix.
    Your task is to correct any spelling discrepancies in the transcribed text.
    Make sure that the names of the following products are spelled correctly:

    Only add necessary punctuation such as periods, commas, and capitalization,
    and use only the context provided. Do not remove or add any words, just correct the parts.

    """.format(
        client_company=client_company,
        client_sdr_name=client_sdr_name,
        all_sdrs_in_company=all_sdrs_in_company
    )

    response_schema = {
        "name": "corrected_sentence",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "corrected_sentence": {"type": "string"},
            },
            "required": ["corrected_sentence"],
            "additionalProperties": False
        }
    }

    response = wrapped_chat_gpt_completion(
        messages=[
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": sentence_to_correct
            }
        ],
        model="gpt-4o-2024-08-06",
        max_tokens=300,
        response_format={"type": "json_schema", "json_schema": response_schema}
    )

    response = json.loads(response)
    response = response.get("corrected_sentence")

    if device_id:
        send_socket_message('corrected-transcript', {'message': response, 'original_sentnece': sentence_to_correct, 'device_id': device_id}, thread_id)

    return response