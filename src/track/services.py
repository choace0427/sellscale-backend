from regex import D
import requests
from sqlalchemy import or_
from src.company.models import Company
from src.contacts.services import apollo_get_contacts
from src.prospecting.models import Prospect
from src.track.models import TrackEvent, TrackSource
from app import db, celery
from src.utils.abstract.attr_utils import deep_get
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

    # send_slack_message(
    #     message=f"Track event created: ```{track_event.to_dict()}```",
    #     webhook_urls=[URL_MAP["eng-sandbox"]],
    # )

    find_company_from_orginfo.delay(track_event.id)
    find_company_from_people_labs(
        track_event_id=track_event.id
    )

    return True


@celery.task
def find_company_from_orginfo(track_event_id):
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
    track_event.company_identify_api = "orginfo"
    track_event.company_identify_payload = response_data
    db.session.commit()

    return f"Track event updated with company ID: {prospect.company_id}"

@celery.task
def find_company_from_people_labs(track_event_id):
    import requests

    track_event = TrackEvent.query.get(track_event_id)

    if track_event is None or track_event.company_identify_api:
        return "Track event not found or already identified"

    # check if any track event exists with given IP address and has company_identification_payload
    other_event = TrackEvent.query.filter(
        TrackEvent.ip_address == track_event.ip_address,
        TrackEvent.company_identify_payload != None,
        TrackEvent.id != track_event_id,
    ).first()
    if other_event:
        track_event.company_identify_api = "peopledatalabs"
        track_event.company_identify_payload = other_event.company_identify_payload
        db.session.add(track_event)
        db.session.commit()
        db.session.close()
        return "Company already identified by another event"

    url = "https://api.peopledatalabs.com/v5/ip/enrich?ip={ip_address}&return_ip_location=true&return_ip_metadata=false&return_person=true&return_if_unmatched=false&titlecase=true&pretty=true"

    url = url.format(ip_address=track_event.ip_address)

    payload={}
    headers = {
    'Content-Type': 'application/json',
    'X-API-Key': '843556532c45042ff713c6bba02cf8a08513ef7c3978124c92884637ee93c63d',
    'accept': 'application/json'
    }

    response = requests.request("GET", url, headers=headers, data=payload)

    track_event.company_identify_api = "peopledatalabs"
    track_event.company_identify_payload = response.json()
    db.session.add(track_event)
    db.session.commit()
    
    deanonymize_track_events_for_people_labs(track_event_id)

    return response.json()

# last 100 track events
def get_track_events():
    track_events = TrackEvent.query.order_by(TrackEvent.created_at.desc()).limit(5000).all()
    return track_events

