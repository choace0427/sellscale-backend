import datetime
from http import client
from typing import Optional
from flask_socketio import send
from regex import D
import requests
from sqlalchemy import or_
from src.client.models import ClientArchetype, ClientSDR, Client
from src.company.models import Company
from src.contacts.services import apollo_get_contacts
from src.ml.openai_wrappers import wrapped_chat_gpt_completion
from src.ml.services import simple_perplexity_response
from src.prospecting.models import Prospect
from src.track.models import DeanonymizedContact, TrackEvent, TrackSource, ICPRouting
from app import db, celery
from src.utils.abstract.attr_utils import deep_get
from src.utils.hasher import generate_uuid
from src.utils.slack import URL_MAP, send_slack_message
from tests import prospect
from tests.research import linkedin


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

def process_deanonymized_contact(deanon_contact_id):
    from src.prospecting.services import add_prospect

    deanon_contact: DeanonymizedContact = DeanonymizedContact.query.get(deanon_contact_id)
    track_event: TrackEvent = TrackEvent.query.get(deanon_contact.track_event_id)
    track_source: TrackSource = TrackSource.query.get(track_event.track_source_id)
    client_id = track_source.client_id
    random_unassigned_client_archetype: ClientArchetype = ClientArchetype.query.filter(
        ClientArchetype.client_id == client_id,
        ClientArchetype.is_unassigned_contact_archetype == True,
    ).first()
    archetype_id = random_unassigned_client_archetype.id
    client_sdr_id = random_unassigned_client_archetype.client_sdr_id

    current_company = deanon_contact.company
    name = deanon_contact.name
    stripped_linkedin_url = deanon_contact.linkedin
    title = deanon_contact.title
    twitter_url = ''
    segment_id = None

    prospect_id = add_prospect(
        client_id=client_id,
        archetype_id=archetype_id,
        client_sdr_id=client_sdr_id,
        company=current_company,
        full_name=name,
        linkedin_url=stripped_linkedin_url,
        title=title,
        twitter_url=twitter_url,
        segment_id=segment_id,
    )

    deanon_contact.prospect_id = prospect_id
    db.session.add(deanon_contact)
    db.session.commit()

    return prospect_id



