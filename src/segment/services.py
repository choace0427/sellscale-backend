from app import db
from sqlalchemy.orm import attributes
from src.prospecting.models import Prospect
from src.segment.models import Segment


def create_new_segment(
    client_sdr_id: int, segment_title: str, filters: dict
) -> Segment or None:
    # dulicate check
    existing_segment = Segment.query.filter_by(
        client_sdr_id=client_sdr_id, segment_title=segment_title
    ).first()
    if existing_segment:
        return None

    new_segment = Segment(
        client_sdr_id=client_sdr_id,
        segment_title=segment_title,
        filters=filters,
    )

    db.session.add(new_segment)
    db.session.commit()

    return new_segment


def get_segments_for_sdr(sdr_id: int) -> list[dict]:
    all_segments: list[Segment] = Segment.query.filter_by(client_sdr_id=sdr_id).all()
    return [segment.to_dict() for segment in all_segments]


def update_segment(
    client_sdr_id: int, segment_id: int, segment_title: str, filters: dict
) -> Segment:
    segment = Segment.query.filter_by(
        client_sdr_id=client_sdr_id, id=segment_id
    ).first()

    if not segment:
        return None

    if segment_title:
        segment.segment_title = segment_title

    if filters:
        segment.filters = filters

    db.session.add(segment)
    db.session.commit()

    return segment


def delete_segment(client_sdr_id: int, segment_id: int) -> tuple[bool, str]:
    segment = Segment.query.filter_by(
        client_sdr_id=client_sdr_id, id=segment_id
    ).first()

    if not segment:
        return False, "Segment not found"

    prospects_with_segment: list[Prospect] = Prospect.query.filter_by(
        segment_id=segment_id
    ).all()
    if len(prospects_with_segment) > 0:
        return False, "Segment has prospects"

    db.session.delete(segment)
    db.session.commit()

    return True, "Segment deleted"
