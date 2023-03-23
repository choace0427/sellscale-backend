import json
from model_import import ClientSDR
from app import db

def update_linked_cookies(client_sdr_id: int, cookies: str):
    """ Updates LinkedIn cookies for Voyager

    Args:
        client_sdr_id (int): ID of the client SDR
        cookies (str): LinkedIn cookies

    Returns:
        status_code (int), message (str): HTTP status code 
    """
    
    sdr: ClientSDR = ClientSDR.query.filter(ClientSDR.id == client_sdr_id).first()
    if not sdr:
        return "No client sdr found with this id", 400 

    sdr.li_at_token = json.loads(cookies).get("li_at")
    sdr.li_cookies = cookies

    db.session.add(sdr)
    db.session.commit()

    return "Updated cookies", 200

