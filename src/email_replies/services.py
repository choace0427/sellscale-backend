from app import db

from typing import Optional
from src.client.models import Client, ClientSDR
from src.email_outbound.models import ProspectEmail
from src.email_replies.models import EmailReplyFramework
from src.ml.openai_wrappers import OPENAI_CHAT_GPT_4_MODEL, wrapped_chat_gpt_completion

from src.prospecting.models import Prospect, ProspectOverallStatus
from src.research.models import AccountResearchPoints, ResearchPointType, ResearchPoints


def get_email_reply_frameworks(
    client_sdr_id: Optional[int], active_only: Optional[bool] = True
) -> list[dict]:
    """Get all EmailReplyFrameworks

    Args:
        client_sdr_id (Optional[int]): ID of the ClientSDR to filter by
        active_only (Optional[bool]): Whether or not to only return active EmailReplyFrameworks

    Returns:
        list: List of EmailReplyFrameworks
    """
    # Get the SellScale reply_frameworks (no ClientSDR)
    reply_frameworks: list[EmailReplyFramework] = EmailReplyFramework.query.filter(
        EmailReplyFramework.client_sdr_id == None,
        EmailReplyFramework.client_archetype_id == None,
    ).all()

    # Get the ClientSDR reply_frameworks
    if client_sdr_id:
        client_sdr_reply_frameworks: list[
            EmailReplyFramework
        ] = EmailReplyFramework.query.filter(
            EmailReplyFramework.client_sdr_id == client_sdr_id
        ).all()

        reply_frameworks.extend(client_sdr_reply_frameworks)

    # Filter out inactive reply_frameworks
    if active_only:
        reply_frameworks = [
            reply_framework
            for reply_framework in reply_frameworks
            if reply_framework.active
        ]

    return [reply_framework.to_dict for reply_framework in reply_frameworks]


def create_email_reply_framework(
    title: str,
    description: Optional[str],
    client_sdr_id: Optional[int],
    client_archetype_id: Optional[int],
    overall_status: Optional[ProspectOverallStatus],
    substatus: Optional[str],
    template: Optional[str],
    additional_instructions: Optional[str],
    research_blocklist: Optional[list[ResearchPointType]],
    use_account_research: Optional[bool],
) -> int:
    """Create an EmailReplyFramework

    Args:
        title (str): Title of the new EmailReplyFramework
        description (Optional[str]): Description of the new EmailReplyFramework
        client_sdr_id (Optional[int]): ID of the ClientSDR to associate with the new EmailReplyFramework
        client_archetype_id (Optional[int]): ID of the ClientArchetype to associate with the new EmailReplyFramework
        overall_status (Optional[ProspectOverallStatus]): The ProspectOverallStatus to associate with the new EmailReplyFramework
        substatus (Optional[str]): The substatus to associate with the new EmailReplyFramework
        template (Optional[str]): The template to associate with the new EmailReplyFramework
        additional_instructions (Optional[str]): The additional instructions to associate with the new EmailReplyFramework
        research_blocklist (Optional[list]): The research blocklist (used to generate messages)
        use_account_research (Optional[bool]): Whether or not to use account research (used to generate messages)

    Returns:
        int: ID of the new EmailReplyFramework
    """
    reply_framework = EmailReplyFramework(
        title=title,
        description=description,
        client_sdr_id=client_sdr_id,
        client_archetype_id=client_archetype_id,
        overall_status=overall_status,
        substatus=substatus,
        template=template,
        additional_instructions=additional_instructions,
        research_blocklist=research_blocklist,
        use_account_research=use_account_research,
    )
    db.session.add(reply_framework)
    db.session.commit()

    return reply_framework.id