def deanonymize_track_events_for_people_labs(track_event_id):
    from src.contacts.services import apollo_org_search, save_apollo_query

    client_sdr_id = 34

    track_event: TrackEvent = TrackEvent.query.get(track_event_id)

    if not track_event or track_event.company_identify_api != "peopledatalabs" or not track_event.company_identify_payload:
        return "Track event not found or not identified by People Data Labs"
        
    company_payload = track_event.company_identify_payload.get("data", {}).get("company", {})
    location = track_event.company_identify_payload.get("data", {}).get("ip", {}).get("location", {}).get("locality")
    company_name = company_payload.get("display_name")
    company_website = company_payload.get("website")
    company_size = company_payload.get("size")
    employee_count = company_payload.get("employee_count")
    person_payload = track_event.company_identify_payload.get("data", {}).get("person", {})
    job_title_role = person_payload.get("job_title_role")
    job_title_levels = person_payload.get("job_title_levels")

    print("Attempting search for details:\ncompany_name: {}\ncompany_website: {}\ncompany_size: {}\nemployee_count: {}\njob_title_role: {}\njob_title_levels: {}".format(
        company_name, company_website, company_size, employee_count, job_title_role, job_title_levels
    ))

    saved_apollo_query = save_apollo_query(domain=company_website)

    # organization = apollo_org_search(
    #     company_name=company_name
    # )
    # if not organization or not organization.get("id"):
    #     return "No organizations found"
    
    # organization_id = organization['id']

    # 'owner', 'founder', 'c_suite', 'partner', 'vp', 'head', 'director', 'manager'. 'senior', 'entry', 'intern'",
    job_title_level_to_apollo_map = {
        'Cxo': ['owner', 'founder', 'c_suite'],
        'Senior': ['manager', 'senior', 'partner'],
        'Director': ['head', 'director'],
        'Owner': ['owner', 'founder', 'c_suite'],
        'Vp': ['vp', 'head', 'director'],
    }
    default = ['manager', 'senior', 'director', 'vp', 'head', 'owner', 'founder', 'c_suite']

    seniorities = []
    if job_title_levels:
        for job_title_level in job_title_levels:
            seniorities.extend(job_title_level_to_apollo_map.get(job_title_level, []))
    if not seniorities:
        roles = default

    # find prospects from apollo
    data = apollo_get_contacts(
            client_sdr_id=1,
            num_contacts=100,
            person_titles=[job_title_role],
            person_not_titles=[],
            organization_num_employees_ranges=[
                    "1,10",
                    "11,20",
                    "21,50",
                    "51,100",
                    "101,200",
                    "201,500",
                    "501,1000",
                    "1001,2000",
                    "2001,5000",
                    "5001,10000",
                    "10001",
                ],
            organization_ids=None,
            person_locations=[location],
            revenue_range={
                    "min": None,
                    "max": None,
                },
            organization_latest_funding_stage_cd=[],
            person_seniorities=seniorities,
            is_prefilter=False,
            q_organization_search_list_id=saved_apollo_query['listId']
        )
    contacts = data['contacts'] + data['people']

    if not contacts:
        data = apollo_get_contacts(
            client_sdr_id=1,
            num_contacts=100,
            person_titles=[job_title_role],
            person_not_titles=None,
            organization_num_employees_ranges=[
                    "1,10",
                    "11,20",
                    "21,50",
                    "51,100",
                    "101,200",
                    "201,500",
                    "501,1000",
                    "1001,2000",
                    "2001,5000",
                    "5001,10000",
                    "10001",
                ],
            organization_ids=None,
            person_locations=[],
            revenue_range={
                    "min": None,
                    "max": None,
                },
            organization_latest_funding_stage_cd=[],
            person_seniorities=seniorities,
            is_prefilter=False,
            q_organization_search_list_id=saved_apollo_query['listId']
        )
        contacts = data['contacts'] + data['people']

    print("Found {} contacts".format(len(contacts)))

    if not contacts:
        return "No contacts"

    linkedin_url = deep_get(contacts[0], "linkedin_url") 
    name = deep_get(contacts[0], "name")
    title = deep_get(contacts[0], "title")
    photo_url = deep_get(contacts[0], "photo_url")
    org_name = deep_get(contacts[0], "organization.name")
    org_website = deep_get(contacts[0], "organization.website_url")
    state = deep_get(contacts[0], "state")
    city = deep_get(contacts[0], "city")
    country = deep_get(contacts[0], "country")
    location = f"{city}, {state}, {country}"
    website_viewed = track_event.window_location

    send_slack_message(
        message="*🔗 LinkedIn*: {}\n*👥 Name*: {}\n*♣ Title*: {}\n*📸 Photo*: {}\n*🌆 Organization*: {}\n*👾 Website*: {}\n*🌎 Location*: {}".format(
            linkedin_url, name, title, photo_url, org_name, org_website, location
        ),
        blocks=[
		{
			"type": "header",
			"text": {
				"type": "plain_text",
				"text": "💡 {name} visited your website.".format(name=name),
				"emoji": True
			}
		},
		{
			"type": "section",
			"text": {
				"type": "mrkdwn",
				"text": "*🔗 LinkedIn*: {linkedin_url}\n*♣️ Title:* {title}\n*🌆 Organization*: {org_name}\n*👾 Website*: {org_website}\n*🌎 Location*: {location}".format(
                    linkedin_url=linkedin_url, org_name=org_name, org_website=org_website, location=location, title=title
                )
			},
			"accessory": {
				"type": "image",
				"image_url": "{photo_url}".format(photo_url=photo_url),
				"alt_text": "profile_picture"
			}
		},
		{
			"type": "context",
			"elements": [
				{
					"type": "mrkdwn",
					"text": "Visited {website_viewed} on {date}".format(website_viewed=website_viewed, date=track_event.created_at.strftime("%Y-%m-%d %H:%M:%S"))
				}
			]
		},
		{
			"type": "actions",
			"elements": [
				{
					"type": "button",
					"text": {
						"type": "plain_text",
						"text": "Engage with {name}".format(name=name),
						"emoji": True
					},
					"value": linkedin_url,
					"action_id": "actionId-0"
				}
			]
		}
	],
        webhook_urls=[URL_MAP["sales-visitors"]],
    )

    return contacts