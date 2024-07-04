from numpy import require
from src.client.models import ClientSDR, Client
from src.message_generation.email.services import generate_magic_subject_line
from src.ml.ai_researcher_services import (
    connect_researcher_to_client_archetype,
    create_ai_researcher,
    create_ai_researcher_question,
    generate_ai_researcher_questions,
    delete_question,
    edit_question,
    get_ai_researcher_answers_for_prospect,
    get_ai_researcher_questions_for_researcher,
    get_ai_researchers_for_client,
    simulate_voice_message,
    run_all_ai_researcher_questions_for_prospect,
    get_generated_email,
)
from src.ml.campaign_curator import curate_campaigns
from src.ml.services import one_shot_linkedin_sequence_generation, find_contacts_from_serp
from src.ml.openai_wrappers import (
    NEWEST_CHAT_GP_MODEL,
    wrapped_chat_gpt_completion,
    wrapped_create_completion,
)
from src.ml.ai_researcher_services import run_ai_researcher_question #for celery task registration
from src.li_conversation.services import detect_demo_set #for celery task registration
from src.ml.spam_detection import run_algorithmic_spam_detection
from src.prospecting.models import Prospect
from src.authentication.decorators import require_user
from app import db

from flask import Blueprint, jsonify, request
from model_import import ClientArchetype
from src.ml.services import (
    answer_question_about_prospect,
    get_perplexity_research,
    get_aree_fix_basic,
    get_sequence_value_props,
    get_icp_classification_prompt_by_archetype_id,
    patch_icp_classification_prompt,
    trigger_icp_classification,
    edit_text,
    trigger_icp_classification_single_prospect,
    get_template_suggestions,
    add_few_shot,
    get_nice_answer,
    get_few_shots,
    update_few_shot,
    get_all_ai_voices,
    create_ai_voice,
    assign_ai_voice
)
from src.ml.fine_tuned_models import get_config_completion

from src.message_generation.models import GeneratedMessage
from src.research.account_research import generate_prospect_research
from src.research.linkedin.services import get_research_and_bullet_points_new
from src.sockets.services import send_socket_message
from src.utils.request_helpers import get_request_parameter

ML_BLUEPRINT = Blueprint("ml", __name__)


@ML_BLUEPRINT.route("/create_profane_word", methods=["POST"])
def post_create_profane_word():
    from src.ml.services import create_profane_word

    words = get_request_parameter("words", request, json=False, required=True)
    profane_words = create_profane_word(words=words)
    return jsonify({"profane_word_id": profane_words.id})


@ML_BLUEPRINT.route("/get_config_completion", methods=["GET"])
def get_config_completion_endpoint():
    from model_import import StackRankedMessageGenerationConfiguration

    config_id = get_request_parameter("config_id", request, json=False, required=True)
    prospect_prompt = get_request_parameter(
        "prospect_prompt", request, json=False, required=True
    )

    configuration: StackRankedMessageGenerationConfiguration = (
        StackRankedMessageGenerationConfiguration.query.get(config_id)
    )
    if configuration is None:
        return jsonify({"error": "Configuration not found"}), 400

    prompt = configuration.computed_prompt.format(prompt=prospect_prompt)

    response, few_shot_prompt = get_config_completion(configuration, prompt)

    return jsonify({"response": response, "few_shot_prompt": few_shot_prompt})


@ML_BLUEPRINT.route("/get_aree_fix/<message_id>", methods=["GET"])
def get_aree_fix_endpoint(message_id):
    # THIS NEEDS TO BE AUTHENTICATED EVENTUALLY
    completion = get_aree_fix_basic(int(message_id))
    return jsonify({"completion": completion})


