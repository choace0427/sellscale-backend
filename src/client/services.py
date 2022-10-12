from app import db
from src.ml.models import GNLPModel, GNLPModelType, ModelProvider
from src.client.models import Client, ClientArchetype, ClientSDR


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

    client_archetype = ClientArchetype(
        client_id=client_id, archetype=archetype, filters=filters
    )
    db.session.add(client_archetype)
    db.session.commit()
    archetype_id = client_archetype.id

    model: GNLPModel = GNLPModel(
        model_provider=ModelProvider.OPENAI_GPT3,
        model_type=GNLPModelType.OUTREACH,
        model_description="baseline_model_{}".format(archetype),
        model_uuid="davinci:ft-personal-2022-07-23-19-55-19",
        archetype_id=archetype_id,
    )
    db.session.add(model)
    db.session.commit()

    return {"client_archetype_id": client_archetype.id}


def create_client_sdr(client_id: int, name: str, email: str):
    c: Client = get_client(client_id=client_id)
    if not c:
        return None

    sdr = ClientSDR(client_id=client_id, name=name, email=email)
    db.session.add(sdr)
    db.session.commit()

    return {"client_sdr_id": sdr.id}
