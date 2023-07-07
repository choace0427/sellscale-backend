from model_import import BumpFramework
from app import db
from src.bump_framework.models import BumpLength
from src.client.models import ClientArchetype
from src.message_generation.services import clear_auto_generated_bumps
from src.prospecting.models import ProspectOverallStatus, ProspectStatus
from typing import Optional


def get_bump_frameworks_for_sdr(
    client_sdr_id: int,
    overall_statuses: Optional[list[ProspectOverallStatus]] = [],
    substatuses: Optional[list[str]] = [],
    client_archetype_ids: Optional[list[int]] = [],
    exclude_client_archetype_ids: Optional[list[int]] = [],
    exclude_ss_default: Optional[bool] = False,
    unique_only: Optional[bool] = False,
    active_only: Optional[bool] = True,
    bumped_count: Optional[int] = None,
) -> list[dict]:
    """Get all bump frameworks for a given SDR and overall status

    Args:
        client_sdr_id (int): The id of the SDR
        overall_statuses (Optional[list[ProspectOverallStatus]], optional): The overall statuses of the bump frameworks. Defaults to [] which is ALL statuses.
        substatuses (Optional[list[str]], optional): The substatuses of the bump frameworks. Defaults to [] which is ALL substatuses.
        client_archetype_ids (Optional[list[int]], optional): The ids of the client archetypes. Defaults to [] which is ALL archetypes.
        exclude_client_archetype_ids (Optional[list[int]], optional): The ids of the client archetypes to exclude. Defaults to [] which is NO archetypes.
        excludeSSDefault (Optional[bool], optional): Whether to exclude bump frameworks with sellscale_default_generated. Defaults to False.
        activeOnly (Optional[bool], optional): Whether to only return active bump frameworks. Defaults to True.
        uniqueOnly (Optional[bool], optional): Whether to only return unique bump frameworks. Defaults to False.
        bumpedCount (Optional[int], optional): The number of times the bump framework has been bumped. Defaults to None.

    Returns:
        list[dict]: A list of bump frameworks
    """
    # If overall_statuses is not specified, grab all overall statuses

    if len(overall_statuses) == 0:
        overall_statuses = [pos for pos in ProspectOverallStatus]

    # If client_archetype_ids is not specified, grab all client archetypes
    if len(client_archetype_ids) == 0:
        client_archetype_ids = [
            ca.id
            for ca in ClientArchetype.query.filter_by(client_sdr_id=client_sdr_id).all()
        ]

    bfs: list[BumpFramework] = BumpFramework.query.filter(
        BumpFramework.client_sdr_id == client_sdr_id,
        BumpFramework.client_archetype_id.in_(client_archetype_ids),
        BumpFramework.client_archetype_id.notin_(exclude_client_archetype_ids),
        BumpFramework.overall_status.in_(overall_statuses),
    )

    # If substatuses is specified, filter by substatuses
    if len(substatuses) > 0:
        bfs = bfs.filter(BumpFramework.substatus.in_(substatuses))

    # If exclude_ss_default is specified, filter by sellscale_default_generated
    if exclude_ss_default:
        bfs = bfs.filter(BumpFramework.sellscale_default_generated == False)

    # If active_only is specified, filter by active
    if active_only:
        bfs = bfs.filter(BumpFramework.active == True)

    # If bumped_count is specified, filter by bumped_count
    if bumped_count is not None and ProspectOverallStatus.BUMPED in overall_statuses:
        bfs = bfs.filter(BumpFramework.bumped_count == bumped_count)

    bfs: list[BumpFramework] = bfs.all()

    # If unique_only is specified, filter by unique
    if unique_only:
        seen = set()
        bf_unique = []
        for bf in bfs:
            seen_tuple = (bf.title, bf.description)
            if seen_tuple in seen:
                continue
            bf_unique.append(bf)
            seen.add(seen_tuple)
        bfs = bf_unique

    return [bf.to_dict() for bf in bfs]


