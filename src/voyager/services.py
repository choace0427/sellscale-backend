import json
import time
import datetime as dt
import random
import os

from src.message_generation.services import process_generated_msg_queue

from src.utils.slack import send_slack_message, URL_MAP

from src.ml.services import chat_ai_classify_active_convo

from src.automation.services import update_phantom_buster_li_at

from src.automation.models import PhantomBusterAgent
from src.prospecting.models import ProspectOverallStatus, ProspectStatusRecords

from src.prospecting.services import send_to_purgatory, update_prospect_status_linkedin

from src.li_conversation.models import LinkedinConversationEntry
from src.research.models import IScraperPayloadCache
from src.prospecting.models import Prospect, ProspectStatus, ProspectHiddenReason
from typing import List, Union
from src.li_conversation.services import create_linkedin_conversation_entry
from model_import import ClientSDR
from app import db
from tqdm import tqdm
from src.utils.abstract.attr_utils import deep_get
from src.voyager.linkedin import LinkedIn
from sqlalchemy import or_


def get_profile_urn_id(prospect_id: int, api: Union[LinkedIn, None] = None):
    """Gets the URN ID of a prospect, saving the URN ID if it's not already saved

    Args:
        prospect_id (int): ID of the prospect
        client_sdr_id (int): Optional - ID of the client SDR

    Returns:
        li_urn_id (str) or None: LinkedIn URN ID
    """

    prospect: Prospect = Prospect.query.get(prospect_id)

    if not prospect:
        return None
    if prospect.li_urn_id:
        return str(prospect.li_urn_id)

    # If we don't have the URN ID, we get one from the iscraper data
    iscraper_data: IScraperPayloadCache = (
        IScraperPayloadCache.get_iscraper_payload_cache_by_linkedin_url(
            prospect.linkedin_url
        )
    )
    if iscraper_data:
        personal_info = json.loads(iscraper_data.payload)
        urn_id = personal_info.get("entity_urn", None)
        if urn_id:
            prospect.li_urn_id = urn_id
            db.session.add(prospect)
            db.session.commit()
            return str(urn_id)

    # If we still don't have the URN ID, we get one from Voyager using the public id
    if api and prospect.linkedin_url:
        public_id = prospect.linkedin_url.split("/in/")[1].split("/")[0]
        if public_id:
            profile = api.get_profile(public_id)
            urn_id = profile.get("profile_id", None) if profile else None
            if urn_id:
                prospect.li_urn_id = urn_id
                db.session.add(prospect)
                db.session.commit()
                return str(urn_id)

    return None


def update_linkedin_cookies(client_sdr_id: int, cookies: str):
    """Updates LinkedIn cookies for Voyager

    Args:
        client_sdr_id (int): ID of the client SDR
        cookies (str): LinkedIn cookies

    Returns:
        status_code (int), message (str): HTTP status code
    """

    sdr: ClientSDR = ClientSDR.query.filter(ClientSDR.id == client_sdr_id).first()
    if not sdr:
        return "No client sdr found with this id", 400

    sdr.li_at_token = json.loads(cookies).get("li_at")
    sdr.li_cookies = cookies

    # Update the pb agent
    if os.environ.get("FLASK_ENV") == "production":
        response = update_phantom_buster_li_at(
            client_sdr_id=client_sdr_id, li_at=sdr.li_at_token
        )

    db.session.add(sdr)
    db.session.commit()

    return "Updated cookies", 200


def clear_linkedin_cookies(client_sdr_id: int):
    """Clears LinkedIn cookies for Voyager

    Args:
        client_sdr_id (int): ID of the client SDR

    Returns:
        status_code (int), message (str): HTTP status code
    """

    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if not sdr:
        return "No client sdr found with this id", 400

    sdr.li_cookies = None

    db.session.add(sdr)
    db.session.commit()

    return "Cleared cookies", 200


