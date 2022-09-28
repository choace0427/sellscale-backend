from app import db
from src.client.models import Client, ClientArchetype


def get_client(client_id: int):
    c: Client = Client.query.get(client_id)
    return c


def create_client(company: str, contact_name: str, contact_email: str):
    from model_import import Client

    c: Client = Client(
        company=company, contact_name=contact_name, contact_email=contact_email
    )
    db.session.add(c)
    db.session.commit()

    return {"client_id": c.id}


def get_client_archetype(client_archetype_id: int):
    ca: ClientArchetype = ClientArchetype.query.get(client_archetype_id)
    return ca


def create_client_archetype(client_id: int, archetype: str, filters: any):
    c: Client = get_client(client_id=client_id)
    if not c:
        return None

    archetype = ClientArchetype(
        client_id=client_id, archetype=archetype, filters=filters
    )
    db.session.add(archetype)
    db.session.commit()

    return {"client_archetype_id": archetype.id}