@ML_BLUEPRINT.route("/generate_sequence_value_props", methods=["POST"])
def get_sequence_value_props_endpoint():
    company = get_request_parameter(
        "company", request, json=True, required=True, parameter_type=str
    )
    selling_to = get_request_parameter(
        "selling_to", request, json=True, required=True, parameter_type=str
    )
    selling_what = get_request_parameter(
        "selling_what", request, json=True, required=True, parameter_type=str
    )
    num = get_request_parameter(
        "num", request, json=True, required=True, parameter_type=int
    )

    result = get_sequence_value_props(company, selling_to, selling_what, num)

    return jsonify({"message": "Success", "data": result}), 200


@ML_BLUEPRINT.route(
    "/icp_classification/icp_prompt/<int:archetype_id>", methods=["GET"]
)
@require_user
def get_icp_classification_prompt_by_archetype_id_endpoint(
    client_sdr_id: int, archetype_id: int
):
    """Gets the ICP classification prompt for a given archetype"""
    archetype: ClientArchetype = ClientArchetype.query.get(archetype_id)
    if archetype is None:
        return jsonify({"message": "Archetype not found"}), 404
    elif archetype.client_sdr_id != client_sdr_id:
        return jsonify({"message": "Archetype does not belong to this user"}), 401

    prompt, filters = get_icp_classification_prompt_by_archetype_id(archetype_id)

    return (
        jsonify({"message": "Success", "data": {"prompt": prompt, "filters": filters}}),
        200,
    )


@ML_BLUEPRINT.route(
    "/icp_classification/icp_prompt/<int:archetype_id>", methods=["PATCH"]
)
@require_user
def patch_icp_classification_prompt_by_archetype_id_endpoint(
    client_sdr_id: int, archetype_id: int
):
    """Updates the ICP classification prompt for a given archetype"""
    prompt = get_request_parameter(
        "prompt", request, json=True, required=True, parameter_type=str
    )
    option_filters = get_request_parameter(
        "option_filters", request, json=True, required=False
    )
    send_slack_message = (
        get_request_parameter(
            "send_slack_message",
            request,
            json=True,
            required=False,
            parameter_type=bool,
        )
        or False
    )

    if prompt == "":
        return jsonify({"message": "Prompt cannot be empty"}), 400

    archetype: ClientArchetype = ClientArchetype.query.get(archetype_id)
    if archetype is None:
        return jsonify({"message": "Archetype not found"}), 404
    elif archetype.client_sdr_id != client_sdr_id:
        return jsonify({"message": "Archetype does not belong to this user"}), 401

    result, prompt = patch_icp_classification_prompt(
        archetype_id,
        prompt,
        send_slack_message,
        option_filters,
    )
    if not result:
        return jsonify({"message": "Error updating prompt"}), 400

    return jsonify({"message": "Success", "new_prompt": prompt}), 200


@ML_BLUEPRINT.route("/icp_classification/trigger/<int:archetype_id>", methods=["POST"])
@require_user
def trigger_icp_classification_endpoint(client_sdr_id: int, archetype_id: int):
    """Runs ICP classification for prospects in a given archetype"""
    prospect_ids = get_request_parameter(
        "prospect_ids", request, json=True, required=True, parameter_type=list
    )

    archetype: ClientArchetype = ClientArchetype.query.get(archetype_id)
    if archetype is None:
        return jsonify({"message": "Archetype not found"}), 404
    elif archetype.client_sdr_id != client_sdr_id:
        return jsonify({"message": "Archetype does not belong to this user"}), 401

    result = trigger_icp_classification(client_sdr_id, archetype_id, prospect_ids)

    return (
        jsonify(
            {
                "message": "Successfully triggered ICP classification. This may take a few minutes."
            }
        ),
        200,
    )


@ML_BLUEPRINT.route(
    "/icp_classification/<int:archetype_id>/prospect/<int:prospect_id>", methods=["GET"]
)
@require_user
def trigger_icp_classification_single_prospect_endpoint(
    client_sdr_id: int, archetype_id: int, prospect_id: int
):
    """Runs ICP classification on a single prospect in a given archetype"""

    prospect: Prospect = Prospect.query.get(prospect_id)
    if prospect is None:
        return jsonify({"message": "Prospect not found"}), 404
    elif prospect.client_sdr_id != client_sdr_id:
        return jsonify({"message": "Prospect does not belong to this archetype"}), 401

    fit, reason = trigger_icp_classification_single_prospect(
        client_sdr_id, archetype_id, prospect_id
    )

    return (
        jsonify({"fit": fit, "reason": reason}),
        200,
    )


