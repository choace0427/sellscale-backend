from datetime import datetime
from typing import Optional
from src.message_generation.models import GeneratedMessage, GeneratedMessageStatus
from src.client.models import Client, ClientArchetype
from src.research.linkedin.services import research_personal_profile_details
from src.prospecting.models import Prospect, ProspectStatus
from app import db
from src.utils.abstract.attr_utils import deep_get
from src.utils.random_string import generate_random_alphanumeric


def prospect_exists_for_archetype(linkedin_url: str, client_id: int):
    from src.prospecting.models import Prospect

    p: Prospect = Prospect.query.filter(
        Prospect.linkedin_url == linkedin_url, Prospect.client_id == client_id
    ).all()

    if len(p) > 0:
        return True
    return False


def update_prospect_status(prospect_id: int, new_status: ProspectStatus):
    from src.prospecting.models import Prospect, ProspectStatus

    p: Prospect = Prospect.query.get(prospect_id)
    current_status = p.status

    if (
        current_status == ProspectStatus.SENT_OUTREACH
        and new_status == ProspectStatus.RESPONDED
    ):
        return update_prospect_status_multi_step(
            prospect_id=prospect_id,
            statuses=[ProspectStatus.ACCEPTED, ProspectStatus.RESPONDED],
        )

    if (
        current_status == ProspectStatus.ACCEPTED
        and new_status == ProspectStatus.ACTIVE_CONVO
    ):
        return update_prospect_status_multi_step(
            prospect_id=prospect_id,
            statuses=[
                ProspectStatus.RESPONDED,
                ProspectStatus.ACTIVE_CONVO,
            ],
        )

    if (
        current_status == ProspectStatus.SENT_OUTREACH
        and new_status == ProspectStatus.ACTIVE_CONVO
    ):
        return update_prospect_status_multi_step(
            prospect_id=prospect_id,
            statuses=[
                ProspectStatus.ACCEPTED,
                ProspectStatus.RESPONDED,
                ProspectStatus.ACTIVE_CONVO,
            ],
        )

    if (
        current_status == ProspectStatus.RESPONDED
        and new_status == ProspectStatus.SCHEDULING
    ):
        return update_prospect_status_multi_step(
            prospect_id=prospect_id,
            statuses=[
                ProspectStatus.ACTIVE_CONVO,
                ProspectStatus.SCHEDULING,
            ],
        )

    if (
        current_status == ProspectStatus.ACCEPTED
        and new_status == ProspectStatus.SCHEDULING
    ):
        return update_prospect_status_multi_step(
            prospect_id=prospect_id,
            statuses=[
                ProspectStatus.RESPONDED,
                ProspectStatus.ACTIVE_CONVO,
                ProspectStatus.SCHEDULING,
            ],
        )

    if (
        current_status == ProspectStatus.SENT_OUTREACH
        and new_status == ProspectStatus.SCHEDULING
    ):
        return update_prospect_status_multi_step(
            prospect_id=prospect_id,
            statuses=[
                ProspectStatus.ACCEPTED,
                ProspectStatus.RESPONDED,
                ProspectStatus.ACTIVE_CONVO,
                ProspectStatus.SCHEDULING,
            ],
        )

    return update_prospect_status_multi_step(
        prospect_id=prospect_id, statuses=[new_status]
    )


def update_prospect_status_multi_step(prospect_id: int, statuses: list):
    success = True
    for status in statuses:
        success = (
            update_prospect_status_helper(prospect_id=prospect_id, new_status=status)
            and success
        )

    return success


def update_prospect_status_helper(prospect_id: int, new_status: ProspectStatus):
    # Status Mapping here: https://excalidraw.com/#json=u5Ynh702JjSM1BNnffooZ,OcIRq8s0Ev--ACW10UP4vQ
    from src.prospecting.models import (
        Prospect,
        ProspectStatusRecords,
        VALID_FROM_STATUSES_MAP,
    )

    p: Prospect = Prospect.query.get(prospect_id)
    if p.status == new_status:
        return True

    if p.status not in VALID_FROM_STATUSES_MAP[new_status]:
        raise Exception(f"Invalid status transition from {p.status} to {new_status}")

    record: ProspectStatusRecords = ProspectStatusRecords(
        prospect_id=prospect_id,
        from_status=p.status,
        to_status=new_status,
    )
    db.session.add(record)
    db.session.commit()

    if not p:
        return False

    p.status = new_status
    db.session.add(p)
    db.session.commit()

    return True


