from http.client import ACCEPTED
import json
import time
import datetime as dt
import random
import os
from tqdm import tqdm
from src.operator_dashboard.models import (
    OperatorDashboardEntry,
    OperatorDashboardEntryPriority,
    OperatorDashboardEntryStatus,
    OperatorDashboardTaskType,
)
from src.operator_dashboard.services import (
    create_operator_dashboard_entry,
    mark_task_complete,
)
from src.slack.models import SlackNotificationType
from src.slack.slack_notification_center import (
    create_and_send_slack_notification_class_message,
)
from src.utils.access import is_production

from tomlkit import datetime
from src.bump_framework.models import BumpFramework
from src.client.sdr.services_client_sdr import compute_sdr_linkedin_health
from src.message_generation.models import (
    GeneratedMessage,
    GeneratedMessageCTA,
    GeneratedMessageStatus,
)

from src.message_generation.services import (
    num_messages_in_linkedin_queue,
    process_generated_msg_queue,
)

from src.utils.slack import send_slack_message, URL_MAP

from src.ml.services import (
    chat_ai_classify_active_convo,
    chat_ai_verify_scheduling_convo,
)

from src.automation.services import (
    create_new_auto_connect_phantom,
    has_phantom_buster_config,
    update_phantom_buster_li_at,
)

from src.automation.models import PhantomBusterAgent
from src.prospecting.models import ProspectOverallStatus, ProspectStatusRecords

from src.prospecting.services import send_to_purgatory, update_prospect_status_linkedin

from src.li_conversation.models import LinkedinConversationEntry
from src.research.models import IScraperPayloadCache
from src.prospecting.models import Prospect, ProspectStatus, ProspectHiddenReason
from typing import List, Union
from src.li_conversation.services import create_linkedin_conversation_entry
from model_import import ClientSDR, Client
from app import db, celery
from tqdm import tqdm
from src.utils.abstract.attr_utils import deep_get
from src.voyager.linkedin import LinkedIn
from sqlalchemy import or_
from fuzzywuzzy import fuzz
from datetime import datetime, timedelta
from src.individual.services import add_individual_from_linkedin_url


US_STATES_TIMEZONES = {
    "Alabama": "America/Chicago",
    "Alaska": "America/Anchorage",
    "Arizona": "America/Phoenix",
    "Arkansas": "America/Chicago",
    "California": "America/Los_Angeles",
    "Colorado": "America/Denver",
    "Connecticut": "America/New_York",
    "Delaware": "America/New_York",
    "Florida": "America/New_York",
    "Georgia": "America/New_York",
    "Hawaii": "Pacific/Honolulu",
    "Idaho": "America/Boise",
    "Illinois": "America/Chicago",
    "Indiana": "America/Indianapolis",
    "Iowa": "America/Chicago",
    "Kansas": "America/Chicago",
    "Kentucky": "America/New_York",
    "Louisiana": "America/Chicago",
    "Maine": "America/New_York",
    "Maryland": "America/New_York",
    "Massachusetts": "America/New_York",
    "Michigan": "America/Detroit",
    "Minnesota": "America/Chicago",
    "Mississippi": "America/Chicago",
    "Missouri": "America/Chicago",
    "Montana": "America/Denver",
    "Nebraska": "America/Chicago",
    "Nevada": "America/Los_Angeles",
    "New Hampshire": "America/New_York",
    "New Jersey": "America/New_York",
    "New Mexico": "America/Denver",
    "New York": "America/New_York",
    "North Carolina": "America/New_York",
    "North Dakota": "America/Chicago",
    "Ohio": "America/New_York",
    "Oklahoma": "America/Chicago",
    "Oregon": "America/Los_Angeles",
    "Pennsylvania": "America/New_York",
    "Rhode Island": "America/New_York",
    "South Carolina": "America/New_York",
    "South Dakota": "America/Chicago",
    "Tennessee": "America/Chicago",
    "Texas": "America/Chicago",
    "Utah": "America/Denver",
    "Vermont": "America/New_York",
    "Virginia": "America/New_York",
    "Washington": "America/Los_Angeles",
    "West Virginia": "America/New_York",
    "Wisconsin": "America/Chicago",
    "Wyoming": "America/Denver",
}


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


