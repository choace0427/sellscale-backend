import datetime
from http import client
import json
from tracemalloc import start
from typing import Optional
from numpy import add
import requests
import os
import time
from app import db

from model_import import SelixSession, SelixSessionTask, SelixSessionStatus, SelixSessionTaskStatus, SelixActionCall
from src.client.models import ClientSDR, Client
from src.contacts.models import SavedApolloQuery

from src.contacts.services import get_contacts_from_predicted_query_filters
from src.ml.openai_wrappers import wrapped_chat_gpt_completion
from src.ml.services import generate_strategy_copilot_response, simple_perplexity_response
from src.strategies.models import Strategies, StrategyStatuses
from src.utils.slack import URL_MAP, send_slack_message

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
    selix_session = SelixSession.query.get(session_id)
    selix_session.memory["counter"] = selix_session.memory.get("counter", 0) + 1
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(selix_session, "memory")
    db.session.add(selix_session)
    db.session.commit()

def set_session_tab(
    selix_session_id: int,
    tab_name: str,
):
    selix_session = SelixSession.query.get(selix_session_id)
    selix_session.memory["tab"] = tab_name
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(selix_session, "memory")
    db.session.add(selix_session)
    db.session.commit()

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
    return selix_action_call.id

def mark_action_complete(selix_action_call_id: int):
    selix_action_call = SelixActionCall.query.get(selix_action_call_id)
    selix_action_call.status = SelixSessionTaskStatus.COMPLETE
    db.session.add(selix_action_call)
    db.session.commit()

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