def fetch_conversation(api: LinkedIn, prospect_id: int, check_for_update: bool = True):
    """Gets the latest conversation with a prospect, syncing the db as needed

    Args:
        api (LinkedIN): instance of LinkedIn class
        prospect_id (int): ID of the prospect
        check_for_update (bool): Optional - Whether to check for new messages from LinkedIn

    Returns:
        convo_entries (LinkedinConversationEntry[]): List of conversation entries
    """

    # Utility function for getting db conversation entries to json
    def get_convo_entries(convo_urn_id: str) -> list[dict]:
        return [
            e.to_dict()
            for e in LinkedinConversationEntry.query.filter_by(
                conversation_url=f"https://www.linkedin.com/messaging/thread/{convo_urn_id}/"
            )
            .order_by(LinkedinConversationEntry.date.desc())
            .all()
        ]

    prospect_urn_id = get_profile_urn_id(prospect_id, api)

    # Check if we need to update the conversation
    details = api.get_conversation_details(prospect_urn_id)

    if details is None:
        return [], "INVALID_CONVO"
    if details == {}:
        return [], "NO_CONVO"

    convo_urn_id = details["id"]
    last_msg_urn_id = details["events"][0]["dashEntityUrn"].replace(
        "urn:li:fsd_message:", ""
    )
    convo_entry = LinkedinConversationEntry.query.filter_by(
        urn_id=last_msg_urn_id
    ).first()

    prospect: Prospect = Prospect.query.get(prospect_id)

    # If the prospect's profile img is expired, update it
    if (
        time.time() * 1000 > int(prospect.img_expire)
        and len(details.get("participants", [])) > 0
    ):
        prospect.img_url = details.get("participants", [])[0].get(
            "com.linkedin.voyager.messaging.MessagingMember", {}
        ).get("miniProfile", {}).get("picture", {}).get(
            "com.linkedin.common.VectorImage", {}
        ).get(
            "rootUrl", ""
        ) + details.get(
            "participants", []
        )[
            0
        ].get(
            "com.linkedin.voyager.messaging.MessagingMember", {}
        ).get(
            "miniProfile", {}
        ).get(
            "picture", {}
        ).get(
            "com.linkedin.common.VectorImage", {}
        ).get(
            "artifacts", [{}, {}, {}]
        )[
            2
        ].get(
            "fileIdentifyingUrlPathSegment", ""
        )
        prospect.img_expire = (
            details.get("participants", [])[0]
            .get("com.linkedin.voyager.messaging.MessagingMember", {})
            .get("miniProfile", {})
            .get("picture", {})
            .get("com.linkedin.common.VectorImage", {})
            .get("artifacts", [{}, {}, {}])[2]
            .get("expiresAt", 0)
        )
        db.session.add(prospect)
        db.session.commit()
    # If the SDR's profile img is expired, update it
    if time.time() * 1000 > int(api.client_sdr.img_expire):
        api.client_sdr.img_url = details.get("events", [])[0].get("from", {}).get(
            "com.linkedin.voyager.messaging.MessagingMember", {}
        ).get("miniProfile", {}).get("picture", {}).get(
            "com.linkedin.common.VectorImage", {}
        ).get(
            "rootUrl", ""
        ) + details.get(
            "events", []
        )[
            0
        ].get(
            "from", {}
        ).get(
            "com.linkedin.voyager.messaging.MessagingMember", {}
        ).get(
            "miniProfile", {}
        ).get(
            "picture", {}
        ).get(
            "com.linkedin.common.VectorImage", {}
        ).get(
            "artifacts", []
        )[
            2
        ].get(
            "fileIdentifyingUrlPathSegment", ""
        )
        api.client_sdr.img_expire = (
            details.get("events", [])[0]
            .get("from", {})
            .get("com.linkedin.voyager.messaging.MessagingMember", {})
            .get("miniProfile", {})
            .get("picture", {})
            .get("com.linkedin.common.VectorImage", {})
            .get("artifacts", [])[2]
            .get("expiresAt", 0)
        )
        db.session.add(api.client_sdr)
        db.session.commit()

    # If li_conversation_thread_id not set, might as well save it now
    if not prospect.li_conversation_thread_id:
        prospect.li_conversation_thread_id = (
            f"https://www.linkedin.com/messaging/thread/{convo_urn_id}/"
        )
        db.session.add(prospect)
        db.session.commit()

    # If not, we return the conversation from the database
    if convo_entry or not check_for_update:
        update_prospect_status(prospect_id=prospect_id, convo_urn_id=convo_urn_id)
        return get_convo_entries(convo_urn_id), "NO_UPDATE"
    else:
        # If we need to update the conversation, we do so
        update_conversation_entries(api, convo_urn_id, prospect)
        messages = get_convo_entries(convo_urn_id)

        # Process if the messages are AI generated or not 
        for message in messages:
            if message.get('ai_generated') is None:
                process_generated_msg_queue(
                    client_sdr_id = api.client_sdr_id,
                    li_message_urn_id = message.get('urn_id'),
                )

        return messages, "UPDATED"



