import openai
from model_import import GeneratedMessageType
from src.email_sequencing.models import EmailSequenceStep, EmailSubjectLineTemplate
from src.ml.openai_wrappers import (
    wrapped_chat_gpt_completion,
)


def magic_edit(message_copy: str):
    """
    Makes edits to message copy to make it more natural and fix spelling and returns 4 choices.
    """
    instruction = "Make adjustments to this paragraph to make it sound more natural and fix any spelling errors."

    return get_edited_options(instruction=instruction, message_copy=message_copy)


def shorten(message_copy: str):
    """
    Shortens message copy using GPT-3.
    """
    instruction = "Make this 10% shorter."

    return get_edited_options(instruction=instruction, message_copy=message_copy)


def get_edited_options(instruction: str, message_copy: str):
    """
    Makes edits prescribed in instruction to message copy and returns 4 choices.
    """
    messages, preview = wrapped_chat_gpt_completion(
        messages=[
            {
                "role": "user",
                "content": "instruction:\n{instruction}\n\ninput:\n{message_copy}\n\noutput:".format(
                    instruction=instruction, message_copy=message_copy
                ),
            },
        ],
        temperature=0.65,
        max_tokens=256,
        top_p=1,
        frequency_penalty=0,
        presence_penalty=0,
        n=4,
    )

    return [choice["text"] for choice in messages["choices"]]


def get_editing_details(message_id: int):
    from model_import import (
        Prospect,
        GeneratedMessage,
        ResearchPoints,
        ResearchPayload,
        ResearchType,
        GeneratedMessageCTA,
        StackRankedMessageGenerationConfiguration,
    )

    generated_message: GeneratedMessage = GeneratedMessage.query.get(message_id)
    if not generated_message:
        return None
    prospect_id = generated_message.prospect_id
    prospect = Prospect.query.get(prospect_id)
    cta = None
    if generated_message.message_cta:
        cta: GeneratedMessageCTA = GeneratedMessageCTA.query.get(
            generated_message.message_cta
        )
    li_payload = ResearchPayload.get_by_prospect_id(
        prospect_id=prospect_id, payload_type=ResearchType.LINKEDIN_ISCRAPER
    )
    serp_payload = ResearchPayload.get_by_prospect_id(
        prospect_id=prospect_id, payload_type=ResearchType.SERP_PAYLOAD
    )
    research_points = None
    if generated_message.research_points:
        research_points: list[ResearchPoints] = ResearchPoints.query.filter(
            ResearchPoints.id.in_(generated_message.research_points)
        ).all()
    config_id = generated_message.stack_ranked_message_generation_configuration_id
    configuration = None
    if config_id:
        configuration = StackRankedMessageGenerationConfiguration.query.get(config_id)

    email_body_template = None
    if generated_message.email_sequence_step_template_id:
        template: EmailSequenceStep = EmailSequenceStep.query.get(
            generated_message.email_sequence_step_template_id
        )
        email_body_template = template.to_dict()

    subject_line_template = None
    if generated_message.email_subject_line_template_id:
        template: EmailSubjectLineTemplate = EmailSubjectLineTemplate.query.get(
            generated_message.email_subject_line_template_id
        )
        subject_line_template = template.to_dict()

    return {
        "prompt": generated_message.prompt,
        "prospect": prospect.to_dict(),
        "cta": cta.to_dict() if cta else None,
        "linkedin_payload": li_payload.payload if li_payload else {},
        "serp_payload": serp_payload.payload if serp_payload else {},
        "research_points": [rp.to_dict() for rp in research_points]
        if research_points
        else [],
        "configuration": configuration.to_dict() if configuration else None,
        "email_body_template": email_body_template,
        "subject_line_template": subject_line_template,
    }
