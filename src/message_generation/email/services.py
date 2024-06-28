# Generations for email messages
# The typicaly flow for generating an email is:
#   1. Generate an AI Prompt
#   2. Generate an email using the AI Prompt
# The intention of this flow is to have both prompt and completion exposed, instead of having 1 function handle both
# This allows for more flexibility in the future, and lets us experiment more easily with different prompts / models.

from app import db
from typing import Optional
from bs4 import BeautifulSoup
from src.message_generation.email.models import EmailAutomatedReply
from src.message_generation.services import get_li_convo_history_transcript_form
from src.ml.ai_researcher_services import get_generated_email, run_all_ai_researcher_questions_for_prospect
from src.sockets.services import send_socket_message
from src.utils.slack import send_slack_message, URL_MAP
from src.ml.services import get_text_generation

from src.client.models import Client, ClientArchetype, ClientSDR
from src.email_outbound.models import ProspectEmail, ProspectEmailOutreachStatus
from src.email_outbound.services import (
    get_email_messages_with_prospect_transcript_format,
)
from src.email_sequencing.models import EmailSequenceStep, EmailSubjectLineTemplate
from src.prospecting.models import Prospect, ProspectOverallStatus
from src.research.models import AccountResearchPoints, ResearchPoints

from src.ml.models import (
    AIResearcherAnswer,
    AIResearcherQuestion,
)

from src.ml.openai_wrappers import (
    OPENAI_CHAT_GPT_4_MODEL,
    OPENAI_CHAT_GPT_4o_MODEL,
    wrapped_chat_gpt_completion,
)


DEFAULT_INITIAL_EMAIL_TEMPLATE = """<p>Hi [[First name]]</p><p></p><p>[[Personalized first line related to them or their company]]</p><p></p><p>[[Mention what we do and offer, and how it can help them based on their background, company, and key details]]</p><p></p><p>[[Include a brief call to action]]</p><p></p><p>Best,</p><p>[[My name]]</p><p>[[My title]]</p>"""

DEFAULT_FOLLOWUP_EMAIL_TEMPLATE = """<p>Hi [[First name]],</p><p></p><p>I just wanted to followup and ask if you saw my previous message. [[Explain why I think a meeting would be valuable]].</p><p></p><p>[[Thank the prospect for taking the time to read your messages]]</p><p></p><p>Best,</p><p>[[My name]]</p><p>[[My title]]</p>"""

DEFAULT_SUBJECT_LINE_TEMPLATE = (
    """[[Infer a captivating subject line from the email body]]"""
)


