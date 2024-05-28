from model_import import (
    GeneratedMessage,
    EmailSchema,
    ProspectEmail,
    StackRankedMessageGenerationConfiguration,
    ClientSDR,
)
from src.research.models import ResearchPayload, ResearchPoints
from model_import import Prospect
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

from src.ml.openai_wrappers import (
    wrapped_chat_gpt_completion,
)
from src.message_generation.services import (
    generate_prompt,
    generate_batches_of_research_points,
    get_notes_and_points_from_perm,
)
from sqlalchemy.sql.expression import func


openai.api_key = os.getenv("OPENAI_KEY")


def generate_prompt_with_instruction(
    prospect_id: int, instruction_id: int, incomplete: bool = False, notes: str = ""
):
    """Generates a prompt for a prospect with an instruction for few shot generation. Prompt looks like

    ```
    prompt: {INFO ABOUT PROSPECT HERE}

    instruction: {AN INSTRUCTION SENTENCE}

    completion: {A COMPLETION MESSAGE}

    Args:
        prospect_id (int): prospect id
        instruction_id (int): instruction id
        incomplete (bool, optional): whether to generate an incomplete prompt. Defaults to False.
        notes (str, optional):  notes to add to the prompt. Defaults to "".
    """
    instruction: GeneratedMessageInstruction = GeneratedMessageInstruction.query.get(
        instruction_id
    )
    if not instruction or not instruction.active:
        return None

    prospect: Prospect = Prospect.query.get(prospect_id)
    if not prospect:
        return None

    instruction_value = instruction.text_value

    prospect_data = ""
    if incomplete:
        incomplete_prompt_value, _ = generate_prompt(prospect_id, notes=notes)
        prompt = "prompt: {prompt_value} \n\ninstruction: {instruction_value}\n\ncompletion:".format(
            prompt_value=incomplete_prompt_value,
            instruction_value=instruction_value,
        )
        prospect_data = incomplete_prompt_value
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
        prospect_data = complete_prompt_value

    return prompt, prospect_data


def get_similar_prospects(prospect_id, n=2):
    """
    Gets similar prospects to the prospect with prospect_id so we can use their messages to generate new few shot messages
    """
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
        .order_by(func.random())
        .limit(n)
        .all()
    )

    return [i[0].id for i in similar_prospects]


def generate_few_shot_generation_completion(prospect_id, notes):
    """
    Generates a few shot generation completion for a prospect using similar prospects and their 'good messages
    """
    instruction_id = 1

    prompt, prospect_data = generate_prompt_with_instruction(
        prospect_id, instruction_id, incomplete=True, notes=notes
    )
    similar_prospects_list = get_similar_prospects(prospect_id, 2)
    examples_for_prompt_from_similar_prospects = [
        generate_prompt_with_instruction(i, instruction_id)[0]
        for i in similar_prospects_list
    ]
    few_shot_prompt = "".join(examples_for_prompt_from_similar_prospects) + prompt

    text = wrapped_chat_gpt_completion(
        messages=[
            {"role": "user", "content": few_shot_prompt},
        ],
        temperature=0.65,
        max_tokens=100,
        top_p=1,
        best_of=8,
        frequency_penalty=0,
        presence_penalty=0,
    )

    completions = [text]

    return completions, prospect_data, instruction_id, few_shot_prompt


def can_generate_with_few_shot(prospect_id: int):
    """
    Checks if we can generate a few shot message for a prospect by seeing if there are at least two 'good samples' for the prospect's persona
    """
    return len(get_similar_prospects(prospect_id, 2)) >= 2


def can_generate_with_patterns(client_sdr_id: int):
    """Checks if we can generate a message with patterns for a client sdr

    Args:
        client_sdr_id (int): The ID of the Client SDR
    """
    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client_id = sdr.client_id
    return (
        StackRankedMessageGenerationConfiguration.query.filter(
            StackRankedMessageGenerationConfiguration.client_id == client_id,
        ).count()
        > 0
    )


def clear_all_good_messages_by_archetype_id(archetype_id: int):
    messages: list = (
        GeneratedMessage.query.join(
            Prospect, Prospect.id == GeneratedMessage.prospect_id
        )
        .filter(
            Prospect.archetype_id == archetype_id, GeneratedMessage.good_message == True
        )
        .all()
    )
    for message in messages:
        message.good_message = None
        db.session.add(message)
    db.session.commit()
    return True


def toggle_message_as_good_message(message_id: int):
    """
    Toggles a message as a good message
    """
    message: GeneratedMessage = GeneratedMessage.query.get(message_id)
    if not message:
        return False

    message.good_message = not message.good_message
    db.session.add(message)
    db.session.commit()
    return True


def mark_messages_as_good_message(generated_message_ids: list):
    """
    Marks a list of messages as good messages
    """
    GeneratedMessage.query.filter(
        GeneratedMessage.id.in_(generated_message_ids)
    ).update({"good_message": True})
    db.session.commit()
    return True
