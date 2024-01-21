from src.track.models import TrackEvent, TrackSource
from app import db
from src.utils.slack import URL_MAP, send_slack_message


def create_track_event(
    ip: str,
    page: str,
    track_key: str,
):
    track_source: TrackSource = TrackSource.query.filter_by(track_key=track_key).first()

    if not track_source:
        return False

    track_source_id = track_source.id
    event_type = "view"  # todo(Aakash) change in future
    window_location = page
    ip_address = ip
    company_id = None

    track_event = TrackEvent(
        track_source_id=track_source_id,
        event_type=event_type,
        window_location=window_location,
        ip_address=ip_address,
        company_id=company_id,
    )

    db.session.add(track_event)
    db.session.commit()

    send_slack_message(
        message=f"Track event created: ```{track_event.to_dict()}```",
        webhook_urls=[URL_MAP["eng-sandbox"]],
    )

    return True
