from datetime import datetime
from typing import Optional
from src.message_generation.models import GeneratedMessage, GeneratedMessageStatus
from src.client.models import Client, ClientArchetype
from src.research.linkedin.services import research_personal_profile_details
from src.prospecting.models import (
    Prospect,
    ProspectStatus,
    ProspectUploadBatch,
    ProspectNote,
)
from model_import import ResearchPayload
from app import db, celery
from src.utils.abstract.attr_utils import deep_get
from src.utils.random_string import generate_random_alphanumeric
from flask import jsonify


def prospect_exists_for_archetype(full_name: str, client_id: int):
    from src.prospecting.models import Prospect

    p: Prospect = Prospect.query.filter(
        Prospect.full_name == full_name, Prospect.client_id == client_id
    ).first()

    if p:
        return p
    return None


def create_note(prospect_id: int, note: str):
    note_id = create_prospect_note(prospect_id=prospect_id, note=note)
    return note_id


def update_prospect_status(
    prospect_id: int,
    new_status: ProspectStatus,
    message: any = {},
    note: Optional[str] = None,
):
    from src.prospecting.models import Prospect, ProspectStatus
    from src.automation.slack_notification import send_slack_block

    p: Prospect = Prospect.query.get(prospect_id)
    current_status = p.status

    if note:
        create_note(prospect_id=prospect_id, note=note)

    # notifications
    if new_status == ProspectStatus.ACCEPTED:
        send_slack_block(
            message_suffix=" accepted your invite! 😀",
            prospect=p,
            new_status=ProspectStatus.ACCEPTED,
            li_message_payload=message,
        )
    if new_status == ProspectStatus.ACTIVE_CONVO:
        send_slack_block(
            message_suffix=" responded to your outreach! 🙌🏽",
            prospect=p,
            new_status=ProspectStatus.ACTIVE_CONVO,
            li_message_payload=message,
        )
    if new_status == ProspectStatus.SCHEDULING:
        send_slack_block(
            message_suffix=" is scheduling! 🙏🔥",
            prospect=p,
            new_status=ProspectStatus.SCHEDULING,
            li_message_payload={"threadUrl": p.li_conversation_thread_id},
        )
    elif new_status == ProspectStatus.DEMO_SET:
        send_slack_block(
            message_suffix=" set a time to demo!! 🎉🎉🎉",
            prospect=p,
            new_status=ProspectStatus.DEMO_SET,
            li_message_payload={"threadUrl": p.li_conversation_thread_id},
        )

    # status jumps
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

    if new_status in (
        ProspectStatus.SCHEDULING,
        ProspectStatus.RESPONDED,
        ProspectStatus.NOT_INTERESTED,
    ):
        p.last_reviewed = datetime.now()
        db.session.add(p)
        db.session.commit()

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


@celery.task
def add_prospect(
    client_id: int,
    archetype_id: int,
    batch: str,
    company: Optional[str] = None,
    company_url: Optional[str] = None,
    employee_count: Optional[str] = None,
    full_name: Optional[str] = None,
    industry: Optional[str] = None,
    linkedin_url: Optional[str] = None,
    linkedin_bio: Optional[str] = None,
    title: Optional[str] = None,
    twitter_url: Optional[str] = None,
    email: Optional[str] = None,
):
    status = ProspectStatus.PROSPECTED

    prospect_exists = prospect_exists_for_archetype(
        full_name=full_name, client_id=client_id
    )

    if linkedin_url and len(linkedin_url) > 0:
        linkedin_url = linkedin_url.replace("https://www.", "")
        if linkedin_url[-1] == "/":
            linkedin_url = linkedin_url[:-1]

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
            email=email,
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
        slug_with_suffix = slug_with_suffix.split("?")[0]
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
        create_prospect_from_linkedin_link.delay(
            archetype_id=archetype_id, url=url, batch=batch
        )

    return True


@celery.task
def create_prospect_from_linkedin_link(
    archetype_id: int, url: str, batch: str, email: str = None
):
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
        email=email,
    )

    return True