def ai_initial_email_prompt(
    client_sdr_id: int,
    prospect_id: int,
    test_template: Optional[str] = None,
    template_id: Optional[int] = None,
    ai_personalization_enabled: Optional[bool] = False,
) -> str:
    """Generate an AI Email Prompt given a prospect. Uses the prospect's sequence step template, otherwise uses a default SellScale template.

    If a test template is provided, it will use that instead of the sequence step template.

    Args:
        client_sdr_id (int): The client SDR ID
        prospect_id (int): The prospect ID
        test_template (Optional[str], optional): The template to test. Defaults to None.
        test_template_id (Optional[int], optional): The sequence step ID to use. Defaults to None.

    Returns:
        str: The AI Email Prompt

    """
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client: Client = Client.query.get(client_sdr.client_id)
    prospect: Prospect = Prospect.query.get(prospect_id)
    client_archetype: ClientArchetype = ClientArchetype.query.get(prospect.archetype_id)
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
    prospect_company_name = prospect.colloquialized_company or prospect.company

    # Collect research points
    prospect_research: list[
        ResearchPoints
    ] = ResearchPoints.get_research_points_by_prospect_id(
        prospect_id=prospect_id,
        email_sequence_step_id=template_id,
    )
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
        EmailSequenceStep.overall_status == ProspectOverallStatus.PROSPECTED,
    ).first()
    if sequence_step is not None:
        template = sequence_step.template

    # Get Sequence Step if it is specified
    if template_id is not None:
        sequence_step: EmailSequenceStep = EmailSequenceStep.query.get(template_id)
        template = sequence_step.template

    # If we are testing a template, use that instead
    if test_template is not None:
        template = test_template

    if ai_personalization_enabled:
        research_points = ""

    prompt = """You are a sales development representative writing on behalf of the salesperson.

Write a personalized cold email with the following objective: {persona_contact_objective}

Write an initial email using the template and only include the personalization information if is is in the template. Stick to the template strictly.

Note - you do not need to include all info.

SDR info --
SDR Name: {client_sdr_name}
Title: {client_sdr_title}

Prospect info --
Prospect Name: {prospect_name}
Prospect Title: {prospect_title}

Prospect Company Name: {prospect_company_name}

More research --
{research_points}

Final instructions
- Do not put generalized fluff, such as "I hope this email finds you well" or "I couldn't help but notice" or  "I noticed".
- Preserve the markdown formatting.
- Feel free to use markdown formatting to make the email look better.
- Prioritize using the Prospect's first name over their full name, unless the template specifies otherwise.

Generate the email body. Do not include the word 'Subject:' or 'Email:' in the output. Do not wrap your answer in quotation marks.

IMPORTANT:
Stick to the template very strictly. Do not deviate from the template:
--- START TEMPLATE ---
{template}
--- END TEMPLATE ---

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
        prospect_company_name=prospect_company_name,
        research_points=research_points,
        persona_contact_objective=prospect_contact_objective,
    )

    return prompt


def ai_followup_email_prompt(
    client_sdr_id: int,
    prospect_id: int,
    thread_id: Optional[str] = None,
    override_sequence_id: Optional[int] = None,
    override_template: Optional[str] = None,
) -> str:
    """Generate an email for a prospect. If override_sequence_id is specified, then that sequence step template will be used in favor of the default.

    Note: If an override template is provided, then the override sequence ID will be ignored.
    Note: This is only applicable to SENT_OUTREACH and BUMPED prospects. ie. No ACTIVE_CONVO, etc. prospects.

    Args:
        client_sdr_id (int): The id of the client sdr
        prospect_id (int): The id of the prospect
        thread_id (Optional[str], optional): The thread id of the email. Defaults to None.
        override_sequence_id (Optional[int], optional): The sequence step ID to use. Defaults to None.
        override_template (Optional[str], optional): The template to test. Defaults to None.
    Returns:
        string: The prompt for the email
    """
    from src.prospecting.nylas.services import get_email_messages_with_prospect

    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client: Client = Client.query.get(client_sdr.client_id)
    prospect: Prospect = Prospect.query.get(prospect_id)
    prospect_email: ProspectEmail = ProspectEmail.query.get(
        prospect.approved_prospect_email_id
    )
    client_archetype: ClientArchetype = ClientArchetype.query.get(prospect.archetype_id)
    account_research: list[AccountResearchPoints] = AccountResearchPoints.query.filter(
        AccountResearchPoints.prospect_id == prospect.id
    ).all()

    # If Prospect is not in SENT_OUTREACH or BUMPED and we are not overriding the sequence step, then we should not be following up with them
    # Example: Prospect is in Active Conversation state, we shouldn't send a bump email
    # TODO: Eventually have intelligent systems that can handle automatically responding to prospect replies.
    if (
        prospect.overall_status
        not in [
            ProspectOverallStatus.SENT_OUTREACH,
            ProspectOverallStatus.BUMPED,
            ProspectOverallStatus.ACCEPTED,
        ]
        and override_sequence_id is None
        and override_template is None
    ):
        raise Exception(
            "Prospect is not in SENT_OUTREACH or BUMPED or ACCEPTED status and shouldn't be followed up with."
        )

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
    ] = ResearchPoints.get_research_points_by_prospect_id(
        prospect_id=prospect_id,
        email_sequence_step_id=override_sequence_id,
    )
    research_points = ""
    for point in prospect_research:
        research_points += f"- {point.value}\n"
    account_points = ""
    for point in account_research:
        account_points += f"- {point.title}: {point.reason}\n"

    # If we have a thread ID, get past messages in a transcript format
    email_transcript = "NO PAST THREAD AVAILABLE"
    if thread_id is not None:
        email_transcript = get_email_messages_with_prospect_transcript_format(
            client_sdr_id=client_sdr_id,
            prospect_id=prospect_id,
            thread_id=thread_id,
        )

    # Use the Default SellScale Template as the template
    template = DEFAULT_FOLLOWUP_EMAIL_TEMPLATE

    # Get the template from the sequence step
    if override_sequence_id:
        sequence_step: EmailSequenceStep = EmailSequenceStep.query.get(
            override_sequence_id
        )
        template = sequence_step.template
    elif override_template:
        template = override_template
    else:
        # Get the template from the sequence step
        if prospect.overall_status in [
            ProspectOverallStatus.SENT_OUTREACH,
            ProspectOverallStatus.ACCEPTED,
        ]:
            sequence_step: EmailSequenceStep = EmailSequenceStep.query.filter(
                EmailSequenceStep.client_sdr_id == client_sdr_id,
                EmailSequenceStep.client_archetype_id == client_archetype.id,
                EmailSequenceStep.active == True,
                EmailSequenceStep.overall_status == ProspectOverallStatus.ACCEPTED,
                EmailSequenceStep.template != None,
            ).first()
            if sequence_step is not None:
                template = sequence_step.template
            else:
                send_slack_message(
                    message=f"⚠️ No sequence step found for archetype '{client_archetype.archetype}' for SDR '{client_sdr.name}'. status=SENT_OUTREACH",
                    webhook_urls=[URL_MAP["operations-auto-bump-email"]],
                )
                return None
        elif prospect.overall_status == ProspectOverallStatus.BUMPED:
            sequence_step: EmailSequenceStep = EmailSequenceStep.query.filter(
                EmailSequenceStep.client_sdr_id == client_sdr_id,
                EmailSequenceStep.client_archetype_id == client_archetype.id,
                EmailSequenceStep.active == True,
                EmailSequenceStep.overall_status == ProspectOverallStatus.BUMPED,
                EmailSequenceStep.bumped_count == prospect_email.times_bumped,
                EmailSequenceStep.template != None,
            ).first()
            if sequence_step is not None:
                template = sequence_step.template
            else:
                send_slack_message(
                    message=f"⚠️ No sequence step found for archetype '{client_archetype.archetype}' for SDR '{client_sdr.name}'. status=BUMPED & bumped_count={prospect_email.times_bumped}",
                    webhook_urls=[URL_MAP["operations-auto-bump-email"]],
                )
                return None

    send_slack_message(
        message=f"About to use template for archetype '{client_archetype.archetype}' for SDR '{client_sdr.name}'. status={prospect.overall_status} & bumped_count={prospect_email.times_bumped if prospect_email else 'None'}\n'{template}'",
        webhook_urls=[URL_MAP["operations-auto-bump-email"]],
    )

    prompt = """You are a sales development representative writing on behalf of the salesperson.

