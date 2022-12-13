from app import db
from typing import Optional

from model_import import (
    SightOnboarding,
    ClientSDR,
    Client,
    ClientArchetype,
    Prospect,
    ResponseConfiguration,
    GeneratedMessageCTA
)


def get_sight_onboarding(client_sdr_id: int):
    """ Gets SightOnboarding record for a specific client_sdr_id.

    Args:
        client_sdr_id (int): ID of the client_sdr.

    Returns:
        SightOnboarding: SightOnboarding record.
    """
    sight_onboarding: SightOnboarding = SightOnboarding.query.filter_by(client_sdr_id=client_sdr_id).first()
    return sight_onboarding


def create_sight_onboarding(
        client_sdr_id: int,
        is_onboarding_complete: Optional[bool] = False,
        completed_credentials: Optional[bool] = False,
        completed_first_persona: Optional[bool] = False,
        completed_ai_behavior: Optional[bool] = False,
        completed_first_campaign: Optional[bool] = False,
        completed_go_live: Optional[bool] = False
):
    """ Creates a new SightOnboarding record. If is_onboarding_complete is True, all other fields are set to True.
    Needs a client_sdr_id in order to tie the onboarding to a specific client.

    Args:
        is_onboarding_complete (Optional[bool], optional): Signals if onboarding is completed. Defaults to False.
        completed_credentials (Optional[bool], optional): Signals if client has completed credentials setup. Defaults to False.
        completed_first_persona (Optional[bool], optional): Signals if client has created first persona. Defaults to False.
        completed_ai_behavior (Optional[bool], optional): Signals if client has set AI behavior setting. Defaults to False.
        completed_first_campaign (Optional[bool], optional): Signals if client has created first campaign. Defaults to False.
        completed_go_live (Optional[bool], optional): Signals if client is ready to go live. Defaults to False.

    Returns:
        int: ID of the newly created SightOnboarding record.
    """
    sight_onboarding = SightOnboarding(client_sdr_id=client_sdr_id)
    if is_onboarding_complete:
        sight_onboarding.is_onboarding_complete = is_onboarding_complete
        sight_onboarding.completed_credentials = True
        sight_onboarding.completed_first_persona = True
        sight_onboarding.completed_ai_behavior = True
        sight_onboarding.completed_first_campaign = True
        sight_onboarding.completed_go_live = True
    else:
        sight_onboarding.completed_credentials = completed_credentials
        sight_onboarding.completed_first_persona = completed_first_persona
        sight_onboarding.completed_ai_behavior = completed_ai_behavior
        sight_onboarding.completed_first_campaign = completed_first_campaign
        sight_onboarding.completed_go_live = completed_go_live

    db.session.add(sight_onboarding)
    db.session.commit()

    return sight_onboarding.id


def update_sight_onboarding(client_sdr_id: int, manual_update_key: Optional[str] = None):
    """ Updates a SightOnboarding record based on the client_sdr_id.
    Also checks other models to see if onboarding criteria is complete.

    Args:
        client_sdr_id (int): ID of the client_sdr.
        manual_update (str): Field to update.

    Returns:
        bool: True if update was successful, False otherwise.
    """
    sight_onboarding: SightOnboarding = SightOnboarding.query.filter_by(client_sdr_id=client_sdr_id).first()
    if manual_update_key:
        if hasattr(sight_onboarding, manual_update_key):
            setattr(sight_onboarding, manual_update_key, True)
        else:
            return False, "Invalid manual_update_key."

    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client: Client = Client.query.get(client_sdr.client_id)

    # Credentials - NEEDS WORK
    # if not sight_onboarding.completed_credentials:
    #     sight_onboarding.completed_credentials = check_completed_credentials(client)

    # First Persona
    # if not sight_onboarding.completed_first_persona:
    #     sight_onboarding.completed_first_persona = check_completed_first_persona(client_sdr_id)

    # AI Behavior - NEEDS WORK
    # if not sight_onboarding.completed_ai_behavior:
    #     sight_onboarding.completed_ai_behavior = check_completed_ai_behavior(client, client_sdr_id)

    # First Campaign
    # if not sight_onboarding.completed_first_campaign:
    #     sight_onboarding.completed_first_campaign = check_completed_first_campaign(client_sdr_id)

    # Mark onboarding as complete if all fields are True
    if sight_onboarding.completed_credentials and \
        sight_onboarding.completed_first_persona and \
        sight_onboarding.completed_ai_behavior and \
        sight_onboarding.completed_first_campaign and \
        sight_onboarding.completed_go_live:
        sight_onboarding.is_onboarding_complete = True
        
    db.session.commit()

    return True, "SightOnboarding record updated successfully."


