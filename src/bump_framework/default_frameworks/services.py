from app import db

from src.bump_framework.models import BumpFramework, BumpLength
from src.bump_framework.services import create_bump_framework
from src.client.models import ClientArchetype
from src.prospecting.models import ProspectOverallStatus, ProspectStatus


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
        )

    return len(DEFAULT_BUMP_FRAMEWORKS)


DEFAULT_BUMP_FRAMEWORKS = [
    {
        "title": "Introduction",
        "description": "Introduce ourself and explain why we can help them.",
        "overall_status": ProspectOverallStatus.ACCEPTED,
        "substatus": None,
        "bump_length": BumpLength.MEDIUM,
        "bumped_count": 0,
    },
    {
        "title": "Follow Up #2",
        "description": "Write a short, 1-2 sentence bump. Do not use the word 'bump'.",
        "overall_status": ProspectOverallStatus.BUMPED,
        "substatus": None,
        "bump_length": BumpLength.SHORT,
        "bumped_count": 1,

    },
    {
        "title": "Follow Up #3",
        "description": "Write a longer follow up about their company and how we can help.",
        "overall_status": ProspectOverallStatus.BUMPED,
        "substatus": None,
        "bump_length": BumpLength.MEDIUM,
        "bumped_count": 2,
    },
    {
        "title": "Follow Up #4",
        "description": "Write one, final short follow up.",
        "overall_status": ProspectOverallStatus.BUMPED,
        "substatus": None,
        "bump_length": BumpLength.SHORT,
        "bumped_count": 3,
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