def deanonymize_track_events_for_people_labs(track_event_id):
    from src.contacts.services import apollo_org_search, save_apollo_query

    client_sdr_id = 34

    import pdb; pdb.set_trace()

    track_event: TrackEvent = TrackEvent.query.get(track_event_id)

    if not track_event or track_event.company_identify_api != "peopledatalabs" or not track_event.company_identify_payload:
        return "Track event not found or not identified by People Data Labs"
    
    
    # Check if there's already a deanonymized contact for the same IP address
    existing_contact = DeanonymizedContact.query.join(TrackEvent).filter(
        TrackEvent.ip_address == track_event.ip_address,
        DeanonymizedContact.track_event_id == TrackEvent.id
    ).first()

    if existing_contact:
        new_contact = DeanonymizedContact(
            name=existing_contact.name,
            company=existing_contact.company,
            title=existing_contact.title,
            visited_date=track_event.created_at,
            linkedin=existing_contact.linkedin,
            email=None,
            tag=None,
            prospect_id=existing_contact.prospect_id,
            location=existing_contact.location,
            track_event_id=track_event.id,
            company_size=existing_contact.company_size
        )
        db.session.add(new_contact)
        db.session.commit()
    
    # confidence score
    p_confidence = deep_get(track_event.company_identify_payload, "data.person.confidence")
    c_confidence = deep_get(track_event.company_identify_payload, "data.company.confidence")
        
    company_payload = deep_get(track_event.company_identify_payload, "data.company", {})
    location = deep_get(company_payload, "location.locality") or deep_get(track_event.company_identify_payload, "data.ip.location")
    company_name = deep_get(company_payload, "display_name")
    company_website = deep_get(company_payload, "website")
    company_size = deep_get(company_payload, "size")
    employee_count = deep_get(company_payload, "employee_count")
    person_payload = deep_get(track_event.company_identify_payload, "data.person", {})
    job_title_role = deep_get(person_payload, "job_title_role")
    job_title_levels = deep_get(person_payload, "job_title_levels")
    ip_location = deep_get(track_event.company_identify_payload, "data.ip.location.region")

    if p_confidence and c_confidence:
        pass
    else:
        return "Low confidence"

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
        'Director': ['head', 'director', 'head'],
        'Owner': ['owner', 'founder', 'c_suite'],
        'Vp': ['vp', 'head', 'director'],
        'Manager': ['manager']
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
            person_locations=[ip_location],
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

    print("Found {} contacts".format(len(contacts)))

    if not contacts:
        return "No contacts"
    
    contact = None
    if len(contacts) > 1:
        person_job_title_sub_role = deep_get(person_payload, "job_title_sub_role")
        if person_job_title_sub_role:
            for person in contacts:
                if person['title'] == person_job_title_sub_role or person_job_title_sub_role.lower() in person['title'].lower():
                    contact = person
                    break
        if not contact and len(contacts) < 5:
            contact = contacts[0]

    elif len(contacts) > 0:
        contact = contacts[0]

    if not contact:
        return "No contact found"

    linkedin_url = deep_get(contact, "linkedin_url") 
    name = deep_get(contact, "name")
    title = deep_get(contact, "title")
    photo_url = deep_get(contact, "photo_url")
    org_name = deep_get(contact, "organization.name")
    org_website = deep_get(contact, "organization.website_url")
    state = deep_get(contact, "state")
    city = deep_get(contact, "city")
    country = deep_get(contact, "country")
    location = f"{city}, {state}, {country}"
    website_viewed = track_event.window_location
    
    # verify that the org_name or org_website is similar to the company_name or company_website
    if not(
        (org_name and company_name and org_name.lower() in company_name.lower()) or
        (org_website and company_website and org_website.lower() in company_website.lower())
    ):
        return "Company name or website do not match"
    
    deanon_contact: DeanonymizedContact = DeanonymizedContact(
        name=name,
        company=org_name,
        title=title,
        visited_date=track_event.created_at,
        linkedin=linkedin_url,
        email=None,
        tag=None,
        prospect_id=None,
        location=location,
        track_event_id=track_event.id,
        company_size=company_size
    )
    db.session.add(deanon_contact)
    db.session.commit()

    track_source: TrackSource = TrackSource.query.get(track_event.track_source_id)
    client_id = track_source.client_id
    client: Client = Client.query.get(client_id)
    webhook_url = client.pipeline_notifications_webhook_url

    webhook_urls = [URL_MAP["sales-visitors"]]
    if webhook_url and client_id != 47:
        webhook_urls.append(webhook_url)

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
        webhook_urls=webhook_urls,
    )

    process_deanonymized_contact(deanon_contact.id)
    categorize_deanonyomized_contact(deanon_contact.id)

    return contacts

def get_website_tracking_script(client_sdr_id: int):
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    track_source: TrackSource = TrackSource.query.filter(
        TrackSource.client_id == client_sdr.client_id,
    ).first()

    if not track_source:
        track_source: TrackSource = TrackSource(
            client_id=client_sdr.client_id,
            track_key=generate_uuid(base=datetime.datetime.now().isoformat())
        )
        db.session.add(track_source)
        db.session.commit()

    return '''
<script>
    !function(){function t(){fetch("https://api.ipify.org/?format=json").then(t=>t.json()).then(t=>{var e,n,o,i;e=t.ip,o=JSON.stringify({ip:e,page:n=window.location.href,track_key:"''' + track_source.track_key + '''"}),(i=new XMLHttpRequest).open("POST","https://sellscale-api-prod.onrender.com/track/webpage",!0),i.setRequestHeader("Content-Type","application/json"),i.send(o)}).catch(t=>console.error("Error fetching IP:",t))}t(),window.onpopstate=function(e){t()},new MutationObserver(function(e){e.forEach(function(e){"childList"===e.type&&t()})}).observe(document.body,{childList:!0,subtree:!0})}();
</script>
    '''

def get_most_recent_track_event(client_sdr_id: int):
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    track_source: TrackSource = TrackSource.query.filter(
        TrackSource.client_id == client_sdr.client_id,
    ).first()

    # most recent track event
    track_event: TrackEvent = TrackEvent.query.filter(
        TrackEvent.track_source_id == track_source.id,
    ).order_by(TrackEvent.created_at.desc()).first()
    return track_event

def verify_track_source(client_sdr_id: int):
    track_event = get_most_recent_track_event(client_sdr_id)

    track_source: TrackSource = TrackSource.query.get(track_event.track_source_id)
    if not track_source:
        return False, "Track source not found"
    
    track_source.verified = True
    track_source.website_base = track_event.window_location and track_event.window_location.split("/")[2]
    db.session.add(track_source)
    db.session.commit()

    return True, track_source.track_key

def get_client_track_source_metadata(client_sdr_id: int):
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    track_source: TrackSource = TrackSource.query.filter(
        TrackSource.client_id == client_sdr.client_id,
    ).first()

    return track_source.to_dict()

