from app import db

from src.client.models import ClientSDR


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
