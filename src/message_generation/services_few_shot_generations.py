from model_import import (
    GeneratedMessage,
    EmailSchema,
    ProspectEmail,
)
from src.research.models import ResearchPayload, ResearchPoints
from model_import import Prospect, GNLPModelType
from app import db, celery

from app import db
import os
import openai
from model_import import (
    GeneratedMessageInstruction,
    Prospect,
    GeneratedMessage,
    GeneratedMessageType,
)
from src.message_generation.services import (
    generate_prompt,
    generate_batches_of_research_points,
    get_notes_and_points_from_perm,
)
from src.research.linkedin.services import get_research_and_bullet_points_new
from src.ml.fine_tuned_models import get_latest_custom_model


openai.api_key = os.getenv("OPENAI_API_KEY")


def generate_prompt_with_instruction(
    prospect_id: int, instruction_id: int, incomplete: bool = False, notes: str = ""
):
    instruction: GeneratedMessageInstruction = GeneratedMessageInstruction.query.get(
        instruction_id
    )
    if not instruction or not instruction.active:
        return None

    prospect: Prospect = Prospect.query.get(prospect_id)
    if not prospect:
        return None

    instruction_value = instruction.text_value

    if incomplete:
        incomplete_prompt_value = generate_prompt(prospect_id, notes=notes)
        prompt = "prompt: {prompt_value} \n\ninstruction: {instruction_value}\n\ncompletion:".format(
            prompt_value=incomplete_prompt_value,
            instruction_value=instruction_value,
        )
    else:
        approved_gm: GeneratedMessage = GeneratedMessage.query.get(
            prospect.approved_outreach_message_id
        )
        complete_prompt_value = approved_gm.prompt
        completion_value = approved_gm.completion
        prompt = "prompt: {prompt_value} \n\ninstruction: {instruction_value}\n\ncompletion: {completion_value}\n\n--\n\n".format(
            prompt_value=complete_prompt_value,
            completion_value=completion_value,
            instruction_value=instruction_value,
        )

    return prompt


def get_similar_prospects(prospect_id, n=2):
    p: Prospect = Prospect.query.get(prospect_id)
    if not p:
        return None

    similar_prospects = (
        db.session.query(Prospect, GeneratedMessage)
        .filter(
            GeneratedMessage.good_message == True,
            GeneratedMessage.id == Prospect.approved_outreach_message_id,
            Prospect.id != prospect_id,
            Prospect.archetype_id == p.archetype_id,
        )
        .limit(n)
        .all()
    )

    return [i[0].id for i in similar_prospects]


def generate_few_shot_generation_for_prospect(prospect_id, instruction_id, cta_id):

    # START
    p: Prospect = Prospect.query.get(prospect_id)
    archetype_id = p.archetype_id

    # check if messages exist, if do don't do anything extra
    research: ResearchPayload = ResearchPayload.query.filter(
        ResearchPayload.prospect_id == prospect_id
    ).first()
    if not research:
        return []

    research_points_list: list[ResearchPoints] = ResearchPoints.query.filter(
        ResearchPoints.research_payload_id == research.id
    ).all()

    perms = generate_batches_of_research_points(points=research_points_list, n=2)

    outreaches = []
    for perm in perms:
        notes, research_points, cta = get_notes_and_points_from_perm(perm, cta_id)
        # END

        completions, model_id, prompt = generate_few_shot_generation_completion(
            prospect_id, notes
        )

        for completion in completions:
            outreaches.append(completion)

    return outreaches


def generate_few_shot_generation_completion(prospect_id, notes):
    instruction_id = 1

    p: Prospect = Prospect.query.get(prospect_id)
    archetype_id = p.archetype_id

    _, model_id = get_latest_custom_model(
        archetype_id=archetype_id, model_type=GNLPModelType.OUTREACH
    )

    prompt = generate_prompt_with_instruction(
        prospect_id, instruction_id, incomplete=True, notes=notes
    )
    similar_prospects_list = get_similar_prospects(prospect_id, 2)
    examples_for_prompt_from_similar_prospects = [
        generate_prompt_with_instruction(i, instruction_id)
        for i in similar_prospects_list
    ]
    few_shot_prompt = "".join(examples_for_prompt_from_similar_prospects) + prompt

    response = openai.Completion.create(
        model="text-davinci-003",
        prompt=few_shot_prompt,
        temperature=0.7,
        max_tokens=100,
        top_p=1,
        best_of=8,
        frequency_penalty=0,
        presence_penalty=0,
    )

    completions = [x["text"] for x in response["choices"]]

    return completions, model_id, prompt, instruction_id, few_shot_prompt


def can_generate_with_few_shot(prospect_id: int):
    return len(get_similar_prospects(prospect_id, 2)) > 0