Write a follow up email to the previous email using the template and only include the information if is is in the template. Stick to the template strictly.

Note - you do not need to include all info.

SDR info --
SDR Name: {client_sdr_name}
Title: {client_sdr_title}

Prospect info --
Prospect Name: {prospect_name}
Prospect Title: {prospect_title}

Prospect Company Name: {prospect_company_name}

More research --
{prospect_research}
{research_points}

Final instructions
- Do not put generalized fluff, such as "I hope this email finds you well" or "I couldn't help but notice" or  "I noticed"
- Preserve the markdown formatting.
- Feel free to use markdown formatting to make the email look better.

Generate the email body. Do not include the word 'Subject:' or 'Email:' in the output.

Here's the template, everything in brackets should be replaced by you. For example: [[prospect_name]] should be replaced by the prospect's name.

IMPORTANT:
Stick to the template very strictly. Do not change this template at all. Do not deviate from the template:
--- START TEMPLATE ---
{template}
--- END TEMPLATE ---

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
        prospect_company_name=prospect_company_name,
        prospect_research=account_points,
        research_points=research_points,
        persona_contact_objective=prospect_contact_objective,
        past_threads="",  # TODO: email_transcript
    )

    return prompt


def ai_multichannel_email_prompt(
    prospect_id: int,
) -> str:
    """Generate a multichannel email prompt. LinkedIn -> Email.

    Args:
        prospect_id (int): The ID of the prospect

    Returns:
        str: The multichannel email prompt
    """
    li_transcript = get_li_convo_history_transcript_form(prospect_id=prospect_id)

    prospect: Prospect = Prospect.query.get(prospect_id)
    client_sdr: ClientSDR = ClientSDR.query.get(prospect.client_sdr_id)
    client: Client = Client.query.get(client_sdr.client_id)

    prompt = """You are a sales development representative writing on behalf of the salesperson.

You are continuing this LinkedIn conversation from a different channel: Email.

=== LINKEDIN CONVERSATION ===

{transcript}

=== END LINKEDIN CONVERSATION ===

Please write an email that transitions seamlessly from the LinkedIn conversation to Email. You can use the following information.

SDR Information:
SDR Name: {sdr_name}
SDR Company: {sdr_company}

Prospect Information:
Prospect Name: {prospect_name}
Prospect Company: {prospect_company}

Generate the email body. Do not include the word 'Subject:' or 'Email:' in the output. Do not wrap your answer in quotation marks.

Be casual and conversational. Do not use any jargon or buzzwords. Do not use any fluff. Do not come off as salesy.

USE HTML FORMATTING. For example: <p>Hey there!</p>.
""".format(
        transcript=li_transcript,
        sdr_name=client_sdr.name,
        sdr_company=client.company,
        prospect_name=prospect.full_name,
        prospect_company=prospect.company,
    )

    return prompt