@ML_BLUEPRINT.route("/edit_text", methods=["POST"])
@require_user
def post_edit_text(client_sdr_id: int):
    """
    Enable user to edit text given an initial text and an instruction prompt.
    """
    initial_text = get_request_parameter(
        "initial_text", request, json=True, required=True, parameter_type=str
    )
    edit_prompt = get_request_parameter(
        "prompt", request, json=True, required=True, parameter_type=str
    )

    result = edit_text(initial_text=initial_text, edit_prompt=edit_prompt)

    return jsonify({"message": "Success", "data": result}), 200


@ML_BLUEPRINT.route("/fill_prompt_from_brain", methods=["POST"])
@require_user
def fill_prompt_from_brain(client_sdr_id: int):
    """
    Enable user to fill a prompt from brain
    """
    prompt = get_request_parameter(
        "prompt", request, json=True, required=True, parameter_type=str
    )
    archetype_id = get_request_parameter(
        "archetype_id", request, json=True, required=True, parameter_type=int
    )

    client_archetype: ClientArchetype = ClientArchetype.query.get(archetype_id)
    if client_archetype is None or client_archetype.client_sdr_id != client_sdr_id:
        return jsonify({"message": "Archetype not found"}), 404

    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client: Client = Client.query.get(client_sdr.client_id)

    company_name = client.company
    company_description = client.description
    company_value_props = client.value_prop_key_points
    persona = client_archetype.archetype
    persona_buy_reason = client_archetype.persona_fit_reason

    result = wrapped_create_completion(
        model=NEWEST_CHAT_GP_MODEL,
        prompt="""You are a sales researcher for {company_name}. Your company does the following:
{company_description}.
Your company's value props are:
{company_value_props}

This is the persona you're reaching out to:
{persona}
The reason this persona would buy your product is:
{persona_buy_reason}

Use this information to complete the following prompt in a way that would be compelling to the persona. Keep the answer concise and to the point.:
{prompt}""".format(
            company_name=company_name,
            company_description=company_description,
            persona=persona,
            persona_buy_reason=persona_buy_reason,
            prompt=prompt,
            company_value_props=company_value_props,
        ),
        max_tokens=100,
    )

    return jsonify({"message": "Success", "data": prompt + result}), 200


@ML_BLUEPRINT.route("/email/body-spam-score", methods=["POST"])
@require_user
def post_email_body_spam_score(client_sdr_id: int):
    """
    Enable user to get spam score of email body
    """
    email_body = get_request_parameter(
        "email_body", request, json=True, required=True, parameter_type=str
    )

    score = run_algorithmic_spam_detection(email_body)

    return jsonify({"score": score}), 200


@ML_BLUEPRINT.route("/campaigns/campaign_curator", methods=["POST"])
@require_user
def post_campaign_curator(client_sdr_id: int):
    """
    Enable user to get a curated list of campaigns based on news, past campaigns, and more information
    """
    additional_instructions = get_request_parameter(
        "additional_instructions",
        request,
        json=True,
        required=False,
        parameter_type=str,
    )
    data = curate_campaigns(client_sdr_id, additional_instructions)
    return jsonify(data), 200


@ML_BLUEPRINT.route("/deep_internet_research", methods=["POST"])
@require_user
def post_deep_internet_research(client_sdr_id: int):
    """
    Enable user to get deep internet research on a prospect
    """
    prospect_id = get_request_parameter(
        "prospect_id", request, json=True, required=True, parameter_type=int
    )

    research = get_perplexity_research(
        prospect_id=prospect_id, client_sdr_id=client_sdr_id
    )

    return jsonify(research), 200


