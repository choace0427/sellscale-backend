from app import db

from typing import Optional
from src.email_replies.models import EmailReplyFramework

from src.prospecting.models import ProspectOverallStatus
from src.research.models import ResearchPointType


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