def update_conversation_entries(api: LinkedIn, convo_urn_id: str, prospect: Prospect):
    """Updates LinkedinConversationEntry table with new entries

    Args:
        api (LinkedIn): instance of LinkedIn class
        convo_urn_id (str): LinkedIn convo URN id

    Returns:
        status_code (int), message (str): HTTP status code
    """

    convo = api.get_conversation(convo_urn_id, limit=60)

    if not convo or len(convo) == 0:
        return "No conversation found", 400

    bulk_objects = []
    for message in tqdm(convo):

        first_name = (
            message.get("from", {})
            .get("com.linkedin.voyager.messaging.MessagingMember", {})
            .get("miniProfile", {})
            .get("firstName", "")
        )
        last_name = (
            message.get("from", {})
            .get("com.linkedin.voyager.messaging.MessagingMember", {})
            .get("miniProfile", {})
            .get("lastName", "")
        )
        urn_id = (
            message.get("from", {})
            .get("com.linkedin.voyager.messaging.MessagingMember", {})
            .get("miniProfile", {})
            .get("entityUrn", "")
            .replace("urn:li:fs_miniProfile:", "")
        )
        public_id = (
            message.get("from", {})
            .get("com.linkedin.voyager.messaging.MessagingMember", {})
            .get("miniProfile", {})
            .get("publicIdentifier", "")
        )
        headline = (
            message.get("from", {})
            .get("com.linkedin.voyager.messaging.MessagingMember", {})
            .get("miniProfile", {})
            .get("occupation", "")
        )
        image_url = message.get("from", {}).get(
            "com.linkedin.voyager.messaging.MessagingMember", {}
        ).get("miniProfile", {}).get("picture", {}).get(
            "com.linkedin.common.VectorImage", {}
        ).get(
            "rootUrl", ""
        ) + message.get(
            "from", {}
        ).get(
            "com.linkedin.voyager.messaging.MessagingMember", {}
        ).get(
            "miniProfile", {}
        ).get(
            "picture", {}
        ).get(
            "com.linkedin.common.VectorImage", {}
        ).get(
            "artifacts", [{}, {}, {}]
        )[
            2
        ].get(
            "fileIdentifyingUrlPathSegment", ""
        )
        image_expire = (
            message.get("from", {})
            .get("com.linkedin.voyager.messaging.MessagingMember", {})
            .get("miniProfile", {})
            .get("picture", {})
            .get("com.linkedin.common.VectorImage", {})
            .get("artifacts", [{}, {}, {}])[2]
            .get("expiresAt", 0)
        )
        msg_urn_id = message.get("dashEntityUrn", "").replace("urn:li:fsd_message:", "")

        msg = (
            message.get("eventContent", {})
            .get("com.linkedin.voyager.messaging.event.MessageEvent", {})
            .get("attributedBody", {})
            .get("text", "")
        )

        bulk_objects.append(
            create_linkedin_conversation_entry(
                conversation_url="https://www.linkedin.com/messaging/thread/{value}/".format(
                    value=message.get("entityUrn", "")
                    .replace("urn:li:fs_event:(", "")
                    .split(",")[0]
                ),
                author=first_name + " " + last_name,
                first_name=first_name,
                last_name=last_name,
                date=dt.datetime.utcfromtimestamp(message.get("createdAt", 0) / 1000),
                profile_url="https://www.linkedin.com/in/{value}/".format(value=urn_id),
                headline=headline,
                img_url=image_url,
                img_expire=image_expire,
                connection_degree="1st" if prospect.li_urn_id == urn_id else "You",
                li_url="https://www.linkedin.com/in/{value}/".format(value=public_id),
                message=msg,
                urn_id=msg_urn_id,
            )
        )
    print("saving objects ...")
    bulk_objects = [obj for obj in bulk_objects if obj]
    db.session.bulk_save_objects(bulk_objects)
    db.session.commit()
    print("Done saving!")

    update_prospect_status(prospect.id, convo_urn_id)

    # Classify conversation
    if prospect.status.value.startswith('ACTIVE_CONVO'):

        latest_convo_entries: List[LinkedinConversationEntry] = (
            LinkedinConversationEntry.query.filter_by(
                conversation_url=f"https://www.linkedin.com/messaging/thread/{convo_urn_id}/"
            )
            .order_by(LinkedinConversationEntry.date.desc())
            .limit(5)
            .all()
        )

        messages = []
        for message in latest_convo_entries:
            messages.append({
                "role": 'user' if message.connection_degree == "You" else 'assistant',
                "content": message.message
            })
        classify_active_convo(prospect.id, messages)

    return "OK", 200