@ML_BLUEPRINT.route("/answer_perplexity_questions", methods=["POST"])
@require_user
def post_answer_perplexity_question(client_sdr_id: int):
    """
    Enable user to answer a list of up to 3 perplexity questions
    """
    question = get_request_parameter(
        "question", request, json=True, required=True, parameter_type=str
    )
    prospect_id = get_request_parameter(
        "prospect_id", request, json=True, required=True, parameter_type=int
    )
    how_its_relevant = get_request_parameter(
        "how_its_relevant", request, json=True, required=True, parameter_type=str
    )
    room_id = get_request_parameter(
        "room_id", request, json=True, required=False, parameter_type=str
    )

    success, answer, reasoning = answer_question_about_prospect(
        client_sdr_id=client_sdr_id,
        prospect_id=prospect_id,
        question=question,
        how_its_relevant=how_its_relevant,
        room_id=room_id,
        questionType='GENERAL'
    )

    if not success:
        return "Error answering question", 400

    return jsonify({"answer": answer, "reasoning": reasoning}), 200


# AI RESEARCHERS
@ML_BLUEPRINT.route("/researchers", methods=["GET"])
@require_user
def get_ai_researchers(client_sdr_id: int):
    """
    Get all AI Researchers for a client where client SDR works
    """
    researchers: list = get_ai_researchers_for_client(client_sdr_id=client_sdr_id)
    return jsonify({"researchers": researchers}), 200


@ML_BLUEPRINT.route("/researchers/create", methods=["POST"])
@require_user
def post_create_ai_researcher(client_sdr_id: int):
    """
    Create an AI Researcher for a client where client SDR works
    """
    name = get_request_parameter(
        "name", request, json=True, required=True, parameter_type=str
    )
    archetype_id = get_request_parameter(
        "archetype_id", request, json=True, required=False, parameter_type=int
    )

    success = create_ai_researcher(name=name, client_sdr_id=client_sdr_id, archetype_id=archetype_id)

    if not success:
        return "Error creating AI Researcher", 400

    return "AI Researcher created successfully", 200


@ML_BLUEPRINT.route(
    "/researchers/archetype/<int:client_archetype_id>/questions", methods=["GET"]
)
@require_user
def get_ai_researcher_questions_for_archetype(
    client_sdr_id: int, client_archetype_id: int
):
    """
    Get all questions for an AI Researcher
    """
    client_archetype: ClientArchetype = ClientArchetype.query.get(client_archetype_id)
    if client_archetype is None or client_archetype.client_sdr_id != client_sdr_id:
        return jsonify({"message": "Archetype not found"}), 404
    if client_archetype.ai_researcher_id is None:
        return jsonify({"message": "Archetype does not have an AI Researcher"}), 400

    questions: list = get_ai_researcher_questions_for_researcher(
        researcher_id=client_archetype.ai_researcher_id
    )
    return jsonify({"questions": questions}), 200


@ML_BLUEPRINT.route("/researchers/<int:researcher_id>/questions", methods=["GET"])
@require_user
def get_ai_researcher_questions(client_sdr_id: int, researcher_id: int):
    """
    Get all questions for an AI Researcher
    """
    questions: list = get_ai_researcher_questions_for_researcher(
        researcher_id=researcher_id
    )
    return jsonify({"questions": questions}), 200


@ML_BLUEPRINT.route("/researchers/questions/<int:question_id>", methods=["DELETE"])
@require_user
def delete_ai_researcher_question(client_sdr_id: int, question_id: int):
    """
    Delete a question for an AI Researcher
    """
    success = delete_question(question_id=question_id)
    if not success:
        return "Error deleting AI Researcher Question", 400

    return "AI Researcher Question deleted successfully", 200