def edit_email_reply_framework(
    reply_framework_id: int,
    title: Optional[str],
    description: Optional[str],
    active: Optional[bool],
    template: Optional[str],
    additional_instructions: Optional[str],
    research_blocklist: Optional[list[ResearchPointType]],
    use_account_research: Optional[bool],
) -> bool:
    """Edit an EmailReplyFramework

    Args:
        reply_framework_id (int): ID of the EmailReplyFramework to edit
        title (Optional[str]): Title of the EmailReplyFramework
        description (Optional[str]): Description of the EmailReplyFramework
        active (Optional[bool]): Whether or not the EmailReplyFramework is active
        template (Optional[str]): The template to associate with the EmailReplyFramework
        additional_instructions (Optional[str]): The additional instructions to associate with the EmailReplyFramework
        research_blocklist (Optional[list]): The research blocklist (used to generate messages)
        use_account_research (Optional[bool]): Whether or not to use account research (used to generate messages)

    Returns:
        bool: Whether or not the EmailReplyFramework was successfully edited
    """
    reply_framework: EmailReplyFramework = EmailReplyFramework.query.get(
        reply_framework_id
    )

    if title:
        reply_framework.title = title
    if description:
        reply_framework.description = description
    if active is not None:
        reply_framework.active = active
    if template:
        reply_framework.template = template
    if additional_instructions:
        reply_framework.additional_instructions = additional_instructions
    if research_blocklist:
        reply_framework.research_blocklist = research_blocklist
    if use_account_research is not None:
        reply_framework.use_account_research = use_account_research

    db.session.commit()

    return True


def generate_reply_using_framework(
    reply_framework_id: int,
    prospect_id: int,
) -> str:
    """Generate a reply using an EmailReplyFramework

    Args:
        reply_framework_id (int): ID of the EmailReplyFramework to use
        prospect_id (int): ID of the Prospect to generate a reply for

    Returns:
        str: Generated reply
    """
    # Get the EmailReplyFramework
    reply_framework: EmailReplyFramework = EmailReplyFramework.query.get(
        reply_framework_id
    )
    if not reply_framework:
        return None

    # Get the Prospect
    prospect: Prospect = Prospect.query.get(prospect_id)
    if not prospect:
        return None
    prospect_email: ProspectEmail = ProspectEmail.query.get(
        prospect.approved_prospect_email_id
    )
    if not prospect_email:
        return None

    # Get the ResearchPoints
    research_points = ResearchPoints.get_research_points_by_prospect_id(
        prospect_id=prospect_id, email_reply_framework_id=reply_framework_id
    )
    research_points_str = "\n".join(
        [
            "• " + rp.value
            for rp in research_points
            if rp.value and rp.value.strip() != ""
        ]
    )
    account_research_points_str = ""
    if reply_framework.use_account_research:
        account_research_points: list[
            AccountResearchPoints
        ] = AccountResearchPoints.query.filter(
            AccountResearchPoints.prospect_id == prospect_id,
        ).all()
        account_research_points_str = "\n".join(
            [
                "• " + arp.reason
                for arp in account_research_points
                if arp.reason and arp.reason.strip() != ""
            ]
        )

    client_sdr: ClientSDR = ClientSDR.query.get(prospect.client_sdr_id)
    client: Client = Client.query.get(client_sdr.client_id)

    prompt = f"""You are a sales development representative writing on behalf of a salesperson.

Please write an email reply to the last email from the prospect.

Note - you do not need to include all info.

SDR info:
SDR Name: {client_sdr.name}

Company info:
Tagline: {client.tagline}
Company Description: {client.description}

Prospect info:
Prospect Name: {prospect.full_name}
Prospect Title: {prospect.title}
Prospect Industry: {prospect.industry}
Prospect Company: {prospect.company}
=== Last Email ===
{prospect_email.last_message}
=== End Last Email ===

Research on the Prospect:
{research_points_str}
{account_research_points_str}

Additional instructions:
- Don't make any [[brackets]] longer than 1 sentence when filled in.
{reply_framework.additional_instructions}

Generate the email body. Do not include the word 'Subject:' or 'Email:' in the output. Preserve the HTML formatting for the email body.

IMPORTANT:
Stick to the template very strictly. Do not change this template at all.  Similar to madlibs, only fill in text where there's a double bracket (ex. [[personalization]] ).
--- START TEMPLATE ---
{reply_framework.template}
--- END TEMPLATE ---

Output:"""

    print(prompt)

    response = wrapped_chat_gpt_completion(
        messages=[{"role": "user", "content": prompt}],
        max_tokens=500,
        model=OPENAI_CHAT_GPT_4_MODEL,
    )

    return response
