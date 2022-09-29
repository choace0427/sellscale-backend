def prospect_exists_for_archetype(linkedin_url: str, client_id: int):
    from src.prospecting.models import Prospect

    p: Prospect = Prospect.query.filter(
        Prospect.linkedin_url == linkedin_url, Prospect.client_id == client_id
    ).all()

    if len(p) > 0:
        return True
    return False