def update_prospect_status(prospect_id: int, convo_urn_id: str):

    prospect: Prospect = Prospect.query.get(prospect_id)

    # Update convo URN id if needed
    if not prospect.li_conversation_urn_id and prospect.li_conversation_thread_id:
        prospect.li_conversation_urn_id = prospect.li_conversation_thread_id.split(
            "thread/"
        )[-1].split("/")[0]
        db.session.commit()

    print("Checking for prospect status updates...")
    latest_convo_entries: List[LinkedinConversationEntry] = (
        LinkedinConversationEntry.query.filter_by(
            conversation_url=f"https://www.linkedin.com/messaging/thread/{convo_urn_id}/"
        )
        .order_by(LinkedinConversationEntry.date.desc())
        .all()
    )

    latest_entry_date = (
        latest_convo_entries[0].date if latest_convo_entries else dt.datetime.now()
    )

    if not latest_convo_entries or len(latest_convo_entries) == 0:
        # Set to -1 so we know we check them and they have missing li convo data
        prospect.times_bumped = -1
        db.session.add(prospect)
        db.session.commit()
        return
    
    # We know the first message is AI generated
    if len(latest_convo_entries) >= 1 and latest_convo_entries[0].ai_generated is None:
        latest_convo_entries[0].ai_generated = True
        #db.session.commit()

    first_and_only_message_was_you = (
        len(latest_convo_entries) == 1
        and latest_convo_entries[0].connection_degree == "You"
    )
    last_msg_was_you = (
        len(latest_convo_entries) > 1
        and latest_convo_entries[0].connection_degree == "You"
    )
    last_2_msg_was_you = (
        len(latest_convo_entries) > 2
        and last_msg_was_you
        and latest_convo_entries[1].connection_degree == "You"
    )
    last_3_msg_was_you = (
        len(latest_convo_entries) > 3
        and last_2_msg_was_you
        and latest_convo_entries[2].connection_degree == "You"
    )
    has_prospect_replied = False
    for entry in latest_convo_entries:
        if entry.connection_degree != "You":
            prospect.li_last_message_from_prospect = entry.message
            db.session.add(prospect)
            db.session.commit()
            has_prospect_replied = True
            break
    record_marked_not_interested = (
        ProspectStatusRecords.query.filter_by(
            prospect_id=prospect_id, to_status=ProspectStatus.NOT_INTERESTED
        )
        .order_by(ProspectStatusRecords.created_at.desc())
        .first()
    )

    if (
        prospect.status in (ProspectStatus.SENT_OUTREACH, ProspectStatus.ACCEPTED)
        and not has_prospect_replied
        and last_msg_was_you
    ):
        update_prospect_status_linkedin(prospect.id, ProspectStatus.RESPONDED)
        prospect.times_bumped = 1
        prospect.last_reviewed = latest_entry_date
        db.session.add(prospect)
        db.session.commit()

        # Make sure the prospect isn't in the main pipeline for 48 hours
        send_to_purgatory(prospect.id, 2, ProspectHiddenReason.RECENTLY_BUMPED)

        return

    # Update the prospect status accordingly
    if (
        first_and_only_message_was_you
        and prospect.status == ProspectStatus.SENT_OUTREACH
    ):
        update_prospect_status_linkedin(
            prospect_id=prospect.id,
            new_status=ProspectStatus.ACCEPTED,
        )
        return

    elif (
        prospect.status
        in (
            ProspectStatus.SENT_OUTREACH,
            ProspectStatus.ACCEPTED,
            ProspectStatus.RESPONDED,
        )
        and has_prospect_replied
    ) or (
        prospect.status in [ProspectStatus.NOT_INTERESTED]
        and not last_msg_was_you
        and (
            record_marked_not_interested
            and record_marked_not_interested.created_at < latest_entry_date
        )
    ):
        update_prospect_status_linkedin(
            prospect_id=prospect.id,
            new_status=ProspectStatus.ACTIVE_CONVO,
        )
        return

    # Set the bumped status and times bumped
    if last_3_msg_was_you:
        prospect.times_bumped = 3
        prospect.last_reviewed = latest_entry_date
        db.session.add(prospect)
        db.session.commit()
        return
    if last_2_msg_was_you:
        prospect.times_bumped = 2
        prospect.last_reviewed = latest_entry_date
        db.session.add(prospect)
        db.session.commit()
        return
    if last_msg_was_you:
        prospect.times_bumped = 1
        prospect.last_reviewed = latest_entry_date
        db.session.add(prospect)
        db.session.commit()
        return


