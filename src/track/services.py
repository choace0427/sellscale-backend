import requests
from sqlalchemy import or_
from src.company.models import Company
from src.prospecting.models import Prospect
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

    find_company(track_event.id)

    return True


def find_company(track_event_id):
    # Step 1: Find the track event
    track_event = TrackEvent.query.get(track_event_id)
    if track_event is None:
        return "Track event not found"

    # Step 2: Use the track_event.ip_address to find the payload
    url = f"https://api.orginfo.io/data/v1/org/company?key=75a60f3adfc391227bd9e5cfb8d266bead61a02f&ip={track_event.ip_address}"
    response = requests.get(url)
    if response.status_code != 200:
        return "Failed to retrieve data from API"

    response_data = response.json()
    company_website = response_data.get("data", {}).get("website")
    if not company_website:
        return "Company website not found in API response"

    # Step 3: Find the company with a matching career page URL
    prospect = Prospect.query.filter(
        Prospect.company_url.ilike(f"%{company_website}%"),
        Prospect.company_id != None,
    ).first()
    if prospect is None:
        return "Company with url: {} not found".format(company_website)

    # Step 4: Update track_event with the company's ID
    track_event.company_id = prospect.company_id
    db.session.commit()

    return f"Track event updated with company ID: {prospect.company_id}"