def get_bump_framework_count_for_sdr(
    client_sdr_id: int, client_archetype_ids: Optional[list[int]] = []
) -> dict:
    """Gets the counts for bump frameworks that belong to a Client SDR in a given archetype.

    Args:
        client_sdr_id (int): _description_
        client_archetype_ids (Optional[list[int]], optional): Which archetypes to retrieve the bump frameworks. Defaults to all archetypes.
    """
    bump_frameworks = get_bump_frameworks_for_sdr(
        client_sdr_id, client_archetype_ids=client_archetype_ids
    )

    counts = {
        "total": len(bump_frameworks),
        ProspectOverallStatus.ACCEPTED.value: 0,
        ProspectOverallStatus.BUMPED.value: 0,
        ProspectStatus.ACTIVE_CONVO_QUESTION.value: 0,
        ProspectStatus.ACTIVE_CONVO_QUAL_NEEDED.value: 0,
        ProspectStatus.ACTIVE_CONVO_OBJECTION.value: 0,
        ProspectStatus.ACTIVE_CONVO_NEXT_STEPS.value: 0,
        ProspectStatus.ACTIVE_CONVO_SCHEDULING.value: 0,
        ProspectStatus.ACTIVE_CONVO_REVIVAL.value: 0,
    }
    for bump_framework in bump_frameworks:
        if bump_framework.get("overall_status") in counts:
            counts[bump_framework.get("overall_status")] += 1
        if bump_framework.get("substatus") in counts:
            counts[bump_framework.get("substatus")] += 1

    return counts


def create_bump_framework(
    client_sdr_id: int,
    client_archetype_id: int,
    title: str,
    description: str,
    overall_status: ProspectOverallStatus,
    length: BumpLength,
    bumped_count: int = None,
    bump_delay_days: int = 2,
    active: bool = True,
    substatus: Optional[str] = None,
    default: Optional[bool] = False,
    sellscale_default_generated: Optional[bool] = False,
) -> int:
    """Create a new bump framework, if default is True, set all other bump frameworks to False

    Args:
        client_sdr_id (int): The id of the SDR
        client_archetype_id (int): The id of the client archetype
        title (str): The title of the bump framework
        description (str): The description of the bump framework
        overall_status (ProspectOverallStatus): The overall status of the bump framework
        length (BumpLength): The length of the bump framework
        bumped_count (int, optional): The number which corresponds to which bump in the sequence this BF appears. Defaults to None.
        bump_delay_days (int, optional): The number of days to wait before bumping. Defaults to 2.
        active (bool, optional): Whether the bump framework is active. Defaults to True.
        substatus (Optional[str], optional): The substatus of the bump framework. Defaults to None.
        default (Optional[bool], optional): Whether the bump framework is the default. Defaults to False.
        sellscale_default_generated (Optional[bool], optional): Whether the bump framework was generated by SellScale. Defaults to False.

    Returns:
        int: The id of the newly created bump framework
    """
    if default:
        all_bump_frameworks: list[BumpFramework] = BumpFramework.query.filter_by(
            client_sdr_id=client_sdr_id,
            client_archetype_id=client_archetype_id,
            overall_status=overall_status,
        )
        if overall_status == ProspectOverallStatus.BUMPED and bumped_count is not None:
            all_bump_frameworks = all_bump_frameworks.filter_by(
                bumped_count=bumped_count
            )
        all_bump_frameworks = all_bump_frameworks.all()
        for bump_framework in all_bump_frameworks:
            bump_framework.default = False
            db.session.add(bump_framework)

    if length not in [BumpLength.LONG, BumpLength.SHORT, BumpLength.MEDIUM]:
        length = BumpLength.MEDIUM

    # Create the Bump Framework
    bump_framework = BumpFramework(
        client_sdr_id=client_sdr_id,
        client_archetype_id=client_archetype_id,
        description=description,
        title=title,
        overall_status=overall_status,
        substatus=substatus,
        bump_length=length,
        bumped_count=bumped_count,
        bump_delay_days=bump_delay_days,
        active=active,
        default=default,
        sellscale_default_generated=sellscale_default_generated,
    )
    db.session.add(bump_framework)
    db.session.commit()
    bump_framework_id = bump_framework.id

    return bump_framework_id


