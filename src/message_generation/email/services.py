import re
from typing import Optional
from bs4 import BeautifulSoup

from src.client.models import Client, ClientArchetype, ClientSDR
from src.email_outbound.models import ProspectEmail, ProspectEmailOutreachStatus
from src.email_sequencing.models import EmailSequenceStep
from src.prospecting.models import Prospect, ProspectOverallStatus
from src.research.models import AccountResearchPoints, ResearchPoints

from src.ml.openai_wrappers import OPENAI_CHAT_GPT_4_MODEL, wrapped_chat_gpt_completion


DEFAULT_INITIAL_EMAIL_TEMPLATE = """Hi [[First name]]

[[Personalized first line related to them or their company]]

[[Mention what we do and offer, and how it can help them based on their background, company, and key details]]

[[Include a brief call to action]]

Best,
[[My name]]
[[My title]]"""


DEFAULT_FOLLOWUP_EMAIL_TEMPLATE = """Hi [[First name]],

I just wanted to followup and ask if you saw my previous message. [[Explain why I think a meeting would be valuable]].

[[Thank the prospect for taking the time to read your messages]]

Best,
[[My name]]
[[My title]]"""


def ai_initial_email_prompt(
    client_sdr_id: int,
    prospect_id: int,
    test_template: Optional[str] = None,
) -> str:
    """Generate an AI Email Prompt given a prospect. Uses the prospect's sequence step template, otherwise uses a default SellScale template.

    If a test template is provided, it will use that instead of the sequence step template.

    Args:
        client_sdr_id (int): The client SDR ID
        prospect_id (int): The prospect ID
        test_template (Optional[str], optional): The template to test. Defaults to None.

    Returns:
        str: The AI Email Prompt

    """
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client: Client = Client.query.get(client_sdr.client_id)
    prospect: Prospect = Prospect.query.get(prospect_id)
    client_archetype: ClientArchetype = ClientArchetype.query.get(
        prospect.archetype_id)
    account_research: list[AccountResearchPoints] = AccountResearchPoints.query.filter(
        AccountResearchPoints.prospect_id == prospect.id
    ).all()

    # Collect company information
    client_sdr_name = client_sdr.name
    client_sdr_title = client_sdr.title
    company_tagline = client.tagline
    company_description = client.description
    company_value_prop_key_points = client.value_prop_key_points
    company_tone_attributes = (
        ", ".join(client.tone_attributes) if client.tone_attributes else ""
    )

    # Collect persona information
    persona_name = client_archetype.archetype
    persona_buy_reason = client_archetype.persona_fit_reason
    prospect_contact_objective = client_archetype.persona_contact_objective
    prospect_name = prospect.full_name
    prospect_title = prospect.title
    prospect_bio = prospect.linkedin_bio
    prospect_company_name = prospect.company

    # Collect research points
    prospect_research: list[
        ResearchPoints
    ] = ResearchPoints.get_research_points_by_prospect_id(prospect_id)
    research_points = ""
    for point in prospect_research:
        research_points += f"- {point.value}\n"
    account_points = ""
    for point in account_research:
        account_points += f"- {point.title}: {point.reason}\n"

    # Use the Default SellScale Template as the template
    template = DEFAULT_INITIAL_EMAIL_TEMPLATE

    # Get Sequence Step (SDR Created) Template, if it exists
    sequence_step: EmailSequenceStep = EmailSequenceStep.query.filter(
        EmailSequenceStep.client_sdr_id == client_sdr_id,
        EmailSequenceStep.client_archetype_id == client_archetype.id,
        EmailSequenceStep.active == True,
        EmailSequenceStep.default == True,
        EmailSequenceStep.overall_status == ProspectOverallStatus.PROSPECTED
    ).first()
    if sequence_step is not None:
        template = sequence_step.template

    # If we are testing a template, use that instead
    if test_template is not None:
        template = test_template

    prompt = """You are a sales development representative writing on behalf of the salesperson.

Write a personalized cold email with the following objective: {persona_contact_objective}

Here's the template, everything in brackets should be replaced by you. For example: [[prospect_name]] should be replaced by the prospect's name.

Stick to the template strictly:
--- START TEMPLATE ---
{template}
--- END TEMPLATE ---

Note - you do not need to include all info.

SDR info --
SDR Name: {client_sdr_name}
Title: {client_sdr_title}

Company info --
Tagline: {company_tagline}
Company description: {company_description}

Useful data --
{value_prop_key_points}

Tone: {company_tone}

Persona info --
Name: {persona_name}

Why they buy --
{persona_buy_reason}

Prospect info --
Prospect Name: {prospect_name}
Prospect Title: {prospect_title}
Prospect Bio:
"{prospect_bio}"
Prospect Company Name: {prospect_company_name}

More research --
{prospect_research}
{research_points}

Final instructions
- Do not put generalized fluff, such as "I hope this email finds you well" or "I couldn't help but notice" or  "I noticed".
- Preserve the markdown formatting.

Generate the email body. Do not include the word 'Subject:' or 'Email:' in the output.

Output:""".format(
        template=template,
        client_sdr_name=client_sdr_name,
        client_sdr_title=client_sdr_title,
        company_tagline=company_tagline,
        company_description=company_description,
        value_prop_key_points=company_value_prop_key_points,
        company_tone=company_tone_attributes,
        persona_name=persona_name,
        persona_buy_reason=persona_buy_reason,
        prospect_name=prospect_name,
        prospect_title=prospect_title,
        prospect_bio=prospect_bio,
        prospect_company_name=prospect_company_name,
        prospect_research=account_points,
        research_points=research_points,
        persona_contact_objective=prospect_contact_objective,
    )

    return prompt