def check_completed_credentials(client: Client):
    """ Checks if a client has completed the credentials setup.

    NEEDS WORK

    Args:
        client (Client): _description_

    Returns:
        _type_: _description_
    """
    return False


def check_completed_first_persona(client_sdr_id: int):
    """ Checks if a client has created a persona. 
    The satisfying conditions are as following:
    - Client SDR has at least one persona
    - Persona has at least 10 prospects

    THIS FUNCTION IS EXPENSIVE AND SHOULD NOT BE USED FREQUENTLY.

    Args:
        client_sdr_id (int): ID of the client_sdr.

    Returns:
        bool: True if client has met onboarding criteria, False otherwise.
    """
    # personas: ClientArchetype = ClientArchetype.query.filter_by(client_sdr_id=client_sdr_id).all()
    # for persona in personas:
    #     persona_id = persona.id
    #     prospects: Prospect = Prospect.query.filter_by(client_archetype_id=persona_id).all()
    #     if len(prospects) >= 10:
    #         return True

    return False


def check_completed_ai_behavior(client: Client, client_sdr_id: int):
    """ Checks if a client has completed the LinkedIn AI responses setup.
     The satisfying conditions are as following:
    - Client SDR must have LinkedIn outbound enabled
    - Client SDR has a scheduling link (for demos)
    - Client SDR has supplied a conversational AI config for a Persona

    THIS FUNCTION IS EXPENSIVE AND SHOULD NOT BE USED FREQUENTLY.

    Args:
        client (Client): Client object.
        client_sdr_id (int): ID of the client_sdr.

    Returns:
        bool: True if client has met onboarding criteria, False otherwise.
    """
    # if client.linkedin_outbound_enabled:
    #     client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    #     if client_sdr.scheduling_link:
    #         personas: ClientArchetype = ClientArchetype.query.filter_by(client_sdr_id=client_sdr_id).all()
    #         for persona in personas:
    #             archetype_id = persona.id
    #             ai_config: ResponseConfiguration = ResponseConfiguration.query.get(archetype_id)
    #             if ai_config:
    #                 return True

    return False


def check_completed_first_campaign(client_sdr_id: int):
    """ Checks if a client has prepared a Campaign. 
    The satisfying conditions are as following:
    - Client SDR has added 4 CTAs (Call to Action)

    THIS FUNCTION IS EXPENSIVE AND SHOULD NOT BE USED FREQUENTLY.

    Args:
        client_sdr_id (int): ID of the client_sdr.

    Returns:
        bool: True if client has met onboarding criteria, False otherwise.
    """
    # personas: ClientArchetype = ClientArchetype.query.filter_by(client_sdr_id=client_sdr_id).all()
    # cta_sum = 0
    # for persona in personas:
    #     archetype_id = persona.id
    #     cta: GeneratedMessageCTA = GeneratedMessageCTA.query.filter_by(archetype_id=archetype_id).all()
    #     cta_sum += len(cta)
    #     if cta_sum >= 4:
    #         return True

    return False


def is_onboarding_complete(client_sdr_id: int):
    """ Checks if onboarding is complete for a specific Client SDR.

    Args:
        client_sdr_id (int): ID of the Client SDR.

    Returns:
        bool: True if onboarding is complete, False otherwise.
    """
    update_sight_onboarding(client_sdr_id)
    sight_onboarding: SightOnboarding = SightOnboarding.query.filter_by(client_sdr_id=client_sdr_id).first()
    return {
        "is_onboarding_complete": sight_onboarding.is_onboarding_complete,
        "completed_credentials": sight_onboarding.completed_credentials,
        "completed_first_persona": sight_onboarding.completed_first_persona,
        "completed_ai_behavior": sight_onboarding.completed_ai_behavior,
        "completed_first_campaign": sight_onboarding.completed_first_campaign,
        "completed_go_live": sight_onboarding.completed_go_live
    }
