from datetime import datetime
from typing import Optional
from src.message_generation.models import GeneratedMessage, GeneratedMessageStatus
from src.client.models import Client, ClientArchetype, ClientSDR
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
from src.utils.slack import send_slack_message
from flask import jsonify
from src.utils.converters.string_converters import (
    get_last_name_from_full_name,
    get_first_name_from_full_name,
)


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

    if (
        current_status == ProspectStatus.ACTIVE_CONVO
        and new_status == ProspectStatus.DEMO_SET
    ):
        return update_prospect_status_multi_step(
            prospect_id=prospect_id,
            statuses=[
                ProspectStatus.SCHEDULING,
                ProspectStatus.DEMO_SET,
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

    try:
        update_prospect_status_multi_step(
            prospect_id=prospect_id, statuses=[new_status]
        )
    except Exception:
        return False

    return True


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

    # Ensures that Active Conversation individuals no longer receive AI responses.
    # Given that the SDR has set this Prospect's Archetype to disable AI after prospect engagement.
    ca: ClientArchetype = ClientArchetype.query.get(p.archetype_id)
    if (
        new_status == ProspectStatus.ACTIVE_CONVO
        and ca.disable_ai_after_prospect_engaged
    ):
        p.deactivate_ai_engagement = True

    db.session.add(p)
    db.session.commit()

    return True


def send_slack_reminder_for_prospect(prospect_id: int, alert_reason: str):
    """Sends an alert in the Client and Client SDR's Slack channel when a prospect's message needs custom attention.

    Args:
        prospect_id (int): ID of the Prospect
        alert_reason (str): Reason for the alert

    Returns:
        bool: True if the alert was sent successfully, False otherwise
    """
    p: Prospect = Prospect.query.get(prospect_id)
    if not p:
        return False
    p_name = p.full_name
    last_li_message = p.li_last_message_from_prospect
    li_convo_thread = p.li_conversation_thread_id

    c_csdr_webhook_urls = []
    c: Client = Client.query.get(p.client_id)
    if not c:
        return False
    c_slack_webhook = c.pipeline_notifications_webhook_url
    if c_slack_webhook:
        c_csdr_webhook_urls.append(c_slack_webhook)

    csdr: ClientSDR = ClientSDR.query.get(p.client_sdr_id)
    if not csdr:
        return False
    csdr_slack_webhook = csdr.pipeline_notifications_webhook_url
    if csdr_slack_webhook:
        c_csdr_webhook_urls.append(csdr_slack_webhook)

    sent = send_slack_message(
        message=f"Prospect {p_name} needs your attention! {alert_reason}",
        blocks=[
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": ":rotating_light: {} (#{}) needs your attention".format(
                        p_name, prospect_id
                    ),
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "{} last responded to you with:\n>{}".format(
                        p_name, last_li_message
                    ),
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "SellScale AI was uncertain of how to handle the message for the following reason:\n`{}`".format(
                        alert_reason
                    ),
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "Please continue the conversation via LinkedIn",
                },
                "accessory": {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Go to LinkedIn",
                        "emoji": True,
                    },
                    "value": li_convo_thread or "https://www.linkedin.com",
                    "url": li_convo_thread or "https://www.linkedin.com",
                    "action_id": "button-action",
                },
            },
        ],
        webhook_urls=c_csdr_webhook_urls,
    )
    if sent:
        p.last_reviewed = datetime.now()
        p.deactivate_ai_engagement = True
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

    first_name = get_first_name_from_full_name(full_name=full_name)
    last_name = get_last_name_from_full_name(full_name=full_name)

    if not prospect_exists:
        prospect: Prospect = Prospect(
            client_id=client_id,
            archetype_id=archetype_id,
            company=company,
            company_url=company_url,
            employee_count=employee_count,
            full_name=full_name,
            first_name=first_name,
            last_name=last_name,
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


@celery.task(bind=True, max_retries=3, default_retry_delay=10)
def create_prospect_from_linkedin_link(
    self, archetype_id: int, url: str, batch: str, email: str = None
):
    try:
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
        full_name = (
            deep_get(payload, "first_name") + " " + deep_get(payload, "last_name")
        )
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
    except Exception as e:
        raise self.retry(exc=e, countdown=2**self.request.retries)


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

    if not prospect.times_bumped:
        prospect.times_bumped = 0
    prospect.times_bumped += 1

    db.session.add(prospect)
    db.session.commit()

    return True


def validate_prospect_json_payload(payload: dict, email_enabled: bool = False):
    """Validate the CSV payload sent by the SDR through Retool.
    This is in respect to validating a prospect.

    At the moment, only linkedin_url and email are enforced (one or the other).
    In the future, additional fields can be added as we see fit.

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

    Args:
        payload (dict): The payload sent by the SDR through Retool.

    Returns:
        (bool, str): A tuple of (is_valid, error_message)
    """
    if len(payload) == 0:
        return False, "No prospects were received."

    for prospect in payload:
        email = prospect.get("email")
        linkedin_url = prospect.get("linkedin_url")

        if not linkedin_url:
            return (
                False,
                "Could not find the required 'linkedin_url' field. Please check your CSV, or make sure each Prospect has a linkedin_url field.",
            )

        if email_enabled and not email:
            return (
                False,
                "Since you are uploading an email list, make sure that every row has an email! Please verify your CSV.",
            )

    return True, "No Error"


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
    batch_id = generate_random_alphanumeric(32)

    seen_linkedin_urls = set()
    no_duplicates_payload = []
    duplicate_count = 0
    for prospect in payload:
        linkedin_url = prospect.get("linkedin_url")
        if linkedin_url not in seen_linkedin_urls:
            seen_linkedin_urls.add(linkedin_url)
            no_duplicates_payload.append(prospect)
        else:
            duplicate_count += 1

    num_prospects = len(no_duplicates_payload)
    prospect_upload_batch: ProspectUploadBatch = ProspectUploadBatch(
        archetype_id=archetype_id,
        batch_id=batch_id,
        num_prospects=num_prospects,
    )
    db.session.add(prospect_upload_batch)
    db.session.commit()

    for prospect in no_duplicates_payload:
        # These have been validated by the time we get here.
        linkedin_url = prospect.get("linkedin_url")
        email = prospect.get("email")

        create_prospect_from_linkedin_link.delay(
            archetype_id=archetype_id, url=linkedin_url, batch=batch_id, email=email
        )

        # In case the csv has a field, we should stay true to those fields.
        # manual_add_prospect: Prospect = Prospect.query.get(prospect_id)
        # if prospect.get("company"):
        #     manual_add_prospect.company = prospect.get("company")
        # if prospect.get("company_url"):
        #     manual_add_prospect.company_url = prospect.get("company_url")
        # if prospect.get("full_name"):
        #     manual_add_prospect.full_name = prospect.get("full_name")
        # if prospect.get("title"):
        #     manual_add_prospect.title = prospect.get("title")

    return "Success", duplicate_count


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


def batch_mark_as_lead(payload: int):
    """Updates prospects as is_lead

    payload = [
        {'id': 1, 'is_lead': True},
        ...
    ]
    """
    for entry in payload:
        prospect_id = entry["id"]
        is_lead = entry["is_lead"]

        prospect: Prospect = Prospect.query.get(prospect_id)
        if not prospect:
            continue
        prospect.is_lead = is_lead
        db.session.add(prospect)
        db.session.commit()

    return True