def generate_email(
    prompt: str, model: Optional[str] = OPENAI_CHAT_GPT_4_MODEL
) -> dict[str, str]:
    """Generate an email for a prospect.

    Args:
        prompt (str): The prompt to generate the email with
        model (Optional[str], optional): The model to use. Defaults to OPENAI_CHAT_GPT_4_MODEL.

    Returns:
        dict[str, str]: The subject and body of the email
    """
    response = get_text_generation(
        [
            {"role": "system", "content": prompt},
        ],
        max_tokens=400,
        temperature=0.3,
        model=model,
        type="EMAIL",
    )

    return {"body": response}


def ai_subject_line_prompt(
    client_sdr_id: int,
    prospect_id: int,
    email_body: str,
    subject_line_template_id: Optional[int] = None,
    test_template: Optional[str] = None,
) -> str:
    """Generate a subject line prompt for a prospect.

    Args:
        client_sdr_id (int): ID of the client SDR
        prospect_id (int): ID of the prospect
        email_body (str): The email body
        subject_line_template_id (Optional[int], optional): The subject line template ID. Defaults to None.
        test_template (Optional[str], optional): The template to test. Defaults to None.

    Returns:
        str: The subject line prompt
    """
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    # client: Client = Client.query.get(client_sdr.client_id)
    prospect: Prospect = Prospect.query.get(prospect_id)
    # client_archetype: ClientArchetype = ClientArchetype.query.get(prospect.archetype_id)
    # account_research: list[AccountResearchPoints] = AccountResearchPoints.query.filter(
    #     AccountResearchPoints.prospect_id == prospect.id
    # ).all()

    # Collect company information
    # client_sdr_name = client_sdr.name
    # client_sdr_title = client_sdr.title
    # company_tagline = client.tagline
    # company_description = client.description
    # company_value_prop_key_points = client.value_prop_key_points
    # company_tone_attributes = (
    #     ", ".join(client.tone_attributes) if client.tone_attributes else ""
    # )

    # Collect persona information
    # persona_name = client_archetype.archetype
    # persona_buy_reason = client_archetype.persona_fit_reason
    prospect_name = prospect.full_name
    prospect_title = prospect.title
    prospect_bio = prospect.linkedin_bio
    prospect_company_name = prospect.colloquialized_company or prospect.company

    # Collect research points
    # prospect_research: list[
    #     ResearchPoints
    # ] = ResearchPoints.get_research_points_by_prospect_id(prospect_id)
    # research_points = ""
    # for point in prospect_research:
    #     research_points += f"- {point.value}\n"
    # account_points = ""
    # for point in account_research:
    #     account_points += f"- {point.title}: {point.reason}\n"

    subject_line = DEFAULT_SUBJECT_LINE_TEMPLATE

    # Get the template using the provided ID
    if subject_line_template_id is not None:
        subject_line_template: EmailSubjectLineTemplate = (
            EmailSubjectLineTemplate.query.get(subject_line_template_id)
        )
        subject_line = subject_line_template.subject_line
    elif test_template is not None:
        subject_line = test_template

    prompt = """Given the following email body, please write a subject line that would be most likely to get a response from the prospect.
-- START EMAIL BODY --
{email_body}
-- END EMAIL BODY --

Here are some facts about the prospect:
Prospect Name: {prospect_name}
Prospect Title: {prospect_title}
Prospect Company: {prospect_company_name}

Do not include the word 'Subject:' in the output. Do not include quotations.

IMPORTANT:
Use the following subject line template strictly. Stick to the template strictly and do not deviate from the template:
--- START TEMPLATE ---
{template}
--- END TEMPLATE ---

Return only the subject line. Do not include the word 'Subject:' in the output.

Output:""".format(
        email_body=email_body,
        prospect_name=prospect_name,
        prospect_title=prospect_title,
        prospect_company_name=prospect_company_name,
        template=subject_line,
    )

    return prompt


