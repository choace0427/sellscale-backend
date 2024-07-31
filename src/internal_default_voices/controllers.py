from flask import Blueprint, jsonify, request, Response

from app import db
from src.bump_framework.models import BumpFramework
from src.internal_default_voices.models import InternalDefaultVoices
from src.message_generation.models import GeneratedMessageCTA, StackRankedMessageGenerationConfiguration, \
    GeneratedMessageAutoBump, GeneratedMessage
from src.utils.request_helpers import get_request_parameter

INTERNAL_VOICES_BLUEPRINT = Blueprint("internal_voices", __name__)


@INTERNAL_VOICES_BLUEPRINT.route("/", methods=["POST"])
def create_internal_default_voice():
    internal_voice_info = get_request_parameter(
        "internal_voice", request, json=True, required=True
    )

    ctas = get_request_parameter(
        "ctas", request, json=True, required=True
    )

    bumps = get_request_parameter(
        "bumps", request, json=True, required=True
    )

    stack = get_request_parameter(
        "stack", request, json=True, required=True
    )

    internal_voice = InternalDefaultVoices(
        title=internal_voice_info["title"],
        description=internal_voice_info["description"],
        count_ctas=len(ctas),
        count_bumps=len(bumps),
    )

    db.session.add(internal_voice)
    db.session.commit()

    for cta in ctas:
        new_cta = GeneratedMessageCTA(
            text_value=cta["text_value"],
            active=cta["active"],
            expiration_date=cta["expiration_date"],
            cta_type=cta["cta_type"],
            auto_mark_as_scheduling_on_acceptance=cta["auto_mark_as_scheduling_on_acceptance"],
            internal_default_voice_id=internal_voice.id,
        )

        db.session.add(new_cta)
        db.session.commit()

    for bump in bumps:
        new_bump = BumpFramework(
            description=bump["description"],
            additional_instructions=bump["additional_instructions"],
            title=bump["title"],
            overall_status=bump["overall_status"],
            substatus=bump["substatus"],
            bump_length=bump["bump_length"],
            bumped_count=bump["bumped_count"],
            bump_delay_days=bump["bump_delay_days"],
            active=bump["active"],
            default=bump["default"],
            sellscale_default_generated=False,
            use_account_research=bump["use_account_research"],
            bump_framework_template_name=bump["bump_framework_template_name"],
            bump_framework_human_readable_prompt=bump["bump_framework_human_readable_prompt"],
            additional_context=bump["additional_context"],
            transformer_blocklist=bump["transformer_blocklist"],
            internal_default_voice_id=internal_voice.id,
        )

        db.session.add(new_bump)
        db.session.commit()

    if stack["instruction"]:
        new_computed_prompt = stack["instruction"] + "\n ## Here are a couple of examples\n--\n"
    else:
        new_computed_prompt = ""

    new_prompt_1 = None
    new_prompt_2 = None
    new_prompt_3 = None
    new_prompt_4 = None
    new_prompt_5 = None
    new_prompt_6 = None
    new_prompt_7 = None

    new_completion_1 = None
    new_completion_2 = None
    new_completion_3 = None
    new_completion_4 = None
    new_completion_5 = None
    new_completion_6 = None
    new_completion_7 = None

    if stack["prompt_1"]:
        new_prompt_1 = stack["prompt_1"]
        new_computed_prompt += f'prompt:{new_prompt_1}\n'

    if stack["completion_1"]:
        new_completion_1 = stack["completion_1"]
        new_computed_prompt += f'response:{new_completion_1}\n\n--\n\n'

    if stack["prompt_2"]:
        new_prompt_2 = stack["prompt_2"]
        new_computed_prompt += f'prompt:{new_prompt_2}\n'
    if stack["completion_2"]:
        new_completion_2 = stack["completion_2"]
        new_computed_prompt += f'response:{new_completion_2}\n\n--\n\n'

    if stack["prompt_3"]:
        new_prompt_3 = stack["prompt_3"]
        new_computed_prompt += f'prompt:{new_prompt_3}\n'

    if stack["completion_3"]:
        new_completion_3 = stack["completion_3"]
        new_computed_prompt += f'response:{new_completion_3}\n\n--\n\n'

    if stack["prompt_4"]:
        new_prompt_4 = stack["prompt_4"]
        new_computed_prompt += f'prompt:{new_prompt_4}\n'
    if stack["completion_4"]:
        new_completion_4 = stack["completion_4"]
        new_computed_prompt += f'response:{new_completion_4}\n\n--\n\n'

    if stack["prompt_5"]:
        new_prompt_5 = stack["prompt_5"]
        new_computed_prompt += f'prompt:{new_prompt_5}\n'
    if stack["completion_5"]:
        new_completion_5 = stack["completion_5"]
        new_computed_prompt += f'response:{new_completion_5}\n\n--\n\n'

    if stack["prompt_6"]:
        new_prompt_6 = stack["prompt_6"]
        new_computed_prompt += f'prompt:{new_prompt_6}\n'
    if stack["completion_6"]:
        new_completion_6 = stack["completion_6"]
        new_computed_prompt += f'response:{new_completion_6}\n\n--\n\n'

    if stack["prompt_7"]:
        new_prompt_7 = stack["prompt_7"]
        new_computed_prompt += f'prompt:{new_prompt_7}\n'
    if stack["completion_7"]:
        new_completion_7 = stack["completion_7"]
        new_computed_prompt += f'response:{new_completion_7}\n\n--\n\n'

    new_computed_prompt += 'prompt: {prompt}\ncompletion:\n'

    new_stack = StackRankedMessageGenerationConfiguration(
        configuration_type=stack["configuration_type"],
        research_point_types=stack["research_point_types"],
        instruction=stack["instruction"],
        computed_prompt=new_computed_prompt,
        name=stack["name"],
        generated_message_type=stack["generated_message_type"],
        priority=stack["priority"],
        prompt_1=new_prompt_1,
        completion_1=new_completion_1,
        prompt_2=new_prompt_2,
        completion_2=new_completion_2,
        prompt_3=new_prompt_3,
        completion_3=new_completion_3,
        prompt_4=new_prompt_4,
        completion_4=new_completion_4,
        prompt_5=new_prompt_5,
        completion_5=new_completion_5,
        prompt_6=new_prompt_6,
        completion_6=new_completion_6,
        prompt_7=new_prompt_7,
        completion_7=new_completion_7,
        internal_default_voice_id=internal_voice.id,
    )

    db.session.add(new_stack)
    db.session.commit()

    return jsonify({"message": "Internal voice created successfully"}), 201