def update_sdr_timezone_from_li(client_sdr_id: int):
    from src.research.linkedin.services import research_personal_profile_details

    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)

    if not client_sdr:
        return "No client sdr found with this id", 400

    if client_sdr.automatically_added_timezone == True:
        return "Timezone already added", 200

    api = LinkedIn(client_sdr_id=client_sdr_id)
    profile = api.get_user_profile()
    if not profile:
        return "No profile found", 400

    entityUrn = deep_get(profile, "miniProfile.entityUrn", None)
    if not entityUrn:
        return "No entityUrn found", 400

    urn_id = entityUrn.replace("urn:li:fs_miniProfile:", "")
    personal_info = research_personal_profile_details(urn_id)

    if not personal_info:
        return "No personal info found", 400

    location = deep_get(personal_info, "location.country")

    timezone = "America/Los_Angeles"
    if location == "United States":
        state = deep_get(personal_info, "location.state")
        if state:
            timezone = US_STATES_TIMEZONES.get(state, "America/Los_Angeles")
    elif location == "United Kingdom":
        timezone = "Europe/London"
    elif location == "Canada":
        timezone = "America/Toronto"

    client_sdr.timezone = timezone
    client_sdr.automatically_added_timezone = True
    db.session.add(client_sdr)
    db.session.commit()

    return timezone


def update_sdr_li_url(client_sdr_id: int):
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)

    if not client_sdr:
        return "No client sdr found with this id", 400

    if client_sdr.individual_id and client_sdr.linkedin_url:
        return "Li URL already added", 200

    api = LinkedIn(client_sdr_id=client_sdr_id)
    profile = api.get_user_profile()
    if not profile:
        return "No profile found", 400

    public_id = deep_get(profile, "miniProfile.publicIdentifier", None)

    if not public_id:
        return "No public id found", 400

    client_sdr.linkedin_url = f"https://www.linkedin.com/in/{public_id}/"
    db.session.add(client_sdr)
    db.session.commit()

    # Create an individual for the SDR
    try:
        success, indiv_id, created = add_individual_from_linkedin_url(
            client_sdr.linkedin_url
        )
    except:
        from model_import import Individual

        individual = Individual.query.filter(
            Individual.li_public_id == public_id
        ).first()
        if individual:
            indiv_id = individual.id
            created = False

    if indiv_id:
        client_sdr.individual_id = indiv_id
        db.session.add(client_sdr)
        db.session.commit()

    return client_sdr.linkedin_url, created


def update_linkedin_cookies(client_sdr_id: int, cookies: str, user_agent: str):
    """Updates LinkedIn cookies for Voyager

    Args:
        client_sdr_id (int): ID of the client SDR
        cookies (str): LinkedIn cookies
        user_agent (str): User agent

    Returns:
        status_code (int), message (str): HTTP status code
    """

    sdr: ClientSDR = ClientSDR.query.filter(ClientSDR.id == client_sdr_id).first()
    client: Client = Client.query.filter(Client.id == sdr.client_id).first()
    if not sdr:
        return "No client sdr found with this id", 400

    # Remove extra quotes
    cookies = cookies.replace(':""', ':"').replace('"",', '",')

    li_at_token = json.loads(cookies).get("li_at")
    sdr.li_at_token = li_at_token

    sdr.user_agent = user_agent

    db.session.add(sdr)
    db.session.commit()

    try:
        if not has_phantom_buster_config(client_sdr_id=client_sdr_id):
            create_new_auto_connect_phantom(
                client_sdr_id=client_sdr_id,
                linkedin_session_cookie=li_at_token,
                user_agent=user_agent,
            )

        num_messages_in_queue = num_messages_in_linkedin_queue(
            client_sdr_id=client_sdr_id
        )
        webhook_urls = [URL_MAP["eng-sandbox"]]
        if client:
            webhook_urls.append(client.pipeline_notifications_webhook_url)

        success = create_and_send_slack_notification_class_message(
            notification_type=SlackNotificationType.LINKEDIN_CONNECTION_CONNECTED,
            arguments={
                "client_sdr_id": sdr.id,
                "num_messages_in_queue": num_messages_in_queue,
            },
        )
        # send_slack_message(
        #     message=f"*Linkedin Reconnected ✅ for {sdr.name} (#{sdr.id})*\nThere are {num_messages_in_queue} in the LinkedIn outbound queue",
        #     webhook_urls=webhook_urls,
        # )
    except:
        send_slack_message(
            message=f"🚨 URGENT ALERT 🚨: Failed to create phantom buster agent for client sdr id #{str(client_sdr_id)}",
            webhook_urls=[URL_MAP["user-errors"]],
        )

    update_sdr_timezone_from_li(client_sdr_id)
    update_sdr_li_url(client_sdr_id)

    # Update the pb agent
    if is_production():
        response = update_phantom_buster_li_at(
            client_sdr_id=client_sdr_id,
            li_at=sdr.li_at_token,
            user_agent=user_agent,
        )

    # Update dashboard entries for connecting LinkedIn
    dash_tasks: list[OperatorDashboardEntry] = OperatorDashboardEntry.query.filter(
        OperatorDashboardEntry.client_sdr_id == client_sdr_id,
        OperatorDashboardEntry.task_type == OperatorDashboardTaskType.CONNECT_LINKEDIN,
    ).all()
    for entry in dash_tasks:
        mark_task_complete(client_sdr_id, entry.id, False)
    db.session.commit()

    # Run a health check
    success, health, details = compute_sdr_linkedin_health(client_sdr_id)

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

    sdr.li_at_token = None

    db.session.add(sdr)
    db.session.commit()

    return "Cleared cookies", 200


