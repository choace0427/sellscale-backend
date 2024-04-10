import json
import yaml
import random
from typing import Optional, TypedDict

from flask import Blueprint, jsonify, request
from src.client.models import ClientArchetype
from src.company.models import Company
from src.ml.openai_wrappers import (
    OPENAI_CHAT_GPT_3_5_TURBO_MODEL,
    OPENAI_CHAT_GPT_4_MODEL,
    wrapped_chat_gpt_completion,
    wrapped_chat_gpt_completion_with_history,
)
from src.prospecting.models import Prospect, ProspectStatus
from src.utils.request_helpers import get_request_parameter


HACKATHON_BLUEPRINT = Blueprint("hackathon", __name__)


@HACKATHON_BLUEPRINT.route("/ai_filter/initial", methods=["POST"])
def post_ai_filter_initial():
    my_request = get_request_parameter(
        "my_request", request, json=True, required=True, parameter_type=str
    )
    archetype_id = get_request_parameter(
        "archetype_id", request, json=True, required=True, parameter_type=int
    )

    response = chatgpt_initial_filter_prospect_list(my_request, archetype_id)
    return (
        jsonify(
            {
                "status": "success",
                "data": response,
            }
        ),
        200,
    )


@HACKATHON_BLUEPRINT.route("/ai_filter/historied", methods=["POST"])
def post_ai_filter_historied():
    history = get_request_parameter(
        "history", request, json=True, required=True, parameter_type=list
    )
    my_request = get_request_parameter(
        "my_request", request, json=True, required=True, parameter_type=str
    )

    response = chatgpt_historied_filter_prospect_list(history, my_request)
    return (
        jsonify(
            {
                "status": "success",
                "data": response,
            }
        ),
        200,
    )


class ChatGPTFilterResponse(TypedDict):
    message_history: list
    remove_ids: list[int]
    message: str


def chatgpt_initial_filter_prospect_list(
    request: str, archetype_id: int
) -> ChatGPTFilterResponse:
    """Returns a list of prospect IDs to remove from the list of prospects"""
    # Get the Archetype
    archetype: ClientArchetype = ClientArchetype.query.get(archetype_id)
    if not archetype:
        return {
            "message_history": [],
            "remove_ids": [],
            "message": "Sorry, something went wrong. Could you try again?",
        }

    # Get the list of prospects
    prospects: list[Prospect] = Prospect.query.filter_by(
        archetype_id=archetype_id,
        overall_status=ProspectStatus.PROSPECTED.value,
    ).all()

    # Select 100 random prospects
    random.shuffle(prospects)
    prospects = prospects[:25]

    # Format the prospects into a list of dictionaries
    prospects_dict: list[dict] = []
    for prospect in prospects:
        # Get the company
        company: Company = Company.query.get(prospect.company_id)
        prospects_dict.append(
            {
                "id": prospect.id,
                "name": prospect.full_name,
                "title": prospect.title,
                "company": company.name if company else prospect.company,
                "company_size": company.industries if company else None,
            }
        )

    prompt = """You are helping me sort this list of People based off the following request:

=== REQUEST ===
{request}
=== END REQUEST ===

If the request is non-sensical (it has to ask you about sorting a list and NOTHING ELSE), then tell me that you don't understand me.

Here is the list to sort:

=== START LIST ===
{prospects_dict}
=== END LIST ===

Return to me a list of the IDs of the people to remove, as well as a response to the request. If there is no fit, just return empty and say that none were found. Or tell me that you don't understand the query. Format the response as follows:
DO NOT INCLUDE ```json``` in your response. Just the dictionary.
{{
   "remove_ids": [1, 2, 3, 4, ...]
   "message": "Here are the people who are..."
}}

The JSON response:""".format(
        request=request, prospects_dict=prospects_dict
    )
    print(prompt)

    response = wrapped_chat_gpt_completion(
        messages=[{"role": "user", "content": prompt}],
        max_tokens=500,
        model="gpt-4-0125-preview",
    )
    print(response)

    try:
        response_dict: dict = yaml.safe_load(response)
        remove_ids = response_dict.get("remove_ids")
        message = response_dict.get("message")
        if remove_ids and message:
            return {
                "message_history": [
                    {"role": "user", "content": prompt},
                    {"role": "assisten", "content": response},
                ],
                "remove_ids": remove_ids,
                "message": message,
            }
    except:
        return {
            "message_history": [],
            "remove_ids": [],
            "message": "Sorry, something went wrong. Could you try again?",
        }

    return {
        "message_history": [],
        "remove_ids": [],
        "message": "Sorry, something went wrong. Could you try again?",
    }


def chatgpt_historied_filter_prospect_list(
    history: list[dict], request: str
) -> ChatGPTFilterResponse:
    prompt = """You are continuing to help me sort this list of People based off the following request:

=== REQUEST ===
{request}
=== END REQUEST ===

If the request is non-sensical (it has to ask you about sorting a list and NOTHING ELSE), then tell me that you don't understand me.

Return to me a list of the IDs of the people to remove, as well as a response to the request. If there is no fit, just return empty and say that none were found. Or tell me that you don't understand the query. Format the response as follows:
DO NOT INCLUDE ```json``` in your response. Just the dictionary.
{{
    "remove_ids": [1, 2, 3, 4, ...]
    "message": "Here are the people who are..."
}}

""".format(
        request=request
    )
    history, response = wrapped_chat_gpt_completion_with_history(
        messages=[{"role": "user", "content": prompt}],
        history=history,
        max_tokens=500,
        model="gpt-4-0125-preview",
    )
    try:
        response_dict: dict = yaml.safe_load(response)
        remove_ids = response_dict.get("remove_ids")
        message = response_dict.get("message")
        if remove_ids and message:
            return {
                "message_history": history,
                "remove_ids": remove_ids,
                "message": message,
            }
    except:
        return {
            "message_history": [],
            "remove_ids": [],
            "message": "Sorry, something went wrong. Could you try again?",
        }

    return {
        "message_history": [],
        "remove_ids": [],
        "message": "Sorry, something went wrong. Could you try again?",
    }