@INTERNAL_VOICES_BLUEPRINT.route("/", methods=["PATCH"])
def patch_internal_default_voice():
    internal_voice_info = get_request_parameter(
        "internal_voice", request, json=True, required=True
    )

    ctas = get_request_parameter(
        "ctas", request, json=True, required=True
    )

    bumps = get_request_parameter(
        "bumps", request, json=True, required=True
    )

    stack = get_request_parameter(
        "stack", request, json=True, required=True
    )

    internal_voice = InternalDefaultVoices.query.get(internal_voice_info["id"])
    internal_voice.title = internal_voice_info["title"]
    internal_voice.description = internal_voice_info["description"]

    db.session.commit()

    for cta in ctas:
        if cta["id"]:
            cta_to_update: GeneratedMessageCTA = GeneratedMessageCTA.query.get(cta["id"])
            cta_to_update.text_value = cta["text_value"]
            cta_to_update.active = cta["active"]
            cta_to_update.expiration_date = cta["expiration_date"]
            cta_to_update.cta_type = cta["cta_type"]
            cta_to_update.auto_mark_as_scheduling_on_acceptance = cta["auto_mark_as_scheduling_on_acceptance"]
            db.session.commit()

    if stack:
        if stack["id"]:
            if stack["instruction"]:
                new_computed_prompt = stack["instruction"] + "\n ## Here are a couple of examples\n--\n"
            else:
                new_computed_prompt = ""

            if stack["prompt_1"]:
                new_prompt_1 = stack["prompt_1"]
                new_computed_prompt += f'prompt:{new_prompt_1}\n'

            if stack["completion_1"]:
                new_completion_1 = stack["completion_1"]
                new_computed_prompt += f'response:{new_completion_1}\n\n--\n\n'

            if stack["prompt_2"]:
                new_prompt_2 = stack["prompt_2"]
                new_computed_prompt += f'prompt:{new_prompt_2}\n'
            if stack["completion_2"]:
                new_completion_2 = stack["completion_2"]
                new_computed_prompt += f'response:{new_completion_2}\n\n--\n\n'

            if stack["prompt_3"]:
                new_prompt_3 = stack["prompt_3"]
                new_computed_prompt += f'prompt:{new_prompt_3}\n'

            if stack["completion_3"]:
                new_completion_3 = stack["completion_3"]
                new_computed_prompt += f'response:{new_completion_3}\n\n--\n\n'

            if stack["prompt_4"]:
                new_prompt_4 = stack["prompt_4"]
                new_computed_prompt += f'prompt:{new_prompt_4}\n'
            if stack["completion_4"]:
                new_completion_4 = stack["completion_4"]
                new_computed_prompt += f'response:{new_completion_4}\n\n--\n\n'

            if stack["prompt_5"]:
                new_prompt_5 = stack["prompt_5"]
                new_computed_prompt += f'prompt:{new_prompt_5}\n'
            if stack["completion_5"]:
                new_completion_5 = stack["completion_5"]
                new_computed_prompt += f'response:{new_completion_5}\n\n--\n\n'

            if stack["prompt_6"]:
                new_prompt_6 = stack["prompt_6"]
                new_computed_prompt += f'prompt:{new_prompt_6}\n'
            if stack["completion_6"]:
                new_completion_6 = stack["completion_6"]
                new_computed_prompt += f'response:{new_completion_6}\n\n--\n\n'

            if stack["prompt_7"]:
                new_prompt_7 = stack["prompt_7"]
                new_computed_prompt += f'prompt:{new_prompt_7}\n'
            if stack["completion_7"]:
                new_completion_7 = stack["completion_7"]
                new_computed_prompt += f'response:{new_completion_7}\n\n--\n\n'

            new_computed_prompt += 'prompt: {prompt}\ncompletion:\n'

            stack_to_update: StackRankedMessageGenerationConfiguration = StackRankedMessageGenerationConfiguration.query.get(stack["id"])
            stack_to_update.configuration_type = stack["configuration_type"]
            stack_to_update.research_point_types = stack["research_point_types"]
            stack_to_update.instruction = stack["instruction"]
            stack_to_update.name = stack["name"]
            stack_to_update.generated_message_type = stack["generated_message_type"]
            stack_to_update.priority = stack["priority"]
            stack_to_update.prompt_1 = stack["prompt_1"]
            stack_to_update.completion_1 = stack["completion_1"]
            stack_to_update.prompt_2 = stack["prompt_2"]
            stack_to_update.completion_2 = stack["completion_2"]
            stack_to_update.prompt_3 = stack["prompt_3"]
            stack_to_update.completion_3 = stack["completion_3"]
            stack_to_update.prompt_4 = stack["prompt_4"]
            stack_to_update.completion_4 = stack["completion_4"]
            stack_to_update.prompt_5 = stack["prompt_5"]
            stack_to_update.completion_5 = stack["completion_5"]
            stack_to_update.prompt_6 = stack["prompt_6"]
            stack_to_update.completion_6 = stack["completion_6"]
            stack_to_update.prompt_7 = stack["prompt_7"]
            stack_to_update.completion_7 = stack["completion_7"]
            stack_to_update.computed_prompt = new_computed_prompt
            db.session.commit()

    for bump in bumps:
        if bump["id"]:
            bump_to_update: BumpFramework = BumpFramework.query.get(bump["id"])
            bump_to_update.description = bump["description"]
            bump_to_update.additional_instructions = bump["additional_instructions"]
            bump_to_update.title = bump["title"]
            bump_to_update.overall_status = bump["overall_status"]
            bump_to_update.substatus = bump["substatus"]
            bump_to_update.bump_length = bump["bump_length"]
            bump_to_update.bumped_count = bump["bumped_count"]
            bump_to_update.bump_delay_days = bump["bump_delay_days"]
            bump_to_update.active = bump["active"]
            bump_to_update.default = bump["default"]
            bump_to_update.use_account_research = bump["use_account_research"]
            bump_to_update.bump_framework_template_name = bump["bump_framework_template_name"]
            bump_to_update.bump_framework_human_readable_prompt = bump["bump_framework_human_readable_prompt"]
            bump_to_update.additional_context = bump["additional_context"]
            bump_to_update.transformer_blocklist = bump["transformer_blocklist"]
            db.session.commit()

    return jsonify({"message": "Internal voice updated successfully"}), 200


