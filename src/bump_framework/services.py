from model_import import BumpFramework
from app import db
from src.bump_framework.models import BumpLength, JunctionBumpFrameworkClientArchetype
from src.client.models import ClientArchetype
from src.prospecting.models import ProspectOverallStatus, ProspectStatus
from typing import Optional


def get_bump_frameworks_for_sdr(
    client_sdr_id: int,
    overall_statuses: Optional[list[ProspectOverallStatus]] = [],
    substatuses: Optional[list[str]] = [],
    client_archetype_ids: Optional[list[int]] = [],
    activeOnly: Optional[bool] = True,
) -> list[dict]:
    """Get all bump frameworks for a given SDR and overall status

    Args:
        client_sdr_id (int): The id of the SDR
        overall_statuses (Optional[list[ProspectOverallStatus]], optional): The overall statuses of the bump frameworks. Defaults to [] which is ALL statuses.
        substatuses (Optional[list[str]], optional): The substatuses of the bump frameworks. Defaults to [] which is ALL substatuses.
        client_archetype_ids (Optional[list[int]], optional): The ids of the client archetypes. Defaults to [] which is ALL archetypes.
        activeOnly (Optional[bool], optional): Whether to only return active bump frameworks. Defaults to True.

    Returns:
        list[dict]: A list of bump frameworks
    """
    # If overall_statuses is not specified, grab all overall statuses
    if len(overall_statuses) == 0:
        overall_statuses = [pos for pos in ProspectOverallStatus]

    # If client_archetype_ids is not specified, grab all client archetypes
    if len(client_archetype_ids) == 0:
        client_archetype_ids = [ca.id for ca in ClientArchetype.query.filter_by(
            client_sdr_id=client_sdr_id).all()]

    # Joined
    joined_query = db.session.query(
        BumpFramework.id.label("bump_framework_id")
    ).join(
        JunctionBumpFrameworkClientArchetype, BumpFramework.id == JunctionBumpFrameworkClientArchetype.bump_framework_id
    ).join(
        ClientArchetype, JunctionBumpFrameworkClientArchetype.client_archetype_id == ClientArchetype.id
    ).filter(
        ClientArchetype.id.in_(client_archetype_ids),
        BumpFramework.client_sdr_id == client_sdr_id,
    ).all()

    # Get all bump frameworks that match the joined query
    bf_list = BumpFramework.query.filter(
        BumpFramework.id.in_([bf.bump_framework_id for bf in joined_query]),
        BumpFramework.overall_status.in_(overall_statuses)
    )

    # If substatuses is specified, filter by substatuses
    if len(substatuses) > 0:
        bf_list = bf_list.filter(BumpFramework.substatus.in_(substatuses))

    if activeOnly:
        bf_list = bf_list.filter(BumpFramework.active == True)

    bf_list: list[BumpFramework] = bf_list.all()

    return [bf.to_dict(include_archetypes=True) for bf in bf_list]


def get_bump_framework_count_for_sdr(client_sdr_id: int, client_archetype_ids: Optional[list[int]] = []) -> dict:
    """Gets the counts for bump frameworks that belong to a Client SDR in a given archetype.

    Args:
        client_sdr_id (int): _description_
        client_archetype_ids (Optional[list[int]], optional): Which archetypes to retrieve the bump frameworks. Defaults to all archetypes.
    """
    bump_frameworks=get_bump_frameworks_for_sdr(client_sdr_id, client_archetype_ids=client_archetype_ids)

    counts = {
        "total": len(bump_frameworks),
        ProspectOverallStatus.ACCEPTED.value: 0,
        ProspectOverallStatus.BUMPED.value: 0,
        ProspectStatus.ACTIVE_CONVO_QUESTION.value: 0,
        ProspectStatus.ACTIVE_CONVO_QUAL_NEEDED.value: 0,
        ProspectStatus.ACTIVE_CONVO_OBJECTION.value: 0,
        ProspectStatus.ACTIVE_CONVO_NEXT_STEPS.value: 0,
        ProspectStatus.ACTIVE_CONVO_SCHEDULING.value: 0,
    }
    for bump_framework in bump_frameworks:
        if bump_framework.get("overall_status") in counts:
            counts[bump_framework.get("overall_status")] += 1
        if bump_framework.get("substatus") in counts:
            counts[bump_framework.get("substatus")] += 1

    return counts


