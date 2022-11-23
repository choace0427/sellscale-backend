from model_import import ResearchPoints
from app import db


def flag_research_point(research_point_id: int):
    """Flags a research point"""
    rp: ResearchPoints = ResearchPoints.query.get(research_point_id)
    if not rp:
        raise Exception("Research point not found")
    rp.flagged = True
    db.session.add(rp)
    db.session.commit()

    return True