@INTERNAL_VOICES_BLUEPRINT.route("/", methods=["GET"])
def get_internal_default_voices():
    internal_default_voices = InternalDefaultVoices.query.all()
    return jsonify([voice.to_dict() for voice in internal_default_voices])


@INTERNAL_VOICES_BLUEPRINT.route("/<int:internal_default_voice_id>", methods=["DELETE"])
def delete_internal_default_voice(internal_default_voice_id: int):
    internal_voice: InternalDefaultVoices = InternalDefaultVoices.query.get(internal_default_voice_id)

    if not internal_voice:
        return "Internal voice not found", 404

    ctas = GeneratedMessageCTA.query.filter_by(internal_default_voice_id=internal_default_voice_id).all()
    bumps = BumpFramework.query.filter_by(internal_default_voice_id=internal_default_voice_id).all()
    stacks = StackRankedMessageGenerationConfiguration.query.filter_by(internal_default_voice_id=internal_default_voice_id).all()

    for cta in ctas:
        db.session.delete(cta)
        db.session.commit()
    for bump in bumps:
        generated_messages = GeneratedMessageAutoBump.query.filter_by(bump_framework_id=bump.id).all()
        for generated_message in generated_messages:
            db.session.delete(generated_message)
            db.session.commit()

        db.session.delete(bump)
        db.session.commit()
    for stack in stacks:
        stack.internal_default_voice_id = None
        db.session.commit()

    db.session.delete(internal_voice)
    db.session.commit()

    return jsonify({"message": "Internal voice deleted successfully"}), 200