def batch_mark_prospects_as_sent_outreach(prospect_ids: list, client_sdr_id: int):
    from src.prospecting.models import Prospect

    prospects = Prospect.query.filter(Prospect.id.in_(prospect_ids)).all()
    updates = []

    for p in prospects:
        prospect_id = p.id

        match_prospect_as_sent_outreach.delay(
            prospect_id=prospect_id,
            client_sdr_id=client_sdr_id,
        )

        updates.append(prospect_id)

    return updates


@celery.task(bind=True, max_retries=3)
def match_prospect_as_sent_outreach(self, prospect_id: int, client_sdr_id: int):
    try:
        prospect: Prospect = Prospect.query.get(prospect_id)

        prospect.client_sdr_id = client_sdr_id
        db.session.add(prospect)
        db.session.commit()

        if not prospect or not prospect.approved_outreach_message_id:
            return

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
    except Exception as e:
        raise self.retry(exc=e, countdown=2**self.request.retries)


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
    if prospect.status == ProspectStatus.ACCEPTED:
        update_prospect_status(
            prospect_id=prospect_id, new_status=ProspectStatus.RESPONDED
        )

    prospect = Prospect.query.get(prospect_id)
    prospect.last_reviewed = datetime.now()
    db.session.add(prospect)
    db.session.commit()

    return True


def add_prospects_from_json_payload(client_id: int, archetype_id: int, payload: dict):
    """
    This is what a sample payload from Retool will look like.
    payload = [
        {
            "company": "Athelas",
            "company_url": "https://athelas.com/",
            "email": "aakash.adesara@gmail.com",
            "full_name": "Aakash Adesara",
            "linkedin_url": "https://www.linkedin.com/in/aaadesara/",
            "title": "Growth Engineer",
        },
        ....
    ]
    """
    couldnt_add = []
    batch_id = generate_random_alphanumeric(32)

    payload = [x for x in payload if len(x.get("full_name", "")) > 0]
    num_prospects = len(payload)

    prospect_upload_batch: ProspectUploadBatch = ProspectUploadBatch(
        archetype_id=archetype_id,
        batch_id=batch_id,
        num_prospects=num_prospects,
    )
    db.session.add(prospect_upload_batch)
    db.session.commit()

    for prospect in payload:
        linkedin_url = prospect.get("linkedin_url")
        email = prospect.get("email")

        if not linkedin_url and not email:
            couldnt_add.append(prospect.get("full_name"))
            continue

        if linkedin_url:
            create_prospect_from_linkedin_link.delay(
                archetype_id=archetype_id, url=linkedin_url, batch=batch_id, email=email
            )
        else:
            add_prospect.delay(
                client_id=client_id,
                archetype_id=archetype_id,
                company=prospect.get("company"),
                company_url=prospect.get("company_url"),
                email=prospect.get("email"),
                full_name=prospect.get("full_name"),
                linkedin_url=prospect.get("linkedin_url"),
                title=prospect.get("title"),
                batch=batch_id,
            )

    if len(couldnt_add) > 0:
        return False, couldnt_add

    return True, []


def create_prospect_note(prospect_id: int, note: str):
    prospect_note: ProspectNote = ProspectNote(
        prospect_id=prospect_id,
        note=note,
    )
    db.session.add(prospect_note)
    db.session.commit()

    return {"prospect_note_id": prospect_note.id}


def delete_prospect_by_id(prospect_id: int):
    from src.research.linkedin.services import reset_prospect_research_and_messages

    reset_prospect_research_and_messages(prospect_id=prospect_id)

    prospect: Prospect = Prospect.query.get(prospect_id)
    db.session.delete(prospect)
    db.session.commit()

    return True


def toggle_ai_engagement(prospect_id: int):
    """Toggle AI engagement on/off for a prospect.a"""
    prospect: Prospect = Prospect.query.get(prospect_id)
    prospect.deactivate_ai_engagement = not prospect.deactivate_ai_engagement
    db.session.add(prospect)
    db.session.commit()

    return True
