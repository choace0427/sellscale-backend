from src.client.services import create_client_archetype
from model_import import ClientSDR, ClientArchetype


def create_unassigned_contacts_archetype(client_sdr_id: int) -> tuple[bool, str]:
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if not client_sdr:
        return False, "Client SDR not found"

    unassigned_contacts_client_archetypes: list[
        ClientArchetype
    ] = ClientArchetype.query.filter_by(
        client_sdr_id=client_sdr_id, is_unassigned_contact_archetype=True
    ).all()
    if len(unassigned_contacts_client_archetypes) >= 1:
        return False, "Unassigned Contacts Archetype already exists"

    data = create_client_archetype(
        client_id=client_sdr.client_id,
        client_sdr_id=client_sdr_id,
        archetype="{name}'s Unassigned Contacts".format(name=client_sdr.name),
        is_unassigned_contact_archetype=True,
        filters=[],
    )
    client_archetype_id = data and data["client_archetype_id"]

    return True, "Unassigned Contacts archetype created with id #{id}".format(
        id=client_archetype_id
    )