def classify_active_convo(prospect_id: int, messages):

    options = [
        'discussing scheduling a time', # ACTIVE_CONVO_SCHEDULING
        'last message was a short reply and the conversation needs more engagement', # ACTIVE_CONVO_NEXT_STEPS
        'there is an objection or abrasion about a product or service', # ACTIVE_CONVO_OBJECTION
        'there is a question', # ACTIVE_CONVO_QUESTION
        'they might not be a great fit or might not be qualified', # ACTIVE_CONVO_QUAL_NEEDED
    ]

    classification = chat_ai_classify_active_convo(messages, options)
    status = None
    if classification == 0:
        status = ProspectStatus.ACTIVE_CONVO_SCHEDULING
    elif classification == 1:
        status = ProspectStatus.ACTIVE_CONVO_NEXT_STEPS
    elif classification == 2:
        status = ProspectStatus.ACTIVE_CONVO_OBJECTION
    elif classification == 3:
        status = ProspectStatus.ACTIVE_CONVO_QUESTION
    elif classification == 4:
        status = ProspectStatus.ACTIVE_CONVO_QUAL_NEEDED
    else:
        status = ProspectStatus.ACTIVE_CONVO

    update_prospect_status_linkedin(prospect_id, status)

    prospect: Prospect = Prospect.query.get(prospect_id)
    client_sdr: ClientSDR = ClientSDR.query.get(prospect.client_sdr_id)
    send_slack_message(
        message=f"Prospect {prospect.full_name} was automatically classified as '{status.value}' because of the state of their convo with {client_sdr.name}!",
        webhook_urls=[URL_MAP["csm-convo-sorter"]],
        blocks=[
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"Prospect {prospect.full_name} was automatically classified as '{status.value}' because of the state of their convo with {client_sdr.name}!",
                    },
                },
                {  # Add prospect title and (optional) last message
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*Title:* {title}\n{last_message}".format(
                            title=prospect.title,
                            last_message=""
                            if not len(messages) > 0
                            else '*Last Message*: "{}"'.format(
                                messages[0].get('content')
                            ),
                        ),
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*SellScale Sight*: <{link}|Link>".format(
                            link="https://app.sellscale.com/home/all-contacts/" + str(prospect.id)
                        ),
                    },
                },
        ]
    )


def fetch_li_prospects_for_sdr(client_sdr_id: int):

    prospects = Prospect.query.filter(
        Prospect.client_sdr_id == client_sdr_id,
        or_(
            Prospect.overall_status == ProspectOverallStatus.ACTIVE_CONVO,
            Prospect.overall_status == ProspectOverallStatus.BUMPED,
            Prospect.overall_status == ProspectOverallStatus.DEMO,
        ),
    ).all()

    print("Fetching conversations for {num} prospects...".format(num=len(prospects)))

    prospect_ids = [
        {"id": p.id, "thread": p.li_conversation_thread_id} for p in prospects
    ]

    for prospect_id in prospect_ids:
        if prospect_id["thread"] is None:
            continue

        # Just update statuses for now
        update_prospect_status(
            prospect_id["id"], prospect_id["thread"].split("/thread/")[1]
        )

        # api = LinkedIn(client_sdr_id)
        # convos, status_text = fetch_conversation(api, prospect_id)
        # print(f"Fetched {len(convos)}, returned status: {status_text}")
        # time.sleep(random.uniform(1, 3))