def create_bump_framework(
    client_sdr_id: int,
    title: str,
    description: str,
    overall_status: ProspectOverallStatus,
    length: BumpLength,
    client_archetype_ids: list[int] = [],
    active: bool = True,
    substatus: Optional[str] = None,
    default: Optional[bool] = False
) -> int:
    """Create a new bump framework, if default is True, set all other bump frameworks to False

    Args:
        title (str): The title of the bump framework
        description (str): The description of the bump framework
        overall_status (ProspectOverallStatus): The overall status of the bump framework
        length (BumpLength): The length of the bump framework
        active (bool, optional): Whether the bump framework is active. Defaults to True.
        client_sdr_id (int): The id of the client SDR. Defaults to None.
        client_archetype_ids (list[int], optional): The ids of the client archetypes. Defaults to [] which is ALL archetypes.
        substatus (Optional[str], optional): The substatus of the bump framework. Defaults to None.
        default (Optional[bool], optional): Whether the bump framework is the default. Defaults to False.

    Returns:
        int: The id of the newly created bump framework
    """
    if default:
        all_bump_frameworks: list[BumpFramework] = BumpFramework.query.filter_by(
            client_sdr_id=client_sdr_id).all()
        for bump_framework in all_bump_frameworks:
            bump_framework.default = False
            db.session.add(bump_framework)

    if length not in [BumpLength.LONG, BumpLength.SHORT, BumpLength.MEDIUM]:
        length = BumpLength.MEDIUM

    # Create the Bump Framework
    bump_framework = BumpFramework(
        description=description,
        title=title,
        overall_status=overall_status,
        substatus=substatus,
        bump_length=length,
        active=active,
        client_sdr_id=client_sdr_id,
        default=default,
        sellscale_default_generated=False,
    )
    db.session.add(bump_framework)
    db.session.commit()
    bump_framework_id = bump_framework.id

    # If client_archetype_ids is not specified, grab all client archetypes
    if len(client_archetype_ids) == 0:
        client_archetype_ids = [ca.id for ca in ClientArchetype.query.filter_by(
            client_sdr_id=client_sdr_id).all()]

    # Remove duplicates from client_archetype_ids
    client_archetype_ids = list(set(client_archetype_ids))

    # Create the BumpFramework + ClientArchetype junction table
    for client_archetype_id in client_archetype_ids:
        junction = JunctionBumpFrameworkClientArchetype(
            bump_framework_id=bump_framework_id,
            client_archetype_id=client_archetype_id,
        )
        db.session.add(junction)
    db.session.commit()

    return bump_framework.id


