import datetime
import json
from typing import Optional
import requests
import os
import time
from app import db

from model_import import SelixSession, SelixSessionTask, SelixSessionStatus, SelixSessionTaskStatus

from src.contacts.services import get_contacts_from_predicted_query_filters

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


def create_review_card(campaign_id: dict):
    print("⚡️ AUTO ACTION: create_review_card({})".format(campaign_id))
    return {"success": True}

def create_strategy(description: str):
    print("⚡️ AUTO ACTION: create_strategy('{}')".format(description))
    return {"success": True}

def create_task(title: str, description: str):
    print("⚡️ AUTO ACTION: create_task('{}', '{}')".format(title, description))
    return {"success": True}


ACTION_MAP = {
    "create_campaign": create_campaign,
    "find_prospects": find_prospects,
    "generate_sequence": generate_sequence,
    "create_review_card": create_review_card,
    "create_strategy": create_strategy,
    "create_task": create_task
}


def run_action(action_name, params):
    return ACTION_MAP[action_name](**params)


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

    return all_messages


def retrieve_actions_needed(thread_id, run_id):
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
        output = run_action(function_name, func_args)

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


def chat_with_assistant(client_sdr_id: int, session_id: Optional[int] = None):
    print("Starting conversation with the assistant. Type 'quit' to end.")
    assistant_id = "asst_uJJtKPGaVeVYQjgqCquTL3Bq" # Selix AI OpenAI Assistant ID

    thread_id = None

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
            session_name="",
            status=SelixSessionStatus.ACTIVE,
            memory={},
            estimated_completion_time=datetime.datetime.now() + datetime.timedelta(hours=24),
            actual_completion_time=None,
            assistant_id=assistant_id,
            thread_id=thread_id
        )
        db.session.add(selix_session)
        db.session.commit()

    while True:
        user_input = input("\n\n#############\n\n😎 You: ")
        if user_input.lower() == "quit":
            break

        add_message_to_thread(thread_id, user_input)
        run_id = run_thread(thread_id, assistant_id)

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
                retrieve_actions_needed(thread_id, run_id)
            time.sleep(1)  # Sleep to avoid hitting the API rate limits too hard

        print("🤖 Assistant:", get_assistant_reply(thread_id))


# Example usage
# chat_with_assistant("asst_uJJtKPGaVeVYQjgqCquTL3Bq")
# create_strategy OR select_existing_strategy
# 2. create_tasks

# DECK:
# https://docs.google.com/presentation/d/1AVmn12UGnUQMhwPuFzI7b9stos50cqJRfYFTbG5NfpA/edit#slide=id.g279d89168bd_0_108