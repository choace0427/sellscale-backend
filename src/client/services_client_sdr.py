from typing import Optional
from app import db

from src.client.models import ClientSDR, LinkedInWarmupStatus, LinkedInWarmupStatusChange


def update_sdr_blacklist_words(client_sdr_id: int, blacklist_words: list[str]) -> bool:
    """Updates the blacklist_words field for a Client SDR

    Args:
        client_sdr_id (int): The id of the Client SDR

    Returns:
        bool: True if successful, False otherwise
    """
    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if not sdr:
        return False

    sdr.blacklisted_words = blacklist_words
    db.session.commit()

    return True


def get_sdr_blacklist_words(client_sdr_id: int) -> list[str]:
    """Gets the blacklist_words field for a Client SDR

    Args:
        client_sdr_id (int): The id of the Client SDR

    Returns:
        list[str]: The blacklist_words field for the Client SDR
    """
    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if not sdr:
        return None

    return sdr.blacklisted_words


def update_sdr_linkedin_sla(
    client_sdr_id: int,
    new_linkedin_warmup_status: LinkedInWarmupStatus,
    custom_sla: Optional[int] = None
) -> tuple[bool, int]:
    """Updates the warmup status for a SDR's LinkedIn segment. If the new status is CUSTOM_WARM_UP,
    then the custom_sla field must be provided.

    Args:
        client_sdr_id (int): _description_
        new_linkedin_warmup_status (LinkedInWarmupStatus): _description_
        custom_sla (Optional[int], optional): _description_. Defaults to None.

    Returns:
        tuple[bool, int]: A boolean indicating whether the update was successful and the
        ID of the new status change record
    """
    # Get the SDR
    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if not sdr:
        return False, None

    # Check if the new status is CUSTOM_WARM_UP and if the custom_sla field is provided
    if new_linkedin_warmup_status == LinkedInWarmupStatus.CUSTOM_WARM_UP and not custom_sla:
        return False, None

    # Determine the new sla value
    new_sla_value = custom_sla if custom_sla else LinkedInWarmupStatus.to_sla_value(new_linkedin_warmup_status)
    if not new_sla_value:
        return False, None

    new_status_change = LinkedInWarmupStatusChange(
        client_sdr_id=client_sdr_id,
        old_status=sdr.linkedin_warmup_status,
        old_sla_value=sdr.weekly_li_outbound_target,
        new_status=new_linkedin_warmup_status,
        new_sla_value=new_sla_value
    )
    db.session.add(new_status_change)
    db.session.commit()

    sdr.linkedin_warmup_status = new_linkedin_warmup_status
    sdr.weekly_li_outbound_target = new_sla_value
    db.session.commit()

    return True, new_status_change.id