def track_event_history(client_sdr_id: int, days=14):
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client_id = client_sdr.client_id

    query = """
        select 
            to_char(track_event.created_at, 'YYYY-MM-DD') created_at,
            count(distinct track_event.ip_address) "distinct_visits",
            count(distinct deanonymized_contact.linkedin) "distinct_deanonymized_visits"
        from track_event
            join track_source on track_source.id = track_event.track_source_id
            left join deanonymized_contact on deanonymized_contact.track_event_id = track_event.id
        where
            track_source.client_id = {client_id}
            and track_event.created_at > NOW() - '14 days'::INTERVAL
        group by 1
        order by 1 desc
        limit {days};
    """

    query = query.format(client_id=client_id, days=days)
    result = db.engine.execute(query)
    
    formatted_result = []
    for row in result:
        formatted_result.append({
            "label": row["created_at"],
            "distinct_visits": row["distinct_visits"],
            "distinct_deanonymized_visits": row["distinct_deanonymized_visits"]
        })
    
    return formatted_result

def top_locations(client_sdr_id, days=14):
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client_id = client_sdr.client_id

    query = """
    select 
        deanonymized_contact.location location,
        count(distinct deanonymized_contact.linkedin) "distinct_deanonymized_visits"
    from track_event
        join track_source on track_source.id = track_event.track_source_id
        left join deanonymized_contact on deanonymized_contact.track_event_id = track_event.id
    where
        track_source.client_id = {client_id}
        and track_event.created_at > NOW() - '{days} days'::INTERVAL
        and deanonymized_contact.location is not null
    group by 1
    order by 2 desc
    limit 5;
    """

    query = query.format(client_id=client_id, days=days)
    result = db.engine.execute(query)

    formatted_result = []
    for row in result:
        formatted_result.append({
            "location": row["location"],
            "distinct_deanonymized_visits": row["distinct_deanonymized_visits"]
        })

    return formatted_result

def deanonymized_contacts(client_sdr_id, days=14):
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client_id = client_sdr.client_id

    query = """
    select 
        deanonymized_contact.id,
        deanonymized_contact.name,
        deanonymized_contact.title,
        deanonymized_contact.linkedin,
        deanonymized_contact.company,
        deanonymized_contact.tag,
        max(deanonymized_contact.visited_date) recent_visited_date,
        count(deanonymized_contact.id) num_visits
    from track_event
        join track_source on track_source.id = track_event.track_source_id
        left join deanonymized_contact on deanonymized_contact.track_event_id = track_event.id
    where
        track_source.client_id = {client_id}
        and track_event.created_at > NOW() - '{date} days'::INTERVAL
        and deanonymized_contact.location is not null
    group by 1,2,3,4,5,6
    order by 5 desc
    """

    query = query.format(client_id=client_id, date=days)
    result = db.engine.execute(query)

    formatted_result = []
    for row in result:
        formatted_result.append({
            "id": row["id"],
            "avatar": '',
            "sdr_name": row["name"],
            "linkedin": True if row["linkedin"] else False,
            "email": '',
            "job": row["title"],
            "company": row["company"],
            "visit_date": row["recent_visited_date"],
            "total_visit": row["num_visits"],
            "intent_score": 'MEDIUM' if row["num_visits"] == 1 else 'HIGH' if row["num_visits"] > 1 and row["num_visits"] <= 2 else 'VERY HIGH',
            "tag": row["tag"]
        })

    return formatted_result

def create_icp_route(
    client_sdr_id: int,
    title: str,
    description: str,
    filter_company: str,
    filter_title: str,
    filter_location: str,
    filter_company_size: str,
    segment_id: Optional[int] = None,
    send_slack: bool = False,
):
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    icp_route = ICPRouting(
        client_id=client_sdr.client_id,
        title=title,
        description=description,
        filter_company=filter_company,
        filter_title=filter_title,
        filter_location=filter_location,
        filter_company_size=filter_company_size,
        segment_id=segment_id,
        send_slack=send_slack,
        active=True
    )

    db.session.add(icp_route)
    db.session.commit()

    return icp_route