def modify_bump_framework(
    client_sdr_id: int,
    bump_framework_id: int,
    overall_status: ProspectOverallStatus,
    length: BumpLength,
    client_archetype_ids: list[int],
    title: Optional[str],
    description: Optional[str],
    default: Optional[bool] = False,
) -> bool:
    """Modify a bump framework

    Args:
        client_sdr_id (int): The id of the client SDR
        bump_framework_id (int): The id of the bump framework
        overall_status (ProspectOverallStatus): The overall status of the bump framework
        length (BumpLength): The length of the bump framework
        client_archetype_ids (list[int]): The ids of the client archetypes
        title (Optional[str]): The title of the bump framework
        description (Optional[str]): The description of the bump framework
        default (Optional[bool]): Whether the bump framework is the default

    Returns:
        bool: Whether the bump framework was modified
    """
    bump_framework: BumpFramework = BumpFramework.query.filter(
        BumpFramework.client_sdr_id == client_sdr_id,
        BumpFramework.id == bump_framework_id
    ).first()

    if title:
        bump_framework.title = title
    if description:
        bump_framework.description = description

    if length not in [BumpLength.LONG, BumpLength.SHORT, BumpLength.MEDIUM]:
        bump_framework.bump_length = BumpLength.MEDIUM
    else:
        bump_framework.bump_length = length

    if default:
        default_bump_frameworks: list[BumpFramework] = BumpFramework.query.filter(
            BumpFramework.client_sdr_id == client_sdr_id,
            BumpFramework.overall_status == overall_status,
            BumpFramework.default == True
        ).all()
        for default_bump_framework in default_bump_frameworks:
            default_bump_framework.default = False
            db.session.add(default_bump_framework)
    bump_framework.default = default

    # Remove duplicates from client_archetype_ids
    client_archetype_ids = list(set(client_archetype_ids))

    # If client_archetype_ids is [], then we want to delete all junctions
    if len(client_archetype_ids) == 0:
        junctions: list[JunctionBumpFrameworkClientArchetype] = JunctionBumpFrameworkClientArchetype.query.filter(
            JunctionBumpFrameworkClientArchetype.bump_framework_id == bump_framework_id
        ).all()
        for junction in junctions:
            db.session.delete(junction)
    else:
        # If client_archetype_ids is specified, we need to perform some actions
        # 1. If the junction does not exist, create it
        # 2. If the junction does exist, do nothing
        # 3. If the junction exists, but the client_archetype_id is not in client_archetype_ids, delete it
        junctions: list[JunctionBumpFrameworkClientArchetype] = JunctionBumpFrameworkClientArchetype.query.filter(
            JunctionBumpFrameworkClientArchetype.bump_framework_id == bump_framework_id,
        ).all()
        junction_archetype_ids = [j.client_archetype_id for j in junctions]

        # Part 1: Create the junctions that don't exist
        for client_archetype_id in client_archetype_ids:
            if client_archetype_id not in junction_archetype_ids:
                junction = JunctionBumpFrameworkClientArchetype(
                    bump_framework_id=bump_framework_id,
                    client_archetype_id=client_archetype_id,
                )
                db.session.add(junction)

        # Part 2: Do nothing

        # Part 3: Delete the junctions that don't exist
        for junction in junctions:
            if junction.client_archetype_id not in client_archetype_ids:
                db.session.delete(junction)

    db.session.add(bump_framework)
    db.session.commit()

    return True


def deactivate_bump_framework(client_sdr_id: int, bump_framework_id: int) -> None:
    """Deletes a BumpFramework entry by marking it as inactive

    Args:
        bump_framework_id (int): The id of the BumpFramework to delete

    Returns:
        None
    """
    bump_framework: BumpFramework = BumpFramework.query.filter(
        BumpFramework.id == bump_framework_id,
        BumpFramework.client_sdr_id == client_sdr_id,
    ).first()

    # Can't deactive the sellscale generated default frameworks
    if bump_framework.sellscale_default_generated:
        return

    bump_framework.active = False
    db.session.add(bump_framework)
    db.session.commit()

    return


def activate_bump_framework(client_sdr_id: int, bump_framework_id: int) -> None:
    """Activates a BumpFramework entry by marking it as active

    Args:
        bump_framework_id (int): The id of the BumpFramework to activate

    Returns:
        None
    """
    bump_framework: BumpFramework = BumpFramework.query.filter(
        BumpFramework.id == bump_framework_id,
        BumpFramework.client_sdr_id == client_sdr_id,
    ).first()
    bump_framework.active = True
    db.session.add(bump_framework)
    db.session.commit()

    return


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
    default_bump_frameworks: list[dict] = []
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
    for bump_framework in bump_frameworks:
        for client_archetype in client_archetypes:
            junction = JunctionBumpFrameworkClientArchetype(
                bump_framework_id=bump_framework.id,
                client_archetype_id=client_archetype.id,
            )
            db.session.add(junction)
    db.session.commit()

    return len(default_bump_frameworks)


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