def add_prospect(
    client_id: int,
    archetype_id: int,
    company: Optional[str],
    company_url: Optional[str],
    employee_count: Optional[str],
    full_name: Optional[str],
    industry: Optional[str],
    linkedin_url: Optional[str],
    linkedin_bio: Optional[str],
    title: Optional[str],
    twitter_url: Optional[str],
    batch: str,
):
    status = ProspectStatus.PROSPECTED

    prospect_exists = prospect_exists_for_archetype(
        linkedin_url=linkedin_url, client_id=client_id
    )

    if not prospect_exists:
        prospect: Prospect = Prospect(
            client_id=client_id,
            archetype_id=archetype_id,
            company=company,
            company_url=company_url,
            employee_count=employee_count,
            full_name=full_name,
            industry=industry,
            linkedin_url=linkedin_url,
            linkedin_bio=linkedin_bio,
            title=title,
            twitter_url=twitter_url,
            batch=batch,
            status=status,
        )
        db.session.add(prospect)
        db.session.commit()


def find_prospect_by_linkedin_slug(slug: str, client_id: int):
    prospect: Prospect = Prospect.query.filter(
        Prospect.linkedin_url.like(f"%{slug}%"),
        Prospect.client_id == client_id,
    ).first()
    return prospect


def get_linkedin_slug_from_url(url: str):
    try:
        split = url.split("/in/")
        slug_with_suffix = split[1]
        slug = slug_with_suffix.split("/")[0]

        return slug
    except:
        raise Exception("Unable to extract slug.")


def get_navigator_slug_from_url(url: str):
    # https://www.linkedin.com/sales/lead/ACwAAAIwZ58B_JRTBED15c8_ZSr00s5KzlHbt3o,NAME_SEARCH,Y5K9
    # becomes ACwAAAIwZ58B_JRTBED15c8_ZSr00s5KzlHbt3o
    try:
        split = url.split("/lead/")
        slug_with_suffix = split[1]
        slug = slug_with_suffix.split(",")[0]

        return slug
    except:
        raise Exception("Unable to extract slug")


def create_prospects_from_linkedin_link_list(
    url_string: str, archetype_id: int, delimeter: str = "..."
):
    from tqdm import tqdm

    prospect_urls = url_string.split(delimeter)
    batch = generate_random_alphanumeric(32)

    for url in tqdm(prospect_urls):
        create_prospect_from_linkedin_link(
            archetype_id=archetype_id, url=url, batch=batch
        )

    return True


def create_prospect_from_linkedin_link(archetype_id: int, url: str, batch: str):
    if "/in/" in url:
        slug = get_linkedin_slug_from_url(url)
    elif "/lead/" in url:
        slug = get_navigator_slug_from_url(url)

    payload = research_personal_profile_details(profile_id=slug)

    if payload.get("detail") == "Profile data cannot be retrieved." or not deep_get(
        payload, "first_name"
    ):
        return False

    client_archetype: ClientArchetype = ClientArchetype.query.get(archetype_id)
    client: Client = Client.query.get(client_archetype.client_id)
    client_id = client.id

    company_name = deep_get(payload, "position_groups.0.company.name")
    company_url = deep_get(payload, "position_groups.0.company.url")
    employee_count = (
        str(deep_get(payload, "position_groups.0.company.employees.start"))
        + "-"
        + str(deep_get(payload, "position_groups.0.company.employees.end"))
    )
    full_name = deep_get(payload, "first_name") + " " + deep_get(payload, "last_name")
    industry = deep_get(payload, "industry")
    linkedin_url = "linkedin.com/in/{}".format(deep_get(payload, "profile_id"))
    linkedin_bio = deep_get(payload, "summary")
    title = deep_get(payload, "sub_title")
    twitter_url = None

    add_prospect(
        client_id=client_id,
        archetype_id=archetype_id,
        company=company_name,
        company_url=company_url,
        employee_count=employee_count,
        full_name=full_name,
        industry=industry,
        linkedin_url=linkedin_url,
        linkedin_bio=linkedin_bio,
        title=title,
        twitter_url=twitter_url,
        batch=batch,
    )

    return True


def batch_mark_prospects_as_sent_outreach(prospect_ids: list):
    from src.prospecting.models import Prospect

    prospects = Prospect.query.filter(Prospect.id.in_(prospect_ids)).all()
    updates = []

    for p in prospects:
        prospect: Prospect = p

        if not prospect or not prospect.approved_outreach_message_id:
            continue

        update_prospect_status(
            prospect_id=prospect.id, new_status=ProspectStatus.SENT_OUTREACH
        )

        message: GeneratedMessage = GeneratedMessage.query.get(
            prospect.approved_outreach_message_id
        )
        message.message_status = GeneratedMessageStatus.SENT
        message.date_sent = datetime.now()
        db.session.add(message)

        db.session.commit()

        updates.append(prospect.id)

    return updates


def batch_update_prospect_statuses(updates: list):
    for update in updates:
        prospect_id = update.get("id")
        new_status = update.get("status")

        update_prospect_status(
            prospect_id=prospect_id, new_status=ProspectStatus[new_status]
        )

    return True


def mark_prospect_reengagement(prospect_id: int):
    prospect: Prospect = Prospect.query.get(prospect_id)
    prospect.last_reviewed = datetime.now()
    db.session.add(prospect)
    db.session.commit()

    return True