def generate_subject_line(prompt: str) -> dict[str, str]:
    """Generate a subject line for a prospect.

    Args:
        prompt (str): The prompt to generate the subject line with

    Returns:
        dict[str, str]: The subject line
    """
    response = get_text_generation(
        [
            {"role": "system", "content": prompt},
        ],
        max_tokens=50,
        temperature=0.3,
        model=OPENAI_CHAT_GPT_4_MODEL,
        type="EMAIL",
    )
    response = response.strip('"')

    return {"subject_line": response}


def generate_magic_subject_line(campaign_id: int, prospect_id: int, sequence_id: int, generate_email: bool = False, room_id: Optional[str] = None, subject_line_id: Optional[int] = None) -> str:
    """Generate a magic subject line for a prospect.

    Args:
        campaign_id (int): The ID of the campaign
        prospect_id (int): The ID of the prospect

    Returns:
        str: The magic subject line
    """
    prospect: Prospect = Prospect.query.get(prospect_id)
    campaign: ClientArchetype = ClientArchetype.query.get(campaign_id)

    if(room_id):
        send_socket_message('subject-stream', {"step": 1, 'room_id': room_id}, room_id)

    
    run_all_ai_researcher_questions_for_prospect(prospect.client_sdr_id, prospect_id, room_id, False)

    if(room_id):
        send_socket_message('subject-stream', {"step": 2, 'room_id': room_id}, room_id)

    ai_research_points: list[AIResearcherAnswer] = AIResearcherAnswer.query.filter_by(prospect_id=prospect_id).all()

    ai_researcher_id = campaign.ai_researcher_id
    ai_questions = AIResearcherQuestion.query.filter_by(researcher_id=ai_researcher_id).all()

    email_body = EmailSequenceStep.query.get(sequence_id).template

    if (generate_email):
        try:
            email_body = get_generated_email(
                email_body=email_body,
                prospectId=prospect_id,
            )
        except Exception as e:
            print(e)

    if (subject_line_id):
        if(room_id):
            send_socket_message('subject-stream', {"step": 3, 'room_id': room_id}, room_id)
        subjectline_template: EmailSubjectLineTemplate = EmailSubjectLineTemplate.query.get(subject_line_id)
        if not subjectline_template.is_magic_subject_line:
            subject_line_strict = False
            subject_line_strict = (
                "[[" not in subjectline_template.subject_line
                and "{{" not in subjectline_template.subject_line
            )
            subject_line = subjectline_template.subject_line
            if (subject_line_strict):
                pass
            elif (not subject_line_strict):
                subject_line_prompt = ai_subject_line_prompt(
                client_sdr_id=prospect.client_sdr_id,
                prospect_id=prospect_id,
                email_body=email_body,
                subject_line_template_id=subjectline_template.id,
            )
                #replace subject line if there were brackets.
                subject_line = generate_subject_line(prompt=subject_line_prompt)
                subject_line = subject_line.get("subject_line")
                # subjectline_template.subject_line = subject_line_prompt
                # db.session.commit()
            return subject_line, email_body

    if(room_id):
        send_socket_message('subject-stream', {"step": 3, 'room_id': room_id}, room_id)
    
    prompt = '''
    # Purpose:
    You are a catchy subject line generator. 
    The subject lines should be informal, be inherently friendly, 
    and mention something specific or internal about the target company.

    ### Bad subject lines
    - “50% off!”
    - “Act Now!”
    - “Limited Time Offer!”
    - “Don't Miss Out!”
    - “Buy One Get One Free!”
    - “Sale Ends Soon!”
    - “Exclusive Deal Just for You!”
    - “Hurry, While Supplies Last!”
    - “Special Discount Inside!”
    - “Save Big Today!”
    - “Unlock Your Savings!”
    - “Best Price Guaranteed!”
    - “Flash Sale Alert!”
    - “Time-Sensitive Offer!”
    - “Exclusive Access!”
    - “Limited Stock Available!”
    - “Final Hours to Save!”
    - “Price Drop!”
    - “Clearance Sale!”
    - “Today Only!”
    - “Act Fast!”
    - "Unlocking AI-Powered Sales Growth"
    - Anything including the name of the person followed by a comma

    Good subject lines are:

    ### GOOD EXAMPLE
    **Person:** 
    Barry Carter (#288346) Vice President of Infrastructure and Cloud, 711
    
    **Good Subject line:**
    7-Eleven meets 24/7 innovation
    
    **Body corresponding to the good subject line:**
    Hi Barry,
    
    I noticed 7-Eleven Japan has been actively exploring GenAI for product planning and edge AI vision detection. At JK Tech, we've developed Gen AI accelerators to help Retail and CPG companies like 7-Eleven deploy AI use cases quickly. We address key challenges like synthesizing structured and unstructured data, protecting sensitive information & access management, and providing an auditable path for AI responses.
    
    Given your role as Vice President of Infrastructure and Cloud, I'd love to show you how we can tailor solutions for 7-Eleven. Are you open to a call next week to discuss how our insights could enhance your GenAI initiatives?
    
    Best regards,
    Becky Pallett
    
    **Reasoning:**
    - 7-Eleven and 24/7 innovation is witty.
    - It uses 7-Eleven and 24/7 as a play with numbers.
    - 24/7 is also how long 711 is open.
    - Finally, 24/7 innovation connects with the body of the email of providing innovation. It's nice and short.

    some more samples of good ones

    Looking to Connect

    Your Take on This?

    Pear studio coffee chats!

    Now, Here's the information you should use to generate the subject line:

    Prospect name, title, and company: {prospect_name}, {prospect_title} at {prospect_company}

    Research points:
    {ai_research_questions}
    {ai_research_answers}

    Email body:
    {email_body}

    Please output ONLY a catchy, even punny, subject line that would increase the open rate of the email. Do not include the word 'Subject:' in the output. Do not include quotations.
    Just the subject line, please.    

    Good subject lines are:
    - 1-4 words
    - Avoid buzzwords (to avoid spam detectors)
    - Sounds friendly or witty.
    - Relate to the prospect's industry or role
    - Include a hint of personalization
    - Create a sense of curiosity or urgency
    - It should not sound like a sales pitch
    - It should not sound generic
    - It should not be a question
    
    Output:'''.format(
        prospect_name=prospect.first_name if prospect.first_name else prospect.full_name, 
        prospect_title=prospect.colloquialized_title if prospect.colloquialized_title else prospect.title,
        prospect_company=prospect.colloquialized_company if prospect.colloquialized_company else prospect.company, 
        ai_research_questions='\n'.join([f'- {question.key}' for question in ai_questions]), 
        ai_research_answers='\n'.join([f'- {answer.raw_response}' for answer in ai_research_points]), 
        email_body=email_body
    )

    answer = wrapped_chat_gpt_completion(
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ],
        model='claude-3-opus-20240229',
        max_tokens=50
        )
    answer = answer.strip('"')

    return answer, email_body


