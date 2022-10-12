from src.automation.models import PhantomBusterConfig
from app import db


def create_phantom_buster_config(
    client_id: int,
    client_sdr_id: int,
    google_sheets_uuid: str,
    phantom_name: str,
    phantom_uuid: str,
):
    pb_config = PhantomBusterConfig(
        client_id=client_id,
        client_sdr_id=client_sdr_id,
        google_sheets_uuid=google_sheets_uuid,
        phantom_name=phantom_name,
        phantom_uuid=phantom_uuid,
    )
    db.session.add(pb_config)
    db.session.commit()

    return {"phantom_buster_config_id": pb_config.id}
