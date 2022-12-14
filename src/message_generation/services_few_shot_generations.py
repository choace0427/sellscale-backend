from app import db
import os
import openai
from model_import import GeneratedMessageInstruction, Prospect, GeneratedMessage
from src.message_generation.services import generate_prompt

openai.api_key = os.getenv("OPENAI_API_KEY")


def generate_prompt_with_instruction(
    prospect_id: int, instruction_id: int, incomplete: bool = False
):
    instruction: GeneratedMessageInstruction = GeneratedMessageInstruction.query.get(
        instruction_id
    )
    if not instruction or not instruction.active:
        return None

    prospect: Prospect = Prospect.query.get(prospect_id)
    if not prospect:
        return None

    approved_gm: GeneratedMessage = GeneratedMessage.query.get(
        prospect.approved_outreach_message_id
    )
    if not approved_gm:
        return None

    prompt_value = generate_prompt(prospect_id)
    instruction_value = instruction.text_value
    completion_value = approved_gm.completion

    if incomplete:
        prompt = "prompt: {prompt_value} \n\ninstruction: {instruction_value}\n\ncompletion:".format(
            prompt_value=prompt_value,
            completion_value=completion_value,
            instruction_value=instruction_value,
        )
    else:
        prompt = "prompt: {prompt_value} \n\ninstruction: {instruction_value}\n\ncompletion: {completion_value}\n\n--\n\n".format(
            prompt_value=prompt_value,
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

    import pdb

    pdb.set_trace()

    return [i.id for i in similar_prospects]


def generate_few_shot_generation_for_prospect(prospect_id, instruction_id):
    similar_prospects_list = get_similar_prospects(prospect_id, 2)
    examples_for_prompt_from_similar_prospects = [
        generate_prompt_with_instruction(i, instruction_id)
        for i in similar_prospects_list
    ]
    #
    incomplete_prompt = generate_prompt_with_instruction(
        prospect_id, instruction_id, incomplete=True
    )
    prompt = "".join(examples_for_prompt_from_similar_prospects) + incomplete_prompt

    response = openai.Completion.create(
        model="text-davinci-003",
        prompt=prompt,
        temperature=0.7,
        max_tokens=70,
        top_p=1,
        best_of=8,
        frequency_penalty=0,
        presence_penalty=0,
    )

    return response
