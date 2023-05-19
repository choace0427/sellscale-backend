from model_import import BumpFramework
from app import db
from src.bump_framework.models import BumpLength, JunctionBumpFrameworkClientArchetype
from src.client.models import ClientArchetype
from src.prospecting.models import ProspectOverallStatus
from typing import Optional


def get_bump_frameworks_for_sdr(
    client_sdr_id: int,
    overall_status: ProspectOverallStatus,
    client_archetype_ids: Optional[list[int]] = [],
    activeOnly: Optional[bool] = True,
) -> list[dict]:
    """Get all bump frameworks for a given SDR and overall status

    Args:
        client_sdr_id (int): The id of the SDR
        overall_status (ProspectOverallStatus): The overall status of the bump framework
        client_archetype_ids (Optional[list[int]], optional): The ids of the client archetypes. Defaults to [] which is ALL archetypes.
        activeOnly (Optional[bool], optional): Whether to only return active bump frameworks. Defaults to True.

    Returns:
        list[dict]: A list of bump frameworks
    """
    # If client_archetype_ids is not specified, grab all client archetypes
    if len(client_archetype_ids) == 0:
        client_archetype_ids = [ca.id for ca in ClientArchetype.query.filter_by(client_sdr_id=client_sdr_id).all()]

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
        BumpFramework.overall_status == overall_status,
    ).all()

    # Get all bump frameworks that match the joined query
    bf_list = BumpFramework.query.filter(
        BumpFramework.id.in_([bf.bump_framework_id for bf in joined_query])
    )

    if activeOnly:
        bf_list = bf_list.filter(BumpFramework.active == True)

    bf_list: list[BumpFramework] = bf_list.all()

    return [bf.to_dict(include_archetypes=True) for bf in bf_list]


def create_bump_framework(
    client_sdr_id: int,
    title: str,
    description: str,
    overall_status: ProspectOverallStatus,
    length: BumpLength,
    client_archetype_ids: list[int] = [],
    active: bool = True,
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
        default (Optional[bool], optional): Whether the bump framework is the default. Defaults to False.

    Returns:
        int: The id of the newly created bump framework
    """
    if default:
        all_bump_frameworks: list[BumpFramework] = BumpFramework.query.filter_by(client_sdr_id=client_sdr_id).all()
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
        bump_length=length,
        active=active,
        client_sdr_id=client_sdr_id,
        default=default,
    )
    db.session.add(bump_framework)
    db.session.commit()
    bump_framework_id = bump_framework.id

    # If client_archetype_ids is not specified, grab all client archetypes
    if len(client_archetype_ids) == 0:
        client_archetype_ids = [ca.id for ca in ClientArchetype.query.filter_by(client_sdr_id=client_sdr_id).all()]

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
