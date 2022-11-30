from app import db
from src.ml.models import GNLPModel, GNLPModelType, ModelProvider
from src.client.models import Client, ClientArchetype, ClientSDR
from src.utils.random_string import generate_random_alphanumeric
from src.prospecting.models import ProspectStatus
from typing import Optional
from src.ml.fine_tuned_models import get_latest_custom_model


def get_client(client_id: int):
    c: Client = Client.query.get(client_id)
    return c


def create_client(company: str, contact_name: str, contact_email: str):
    from model_import import Client

    c: Client = Client.query.filter_by(company=company).first()
    if c:
        return {"client_id": c.id}

    c: Client = Client(
        company=company,
        contact_name=contact_name,
        contact_email=contact_email,
        active=True,
        notification_allowlist=[
            ProspectStatus.SCHEDULING,
            ProspectStatus.DEMO_SET,
            ProspectStatus.ACTIVE_CONVO,
            ProspectStatus.ACCEPTED,
        ],
    )
    db.session.add(c)
    db.session.commit()

    return {"client_id": c.id}


def get_client_archetype(client_archetype_id: int):
    ca: ClientArchetype = ClientArchetype.query.get(client_archetype_id)
    return ca


def create_client_archetype(
    client_id: int,
    archetype: str,
    filters: any,
    base_archetype_id: Optional[int] = None,
):
    c: Client = get_client(client_id=client_id)
    if not c:
        return None

    client_archetype = ClientArchetype(
        client_id=client_id, archetype=archetype, filters=filters
    )
    db.session.add(client_archetype)
    db.session.commit()
    archetype_id = client_archetype.id

    if base_archetype_id:
        _, model_id = get_latest_custom_model(base_archetype_id, GNLPModelType.OUTREACH)
        base_model: GNLPModel = GNLPModel.query.get(model_id)
        model = GNLPModel(
            model_provider=base_model.model_provider,
            model_type=base_model.model_type,
            model_description="baseline_model_{}".format(archetype),
            model_uuid=base_model.model_uuid,
            archetype_id=archetype_id,
        )
        db.session.add(model)
        db.session.commit()
    else:
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

    sdr = ClientSDR(
        client_id=client_id, name=name, email=email, weekly_li_outbound_target=100
    )
    db.session.add(sdr)
    db.session.commit()

    return {"client_sdr_id": sdr.id}


def reset_client_sdr_sight_auth_token(client_sdr_id: int):
    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if not sdr:
        return None

    sdr.auth_token = generate_random_alphanumeric(32)
    db.session.commit()

    return {"token": sdr.auth_token}


def rename_archetype(new_name: str, client_archetype_id: int):
    """
    Rename an archetype
    """
    ca: ClientArchetype = ClientArchetype.query.get(client_archetype_id)
    if not ca:
        return None

    ca.archetype = new_name
    db.session.add(ca)
    db.session.commit()

    return True


def toggle_archetype_active(archetype_id: int):
    """
    Toggle an archetype's active status
    """
    ca: ClientArchetype = ClientArchetype.query.get(archetype_id)
    if not ca:
        return None

    ca.active = not ca.active
    db.session.add(ca)
    db.session.commit()

    return True


def update_client_sdr_scheduling_link(client_sdr_id: int, scheduling_link: str):
    """
    Update the scheduling link for a Client SDR
    """
    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if not sdr:
        return None

    sdr.scheduling_link = scheduling_link
    db.session.add(sdr)
    db.session.commit()

    return True


def update_client_sdr_email(client_sdr_id: int, email: str):
    """
    Update the email for a Client SDR
    """
    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if not sdr:
        return None

    sdr.email = email
    db.session.add(sdr)
    db.session.commit()

    return True