@ML_BLUEPRINT.route("/researchers/questions/<int:question_id>", methods=["PATCH"])
@require_user
def patch_ai_researcher_question(client_sdr_id: int, question_id: int):
    """
    Update a question for an AI Researcher
    """
    key = get_request_parameter(
        "key", request, json=True, required=True, parameter_type=str
    )
    type = get_request_parameter(
        "type", request, json=True, required=True, parameter_type=str
    )
    relevancy = get_request_parameter(
        "relevancy", request, json=True, required=True, parameter_type=str
    )

    success = edit_question(question_id=question_id, key=key, relevancy=relevancy, question_type=type)

    if not success:
        return "Error updating AI Researcher Question", 400

    return "AI Researcher Question updated successfully", 200


@ML_BLUEPRINT.route("/researchers/questions/create", methods=["POST"])
@require_user
def post_create_ai_researcher_question(client_sdr_id: int):
    """
    Create a question for an AI Researcher
    """
    type = get_request_parameter(
        "type", request, json=True, required=True, parameter_type=str
    )
    key = get_request_parameter(
        "key", request, json=True, required=True, parameter_type=str
    )
    relevancy = get_request_parameter(
        "relevancy", request, json=True, required=True, parameter_type=str
    )
    researcher_id = get_request_parameter(
        "researcher_id", request, json=True, required=True, parameter_type=int
    )

    success = create_ai_researcher_question(
        type=type, key=key, relevancy=relevancy, researcher_id=researcher_id
    )

    if not success:
        return "Error creating AI Researcher Question", 400

    return "AI Researcher Question created successfully", 200

#endpoint to generate ai researcher questions
@ML_BLUEPRINT.route("/researchers/questions/generate", methods=["POST"])
@require_user
def post_generate_ai_researcher_questions(client_sdr_id: int):
    """
    Generate AI Researcher questions for a prospect
    """
    researcher_id = get_request_parameter(
        "researcher_id", request, json=True, required=True, parameter_type=int
    )

    campaign_id = get_request_parameter(
        "campaign_id", request, json=True, required=True, parameter_type=int
    )

    room_id = get_request_parameter(
        "room_id", request, json=True, required=True, parameter_type=str
    )

    result = generate_ai_researcher_questions.delay(
        researcher_id=researcher_id, client_sdr_id=client_sdr_id, campaign_id=campaign_id, room_id=room_id
    )

    return "AI Researcher answers created successfully", 200


@ML_BLUEPRINT.route("/researchers/answers", methods=["POST"])
@require_user
def get_ai_researcher_answers(client_sdr_id: int):
    """
    Get all AI Researcher answers for a prospect
    """
    prospect_id = get_request_parameter(
        "prospect_id", request, json=True, required=True, parameter_type=int
    )

    answers: list = get_ai_researcher_answers_for_prospect(prospect_id=prospect_id)
    return jsonify({"answers": answers}), 200


@ML_BLUEPRINT.route("/researchers/answers/create", methods=["POST"])
@require_user
def post_run_all_ai_researcher_questions_for_prospect(client_sdr_id: int):
    """
    Run all AI Researcher questions for a prospect
    """
    prospect_id = get_request_parameter(
        "prospect_id", request, json=True, required=True, parameter_type=int
    )
    room_id = get_request_parameter(
        "room_id", request, json=True, required=True, parameter_type=str
    )

    success = run_all_ai_researcher_questions_for_prospect(
        client_sdr_id=client_sdr_id, prospect_id=prospect_id, room_id=room_id
    )

    if not success:
        return "Error running all AI Researcher questions for a prospect", 400

    return "All AI Researcher questions for a prospect ran successfully", 200


@ML_BLUEPRINT.route("/researcher/connect", methods=["POST"])
@require_user
def post_connect_researchers(client_sdr_id: int):
    """
    Connect AI Researcher to an archetype
    """
    client_archetype_id = get_request_parameter(
        "client_archetype_id", request, json=True, required=True, parameter_type=int
    )
    researcher_id = get_request_parameter(
        "researcher_id", request, json=True, required=True, parameter_type=int
    )

    success = connect_researcher_to_client_archetype(
        client_sdr_id=client_sdr_id,
        client_archetype_id=client_archetype_id,
        ai_researcher_id=researcher_id,
    )

    if not success:
        return "Error connecting AI Researchers to a prospect", 400

    return "AI Researchers connected to a prospect successfully", 200

