from model_import import ClientPod, ClientSDR
from app import db


def create_client_pod(client_id: int, name: str) -> ClientPod:
    """
    Creates a new client pod for a client
    """
    client_pod = ClientPod(
        client_id=client_id,
        name=name,
        active=True,
    )
    db.session.add(client_pod)
    db.session.commit()
    return client_pod


def client_pod_has_client_sdrs(client_pod_id: int):
    """
    Returns True if the client pod has any client sdrs
    """
    client_sdrs = ClientSDR.query.filter_by(client_pod_id=client_pod_id).all()
    return len(client_sdrs) > 0


def delete_client_pod(client_pod_id: int):
    """
    Deletes a client pod
    """
    client_pod = ClientPod.query.filter_by(id=client_pod_id).first()
    if client_pod_has_client_sdrs(client_pod_id):
        return False, "Client pod has client sdrs so cannot be deleted"
    db.session.delete(client_pod)
    db.session.commit()
    return True, "OK"


def add_client_sdr_to_client_pod(client_sdr_id: int, client_pod_id: int) -> bool:
    """
    Adds a client sdr to a client pod
    """
    client_sdr = ClientSDR.query.filter_by(id=client_sdr_id).first()
    client_sdr.client_pod_id = client_pod_id
    db.session.commit()
    return True
