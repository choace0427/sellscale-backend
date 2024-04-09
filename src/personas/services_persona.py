from model_import import (
    Persona,
    ClientSDR,
    PersonaToAssetMapping,
    ClientAssets,
    StackRankedMessageGenerationConfiguration,
    SavedApolloQuery,
)
from app import db


def get_all_personas(client_sdr_id: int) -> list[dict]:
    """Gets all personas at the same client as the given client_sdr_id"""
    personas: list[Persona] = Persona.query.filter_by(client_sdr_id=client_sdr_id).all()
    return [persona.to_dict() for persona in personas]


def create_persona(
    client_sdr_id: int,
    name: str,
    description: str,
) -> dict:
    """Creates a new persona"""
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client_id: int = client_sdr.client_id
    persona = Persona(
        client_sdr_id=client_sdr_id,
        client_id=client_id,
        name=name,
        description=description,
    )
    db.session.add(persona)
    db.session.commit()
    return persona.to_dict()


def link_persona_to_saved_apollo_query(
    persona_id: int, saved_apollo_query_id: int
) -> bool:
    """Links a persona to a saved apollo query"""
    saved_apollo_query: SavedApolloQuery = SavedApolloQuery.query.get(
        saved_apollo_query_id
    )
    persona: Persona = Persona.query.get(persona_id)

    if saved_apollo_query.client_sdr_id != persona.client_sdr_id:
        return False

    persona = Persona.query.get(persona_id)
    persona.saved_apollo_query_id = saved_apollo_query_id
    db.session.commit()
    return True


def link_persona_to_stack_ranked_message_generation_configuration(
    persona_id: int, stack_ranked_message_generation_configuration_id: int
) -> bool:
    """Links a persona to a stack ranked message generation configuration"""
    srmgc: StackRankedMessageGenerationConfiguration = (
        StackRankedMessageGenerationConfiguration.query.get(
            stack_ranked_message_generation_configuration_id
        )
    )
    persona: Persona = Persona.query.get(persona_id)
    if srmgc.client_id != persona.client_id:
        return False

    persona = Persona.query.get(persona_id)
    persona.stack_ranked_message_generation_configuration_id = (
        stack_ranked_message_generation_configuration_id
    )
    db.session.commit()
    return True


def link_asset_to_persona(persona_id: int, asset_id: int) -> bool:
    """Links an asset to a persona"""
    client_asset: ClientAssets = ClientAssets.query.get(asset_id)
    persona: Persona = Persona.query.get(persona_id)
    if client_asset.client_id != persona.client_id:
        return False

    persona_to_asset_mapping = PersonaToAssetMapping(
        persona_id=persona_id,
        client_assets_id=asset_id,
    )
    db.session.add(persona_to_asset_mapping)
    db.session.commit()
    return True


def unlink_asset_from_persona(persona_id: int, asset_id: int) -> bool:
    """Unlinks an asset from a persona"""
    client_asset: ClientAssets = ClientAssets.query.get(asset_id)
    persona: Persona = Persona.query.get(persona_id)
    if client_asset.client_id != persona.client_id:
        return False

    persona_to_asset_mapping = PersonaToAssetMapping.query.filter_by(
        persona_id=persona_id, client_assets_id=asset_id
    ).first()
    db.session.delete(persona_to_asset_mapping)
    db.session.commit()
    return True