def modify_bump_framework(
    client_sdr_id: int,
    client_archetype_id: int,
    bump_framework_id: int,
    overall_status: ProspectOverallStatus,
    length: BumpLength,
    title: Optional[str],
    description: Optional[str],
    bumped_count: Optional[int] = None,
    bump_delay_days: Optional[int] = None,
    default: Optional[bool] = False,
) -> bool:
    """Modify a bump framework

    Args:
        client_sdr_id (int): The id of the client SDR
        client_archetype_id(int): The id of the client Archetype
        bump_framework_id (int): The id of the bump framework
        overall_status (ProspectOverallStatus): The overall status of the bump framework
        length (BumpLength): The length of the bump framework
        title (Optional[str]): The title of the bump framework
        description (Optional[str]): The description of the bump framework
        bumped_count (Optional[int], optional): The number which corresponds to which bump in the sequence this BF appears. Defaults to None.
        bump_delay_days (Optional[int], optional): The number of days to wait before bumping. Defaults to 2.
        default (Optional[bool]): Whether the bump framework is the default

    Returns:
        bool: Whether the bump framework was modified
    """
    bump_framework: BumpFramework = BumpFramework.query.filter(
        BumpFramework.client_sdr_id == client_sdr_id,
        BumpFramework.id == bump_framework_id,
    ).first()

    if title:
        bump_framework.title = title
    if description:
        bump_framework.description = description

    if length not in [BumpLength.LONG, BumpLength.SHORT, BumpLength.MEDIUM]:
        bump_framework.bump_length = BumpLength.MEDIUM
    else:
        bump_framework.bump_length = length

    if bumped_count:
        bump_framework.bumped_count = bumped_count

    if bump_delay_days:
        bump_framework.bump_delay_days = bump_delay_days

    if default:
        default_bump_frameworks: list[BumpFramework] = BumpFramework.query.filter(
            BumpFramework.client_sdr_id == client_sdr_id,
            BumpFramework.client_archetype_id == client_archetype_id,
            BumpFramework.overall_status == overall_status,
            BumpFramework.default == True,
        )
        if overall_status == ProspectOverallStatus.BUMPED and bumped_count is not None:
            default_bump_frameworks = default_bump_frameworks.filter(
                BumpFramework.bumped_count == bumped_count
            )
        default_bump_frameworks = default_bump_frameworks.all()
        for default_bump_framework in default_bump_frameworks:
            default_bump_framework.default = False
            db.session.add(default_bump_framework)
    bump_framework.default = default

    bump_framework.sellscale_default_generated = False

    db.session.add(bump_framework)
    db.session.commit()

    # Delete auto_generated_messages using this bump_framework
    clear_auto_generated_bumps(bump_framework_id)

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


def clone_bump_framework(client_sdr_id: int, bump_framework_id: int, target_archetype_id: int) -> int:
    """ Clones (imports) an existent bump framework's attributes into a new bump framework under the target archetype

    Args:
        client_sdr_id (int): ID of the client SDR
        bump_framework_id (int): ID of the bump framework to clone
        target_archetype_id (int): ID of the target archetype

    Returns:
        int: ID of the new bump framework
    """
    archetype: ClientArchetype = ClientArchetype.query.get(target_archetype_id)
    if not archetype:
        return -1
    elif archetype.client_sdr_id != client_sdr_id:
        return -1

    existing_bf: BumpFramework = BumpFramework.query.get(bump_framework_id)
    if not existing_bf:
        return -1
    elif existing_bf.client_sdr_id != client_sdr_id:
        return -1

    new_framework_id: int = create_bump_framework(
        client_sdr_id=client_sdr_id,
        client_archetype_id=target_archetype_id,
        overall_status=existing_bf.overall_status,
        substatus=existing_bf.substatus,
        length=existing_bf.bump_length,
        title=existing_bf.title,
        description=existing_bf.description,
        bumped_count=existing_bf.bumped_count,
        default=True,
        sellscale_default_generated=False,
    )

    return new_framework_id