def edit_strategy(
    edit_description: str,
    session_id: int
):
    print("⚡️ AUTO ACTION: edit_strategy('{}')".format(edit_description))
    
    selix_action_id = create_selix_action_call_entry(
        selix_session_id=session_id,
        action_title="Edit Strategy",
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
                    title, edit_description
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
                    description, edit_description
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

    mark_action_complete(selix_action_id)
    set_session_tab(session_id, "STRATEGY_CREATOR")
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

    response, citations, images = simple_perplexity_response(
        model="llama-3-sonar-large-32k-online",
        prompt=query + "\nReturn your response in maximum 1-2 paragraphs."
    )

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

    mark_action_complete(selix_action_id)
    set_session_tab(session_id, "BROWSER")
    return {"response": response}

def create_review_card(campaign_id: dict):
    print("⚡️ AUTO ACTION: create_review_card({})".format(campaign_id))
    return {"success": True}

def create_strategy(description: str, session_id: int):
    print("⚡️ AUTO ACTION: create_strategy('{}')".format(description))

    selix_action_id = create_selix_action_call_entry(
        selix_session_id=session_id,
        action_title="Create Strategy",
        action_description="Create a strategy based on the description provided: {}".format(description),
        action_function="create_strategy",
        action_params={"description": description}
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
        model="gpt-4",
    )

    chat_content = [
        {"sender": "user", "query": description, "id": 1}
    ]
    strategy_response = generate_strategy_copilot_response(chat_content)
    strategy_title = strategy_response.get("response", "").strip()

    session: SelixSession = SelixSession.query.get(session_id)
    client_sdr: ClientSDR = ClientSDR.query.get(session.client_sdr_id)

    strategy: Strategies = Strategies(
        title=title,
        description=strategy_title,
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

    selix_task = SelixSessionTask(
        selix_session_id=session_id,
        actual_completion_time=datetime.datetime.now(),
        title="Create Strategy",
        description="Create a strategy based on the description provided: {}".format(description),
        status=SelixSessionTaskStatus.COMPLETE
    )
    db.session.add(selix_task)
    db.session.commit()

    session_tasks = SelixSessionTask.query.filter_by(selix_session_id=session_id, status=SelixSessionTaskStatus.QUEUED).all()
    for task in session_tasks:
        task.status = SelixSessionTaskStatus.COMPLETE
        task.actual_completion_time = datetime.datetime.now()
        db.session.add(task)
    db.session.commit()

    mark_action_complete(selix_action_id)
    set_session_tab(session_id, "STRATEGY_CREATOR")
    return {"success": True}

def create_task(title: str, description: str, session_id: int):
    print("⚡️ AUTO ACTION: create_task('{}', '{}')".format(title, description))
    
    selix_action_id = create_selix_action_call_entry(
        selix_session_id=session_id,
        action_title="Create Task",
        action_description="Create a task with the title: {} and description: {}".format(title, description),
        action_function="create_task",
        action_params={"title": title, "description": description}
    )

    task = SelixSessionTask(
        selix_session_id=session_id,
        actual_completion_time=None,
        title=title,
        description=description,
        status=SelixSessionTaskStatus.QUEUED
    )
    db.session.add(task)
    db.session.commit()

    mark_action_complete(selix_action_id)
    set_session_tab(session_id, "PLANNER")
    return {"success": True}

def wait_for_ai_execution(session_id: int):
    print("⚡️ AUTO ACTION: wait_for_ai_execution()")
    

    selix_action_id = create_selix_action_call_entry(
        selix_session_id=session_id,
        action_title="Wait for AI Execution",
        action_description="Wait for AI Execution to complete.",
        action_function="wait_for_ai_execution",
        action_params={}
    )

    session: SelixSession = SelixSession.query.get(session_id)
    session.estimated_completion_time = datetime.datetime.now() + datetime.timedelta(hours=24)
    session.status = SelixSessionStatus.PENDING_OPERATOR
    
    send_slack_message(
        message="Selix Session is waiting for operator: {}".format(session.id),
        webhook_urls=[URL_MAP['eng-sandbox']]
    )
    
    mark_action_complete(selix_action_id)
    set_session_tab(session_id, "PLANNER")
    return {"success": True}


ACTION_MAP = {
    "create_campaign": create_campaign,
    "find_prospects": find_prospects,
    "generate_sequence": generate_sequence,
    "create_review_card": create_review_card,
    "create_strategy": create_strategy,
    "create_task": create_task,
    "wait_for_ai_execution": wait_for_ai_execution,
    "search_internet": search_internet,
    "edit_strategy": edit_strategy
}


def run_action(action_name, params, session_id):
    return ACTION_MAP[action_name](**params, session_id=session_id)


# ACTIONS - END


def create_thread():
    response = requests.post(f"{API_URL}/threads", headers=HEADERS, json={})
    print("✨ Created thread: ", response.json()["id"], "\n")
    return response.json()["id"]


def add_message_to_thread(thread_id, content, role="user"):
    data = {"role": role, "content": content}
    requests.post(f"{API_URL}/threads/{thread_id}/messages", headers=HEADERS, json=data)


def run_thread(thread_id, assistant_id):
    data = {
        "assistant_id": assistant_id,
    }
    response = requests.post(
        f"{API_URL}/threads/{thread_id}/runs", headers=HEADERS, json=data
    )

    session_id = SelixSession.query.filter_by(thread_id=thread_id).first().id
    increment_session_counter(session_id)

    return response.json()["id"]


def get_assistant_reply(thread_id):
    try:
        response = requests.get(
            f"{API_URL}/threads/{thread_id}/messages", headers=HEADERS
        )
        last_message = response.json()["data"][0]["content"][0]["text"]["value"]
        return last_message
    except:
        return ""
    
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

    # Exclude the very last two message in the list
    if all_messages and len(all_messages) > 1:
        all_messages = all_messages[0:len(all_messages) - 2]

    selix_session_id = SelixSession.query.filter_by(thread_id=thread_id).first().id
    action_calls = get_action_calls(selix_session_id)
    
    all_messages.extend(action_calls)

    all_messages.sort(key=lambda x: x["created_time"])

    if len(all_messages) > 6:
        selix_session: SelixSession = SelixSession.query.filter_by(thread_id=thread_id).first()
        transcript_str = "\n".join([f"{message['role']}: {message['message']}" for message in all_messages if message["type"] == "message"])
        if selix_session.session_name == "New Session":
            rename_session(selix_session.id, transcript_str)

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


def chat_with_assistant(
        client_sdr_id: int, 
        session_id: Optional[int] = None, 
        in_terminal: Optional[bool] = True, 
        room_id: Optional[int] = None,
        additional_context: Optional[str] = None
):
    print("Starting conversation with the assistant. Type 'quit' to end.")
    assistant_id = "asst_uJJtKPGaVeVYQjgqCquTL3Bq" # Selix AI OpenAI Assistant ID

    thread_id = None
    selix_session = None

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
            session_name="New Session",
            status=SelixSessionStatus.ACTIVE,
            memory={},
            estimated_completion_time=datetime.datetime.now() + datetime.timedelta(hours=24),
            actual_completion_time=None,
            assistant_id=assistant_id,
            thread_id=thread_id
        )
        db.session.add(selix_session)
        db.session.commit()
    
    if not additional_context:
        client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
        client: Client = Client.query.get(client_sdr.client_id)
        pre_filters: SavedApolloQuery = SavedApolloQuery.query.filter(
            SavedApolloQuery.segment_description.isnot(None)
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

# Example usage
# chat_with_assistant("asst_uJJtKPGaVeVYQjgqCquTL3Bq")
# create_strategy OR select_existing_strategy
# 2. create_tasks

# DECK:
# https://docs.google.com/presentation/d/1AVmn12UGnUQMhwPuFzI7b9stos50cqJRfYFTbG5NfpA/edit#slide=id.g279d89168bd_0_108