def ai_followup_email_prompt(
    client_sdr_id: int,
    prospect_id: int,
    thread_id: str,
    override_sequence_id: Optional[int],
) -> str:
    """Generate an email for a prospect. If override_sequence_id is specified, then that sequence step template will be used in favor of the default.

    Note: This is only applicable to SENT_OUTREACH and BUMPED prospects. ie. No ACTIVE_CONVO, etc. prospects.

    Args:
        client_sdr_id (int): The id of the client sdr
        prospect_id (int): The id of the prospect
        thread_id (str): The id of the thread
        override_sequence_id (int): The id of a sequence step to use. Overrides the default.
    Returns:
        string: The prompt for the email
    """
    from src.prospecting.nylas.services import get_email_messages_with_prospect

    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client: Client = Client.query.get(client_sdr.client_id)
    prospect: Prospect = Prospect.query.get(prospect_id)
    prospect_email: ProspectEmail = ProspectEmail.query.get(
        prospect.approved_prospect_email_id)
    client_archetype: ClientArchetype = ClientArchetype.query.get(
        prospect.archetype_id)
    account_research: list[AccountResearchPoints] = AccountResearchPoints.query.filter(
        AccountResearchPoints.prospect_id == prospect.id
    ).all()

    # If Prospect is not in SENT_OUTREACH or BUMPED and we are not overriding the sequence step, then we should not be following up with them
    # Example: Prospect is in Active Conversation state, we shouldn't send a bump email
    # TODO: Eventually have intelligent systems that can handle automatically responding to prospect replies.
    if prospect.overall_status not in [ProspectOverallStatus.SENT_OUTREACH, ProspectOverallStatus.BUMPED] and override_sequence_id is None:
        raise Exception(
            "Prospect is not in SENT_OUTREACH or BUMPED status and shouldn't be followed up with.")

    # Collect company information
    client_sdr_name = client_sdr.name
    client_sdr_title = client_sdr.title
    company_tagline = client.tagline
    company_description = client.description
    company_value_prop_key_points = client.value_prop_key_points
    company_tone_attributes = (
        ", ".join(client.tone_attributes) if client.tone_attributes else ""
    )

    # Collect persona information
    persona_name = client_archetype.archetype
    persona_buy_reason = client_archetype.persona_fit_reason
    prospect_contact_objective = client_archetype.persona_contact_objective
    prospect_name = prospect.full_name
    prospect_title = prospect.title
    prospect_bio = prospect.linkedin_bio
    prospect_company_name = prospect.company

    # Collect research points
    prospect_research: list[
        ResearchPoints
    ] = ResearchPoints.get_research_points_by_prospect_id(prospect_id)
    research_points = ""
    for point in prospect_research:
        research_points += f"- {point.value}\n"
    account_points = ""
    for point in account_research:
        account_points += f"- {point.title}: {point.reason}\n"

    # Convert past messages to text. Append '>' to each line to make it a quote
    past_messages = []
    past_messages_raw = get_email_messages_with_prospect(
        client_sdr_id, prospect_id, thread_id
    )
    if past_messages_raw:
        for thread in past_messages_raw:
            body: str = thread.get("body")
            bs = BeautifulSoup(body, "html.parser")
            body: str = bs.get_text()
            body: str = re.sub(r"\n+", "\n", body)
            body: str = "> " + body
            body: str = body.strip().replace("\n", "\n> ")
            past_messages.append(body)

    # Use the Default SellScale Template as the template
    template = DEFAULT_FOLLOWUP_EMAIL_TEMPLATE

    # Get the template from the sequence step
    if override_sequence_id:
        sequence_step: EmailSequenceStep = EmailSequenceStep.query.get(
            override_sequence_id)
        template = sequence_step.template
    else:
        # Get the template from the sequence step
        if prospect_email.outreach_status == ProspectEmailOutreachStatus.SENT_OUTREACH:
            sequence_step: EmailSequenceStep = EmailSequenceStep.query.filter(
                EmailSequenceStep.client_sdr_id == client_sdr_id,
                EmailSequenceStep.client_archetype_id == client_archetype.id,
                EmailSequenceStep.active == True,
                EmailSequenceStep.default == True,
                EmailSequenceStep.overall_status == ProspectOverallStatus.SENT_OUTREACH
            ).first()
            template = sequence_step.template
        elif prospect.overall_status == ProspectOverallStatus.BUMPED:
            sequence_step: EmailSequenceStep = EmailSequenceStep.query.filter(
                EmailSequenceStep.client_sdr_id == client_sdr_id,
                EmailSequenceStep.client_archetype_id == client_archetype.id,
                EmailSequenceStep.active == True,
                EmailSequenceStep.default == True,
                EmailSequenceStep.overall_status == ProspectOverallStatus.BUMPED,
                EmailSequenceStep.bumped_count == prospect_email.times_bumped
            ).first()
            template = sequence_step.template

    prompt = """You are a sales development representative writing on behalf of the salesperson.

Write a follow up email to the previous email. The followup email should use information about the recipient in a highly personalized manner.

Here's the template, everything in brackets should be replaced by you. For example: [[prospect_name]] should be replaced by the prospect's name.

Stick to the template strictly:
--- START TEMPLATE ---
{template}
--- END TEMPLATE ---

Note - you do not need to include all info.

SDR info --
SDR Name: {client_sdr_name}
Title: {client_sdr_title}

Company info --
Tagline: {company_tagline}
Company description: {company_description}

Useful data --
{value_prop_key_points}

Tone: {company_tone}

Persona info --
Name: {persona_name}

Why they buy --
{persona_buy_reason}

Prospect info --
Prospect Name: {prospect_name}
Prospect Title: {prospect_title}
Prospect Bio:
"{prospect_bio}"
Prospect Company Name: {prospect_company_name}

More research --
{prospect_research}
{research_points}

Past thread
--- START THREAD ---
{past_threads}
--- END THREAD ---

Final instructions
- Do not put generalized fluff, such as "I hope this email finds you well" or "I couldn't help but notice" or  "I noticed"
- Preserve the markdown formatting.

Generate the email body. Do not include the word 'Subject:' or 'Email:' in the output.

Output:""".format(
        template=template,
        client_sdr_name=client_sdr_name,
        client_sdr_title=client_sdr_title,
        company_tagline=company_tagline,
        company_description=company_description,
        value_prop_key_points=company_value_prop_key_points,
        company_tone=company_tone_attributes,
        persona_name=persona_name,
        persona_buy_reason=persona_buy_reason,
        prospect_name=prospect_name,
        prospect_title=prospect_title,
        prospect_bio=prospect_bio,
        prospect_company_name=prospect_company_name,
        prospect_research=account_points,
        research_points=research_points,
        persona_contact_objective=prospect_contact_objective,
        past_threads="\n\n".join(past_messages),
    )

    return prompt


def generate_email(prompt: str) -> dict[str, str]:
    """Generate an email for a prospect.

    Args:
        prompt (str): The prompt to generate the email with

    Returns:
        dict[str, str]: The subject and body of the email
    """
    response = wrapped_chat_gpt_completion(
        [
            {"role": "system", "content": prompt},
        ],
        temperature=0.7,
        max_tokens=400,
        model=OPENAI_CHAT_GPT_4_MODEL,
    )
    response = response if isinstance(response, str) else ""

    return {"body": response}