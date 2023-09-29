from app import db

from src.bump_framework.models import BumpFramework, BumpLength
from src.bump_framework.services import create_bump_framework
from src.client.models import ClientArchetype
from src.prospecting.models import ProspectOverallStatus, ProspectStatus
from src.research.models import ResearchPointType


def create_default_bump_frameworks(client_sdr_id: int, client_archetype_id: int) -> int:
    """Creates a set of default BumpFramework entries for a given client_sdr_id and archetype_id

    Args:
        client_sdr_id (int): The id of the client_sdr
        archetype_id (int): The id of the archetype

    Returns:
        int: The number of BumpFramework entries created
    """
    # Get all bump frameworks that have sellscale_default_generated = True
    bump_frameworks: list[BumpFramework] = BumpFramework.query.filter(
        BumpFramework.client_sdr_id == client_sdr_id,
        BumpFramework.client_archetype_id == client_archetype_id,
        BumpFramework.sellscale_default_generated == True,
    ).all()

    # If they exist, return 0 (no new bump frameworks created)
    if len(bump_frameworks) > 0:
        return 0

    # Create the default bump frameworks
    for default_bump_framework in DEFAULT_BUMP_FRAMEWORKS:
        create_bump_framework(
            client_sdr_id=client_sdr_id,
            client_archetype_id=client_archetype_id,
            title=default_bump_framework["title"],
            description=default_bump_framework["description"],
            overall_status=default_bump_framework["overall_status"],
            length=default_bump_framework["bump_length"],
            bumped_count=default_bump_framework["bumped_count"],
            active=True,
            substatus=default_bump_framework["substatus"],
            default=True,
            sellscale_default_generated=True,
            bump_framework_template_name=default_bump_framework[
                "bump_framework_template_name"
            ]
            if "bump_framework_template_name" in default_bump_framework
            else None,
            bump_framework_human_readable_prompt=default_bump_framework[
                "bump_framework_human_readable_prompt"
            ]
            if "bump_framework_human_readable_prompt" in default_bump_framework
            else None,
            additional_context=default_bump_framework["additional_context"]
            if "additional_context" in default_bump_framework
            else None,
            transformer_blocklist=default_bump_framework["transformer_blocklist"]
            if "transformer_blocklist" in default_bump_framework
            else [],
        )

    return len(DEFAULT_BUMP_FRAMEWORKS)


DEFAULT_BUMP_FRAMEWORKS = [
    {
        "title": "Pain Points Opener",
        "description": "1. Thank them for connecting\n2. Connect with their role and any pain points that they have in their role based on what our company does\n3. How is it going with pain points they my face in their role?",
        "overall_status": ProspectOverallStatus.ACCEPTED,
        "substatus": None,
        "bump_length": BumpLength.MEDIUM,
        "bumped_count": 0,
        "bump_framework_template_name": "pain_points_opener",
        "bump_framework_human_readable_prompt": "Tap into a potential pain point that they may have in their role and connect with them on that",
        "additional_context": "What pain points would this persona have? (bullet points)\nAnswer: \n- _________________",
        "transformer_blocklist": [
            x.value
            for x in ResearchPointType
            if x.value
            not in ["CURRENT_EXPERIENCE_DESCRIPTION", "CURRENT_JOB_DESCRIPTION"]
        ],
    },
    {
        "title": "Introduction to Us",
        "description": "1. Introduce what [our company] does\n2. Connect with them using [their profile]\n3. Ask if they're open to chat for 15 minutes",
        "overall_status": ProspectOverallStatus.BUMPED,
        "substatus": None,
        "bump_length": BumpLength.MEDIUM,
        "bumped_count": 1,
        "bump_framework_template_name": "introduction_to_us",
        "bump_framework_human_readable_prompt": "Introduce what our company does and connect with them using their profile",
        "additional_context": "",
        "transformer_blocklist": [],
    },
    {
        "title": "Short Follow Up Related to Role",
        "description": "Do a short follow-up acknowledging they're busy using their role description - and that we'd love to chat about any [relevant painpoints their role may face]",
        "overall_status": ProspectOverallStatus.BUMPED,
        "substatus": None,
        "bump_length": BumpLength.SHORT,
        "bumped_count": 2,
        "bump_framework_template_name": "short_follow_up_related_to_role",
        "bump_framework_human_readable_prompt": "Do a short follow-up acknowledging they're busy using their role description - and that we'd love to chat about any relevant painpoints their role may face",
        "additional_context": "Which pain points would this persona have? (bullet points)\nAnswer: \n- _________________",
        "transformer_blocklist": [],
    },
    {
        "title": "Any other person?",
        "description": "Ask if there's another person better to connect regarding the pain points our product solves.",
        "overall_status": ProspectOverallStatus.BUMPED,
        "substatus": None,
        "bump_length": BumpLength.SHORT,
        "bumped_count": 3,
        "bump_framework_template_name": "any_other_person",
        "bump_framework_human_readable_prompt": "Ask if there's another person better to connect regarding the pain points our product solves",
        "additional_context": "",
        "transformer_blocklist": [],
    },
    {
        "title": "Scheduling",
        "description": "Ask them what time they're available.",
        "overall_status": ProspectOverallStatus.ACTIVE_CONVO,
        "substatus": ProspectStatus.ACTIVE_CONVO_SCHEDULING.value,
        "bump_length": BumpLength.MEDIUM,
        "bumped_count": None,
    },
    {
        "title": "Not Interested",
        "description": "Ask why they are not interested and if we can address any of their concerns.",
        "overall_status": ProspectOverallStatus.ACTIVE_CONVO,
        "substatus": ProspectStatus.ACTIVE_CONVO_OBJECTION.value,
        "bump_length": BumpLength.MEDIUM,
        "bumped_count": None,
    },
]