def create_email_automated_reply_entry(
    prospect_id: int,
    client_sdr_id: int,
    prompt: str,
    email_body: str,
) -> int:
    """Create an EmailAutomatedReply entry.

    Args:
        prospect_id (int): ID of the prospect
        client_sdr_id (int): ID of the client SDR
        prompt (str): The prompt used to generate the email
        email_body (str): The email body

    Returns:
        int: The ID of the EmailAutomatedReply entry
    """
    email_automated_reply = EmailAutomatedReply(
        prospect_id=prospect_id,
        client_sdr_id=client_sdr_id,
        prompt=prompt,
        email_body=email_body,
    )
    db.session.add(email_automated_reply)
    db.session.commit()

    return email_automated_reply.id


def get_email_automated_reply_entry(
    prospect_id: int,
) -> list[dict]:
    """Get an EmailAutomatedReply entry.

    Args:
        prospect_id (int): The ID of the prospect.

    Returns:
        dict: The EmailAutomatedReply entry
    """
    automated_replies_query = EmailAutomatedReply.query.filter(
        EmailAutomatedReply.prospect_id == prospect_id,
    ).order_by(EmailAutomatedReply.id.desc())
    automated_replies: list[EmailAutomatedReply] = automated_replies_query.all()

    return [automated_reply.to_dict() for automated_reply in automated_replies]