def fetch_conversation(api: LinkedIn, prospect_id: int, check_for_update: bool = True):
    """Gets the latest conversation with a prospect, syncing the db as needed

    Args:
        api (LinkedIn | None): instance of LinkedIn class
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

    if not check_for_update:
        prospect: Prospect = Prospect.query.get(prospect_id)
        if prospect.li_conversation_urn_id:
            # Removing this saves us about ~5 seconds in prod
            # update_prospect_status(prospect_id=prospect_id, convo_urn_id=prospect.li_conversation_urn_id)
            return get_convo_entries(prospect.li_conversation_urn_id), "NO_UPDATE"

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

    # If li_conversation_thread_id not set, might as well save it now
    if not prospect.li_conversation_thread_id or not prospect.li_conversation_urn_id:
        prospect.li_conversation_thread_id = (
            f"https://www.linkedin.com/messaging/thread/{convo_urn_id}/"
        )
        prospect.li_conversation_urn_id = convo_urn_id
        db.session.add(prospect)
        db.session.commit()

    # If not, we return the conversation from the database
    if convo_entry:
        update_prospect_status(prospect_id=prospect_id, convo_urn_id=convo_urn_id)
        return get_convo_entries(convo_urn_id), "NO_UPDATE"
    else:
        # If we need to update the conversation, we do so
        update_conversation_entries(api, convo_urn_id, prospect.id)
        messages = get_convo_entries(convo_urn_id)

        # Process if the messages are AI generated or not
        for message in messages:
            if message.get("ai_generated") is None:
                process_generated_msg_queue(
                    client_sdr_id=api.client_sdr_id,
                    li_message_urn_id=message.get("urn_id"),
                    li_convo_entry_id=message.get("id"),
                )

        return messages, "UPDATED"


def update_conversation_entries(api: LinkedIn, convo_urn_id: str, prospect_id: int):
    """Updates LinkedinConversationEntry table with new entries

    Args:
        api (LinkedIn): instance of LinkedIn class
        convo_urn_id (str): LinkedIn convo URN id

    Returns:
        status_code (int), message (str): HTTP status code
    """
    prospect: Prospect = Prospect.query.get(prospect_id)

    convo = api.get_conversation(convo_urn_id, limit=60)
    update_profile_picture(api.client_sdr_id, prospect_id, convo)

    if not convo or len(convo) == 0:
        send_slack_message(
            message=f"Attempted to update (& auto detect status) for a li convo that's empty! Prospect: {prospect.full_name} (#{prospect.id})",
            webhook_urls=[URL_MAP["csm-convo-sorter"]],
        )

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
                client_sdr_id=prospect.client_sdr_id,
                prospect_id=prospect.id,
            )
        )
    bulk_objects = [obj for obj in bulk_objects if obj]
    db.session.bulk_save_objects(bulk_objects)
    db.session.commit()

    run_conversation_bump_analytics(convo_urn_id=convo_urn_id)

    update_prospect_status(prospect.id, convo_urn_id)

    # Classify conversation
    prospect: Prospect = Prospect.query.get(prospect_id)
    if prospect.status.value.startswith("ACTIVE_CONVO"):
        latest_convo_entries: list[LinkedinConversationEntry] = (
            LinkedinConversationEntry.query.filter_by(
                conversation_url=f"https://www.linkedin.com/messaging/thread/{convo_urn_id}/"
            )
            .order_by(LinkedinConversationEntry.date.desc())
            .limit(5)
            .all()
        )

        messages = []
        for message in latest_convo_entries:
            timestamp = message.date.strftime("%m/%d/%Y, %H:%M:%S")
            messages.append(f"{message.author} ({timestamp}): {message.message}")
        messages.reverse()

        if prospect.status not in [ProspectStatus.ACTIVE_CONVO_SCHEDULING, ProspectStatus.DEMO_SET]:
            classify_active_convo(prospect.id, messages)

    latest_convo_entry: LinkedinConversationEntry = (
        LinkedinConversationEntry.query.filter_by(
            conversation_url=f"https://www.linkedin.com/messaging/thread/{convo_urn_id}/"
        )
        .order_by(LinkedinConversationEntry.date.desc())
        .first()
    )

    # Auto-complete `scheduling_needed_` dash cards
    scheduling_needed_entry: OperatorDashboardEntry = (
        OperatorDashboardEntry.query.filter(
            OperatorDashboardEntry.status == OperatorDashboardEntryStatus.PENDING,
            OperatorDashboardEntry.client_sdr_id == prospect.client_sdr_id,
            OperatorDashboardEntry.tag == f"scheduling_needed_{prospect.id}",
        ).first()
    )
    if scheduling_needed_entry:
        if (
            latest_convo_entry
            and latest_convo_entry.connection_degree == "You"
            and latest_convo_entry.date > scheduling_needed_entry.created_at
        ):
            mark_task_complete(prospect.client_sdr_id, scheduling_needed_entry.id)

    # Auto-complete any `rep_intervention_needed_` dash cards for this prospect
    rep_intervention_needed_entries: list[OperatorDashboardEntry] = (
        OperatorDashboardEntry.query.filter(
            OperatorDashboardEntry.status == OperatorDashboardEntryStatus.PENDING,
            OperatorDashboardEntry.client_sdr_id == prospect.client_sdr_id,
            OperatorDashboardEntry.tag
            == f"rep_intervention_needed_{prospect.client_sdr_id}_{prospect_id}",
        ).all()
    )

    for entry in rep_intervention_needed_entries:
        if (
            latest_convo_entry
            and latest_convo_entry.connection_degree == "You"
            and latest_convo_entry.date > entry.created_at
        ):
            mark_task_complete(prospect.client_sdr_id, entry.id)

    return "OK", 200


@celery.task(name="run_fast_analytics_backfill")
def run_fast_analytics_backfill():
    # Fetch and process data
    fetch_query = """
    SELECT
        bump_framework.id,
        COUNT(DISTINCT a.thread_urn_id) AS new_etl_num_times_used,
        COUNT(DISTINCT b.thread_urn_id) FILTER (WHERE b.connection_degree <> 'You') AS new_etl_num_times_converted
    FROM bump_framework
    JOIN linkedin_conversation_entry a ON a.bump_framework_id = bump_framework.id
    JOIN linkedin_conversation_entry b ON b.thread_urn_id = a.thread_urn_id
    GROUP BY bump_framework.id;
    """
    result = db.session.execute(fetch_query)
    data = result.fetchall()

    # Bulk update bump frameworks
    update_data = [
        {
            "id": id,
            "etl_num_times_used": new_used,
            "etl_num_times_converted": new_converted,
        }
        for id, new_used, new_converted in data
    ]

    db.session.bulk_update_mappings(BumpFramework, update_data)

    # Commit final changes
    db.session.commit()

    return True


def run_backfill_bf_analytics() -> bool:
    # Get all LIConvoEntries that have a bump framework
    convo_entries: list[LinkedinConversationEntry] = (
        LinkedinConversationEntry.query.filter(
            LinkedinConversationEntry.bump_framework_id != None,
            LinkedinConversationEntry.bump_analytics_processed == False,
        )
    ).all()

    # Put unique convo_urn_ids into a set
    convo_urn_ids: set[int] = set()
    for entry in convo_entries:
        convo_urn_ids.add(entry.conversation_url.split("/")[-2])

    print(len(convo_urn_ids))

    # Get entire conversations for the unique urns
    for convo_urn_id in convo_urn_ids:
        # Get all entries for the convo_urn_id
        convo_entries: list[LinkedinConversationEntry] = (
            LinkedinConversationEntry.query.filter_by(
                conversation_url=f"https://www.linkedin.com/messaging/thread/{convo_urn_id}/"
            )
            .order_by(LinkedinConversationEntry.date.asc())
            .all()
        )
        # If a bump framework is present, add to the count
        for index, entry in enumerate(tqdm(convo_entries)):
            if entry.bump_framework_id and entry.bump_analytics_processed == False:
                bump: BumpFramework = BumpFramework.query.get(entry.bump_framework_id)
                bump.etl_num_times_used = bump.etl_num_times_used or 0
                bump.etl_num_times_used += 1
                # Check to see if the next message is from the prospect
                if index + 1 < len(convo_entries):
                    next_entry = convo_entries[index + 1]
                    if next_entry.connection_degree != "You":
                        bump.etl_num_times_converted = bump.etl_num_times_converted or 0
                        bump.etl_num_times_converted += 1
                db.session.commit()
            entry.bump_analytics_processed = True

    return len(convo_urn_ids)


def run_conversation_bump_analytics(convo_urn_id: str) -> bool:
    convo_entries: list[LinkedinConversationEntry] = (
        LinkedinConversationEntry.query.filter(
            LinkedinConversationEntry.conversation_url
            == f"https://www.linkedin.com/messaging/thread/{convo_urn_id}/",
            or_(
                LinkedinConversationEntry.bump_analytics_processed == None,
                LinkedinConversationEntry.bump_analytics_processed == False,
            ),
        )
        .order_by(LinkedinConversationEntry.date.asc())
        .all()
    )

    if not convo_entries:
        return True

    # For entries, if the entry has a bump framework, check to see if the next message is from the prospect
    for index, entry in enumerate(convo_entries):
        if entry.bump_framework_id:
            if index + 1 < len(convo_entries):
                next_entry = convo_entries[index + 1]
                if next_entry.connection_degree != "You":
                    # Prospect responded, this bump was successful
                    bump: BumpFramework = BumpFramework.query.get(
                        entry.bump_framework_id
                    )
                    bump.etl_num_times_converted = bump.etl_num_times_converted or 0
                    bump.etl_num_times_converted += 1
        entry.bump_analytics_processed = True
        db.session.commit()

    return True


def update_prospect_status(prospect_id: int, convo_urn_id: str):
    prospect: Prospect = Prospect.query.get(prospect_id)

    # Update convo URN id if needed
    if not prospect.li_conversation_urn_id and prospect.li_conversation_thread_id:
        prospect.li_conversation_urn_id = prospect.li_conversation_thread_id.split(
            "thread/"
        )[-1].split("/")[0]
        db.session.commit()

    if not prospect.li_conversation_urn_id and convo_urn_id:
        prospect.li_conversation_urn_id = convo_urn_id
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
        db.session.commit()
        return

    # We know the first message is AI generated
    if len(latest_convo_entries) >= 1 and latest_convo_entries[-1].ai_generated is None:
        latest_convo_entries[-1].ai_generated = True
        # db.session.commit()

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

    last_message_from_me = (
        latest_convo_entries[0]
        if latest_convo_entries[0].connection_degree == "You"
        else None
    )
    if (
        last_message_from_me
        and last_message_from_me.date > dt.datetime.now() - dt.timedelta(days=1)
        and prospect.status not in [ProspectStatus.ACCEPTED]
    ):
        send_to_purgatory(
            prospect_id=prospect_id,
            days=2,
            reason=ProspectHiddenReason.RECENTLY_BUMPED,
        )

    # Update the last message values accordingly
    has_prospect_replied = False
    last_msg_from_prospect = None
    last_msg_from_sdr = None
    for entry in latest_convo_entries:
        if entry.connection_degree == "You":
            if not last_msg_from_sdr:
                last_msg_from_sdr = entry
        else:
            if not last_msg_from_prospect:
                last_msg_from_prospect = entry

    if last_msg_from_prospect:
        prospect.li_last_message_from_prospect = last_msg_from_prospect.message
        has_prospect_replied = True

    if last_msg_from_sdr:
        prospect.li_last_message_from_sdr = last_msg_from_sdr.message

    if last_msg_from_prospect or last_msg_from_sdr:
        prospect.li_last_message_timestamp = latest_convo_entries[0].date
        prospect.li_is_last_message_from_sdr = (
            latest_convo_entries[0].connection_degree == "You"
        )
        db.session.add(prospect)
        db.session.commit()

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

        # Make sure the prospect isn't in the main pipeline for 24 hours
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

        check_and_notify_for_auto_mark_scheduling(prospect_id=prospect_id)

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
    if (
        last_msg_from_prospect
        and prospect.overall_status != ProspectOverallStatus.ACCEPTED
        and prospect.overall_status != ProspectStatus.PROSPECTED
        and prospect.overall_status != ProspectStatus.SENT_OUTREACH
        and prospect.status != ProspectStatus.ACTIVE_CONVO_REVIVAL
        and prospect.status != ProspectStatus.ACTIVE_CONVO_QUEUED_FOR_SNOOZE
    ):
        prospect.hidden_until = dt.datetime.now()
        db.session.add(prospect)
        db.session.commit()


def check_and_notify_for_auto_mark_scheduling(prospect_id: int):
    prospect: Prospect = Prospect.query.get(prospect_id)
    client_id: int = prospect.client_id
    prospect_full_name: str = prospect.full_name
    client: Client = Client.query.get(client_id)
    company: str = client.company

    # Check if the message should be marked as scheduling based on the Generated Message CTA
    approved_outreach_message_id = prospect.approved_outreach_message_id
    gm: GeneratedMessage = GeneratedMessage.query.get(approved_outreach_message_id)
    client_sdr: ClientSDR = ClientSDR.query.get(prospect.client_sdr_id)
    sdr_name: str = client_sdr.name
    if gm:
        gm_cta_id: int = gm.message_cta
        gm_cta: GeneratedMessageCTA = GeneratedMessageCTA.query.get(gm_cta_id)
        if gm_cta and gm_cta.auto_mark_as_scheduling_on_acceptance:
            update_prospect_status_linkedin(
                prospect_id=prospect.id,
                new_status=ProspectStatus.ACTIVE_CONVO,
                quietly=True,
            )
            update_prospect_status_linkedin(
                prospect_id=prospect.id,
                new_status=ProspectStatus.ACTIVE_CONVO_SCHEDULING,
                footer_note="Note: Conversation marked as 'Scheduling' based on the CTA.",
                quietly=True,
            )

            direct_link = "https://app.sellscale.com/authenticate?stytch_token_type=direct&token={auth_token}&redirect=prospects/{prospect_id}".format(
                auth_token=client_sdr.auth_token, prospect_id=prospect_id
            )

            # send Slack message to Internal SellScale Urgent Alerts channel
            send_slack_message(
                message=f"""
                *🛎 New scheduling CTA accepted!*
                ```
                {gm.completion}
                ```

                Please follow up with some times via the reply framework here:

                *Direct Link:* {direct_link}

                *SDR*: {sdr_name} ({company})
                """,
                webhook_urls=[URL_MAP["csm-urgent-alerts"]],
            )

            return


def classify_active_convo(prospect_id: int, messages):
    # Make sure the prospect's status is not already ACTIVE_CONVO_REVIVAL
    prospect: Prospect = Prospect.query.get(prospect_id)
    if prospect.status == ProspectStatus.ACTIVE_CONVO_REVIVAL:
        return

    status = get_prospect_status_from_convo(messages, prospect.client_sdr_id, prospect.status)

    # Make sure the prospect's status has changed before sending messages
    prospect: Prospect = Prospect.query.get(prospect_id)
    if prospect.status == status:
        return

    success, message = update_prospect_status_linkedin(prospect_id, status)

    # Make sure the prospect's status has changed before sending messages
    if not success:
        return

    # Send slack message
    prospect: Prospect = Prospect.query.get(prospect_id)
    client_sdr: ClientSDR = ClientSDR.query.get(prospect.client_sdr_id)
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"Prospect {prospect.full_name} was automatically classified as '{status.value}' because of the state of their convo with {client_sdr.name}!",
            },
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Title:* {prospect.title}"},
        },
    ]

    block_messages = []
    for i, message in enumerate(messages):
        if i >= 5:
            break
        length = 130
        text = message.get("content", "")
        truncated_text = (text[:length] + "...") if len(text) > length else text
        block_messages.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{'SDR' if message.get('role') == 'user' else 'Prospect'}*: {truncated_text}",
                },
            }
        )
    blocks += block_messages

    blocks.append(
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*{name}'s Direct Login*: <{link}|Link>".format(
                    link="https://app.sellscale.com/authenticate?stytch_token_type=direct&token="
                    + str(client_sdr.auth_token),
                    name=client_sdr.name,
                ),
            },
        }
    )
    blocks.append(
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*SellScale Sight*: <{link}|Contact Link>".format(
                    link="https://app.sellscale.com/home/all-contacts/"
                    + str(prospect.id)
                ),
            },
        }
    )

    send_slack_message(
        message=f"Prospect {prospect.full_name} was automatically classified as '{status.value}' because of the state of their convo with {client_sdr.name}!",
        webhook_urls=[URL_MAP["csm-convo-sorter"]],
        blocks=blocks,
    )


def get_prospect_status_from_convo(
    messages: list[str], client_sdr_id: int, current_status: str
) -> ProspectStatus:
    """Determines what a prospect status should be based on the state of their convo

    Args:
        messages (list[str]): List of messages in the convo
        client_sdr_id (int): ID of the Client SDR

    Returns:
        ProspectStatus: The new status of the prospect
    """

    # Short circuit by using our own heuristics
    def get_prospect_status_from_convo_heuristics(messages):
        most_recent_message = messages[-1] if messages else ""
        scheduling_key_words = [
            "today",
            "tomorrow",
            "@",
            "week",
            "month",
            "monday",
            "tuesday",
            "wednesday",
            "thursday",
            "friday",
            "saturday",
            "sunday",
            "hear more",
        ]

        # If the most recent message is from the prospect, run our heuristics
        sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
        is_sdr_message = fuzz.ratio(most_recent_message.split("(")[0], sdr.name) > 80
        if not is_sdr_message:
            message_lowered = most_recent_message.lower()

            # Detect scheduling
            for key_word in scheduling_key_words:
                if key_word in message_lowered:
                    return ProspectStatus.ACTIVE_CONVO_SCHEDULING

        return None

    clientSDR: ClientSDR = ClientSDR.query.get(client_sdr_id)

    # Get heuristic based status (used for Scheduling, mainly)
    heuristic_status = get_prospect_status_from_convo_heuristics(messages)
    if heuristic_status:
        # Run a ChatGPT verifier to make sure the status is doubly-correct
        correct = chat_ai_verify_scheduling_convo(messages, clientSDR.name, current_status)
        if correct:
            return heuristic_status

    # Get status from AI
    classify_status = chat_ai_classify_active_convo(messages, clientSDR.name)

    return classify_status


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


def update_profile_picture(client_sdr_id: int, prospect_id: int, convo):
    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    prospect: Prospect = Prospect.query.get(prospect_id)

    if len(convo) == 0:
        return
    if time.time() * 1000 <= int(prospect.img_expire) and time.time() * 1000 <= int(
        sdr.img_expire
    ):
        return

    sdr_updated = False
    prospect_updated = False
    for message in tqdm(convo):
        urn_id = (
            message.get("from", {})
            .get("com.linkedin.voyager.messaging.MessagingMember", {})
            .get("miniProfile", {})
            .get("entityUrn", "")
            .replace("urn:li:fs_miniProfile:", "")
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

        if prospect.li_urn_id == urn_id:
            prospect.img_url = image_url
            prospect.img_expire = image_expire
            db.session.add(prospect)
            db.session.commit()
            prospect_updated = True
        else:
            sdr.img_url = image_url
            sdr.img_expire = image_expire
            db.session.add(sdr)
            db.session.commit()
            sdr_updated = True

        if sdr_updated and prospect_updated:
            return


def queue_withdraw_li_invites(client_sdr_id: int, prospect_ids: list[int]):
    from src.automation.orchestrator import add_process_list

    return add_process_list(
        type="li_invite_withdraw",
        args_list=[
            {"client_sdr_id": client_sdr_id, "prospect_id": p_id}
            for p_id in prospect_ids
        ],
        chunk_size=1000,
        chunk_wait_days=1,
        buffer_wait_minutes=5,
        append_to_end=True,
        init_wait_minutes=5,
    )


@celery.task
def withdraw_li_invite(client_sdr_id: int, prospect_id: int):
    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    prospect: Prospect = Prospect.query.get(prospect_id)

    pba = PhantomBusterAgent("1386024932692725")
    pba.update_argument(key="sessionCookie", new_value=sdr.li_at_token)
    pba.update_argument(
        key="profilesToWithdraw", new_value="https://www." + prospect.linkedin_url
    )

    pba.run_phantom()

    send_slack_message(
        message=f"Calling withdraw from queue, sdr:{client_sdr_id}, prospect:{prospect_id}",
        webhook_urls=[URL_MAP["eng-sandbox"]],
    )

    return True, "Success"


def archive_convo(prospect_id: int):
    prospect: Prospect = Prospect.query.get(prospect_id)
    if not prospect:
        return False, "Prospect not found"

    if prospect.li_urn_id is None or prospect.li_conversation_urn_id is None:
        return False, "Prospect does not have voyager URN IDs set"

    api = LinkedIn(prospect.client_sdr_id)
    profile = api.get_user_profile(use_cache=False)
    sdr_urn_id = (
        profile.get("miniProfile", {})
        .get("entityUrn", "")
        .replace("urn:li:fs_miniProfile:", "")
    )

    result = api.archive_conversation(
        sdr_urn_id=sdr_urn_id,
        conversation_urn_id=prospect.li_conversation_urn_id,
    )
    if result is None:
        return False, "Failed to archive conversation"

    return True, "Success"


def create_linkedin_connection_needed_operator_dashboard_card(client_sdr_id: int):
    create_operator_dashboard_entry(
        client_sdr_id=client_sdr_id,
        urgency=OperatorDashboardEntryPriority.HIGH,
        tag="connect_linkedin_{client_sdr_id}".format(client_sdr_id=client_sdr_id),
        emoji="🌐",
        title="Connect LinkedIn",
        subtitle="In order to conduct outbound on LinkedIn, you will need to connect your LinkedIn account to SellScale.",
        cta="Connect LinkedIn",
        cta_url="/",
        status=OperatorDashboardEntryStatus.PENDING,
        due_date=datetime.now() + timedelta(days=1),
        task_type=OperatorDashboardTaskType.CONNECT_LINKEDIN,
        task_data={
            "client_sdr_id": client_sdr_id,
        },
    )

    return True


def create_slack_connection_needed_operator_dashboard_card(client_sdr_id: int):
    create_operator_dashboard_entry(
        client_sdr_id=client_sdr_id,
        urgency=OperatorDashboardEntryPriority.HIGH,
        tag="add_slack_connection_{client_sdr_id}".format(client_sdr_id=client_sdr_id),
        emoji="💬",
        title="Connect Slack",
        subtitle="SellScale will send pipeline updates, task reminders, and various other communications to a Slack channel of your choice.",
        cta="Connect Slack",
        cta_url="/",
        status=OperatorDashboardEntryStatus.PENDING,
        due_date=datetime.now() + timedelta(days=1),
        task_type=OperatorDashboardTaskType.CONNECT_SLACK,
        task_data={
            "client_sdr_id": client_sdr_id,
        },
    )

    return True


def create_add_pre_filters_operator_dashboard_card(client_sdr_id: int):
    create_operator_dashboard_entry(
        client_sdr_id=client_sdr_id,
        urgency=OperatorDashboardEntryPriority.MEDIUM,
        tag="create_prefilters_{client_sdr_id}".format(client_sdr_id=client_sdr_id),
        emoji="👥",
        title="Create Pre-Filter",
        subtitle="Set high level filters to hone in on your outreach TAM.",
        cta="Create",
        cta_url="/",
        status=OperatorDashboardEntryStatus.PENDING,
        due_date=datetime.now() + timedelta(days=1),
        task_type=OperatorDashboardTaskType.CREATE_PREFILTERS,
        task_data={
            "client_sdr_id": client_sdr_id,
        },
    )

    return True


@celery.task
def send_generated_messages():

    gen_msgs: list[GeneratedMessage] = GeneratedMessage.query.filter_by(
        status=GeneratedMessageStatus.QUEUED_FOR_OUTREACH
    ).all()
    for msg in gen_msgs:
        prospect: Prospect = Prospect.query.get(msg.prospect_id)
        prospect.linkedin_url

        success = send_generated_message_for_sdr(
            prospect.client_sdr_id, prospect.linkedin_url, msg.completion
        )
        if success:
            msg.status = GeneratedMessageStatus.SENT
            db.session.add(msg)
            db.session.commit()
            return  # Return after sending one message


def send_generated_message_for_sdr(client_sdr_id: int, li_url: str, msg: str):

    if client_sdr_id != 34:
        return False

    api = LinkedIn(client_sdr_id)
    public_id = li_url.split("/in/")[1].split("/")[0]

    success = api.add_connection(public_id, msg)

    return success