@ML_BLUEPRINT.route("/researcher/email-personalize", methods=["POST"])
@require_user
def post_personalize_email(client_sdr_id: int):
    """
    Personalize an email body using AI Researcher
    """
    email_body = get_request_parameter(
        "email_body", request, json=True, required=True, parameter_type=str
    )
    prospect_id = get_request_parameter(
        "prospect_id", request, json=True, required=True, parameter_type=int
    )

    personalized_email = get_generated_email(
        email_body=email_body,
        prospectId=prospect_id,
    )

    if not personalized_email:
        return "Error personalizing email body", 400

    return jsonify({"personalized_email": personalized_email}), 200

@ML_BLUEPRINT.route("/template_suggestion", methods=["POST"])
@require_user
def post_template_suggestion(client_sdr_id: int):
    """
    Personalize an email body using AI Researcher
    """
    archetype_id = get_request_parameter(
        "archetype_id", request, json=True, required=True, parameter_type=str
    )
    template_content = get_request_parameter(
        "template_content", request, json=True, required=True, parameter_type=str
    )

    personalized_email = get_template_suggestions(
        archetype_id=archetype_id,
        template_content=template_content,
    )

    if not personalized_email:
        return "Error personalizing email body", 400

    return jsonify({"personalized_email": personalized_email}), 200

@ML_BLUEPRINT.route("/simulate_voice", methods=["POST"])
@require_user
def post_simulate_voice(client_sdr_id: int):
    """
    Simulate a voice message using AI Researcher
    """
    text = get_request_parameter(
        "text", request, json=True, required=True, parameter_type=str
    )
    voice_params = get_request_parameter(
        "voiceParams", request, json=True, required=True, parameter_type=dict
    )

    simulated_voice = simulate_voice_message(
        text=text,
        voice_params=voice_params,
    )

    if not simulated_voice:
        return "Error simulating voice message", 400

    return jsonify({"simulated_voice": simulated_voice}), 200

@ML_BLUEPRINT.route("/simulate-magic-subject-line", methods=["POST"])
@require_user
def post_simulate_magic_subject_line(client_sdr_id: int):
    """
    Simulate a magic subject line using AI Researcher
    """
    sequence_id = get_request_parameter(
        "sequence_id", request, json=True, required=True, parameter_type=int
    )
    prospect_id = get_request_parameter(
        "prospect_id", request, json=True, required=True, parameter_type=int
    )
    archetype_id = get_request_parameter(
        "archetype_id", request, json=True, required=True, parameter_type=int
    )
    room_id = get_request_parameter(
        "room_id", request, json=True, required=True, parameter_type=str
    )
    #not required. Comes from sequencing page.
    subject_line_id = get_request_parameter(
        "subject_line_id", request, json=True, required=False, parameter_type=str
    )

    magic_subject_line, personalized_email, ai_research_points = generate_magic_subject_line(archetype_id, prospect_id=prospect_id, sequence_id=sequence_id, generate_email=True, room_id=room_id, subject_line_id=subject_line_id)

    if (room_id):
        send_socket_message('subject-stream', {"message":"done", 'room_id': room_id}, room_id)

    if not magic_subject_line:
        return "Error simulating magic subject line", 400

    return jsonify({
        "magic_subject_line": magic_subject_line,
        "personalized_email": personalized_email,
        "ai_research": [point.to_dict() for point in ai_research_points]
    }), 200

