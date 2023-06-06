from app import db

from src.bump_framework.models import BumpFramework, BumpLength, JunctionBumpFrameworkClientArchetype
from src.client.models import ClientArchetype
from src.prospecting.models import ProspectOverallStatus, ProspectStatus


def create_default_bump_frameworks(client_sdr_id: int) -> int:
    """Creates a set of default BumpFramework entries for a given client_sdr_id.

    Args:
        client_sdr_id (int): The id of the client_sdr

    Returns:
        int: The number of BumpFramework entries created
    """
    # Get all bump frameworks that have sellscale_default_generated = True
    bump_frameworks: list[BumpFramework] = BumpFramework.query.filter(
        BumpFramework.client_sdr_id == client_sdr_id,
        BumpFramework.sellscale_default_generated == True,
    ).all()

    # If they exist, return 0 (no new bump frameworks created)
    if len(bump_frameworks) > 0:
        return 0

    # Create the default bump frameworks
    default_bump_frameworks: list[BumpFramework] = []
    for default_bump_framework in DEFAULT_BUMP_FRAMEWORKS:
        bf = BumpFramework(
            client_sdr_id=client_sdr_id,
            title=default_bump_framework["title"],
            description=default_bump_framework["description"],
            active=True,
            overall_status=default_bump_framework["overall_status"],
            substatus=default_bump_framework["substatus"],
            default=True,
            bump_length=default_bump_framework["bump_length"],
            sellscale_default_generated=True,
        )
        db.session.add(bf)
        default_bump_frameworks.append(bf)
    db.session.commit()

    # Create the default junctions
    client_archetypes: list[ClientArchetype] = ClientArchetype.query.filter(
        ClientArchetype.client_sdr_id == client_sdr_id,
    ).all()
    for bump_framework in default_bump_frameworks:
        for client_archetype in client_archetypes:
            junction = JunctionBumpFrameworkClientArchetype(
                bump_framework_id=bump_framework.id,
                client_archetype_id=client_archetype.id,
            )
            db.session.add(junction)
    db.session.commit()

    return len(default_bump_frameworks)


def add_archetype_to_default_bump_frameworks(client_sdr_id: int, archetype_id: int) -> None:
    """Adds an archetype to the default bump frameworks

    Args:
        client_sdr_id (int): The id of the client_sdr
        archetype_id (int): The id of the archetype to add
    """
    # Get all bump frameworks that have sellscale_default_generated = True
    bump_frameworks: list[BumpFramework] = BumpFramework.query.filter(
        BumpFramework.client_sdr_id == client_sdr_id,
        BumpFramework.sellscale_default_generated == True,
    ).all()

    # Get the archetype
    archetype: ClientArchetype = ClientArchetype.query.filter(
        ClientArchetype.id == archetype_id,
        ClientArchetype.client_sdr_id == client_sdr_id,
    ).first()

    # Add the archetype to the default bump frameworks
    for bump_framework in bump_frameworks:
        junction = JunctionBumpFrameworkClientArchetype(
            bump_framework_id=bump_framework.id,
            client_archetype_id=archetype.id,
        )
        db.session.add(junction)
    db.session.commit()

    return


DEFAULT_BUMP_FRAMEWORKS = [
    {
        "title": "Introduction",
        "description": "Introduce ourself and explain why we can help them.",
        "overall_status": ProspectOverallStatus.ACCEPTED,
        "substatus": None,
        "bump_length": BumpLength.MEDIUM
    },
    {
        "title": "Follow Up #1",
        "description": "Write a short, 1-2 sentence bump. Do not use the word 'bump'.",
        "overall_status": ProspectOverallStatus.BUMPED,
        "substatus": None,
        "bump_length": BumpLength.SHORT
    },
    {
        "title": "Follow Up #2",
        "description": "Write a longer follow up about their company and how we can help.",
        "overall_status": ProspectOverallStatus.BUMPED,
        "substatus": None,
        "bump_length": BumpLength.MEDIUM
    },
    {
        "title": "Follow Up #3",
        "description": "Write one, final short follow up.",
        "overall_status": ProspectOverallStatus.BUMPED,
        "substatus": None,
        "bump_length": BumpLength.SHORT
    },
    {
        "title": "Scheduling",
        "description": "Ask them what time they're available.",
        "overall_status": ProspectOverallStatus.ACTIVE_CONVO,
        "substatus": ProspectStatus.ACTIVE_CONVO_SCHEDULING.value,
        "bump_length": BumpLength.MEDIUM
    },
    {
        "title": "Not Interested",
        "description": "Ask why they are not interested and if we can address any of their concerns.",
        "overall_status": ProspectOverallStatus.ACTIVE_CONVO,
        "substatus": ProspectStatus.ACTIVE_CONVO_OBJECTION.value,
        "bump_length": BumpLength.MEDIUM
    },
]
