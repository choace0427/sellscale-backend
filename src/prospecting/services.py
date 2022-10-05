from src.prospecting.models import ProspectStatus
from db import db


def prospect_exists_for_archetype(linkedin_url: str, client_id: int):
    from src.prospecting.models import Prospect

    p: Prospect = Prospect.query.filter(
        Prospect.linkedin_url == linkedin_url, Prospect.client_id == client_id
    ).all()

    if len(p) > 0:
        return True
    return False


def update_prospect_status(prospect_id: int, new_status: ProspectStatus):
    from src.prospecting.models import Prospect

    p: Prospect = Prospect.query.get(prospect_id)
    if not p:
        return False

    p.status = new_status
    db.session.add(p)
    db.session.commit()

    return True