@ML_BLUEPRINT.route("/add-few-shot", methods=["POST"])
@require_user
def post_add_few_shot(client_sdr_id: int):
    """
    Add a new FewShot entry using AI Researcher
    """
    client_archetype_id = get_request_parameter(
        "client_archetype_id", request, json=True, required=True, parameter_type=int
    )
    original_string = get_request_parameter(
        "original_string", request, json=True, required=True, parameter_type=str
    )
    edited_string = get_request_parameter(
        "edited_string", request, json=True, required=True, parameter_type=str
    )

    success = add_few_shot(
        client_archetype_id=client_archetype_id,
        original_string=original_string,
        edited_string=edited_string,
    )

    if not success:
        return "Error adding FewShot entry", 400

    return jsonify(success), 200


@ML_BLUEPRINT.route("/quick", methods=["POST"])
@require_user
def post_universal_prompt(client_sdr_id: int):
    """
    Add a new FewShot entry using AI Researcher
    """
    string = get_request_parameter(
        "userInput", request, json=True, required=True, parameter_type=str
    )
    campaign_id = get_request_parameter(
        "campaign_id", request, json=True, required=False, parameter_type=str
    )
    room_id = get_request_parameter(
        "edited_string", request, json=True, required=False, parameter_type=str
    )
    context_info = get_request_parameter(
        "contextInfo", request, json=True, required=False, parameter_type=str
    )

    success = get_nice_answer(
        userInput=string, client_sdr_id=client_sdr_id, campaign_id=campaign_id, context_info=context_info
    )

    return jsonify({'response': success}), 200
@ML_BLUEPRINT.route("/voices/all", methods=["GET"])
@require_user
def get_get_all_ai_voices(client_sdr_id: int):
    """
    Retrieve all AI Voice entries
    """
    ai_voices_list = get_all_ai_voices(client_sdr_id=client_sdr_id)

    return jsonify(ai_voices_list), 200


@ML_BLUEPRINT.route("/voices", methods=["POST"])
@require_user
def post_create_ai_voice(client_sdr_id: int):
    """
    Create an AI Voice entry
    """
    name = get_request_parameter(
        "name", request, json=True, required=True, parameter_type=str
    )
    client_archetype_id = get_request_parameter(
        "client_archetype_id", request, json=True, required=True, parameter_type=int
    )

    success = create_ai_voice(name=name, client_sdr_id=client_sdr_id, client_archetype_id=client_archetype_id)

    if not success:
        return "Error creating AI Voice entry", 400

    return jsonify(success), 200

@ML_BLUEPRINT.route("/voices", methods=["PUT"])
@require_user
def put_ai_voice(client_sdr_id: int):
    """
    Create an AI Voice entry
    """
    void_id = None
    voice_id = get_request_parameter(
        "voice_id", request, json=True, required=False, parameter_type=int
    )

    archetype_id = get_request_parameter(
        "archetype_id", request, json=True, required=True, parameter_type=int
    )

    success = assign_ai_voice(voice_id=voice_id, archetype_id=archetype_id )

    if not success:
        return "Error creating AI Voice entry", 400

    return jsonify(success), 200

@ML_BLUEPRINT.route("/few-shot", methods=["POST"])
@require_user
def post_few_shot(client_sdr_id: int):
    """
    Create a FewShot entry
    """
    ai_voice_id = get_request_parameter(
        "voice_id", request, json=True, required=False, parameter_type=int
    )

    # Assuming the function add_few_shot is defined in src/ml/services.py
    success = get_few_shots(ai_voice_id=ai_voice_id)

    if not success:
        return jsonify([]), 200

    return jsonify(success), 200

@ML_BLUEPRINT.route("/few-shot", methods=["PUT"])
@require_user
def put_few_shot(client_sdr_id: int):
    """
    DELETE a FewShot entry
    """
    id = get_request_parameter(
        "id", request, json=True, required=True, parameter_type=int
    )

    # Assuming the function add_few_shot is defined in src/ml/services.py
    success = update_few_shot(id=id)

    if not success:
        return jsonify({}), 200

    return jsonify(success), 200
