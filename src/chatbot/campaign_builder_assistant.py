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

from model_import import SelixSession, SelixSessionTask, SelixSessionStatus, SelixSessionTaskStatus
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


def generate_sequence(channel: str, steps: list):
    print("⚡️ AUTO ACTION: generate_sequence('{}', {})".format(channel, steps))
    return {"channel": channel, "num_steps": 1, "steps": steps}

def search_internet(query: str, session_id: int):
    print("⚡️ AUTO ACTION: search_internet('{}')".format(query))

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

    return {"response": response}

def create_review_card(campaign_id: dict):
    print("⚡️ AUTO ACTION: create_review_card({})".format(campaign_id))
    return {"success": True}

def create_strategy(description: str, session_id: int):
    print("⚡️ AUTO ACTION: create_strategy('{}')".format(description))

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

    return {"success": True}

def create_task(title: str, description: str, session_id: int):
    print("⚡️ AUTO ACTION: create_task('{}', '{}')".format(title, description))

    task = SelixSessionTask(
        selix_session_id=session_id,
        actual_completion_time=None,
        title=title,
        description=description,
        status=SelixSessionTaskStatus.QUEUED
    )
    db.session.add(task)
    db.session.commit()

    return {"success": True}

def wait_for_ai_execution(session_id: int):
    print("⚡️ AUTO ACTION: wait_for_ai_execution()")

    session: SelixSession = SelixSession.query.get(session_id)
    session.estimated_completion_time = datetime.datetime.now() + datetime.timedelta(hours=24)
    session.status = SelixSessionStatus.PENDING_OPERATOR
    
    send_slack_message(
        message="Selix Session is waiting for operator: {}".format(session.id),
        webhook_urls=[URL_MAP['eng-sandbox']]
    )

    return {"success": True}


ACTION_MAP = {
    "create_campaign": create_campaign,
    "find_prospects": find_prospects,
    "generate_sequence": generate_sequence,
    "create_review_card": create_review_card,
    "create_strategy": create_strategy,
    "create_task": create_task,
    "wait_for_ai_execution": wait_for_ai_execution,
    "search_internet": search_internet
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
                "role": message["role"],
                "message": message["content"][0]["text"]["value"],
                "created_time": message["created_at"]
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

    return all_messages


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