def update_icp_route(
    client_sdr_id: int,
    icp_route_id: int,
    title: Optional[str] = None,
    description: Optional[str] = None,
    filter_company: Optional[str] = None,
    filter_title: Optional[str] = None,
    filter_location: Optional[str] = None,
    filter_company_size: Optional[str] = None,
    segment_id: Optional[int] = None,
    send_slack: Optional[bool] = None,
    active: Optional[bool] = None,
):
    client_sd: ClientSDR = ClientSDR.query.get(client_sdr_id)
    icp_route = ICPRouting.query.get(icp_route_id)

    if not icp_route or icp_route.client_id != client_sd.client_id:
        return "ICP Route not found"

    if title:
        icp_route.title = title
    if description:
        icp_route.description = description
    if filter_company:
        icp_route.filter_company = filter_company
    if filter_title:
        icp_route.filter_title = filter_title
    if filter_location:
        icp_route.filter_location = filter_location
    if filter_company_size:
        icp_route.filter_company_size = filter_company_size
    if segment_id:
        icp_route.segment_id = segment_id
    if send_slack is not None:
        icp_route.send_slack = send_slack
    if active is not None:
        icp_route.active = active

    db.session.commit()

    return icp_route

def get_all_icp_routes(client_sdr_id: int):
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    icp_routes = ICPRouting.query.filter(
        ICPRouting.client_id == client_sdr.client_id
    ).order_by(ICPRouting.created_at.desc()).all()

    return icp_routes

def get_icp_route_details(client_sdr_id: int, icp_route_id: int):
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    icp_route = ICPRouting.query.filter(
        ICPRouting.client_id == client_sdr.client_id,
        ICPRouting.id == icp_route_id
    ).first()

    if not icp_route:
        return "ICP Route not found"

    return icp_route.to_dict()

def categorize_deanonymized_contacts(deanonymized_contact_ids: list[int], async_=True):
    for deanon_contact_id in deanonymized_contact_ids:
        if async_:
            categorize_deanonyomized_contact.delay(deanon_contact_id)
        else:
            categorize_deanonyomized_contact(deanon_contact_id)

    return True

@celery.task
def categorize_deanonyomized_contact(deanon_contact_id: int):
    deanon_contact: DeanonymizedContact = DeanonymizedContact.query.get(deanon_contact_id)
    track_event: TrackEvent = TrackEvent.query.get(deanon_contact.track_event_id)
    track_source: TrackSource = TrackSource.query.get(track_event.track_source_id)
    client_id = track_source.client_id
    
    icp_routings: list[ICPRouting] = ICPRouting.query.filter(
        ICPRouting.client_id == client_id,
        ICPRouting.active == True
    ).all()

    company_information = simple_perplexity_response("llama-3-sonar-large-32k-online", "Tell me about the company called {}. Respond in 1 succinct paragraph, 2-4 sentences max. Include what they do, what they sell, who they serve.".format(deanon_contact.company))
    prospect_information = simple_perplexity_response("llama-3-sonar-large-32k-online", "Tell me about the person named {} who works at {}. Respond in 1 succinct paragraph, 2-4 sentences max. Include their role, responsibilities, and any other relevant information.".format(deanon_contact.name, deanon_contact.company))

    prompt = """
You are an ICP categorizer. Here are the options for the different ICPs you have access to:
{icp_routes}

Here is information about the prospect we are considering.
Name: {name}
Company: {company}
Title: {title}
Visited Date: {visited_date}
LinkedIn: {linkedin}
Email: {email}
Location: {location}
Company Size: {company_size}

Short summary about prospect:
{prospect_information}

Short summary about company: 
{company_information}

Which route should we categorize this prospect under? 

IMPORTANT: Only respond with the ICP Route Id # and absolutely nothing else.
ex. 1
ex. 3

Icp Route Id #:"""

    gpt_response = wrapped_chat_gpt_completion(
        messages=[
            {
                "role": "user",
                "content": prompt.format(
                    icp_routes="\n".join([f"{route.id}: {route.title} - {route.description}" for route in icp_routings] + ["-1: None of the above"]),
                    name=deanon_contact.name,
                    company=deanon_contact.company,
                    title=deanon_contact.title,
                    visited_date=deanon_contact.visited_date,
                    linkedin=deanon_contact.linkedin,
                    email=deanon_contact.email,
                    location=deanon_contact.location,
                    company_size=deanon_contact.company_size,
                    prospect_information=prospect_information[0],
                    company_information=company_information[0]
                )
            }
        ],
        max_tokens=30,
        model='gpt-4o'
    )

    icp_route_id = int(gpt_response)

    icp_route: ICPRouting = ICPRouting.query.get(icp_route_id)
    if not icp_route:
        return "ICP Route not found"
    
    deanon_contact.icp_route_id = icp_route_id
    deanon_contact.tag = icp_route.title
    db.session.add(deanon_contact)
    db.session.commit()

    return icp_route_id
