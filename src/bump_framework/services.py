from model_import import BumpFramework
from app import db
from src.prospecting.models import ProspectOverallStatus
from typing import Optional


def get_bump_frameworks_for_sdr(
    client_sdr_id: int,
    overall_status: ProspectOverallStatus,
    activeOnly: Optional[bool] = True,
) -> list[dict]:
    """Get all bump frameworks for a given SDR and overall status

    Args:
        client_sdr_id (int): The id of the SDR
        overall_status (ProspectOverallStatus): The overall status of the bump framework
        activ

    Returns:
        list[dict]: A list of bump frameworks
    """
    bf_list = BumpFramework.query.filter(
        BumpFramework.client_sdr_id == client_sdr_id,
        BumpFramework.overall_status == overall_status,
    )

    if activeOnly:
        bf_list = bf_list.filter(BumpFramework.active == True)

    bf_list: list[BumpFramework] = bf_list.all()

    return [bf.to_dict() for bf in bf_list]


def create_bump_framework(
    client_sdr_id: int,
    title: str,
    description: str,
    overall_status: ProspectOverallStatus,
    active: bool = True,
    default: Optional[bool] = False
) -> int:
    """Create a new bump framework, if default is True, set all other bump frameworks to False

    Args:
        title (str): The title of the bump framework
        description (str): The description of the bump framework
        overall_status (ProspectOverallStatus): The overall status of the bump framework
        active (bool, optional): Whether the bump framework is active. Defaults to True.
        client_sdr_id (int): The id of the client SDR. Defaults to None.
        default (Optional[bool], optional): Whether the bump framework is the default. Defaults to False.

    Returns:
        int: The id of the newly created bump framework
    """
    if default:
        all_bump_frameworks: list[BumpFramework] = BumpFramework.query.filter_by(client_sdr_id=client_sdr_id).all()
        for bump_framework in all_bump_frameworks:
            bump_framework.default = False
            db.session.add(bump_framework)

    bump_framework = BumpFramework(
        description=description,
        title=title,
        overall_status=overall_status,
        active=active,
        client_sdr_id=client_sdr_id,
        default=default,
    )
    db.session.add(bump_framework)
    db.session.commit()
    return bump_framework.id


def modify_bump_framework(
    client_sdr_id: int,
    bump_framework_id: int,
    overall_status: ProspectOverallStatus,
    title: Optional[str],
    description: Optional[str],
    default: Optional[bool] = False,
) -> bool:
    """Modify a bump framework

    Args:
        client_sdr_id (int): The id of the client SDR
        bump_framework_id (int): The id of the bump framework
        overall_status (ProspectOverallStatus): The overall status of the bump framework
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
