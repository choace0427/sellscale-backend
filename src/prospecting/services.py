def prospect_exists_for_archetype(linkedin_url: str, archetype_id: int):
    from src.prospecting.models import Prospect

    p: Prospect = Prospect.query.filter(
        Prospect.linkedin_url == linkedin_url, Prospect.archetype_id == archetype_id
    ).all()

    if len(p) > 0:
        return True
    return False
