import json
import yaml
from typing import List, Union, Optional

from src.ml.services import chat_ai_verify_demo_set, get_text_generation
from src.heuristic_keywords.heuristics import demo_key_words

from src.utils.lists import format_str_join
from src.client.models import ClientArchetype
from src.li_conversation.autobump_helpers.services_firewall import (
    rule_no_stale_message,
    run_autobump_firewall,
)
from src.message_generation.models import (
    GeneratedMessage,
    GeneratedMessageAutoBump,
    GeneratedMessageCTA,
    SendStatus,
    StackRankedMessageGenerationConfiguration,
)
from src.message_generation.services import (
    get_li_convo_history,
    get_prospect_research_points,
)
from src.prospecting.models import (
    ProspectHiddenReason,
    ProspectOverallStatus,
    ProspectStatus,
    ProspectStatusRecords,
)
from src.li_conversation.conversation_analyzer.li_email_finder import (
    update_all_outstanding_prospect_emails,
)

from src.li_conversation.models import LinkedInConvoMessage
from src.bump_framework.models import BumpFrameworkTemplates, BumpLength
from src.prospecting.services import send_to_purgatory, update_prospect_status_linkedin
from src.research.models import ResearchPoints
from src.utils.datetime.dateparse_utils import get_working_hours_in_utc, is_weekend
from src.utils.slack import exception_to_str

from src.voyager.linkedin import LinkedIn

from sqlalchemy import or_
from app import db, celery

from model_import import (
    LinkedinConversationEntry,
    ClientSDR,
    Prospect,
    LinkedinConversationScrapeQueue,
    Client,
)
from src.automation.models import PhantomBusterAgent
from src.ml.openai_wrappers import wrapped_create_completion
from src.utils.slack import URL_MAP
from src.utils.slack import send_slack_message
from datetime import datetime, timedelta
from tqdm import tqdm
from src.utils.slack import send_slack_message
from model_import import BumpFramework
from sqlalchemy.sql.expression import func

import random
import time
import pytz


def update_linkedin_conversation_entries():
    """
    Update the LinkedinConversationEntry table with new entries
    """
    LINKEDIN_CONVERSATION_SCRAPER_PHANTOM_ID = 3365881184675991
    p: PhantomBusterAgent = PhantomBusterAgent(LINKEDIN_CONVERSATION_SCRAPER_PHANTOM_ID)
    data = p.get_output()

    all_messages = []
    for conversation_obj in data:
        if not conversation_obj.get("conversationUrl"):
            continue

        messages = conversation_obj.get("messages")
        all_messages = all_messages + messages

    bulk_objects = []
    for message in tqdm(all_messages):
        bulk_objects.append(
            create_linkedin_conversation_entry(
                conversation_url=message.get("conversationUrl", ""),
                author=message.get("author", ""),
                first_name=message.get("firstName", ""),
                last_name=message.get("lastName", ""),
                date=message.get("date", ""),
                profile_url=message.get("profileUrl", ""),
                headline=message.get("headline", ""),
                img_url=message.get("imgUrl", ""),
                connection_degree=message.get("connectionDegree", ""),
                li_url=message.get("url", ""),
                message=message.get("message", ""),
            )
        )
    bulk_objects = [obj for obj in bulk_objects if obj]
    db.session.bulk_save_objects(bulk_objects)
    db.session.commit()


def check_for_duplicate_linkedin_conversation_entry(
    conversation_url: str,
    author: str,
    message: str,
    urn_id: Union[str, None] = None,
):
    """
    Check for duplicates and return True if duplicate exists
    """
    if urn_id:
        return LinkedinConversationEntry.query.filter(
            LinkedinConversationEntry.urn_id == urn_id,
            LinkedinConversationEntry.message == message,
        ).first()
    else:
        return LinkedinConversationEntry.query.filter(
            LinkedinConversationEntry.conversation_url == conversation_url,
            LinkedinConversationEntry.author == author,
            LinkedinConversationEntry.message == message,
        ).first()


# DELETE ME
# def backfill_gen_message_data():
#     from tqdm import tqdm
#     # Get all active SDRs
#     sdrs: list[ClientSDR] = ClientSDR.query.filter(ClientSDR.active == True).all()

#     # Get Aakash's SDR
#     # sdr: ClientSDR = ClientSDR.query.filter(ClientSDR.id == 1).first()
#     # sdrs: list[ClientSDR] = [sdr]

#     # For each SDR
#     for sdr in sdrs:
#         # Get prospects that are in a status that is not prospected
#         joined_query = (
#             db.session.query(
#                 Prospect.id.label("prospect_id"),
#                 LinkedinConversationEntry.id.label("linkedin_convo_entry_id"),
#                 LinkedinConversationEntry.message.label("linkedin_convo_entry_message"),
#                 GeneratedMessage.id.label("gen_message_id"),
#                 GeneratedMessage.completion.label("gen_message_completion"),
#             )
#             .join(
#                 LinkedinConversationEntry,
#                 Prospect.li_conversation_urn_id == LinkedinConversationEntry.thread_urn_id,
#             )
#             .join(
#                 GeneratedMessage,
#                 (GeneratedMessage.prospect_id == Prospect.id) &
#                 (func.length(LinkedinConversationEntry.message) > 20) &
#                 (GeneratedMessage.completion.startswith(func.substr(LinkedinConversationEntry.message, 1, func.length(LinkedinConversationEntry.message) - 1)))
#             )
#             .filter(
#                 Prospect.client_sdr_id == sdr.id,
#                 Prospect.approved_outreach_message_id.isnot(None),
#                 LinkedinConversationEntry.initial_message_id == None
#             ).all()
#         )
#         # For every entry in the joined query, update the LI Convo Entry
#         for query in tqdm(joined_query):
#             prospect_id = query.prospect_id
#             linkedin_convo_entry_id = query.linkedin_convo_entry_id
#             linkedin_convo_entry_message = query.linkedin_convo_entry_message
#             gen_message_id = query.gen_message_id
#             gen_message_completion = query.gen_message_completion

#             gm: GeneratedMessage = GeneratedMessage.query.get(gen_message_id)
#             cta: GeneratedMessageCTA = GeneratedMessageCTA.query.get(gm.message_cta)
#             research_points: list[ResearchPoints] = ResearchPoints.query.filter(
#                 ResearchPoints.id.in_(gm.research_points)
#             ).all()
#             research_points = [rp.value for rp in research_points]
#             sr_config: StackRankedMessageGenerationConfiguration = StackRankedMessageGenerationConfiguration.query.get(
#                 gm.stack_ranked_message_generation_configuration_id
#             )

#             # Update the LI Convo Entry
#             li_convo_entry: LinkedinConversationEntry = LinkedinConversationEntry.query.get(
#                 linkedin_convo_entry_id
#             )
#             li_convo_entry.initial_message_id = gen_message_id
#             li_convo_entry.initial_message_cta_id = gm.message_cta
#             li_convo_entry.initial_message_cta_text = cta.text_value if cta else None
#             li_convo_entry.initial_message_research_points = research_points
#             li_convo_entry.initial_message_stack_ranked_config_id = gm.stack_ranked_message_generation_configuration_id
#             li_convo_entry.initial_message_stack_ranked_config_name = sr_config.name if sr_config else None

#             db.session.commit()


def create_linkedin_conversation_entry(
    conversation_url: str,
    author: str,
    first_name: str,
    last_name: str,
    date: datetime,
    profile_url: str,
    headline: str,
    img_url: str,
    connection_degree: str,
    li_url: str,
    message: str,
    urn_id: Union[str, None] = None,
    img_expire: int = 0,
    client_sdr_id: int = -1,
    prospect_id: int = -1,
):
    if message.strip() == "":
        return None

    prospect: Prospect = Prospect.query.get(prospect_id)
    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)

    direct_link = "https://app.sellscale.com/authenticate?stytch_token_type=direct&token={auth_token}&redirect=prospects/{prospect_id}".format(
        auth_token=sdr.auth_token, prospect_id=prospect_id
    )

    """
    Check for duplicates and duplicate does not exist, create a new LinkedinConversationEntry
    """
    duplicate_exists = check_for_duplicate_linkedin_conversation_entry(
        conversation_url=conversation_url,
        author=author,
        message=message,
        urn_id=urn_id,
    )

    # ensure date is from last 7 days
    if date < datetime.now() - timedelta(days=7):
        return None

    # Get the Thread URN ID from the conversation URL
    try:
        if conversation_url:
            splitted = conversation_url.split("/")
            thread_urn_id = splitted[-2]
        else:
            thread_urn_id = ""
    except:
        thread_urn_id = ""

    if not duplicate_exists:
        new_linkedin_conversation_entry = LinkedinConversationEntry(
            conversation_url=conversation_url,
            author=author,
            first_name=first_name,
            last_name=last_name,
            date=date,
            profile_url=profile_url,
            headline=headline,
            img_url=img_url,
            img_expire=img_expire,
            connection_degree=connection_degree,
            li_url=li_url,
            message=message,
            thread_urn_id=thread_urn_id,
            urn_id=urn_id,
        )

        # Check if this conversation entry is a generated initial message
        initial_message: GeneratedMessage = GeneratedMessage.query.filter(
            GeneratedMessage.completion.startswith(
                func.substr(message, 1, func.length(message) - 1)
            ),
            GeneratedMessage.prospect_id == prospect_id,
        ).first()
        if initial_message:
            message_cta: GeneratedMessageCTA = GeneratedMessageCTA.query.get(
                initial_message.message_cta
            )
            research_points: list[ResearchPoints] = []
            if initial_message.research_points:
                research_points = ResearchPoints.query.filter(
                    ResearchPoints.id.in_(initial_message.research_points)
                ).all()
            stack_ranked_config: StackRankedMessageGenerationConfiguration = (
                StackRankedMessageGenerationConfiguration.query.get(
                    initial_message.stack_ranked_message_generation_configuration_id
                )
            )
            research_points = [rp.value for rp in research_points]
            new_linkedin_conversation_entry.initial_message_id = initial_message.id
            new_linkedin_conversation_entry.initial_message_cta_id = (
                initial_message.message_cta
            )
            new_linkedin_conversation_entry.initial_message_cta_text = (
                message_cta.text_value if message_cta else ""
            )
            new_linkedin_conversation_entry.initial_message_research_points = (
                research_points
            )
            new_linkedin_conversation_entry.initial_message_stack_ranked_config_id = (
                initial_message.stack_ranked_message_generation_configuration_id
            )
            new_linkedin_conversation_entry.initial_message_stack_ranked_config_name = (
                stack_ranked_config.name if stack_ranked_config else ""
            )
            new_linkedin_conversation_entry.ai_generated = True

        db.session.commit()

        # A new message is being recorded, increase unread message count
        if prospect_id != -1:
            prospect: Prospect = Prospect.query.get(prospect_id)
            if connection_degree == "You":
                prospect.li_unread_messages = 0
            else:
                if not prospect.li_unread_messages:
                    prospect.li_unread_messages = 1
                else:
                    prospect.li_unread_messages += 1

            if (
                connection_degree != "You"
                and prospect.hidden_until
                and prospect.hidden_until > date
            ):
                prospect.hidden_until = None

            db.session.add(prospect)
            db.session.commit()

            # Flag as urgent if message is new and mentions something urgent
        if not duplicate_exists and client_sdr_id != -1 and connection_degree != "You":
            detect_time_sensitive_keywords(
                message=message,
                client_sdr_id=client_sdr_id,
                author=author,
                direct_link=direct_link,
                prospect_id=prospect_id,
            )
            detect_multithreading_keywords(
                message=message,
                client_sdr_id=client_sdr_id,
                author=author,
                direct_link=direct_link,
                prospect_id=prospect_id,
            )
            detect_queue_for_snooze_keywords(
                message=message,
                client_sdr_id=client_sdr_id,
                author=author,
                direct_link=direct_link,
                prospect_id=prospect_id,
            )
            detect_queue_for_continue_the_sequence_keywords(
                message=message,
                client_sdr_id=client_sdr_id,
                author=author,
                direct_link=direct_link,
                prospect_id=prospect_id,
            )

        detect_demo_set.delay(thread_urn_id, prospect.id)

        return new_linkedin_conversation_entry
    else:
        # Populate the urn_id is it's not already set
        added = False

        if urn_id and not duplicate_exists.urn_id:
            duplicate_exists.urn_id = urn_id
            added = True

        if img_url and not duplicate_exists.img_url:
            duplicate_exists.img_url = img_url
            added = True

        if thread_urn_id and not duplicate_exists.thread_urn_id:
            duplicate_exists.thread_urn_id = thread_urn_id
            added = True

        # If the current image is expired, replace it
        if img_expire and time.time() * 1000 > int(duplicate_exists.img_expire):
            duplicate_exists.img_url = img_url
            duplicate_exists.img_expire = img_expire
            added = True

        if added:
            db.session.add(duplicate_exists)
            db.session.commit()
            return duplicate_exists
        else:
            return None


@celery.task(max_retries=3)
def detect_demo_set(thread_urn_id: str, prospect_id: int):
    prospect: Prospect = Prospect.query.get(prospect_id)
    clientSDR: ClientSDR = ClientSDR.query.get(prospect.client_sdr_id)

    # Get the conversation entries for the thread
    conversation_entries = (
        LinkedinConversationEntry.query.filter(
            LinkedinConversationEntry.thread_urn_id == thread_urn_id,
        )
        .order_by(LinkedinConversationEntry.created_at.asc())
        .all()
    )

    latest_message = conversation_entries[-1]

    # Run the demo set ruleset
    if latest_message:
        message_lowered = latest_message.message.lower()
        for key_word in demo_key_words:
            if key_word in message_lowered:
                messages = [x.message for x in conversation_entries]
                is_demo_set = chat_ai_verify_demo_set(messages, prospect.full_name)
                if is_demo_set:
                    send_slack_message(
                        message=f"""
                        🎉🎉🎉 !!!!! DEMO SET DETECTED!!!!!! 🎉🎉🎉
                        ```
                        {messages[-5:] if len(messages) >= 5 else messages}
                        ```
                        These are the last 5 messages.
                        ⏰ Current Status: "DEMO_SET"

                        > 🤖 Rep: {clientSDR.name} | 👥 Prospect: {prospect.full_name}

                        🎊🎈 Take action and mark as ✅ (if wrong, inform an engineer)
                        🔗 Direct Link: https://app.sellscale.com/authenticate?stytch_token_type=direct&token={clientSDR.auth_token}&redirect=prospects/{prospect.id}
                        """,
                        webhook_urls=[URL_MAP["ops-demo-set-detection"]],
                    )
                else:
                    send_slack_message(
                        message=f"""
                        !!!!!❌ DEMO SET, Open AI said not a demo though. ❌!!!!!!
                        ```
                        {messages[-5:] if len(messages) >= 5 else messages}
                        ```
                        These are the last 5 messages.
                        ⏰ Current Status: "DEMO_SET"

                        > 🤖 Rep: {clientSDR.name} | 👥 Prospect: {prospect.full_name}

                        🎊🎈 Take action and mark as ✅ (if wrong, inform an engineer)
                        🔗 Direct Link: https://app.sellscale.com/authenticate?stytch_token_type=direct&token={clientSDR.auth_token}&redirect=prospects/{prospect.id}
                        """,
                        webhook_urls=[URL_MAP["ops-demo-set-detection"]],
                    )
                break
    # Check for a demo set keyword


def detect_time_sensitive_keywords(
    message: str, client_sdr_id: int, author: str, direct_link: str, prospect_id: int
) -> None:
    """Detects time-sensitive keywords in a message and sends an alert to the CSM team

    Args:
        message (str): The message to check for time-sensitive keywords
        client_sdr_id (int): The ID of the ClientSDR that received the message
        author (str): The name of the person who sent the message
        direct_link (str): The direct link to the message

    Returns:
        None

    """
    lowered_message = message.lower()
    time_sensitive_keywords = set(
        [
            "tomorrow",
            "@",
            "today",
            "week",
            "month",
            "monday",
            "tuesday",
            "wednesday",
            "thursday",
            "friday",
            "saturday",
            "sunday",
            " phone",
            " cell",
            " call",
            "schedule",
            "available dates",
            "a conversation",
            "discuss",
            "next year",
            "later",
            "next week",
            "next month",
            "2023",
            "2024",
        ]
    )
    for keyword in time_sensitive_keywords:
        if keyword in lowered_message:
            sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
            prospect: Prospect = Prospect.query.get(prospect_id)

            if prospect.status in (
                ProspectStatus.DEMO_LOSS,
                ProspectStatus.DEMO_SET,
                ProspectStatus.DEMO_WON,
                ProspectStatus.ACTIVE_CONVO_SCHEDULING,
            ):
                return None

            old_status = prospect.status.value

            send_slack_message(
                message=f"""
{author} wrote to {sdr.name} with the message:
```
{message}
```
⏰ Time-sensitive keyword was detected: "{keyword}"

> ✨ *Automatic Scheduling Sorter:* Old `{old_status}` -> New `ACTIVE_CONVO_SCHEDULING`
> 🤖 *SDR:* {sdr.name} | 👥 *Prospect:* {prospect.full_name}

Take appropriate action then mark this message as ✅ (_if this classification was wrong, please let an engineer know_)

*Direct Link:* {direct_link}
                """,
                webhook_urls=[URL_MAP["csm-urgent-alerts"]],
            )

            print("Updating prospect status to ACTIVE_CONVO_SCHEDULING")

            # TODO: Delete if no one complains
            # update_prospect_status_linkedin(
            #     prospect_id=prospect_id,
            #     new_status=ProspectStatus.ACTIVE_CONVO_SCHEDULING,
            # )
            return


def detect_multithreading_keywords(
    message: str, client_sdr_id: int, author: str, direct_link: str, prospect_id: int
) -> None:
    """Detects multithreading keywords in a message and sends an alert to the CSM team

    Args:
        message (str): The message to check for multithreading keywords
        client_sdr_id (int): The ID of the ClientSDR that received the message
        author (str): The name of the person who sent the message
        direct_link (str): The direct link to the message

    Returns:
        None

    """
    lowered_message = message.lower()
    multithreading_keywords = set(
        [
            "to reach out to",
        ]
    )
    for keyword in multithreading_keywords:
        if keyword in lowered_message:
            sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
            prospect: Prospect = Prospect.query.get(prospect_id)

            send_slack_message(
                message=f"""

{author} wrote to {sdr.name} with the message:
```
{message}
```
🧵 Multithreading keyword was detected: "{keyword}"

> ✨ *Automatic Scheduling Sorter:* Old `{prospect.status.value}` -> New `ACTIVE_CONVO_REFERRAL`
> 🤖 *SDR:* {sdr.name} | 👥 *Prospect:* {prospect.full_name}

Take appropriate action then mark this message as ✅ (_if this classification was wrong, please let an engineer know_)

*Direct Link:* {direct_link}
                """,
                webhook_urls=[URL_MAP["csm-urgent-alerts"]],
            )

            update_prospect_status_linkedin(
                prospect_id=prospect_id,
                new_status=ProspectStatus.ACTIVE_CONVO_REFERRAL,
            )

            return


def detect_queue_for_snooze_keywords(
    message: str, client_sdr_id: int, author: str, direct_link: str, prospect_id: int
) -> None:
    """Detects multithreading keywords in a message and sends an alert to the CSM team

    Args:
        message (str): The message to check for multithreading keywords
        client_sdr_id (int): The ID of the ClientSDR that received the message
        author (str): The name of the person who sent the message
        direct_link (str): The direct link to the message

    Returns:
        None

    """
    lowered_message = message.lower()
    multithreading_keywords = set(
        [
            "traveling",
            " weeks",
            "reach out later",
            "connect later",
            " after new years",
            "reach back out",
            "reach out again",
            "reach out next",
            "reach out in",
            "vacation",
        ]
    )
    for keyword in multithreading_keywords:
        if keyword in lowered_message:
            sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
            prospect: Prospect = Prospect.query.get(prospect_id)

            send_slack_message(
                message=f"""
{author} wrote to {sdr.name} with the message:
```
{message}
```
🧵 Auto-snoozing keyword was detected: "{keyword}"

> ✨ *Automatic Scheduling Sorter:* Old `{prospect.status.value}` -> New `ACTIVE_CONVO_QUEUED_FOR_SNOOZE`
> 🤖 *SDR:* {sdr.name} | 👥 *Prospect:* {prospect.full_name}

Take appropriate action then mark this message as ✅ (_if this classification was wrong, please let an engineer know_)
                """,
                webhook_urls=[URL_MAP["csm-urgent-alerts"]],
            )

            update_prospect_status_linkedin(
                prospect_id=prospect_id,
                new_status=ProspectStatus.ACTIVE_CONVO_QUEUED_FOR_SNOOZE,
            )

            return


def detect_queue_for_continue_the_sequence_keywords(
    message: str, client_sdr_id: int, author: str, direct_link: str, prospect_id: int
) -> None:
    """Detects multithreading keywords in a message and sends an alert to the CSM team
    if the message is from the prospect and the message is short (less than 25 characters)

    Args:
        message (str): The message to check for multithreading keywords
        client_sdr_id (int): The ID of the ClientSDR that received the message
        author (str): The name of the person who sent the message
        direct_link (str): The direct link to the message

    Returns:
        None

    """
    lowered_message = message.lower()
    multithreading_keywords = set(
        [
            "my pleasure",
            "thanks",
            "great to connect",
            "hi ",
            "hi, ",
            "hello",
            "i'd love to connect",
            "let's connect",
            "you're welcome",
            "thank",
        ]
    )

    multithreading_invalid_words = set(
        [
            "no thanks",
            "not interested",
            "no, thanks",
        ]
    )

    all_records: list = (
        ProspectStatusRecords.query.filter(
            ProspectStatusRecords.prospect_id == prospect_id
        )
        .order_by(ProspectStatusRecords.id.desc())
        .all()
    )
    num_records = len(all_records)

    for keyword in multithreading_keywords:
        if (
            keyword in lowered_message
            and len(lowered_message) < 25
            and num_records <= 5
            and not any(
                invalid_keyword in lowered_message
                for invalid_keyword in multithreading_invalid_words
            )
        ):
            sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
            prospect: Prospect = Prospect.query.get(prospect_id)

            send_slack_message(
                message=f"""
{author} wrote to {sdr.name} with the message:
```
{message}
```

🧵 Auto-continue-the-sequence keyword was detected: "{keyword}"

> ✨ *Automatic Scheduling Sorter:* Old `{prospect.status.value}` -> New `ACTIVE_CONVO_CONTINUE_SEQUENCE`
> 🤖 *SDR:* {sdr.name} | 👥 *Prospect:* {prospect.full_name}

Take appropriate action then mark this message as ✅ (_if this classification was wrong, please let an engineer know_)

*Direct Link:* {direct_link}
                """,
                webhook_urls=[URL_MAP["continue-sequence-alerts"]],
            )

            update_prospect_status_linkedin(
                prospect_id=prospect_id,
                new_status=ProspectStatus.ACTIVE_CONVO_CONTINUE_SEQUENCE,
            )

            return


def update_li_conversation_extractor_phantom(client_sdr_id) -> tuple[str, int]:
    """
    Update the LinkedIn conversation extractor phantom
    """
    client_sdr: ClientSDR = ClientSDR.query.filter_by(id=client_sdr_id).first()
    li_at_token = client_sdr.li_at_token
    client_sdr_id = client_sdr.id

    CLIENT_CSV_LINK = "https://sellscale-api-prod.onrender.com/li_conversation/{client_sdr_id}".format(
        client_sdr_id=client_sdr_id
    )

    if not li_at_token:
        return "No LinkedIn access token found for this SDR.", 400

    pb_agent = PhantomBusterAgent("3365881184675991")
    pb_agent.update_argument("sessionCookie", li_at_token)
    pb_agent.update_argument("spreadsheetUrl", CLIENT_CSV_LINK)

    status = pb_agent.run_phantom()
    status_code = status.status_code

    if status_code == 200:
        client_sdr = ClientSDR.query.filter_by(id=client_sdr_id).first()
        client_sdr.last_li_conversation_scrape_date = datetime.now()
        db.session.add(client_sdr)
        db.session.commit()

    return "OK", 200


def get_next_client_sdr_to_scrape():
    data = db.session.execute(
        """
        select
            client_sdr.id
        from client_sdr
            join client on client.id = client_sdr.client_id
        where client.active
            and client_sdr.li_at_token is not null
            and
                (client_sdr.last_li_conversation_scrape_date is Null
                    or client_sdr.last_li_conversation_scrape_date < NOW() - '24 hours'::INTERVAL)
        order by last_li_conversation_scrape_date desc
        limit 1;
    """
    ).fetchall()

    client_sdr_id = None
    if len(data) > 0:
        client_sdr_id = data[0][0]

    return client_sdr_id


@celery.task
def run_next_client_sdr_scrape():
    client_sdr_id = get_next_client_sdr_to_scrape()
    client_sdr: ClientSDR = ClientSDR.query.filter_by(id=client_sdr_id).first()
    if client_sdr_id:
        client_sdr_name: str = client_sdr.name
        update_li_conversation_extractor_phantom(client_sdr_id)
        send_slack_message(
            message="✅ LinkedIn conversation scrape for {client_sdr_name} (#{client_sdr_id}) completed.".format(
                client_sdr_name=client_sdr_name, client_sdr_id=client_sdr_id
            ),
            webhook_urls=[URL_MAP["eng-sandbox"]],
        )


def generate_chat_gpt_response_to_conversation_thread(
    prospect_id: int,
    convo_history: List[LinkedInConvoMessage],
    bump_framework_id: Optional[int] = None,
    account_research_copy: str = "",
    override_bump_length: Optional[BumpLength] = None,
    max_retries: int = 3,
    use_cache: bool = False,
    bump_framework_template_id: Optional[int] = None,
    override_bump_framework_template: Optional[str] = None,
):
    for _ in range(max_retries):
        # try:
        return generate_chat_gpt_response_to_conversation_thread_helper(
            prospect_id=prospect_id,
            convo_history=convo_history,
            bump_framework_id=bump_framework_id,
            account_research_copy=account_research_copy,
            override_bump_length=override_bump_length,
            use_cache=use_cache,
            bump_framework_template_id=bump_framework_template_id,
            override_bump_framework_template=override_bump_framework_template,
        )
        # except Exception as e:
        #     time.sleep(2)
        #     continue


def generate_smart_response(
    prospect_id: int,
    additional_instructions: str,
):
    from model_import import Prospect, Client

    convo_history = get_li_convo_history(
        prospect_id=prospect_id,
    )

    msg = next(filter(lambda x: x.connection_degree == "You", convo_history), None)
    if not msg:
        prospect: Prospect = Prospect.query.get(prospect_id)
        client_sdr_id = prospect.client_sdr_id
        sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
        sender = sdr.name
    else:
        sender = msg.author

    transcript = "\n\n".join(
        [x.author + " (" + str(x.date)[0:10] + "): " + x.message for x in convo_history]
    )
    content = transcript + "\n\n" + sender + " (" + str(datetime.now())[0:10] + "):"

    prospect: Prospect = Prospect.query.get(prospect_id)
    client_sdr: ClientSDR = ClientSDR.query.get(prospect.client_sdr_id)
    client: Client = Client.query.get(prospect.client_id)
    archetype: ClientArchetype = ClientArchetype.query.get(prospect.archetype_id)

    prospect_name = prospect.full_name
    prospect_title = prospect.title
    prospect_company = prospect.company

    client_sdr_name = client_sdr.name
    company_name = client
    archetype_name = archetype.archetype
    archetype_fit_reason = archetype.persona_fit_reason
    archetype_contact_objective = archetype.persona_contact_objective

    company_mission = client.mission
    company_tagline = client.tagline
    company_description = client.description
    company_value_props = client.value_prop_key_points

    research_points = ResearchPoints.get_research_points_by_prospect_id(prospect_id)
    research_points_str = "\n".join(
        [
            "• " + rp.value
            for rp in research_points
            if rp.value and rp.value.strip() != ""
        ]
    )

    prompt = """I'm responding to a client on LinkedIn.

My contact objective is: {archetype_contact_objective}

# Here is information about my company:
Name: {company_name}
Tagline: {company_tagline}
Description: {company_description}
Mission: {company_mission}
Value props: {company_value_props}

# Here is information about the persona I'm reaching out to
Persona name: {archetype_name}
Why do they buy our product?: {archetype_fit_reason}

# Here is information about the prospect:
Title: {prospect_title}
Company: {prospect_company}
Name: {prospect_name}
Account research:
{research_points_str}

Additional Instructions: {additional_instructions}

----
Instruction:
Type a personalized response to this prospect - using account research where relevant - that is efficient and fast to read on a phone.
If the request includes additional instructions, utilize these instructions to structure or incorporate into the response, based on what's requested.


Transcript:
{content}""".format(
        prospect_name=prospect_name,
        prospect_title=prospect_title,
        prospect_company=prospect_company,
        client_sdr_name=client_sdr_name,
        company_name=company_name,
        company_tagline=company_tagline,
        company_description=company_description,
        company_mission=company_mission,
        company_value_props=company_value_props,
        archetype_name=archetype_name,
        archetype_fit_reason=archetype_fit_reason,
        archetype_contact_objective=archetype_contact_objective,
        research_points_str=research_points_str,
        content=content,
        additional_instructions=additional_instructions,
    )

    response = get_text_generation(
        [
            {
                "role": "user",
                "content": prompt,
            }
        ],
        max_tokens=200,
        model="gpt-4",
        type="LI_MSG_OTHER",
        prospect_id=prospect_id,
        client_sdr_id=prospect.client_sdr_id,
    )

    return response


def generate_chat_gpt_response_to_conversation_thread_helper(
    prospect_id: int,
    convo_history: List[LinkedInConvoMessage],
    bump_framework_id: Optional[int] = None,
    account_research_copy: str = "",
    override_bump_length: Optional[BumpLength] = None,
    use_cache: bool = False,
    bump_framework_template_id: Optional[int] = None,
    override_bump_framework_template: Optional[str] = None,
):
    from model_import import Prospect
    from src.client.services import get_available_times_via_calendly

    # First the first message from the SDR
    msg = next(filter(lambda x: x.connection_degree == "You", convo_history), None)
    if not msg:
        prospect: Prospect = Prospect.query.get(prospect_id)
        client_sdr_id = prospect.client_sdr_id
        sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
        sender = sdr.name
    else:
        sender = msg.author

    prospect: Prospect = Prospect.query.get(prospect_id)
    client_sdr: ClientSDR = ClientSDR.query.get(prospect.client_sdr_id)
    client: Client = Client.query.get(client_sdr.client_id)
    user_name = client_sdr.name
    user_title = client_sdr.title or "sales rep"
    user_company = client.company
    user_tagline = client.tagline
    user_company_description = client.description
    # archetype: ClientArchetype = ClientArchetype.query.get(prospect.archetype_id)
    # bump_framework_template: BumpFrameworkTemplates = (
    #     BumpFrameworkTemplates.query.get(bump_framework_template_id)
    #     if bump_framework_template_id
    #     else None
    # )
    if bump_framework_id:
        bump_framework: Optional[BumpFramework] = BumpFramework.query.get(
            bump_framework_id
        )
    else:
        bump_framework = None

    # If we don't have a bump framework template, use the legacy system
    if not bump_framework:
        return generate_chat_gpt_response_to_conversation_thread_helper_legacy(
            prospect_id=prospect_id,
            convo_history=convo_history,
            bump_framework_id=bump_framework_id,
            account_research_copy=account_research_copy,
            override_bump_length=override_bump_length,
            use_cache=use_cache,
            bump_framework_template_id=bump_framework_template_id,
        )

    ###################################
    ##### Use new template system #####
    ###################################

    transcript = "\n\n".join(
        [x.author + " (" + str(x.date)[0:10] + "): " + x.message for x in convo_history]
    )
    convo_history = (
        transcript + "\n\n" + sender + " (" + str(datetime.now())[0:10] + "):"
    )

    if bump_framework.use_account_research:
        # Grab 3 random points from the research points
        research_points: list[
            ResearchPoints
        ] = ResearchPoints.get_research_points_by_prospect_id(
            prospect_id=prospect_id, bump_framework_id=bump_framework_id
        )
        found_points = [research_point.to_dict() for research_point in research_points]
        random_sample_points = random.sample(found_points, min(len(found_points), 3))
        notes = "\n".join([point.get("value") for point in random_sample_points])
    else:
        notes = ""

    name = prospect.full_name
    industry = prospect.industry
    title = (
        prospect.colloquialized_title
        if prospect.colloquialized_title
        else prospect.title
    )
    company = (
        prospect.colloquialized_company
        if prospect.colloquialized_company
        else prospect.company
    )
    human_feedback = bump_framework.human_feedback
    template = bump_framework.description
    additional_instructions = bump_framework.additional_instructions

    if override_bump_framework_template:
        template = override_bump_framework_template

    prompt = f"""
You are a sales development representative writing on behalf of the SDR.

Write a personalized follow up message on LinkedIn that follows the template below. Use the information provided to personalize the message if necessary.
Note - you do not need to include all info.

SDR info --
Your Name: {user_name}
Your Title: {user_title}

Your Company info:
Your Company Name: {user_company}
Your Company Tagline: {user_tagline}
Your Company description: {user_company_description}

Prospect info --
Prospect Name: {name}
Prospect Title: {title}
Prospect Company Name: {company}
More research:
"{notes}"

Additional instructions:
- Make the message flow with the rest of the conversation.
- Do not put generalized fluff, such as "I hope this email finds you well" or "I couldn't help but notice" or  "I noticed".
- Don't make any [[brackets]] longer than 1 sentence when filled in.
{human_feedback}
{additional_instructions}

IMPORTANT:
Stick to the template very strictly. Do not deviate from the template:
--- START TEMPLATE ---
--------------------
{template}
--------------------
--- END TEMPLATE ---

Here is the conversation history:
{convo_history}

Important: Only personalize the message where there are [[brackets]] in the template with the double square brackets. Do not deviate from the template.
Important: Only respond with the message you would send to the prospect. Do not include any additional information in your response.

Output:"""

    response = get_text_generation(
        [{"role": "user", "content": prompt}],
        max_tokens=500,
        model="gpt-4",
        type="LI_MSG_OTHER",
        prospect_id=prospect_id,
        client_sdr_id=prospect.client_sdr_id,
        use_cache=use_cache,
    )

    if bump_framework.inject_calendar_times and client_sdr.scheduling_link:

        def date_suffix(day):
            day = int(day)
            if 4 <= day <= 20 or 24 <= day <= 30:
                return str(day) + "th"
            else:
                return str(day) + ["st", "nd", "rd"][day % 10 - 1]

        try:
            availability = get_available_times_via_calendly(
                calendly_url=client_sdr.scheduling_link,
                dt=(datetime.utcnow() + timedelta(days=1)),
                tz=client_sdr.timezone,
            )

            if availability:
                times = availability.get("times", [])
                other_dates = availability.get("other_dates", [])

                formatted_times = [t.strftime("%-I:%M%p").lower() for t in times]
                formatted_dates = [date_suffix(d.strftime("%-d")) for d in other_dates]

                if times and len(times) > 0:
                    message = (
                        "I'm free tomorrow at "
                        + format_str_join(formatted_times, "or")
                        + "."
                    )
                    if formatted_dates and len(formatted_dates) > 0:
                        message += (
                            " If that doesn't work, I'm also free on the "
                            + format_str_join(formatted_dates, "or")
                            + "."
                        )
                elif other_dates and len(other_dates) > 0:
                    message = (
                        "I'm free on the "
                        + format_str_join(formatted_dates, "or")
                        + "."
                    )

                message += (
                    f"\n{client_sdr.scheduling_link}\n\nLet me know what works for you!"
                )

                response = f"""{response}\n\n{message}""".strip()

        except Exception as e:
            print(e)

    print(prompt)
    print(response)

    return response, prompt


def generate_chat_gpt_response_to_conversation_thread_helper_legacy(
    prospect_id: int,
    convo_history: List[LinkedInConvoMessage],
    bump_framework_id: Optional[int] = None,
    account_research_copy: str = "",
    override_bump_length: Optional[BumpLength] = None,
    use_cache: bool = False,
    bump_framework_template_id: Optional[int] = None,
):
    from model_import import Prospect

    # First the first message from the SDR
    msg = next(filter(lambda x: x.connection_degree == "You", convo_history), None)
    if not msg:
        prospect: Prospect = Prospect.query.get(prospect_id)
        client_sdr_id = prospect.client_sdr_id
        sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
        sender = sdr.name
    else:
        sender = msg.author

    transcript = "\n\n".join(
        [x.author + " (" + str(x.date)[0:10] + "): " + x.message for x in convo_history]
    )
    content = transcript + "\n\n" + sender + " (" + str(datetime.now())[0:10] + "):"

    prospect: Prospect = Prospect.query.get(prospect_id)
    client_sdr: ClientSDR = ClientSDR.query.get(prospect.client_sdr_id)
    client: Client = Client.query.get(client_sdr.client_id)
    user_title = client_sdr.title or "sales rep"
    company = client.company
    archetype: ClientArchetype = ClientArchetype.query.get(prospect.archetype_id)
    bump_framework_template: Optional[BumpFrameworkTemplates] = (
        BumpFrameworkTemplates.query.get(bump_framework_template_id)
        if bump_framework_template_id
        else None
    )

    details = "\nFor some context, {first_name} is a {title} at {company}. Use these details when personalizing.".format(
        first_name=prospect.first_name,
        title=prospect.title,
        company=prospect.company,
    )

    message_content = (
        "You are "
        + sender
        + " who is writing a follow up response to a message thread. You are messaging as a "
        + user_title
        + " from "
        + company
        + ". Keep responses friendly and concise while also adding personalization where relevant.\n"
        + "\n------\n"
        + details
    )

    if bump_framework_id:
        bump_framework: Optional[BumpFramework] = BumpFramework.query.get(
            bump_framework_id
        )
    else:
        bump_framework = None

    # Only include account research if the framework is set to use it
    if not bump_framework or bump_framework.use_account_research:
        if account_research_copy:
            message_content = message_content + (
                "\n\nNaturally integrate pieces of information from this account research into the messaging:\n-----\n"
                + account_research_copy
                + "\n-----\n"
            )

    if (
        override_bump_length == BumpLength.SHORT
        or (bump_framework and bump_framework.bump_length == BumpLength.SHORT)
        or (bump_framework_template and bump_framework_template.length == "SHORT")
    ):
        message_content = message_content + ("\nLength: 1 sentence.")
    elif (
        override_bump_length == BumpLength.MEDIUM
        or (bump_framework and bump_framework.bump_length == BumpLength.MEDIUM)
        or (bump_framework_template and bump_framework_template.length == "MEDIUM")
    ):
        message_content = message_content + ("\nLength: 2-3 sentences")
    elif (
        override_bump_length == BumpLength.LONG
        or (bump_framework and bump_framework.bump_length == BumpLength.LONG)
        or (bump_framework_template and bump_framework_template.length == "LONG")
    ):
        message_content = message_content + (
            "\nLength: 1 paragraph with 1-2 sentences per paragraph. Separate with line breaks."
        )

    if bump_framework:
        message_content = message_content + (
            "\n\nYou will be using the bump framework below to construct the message - follow the instructions carefully to construct the message:\nBump Framework:\n----\n "
            + bump_framework.description
            + "\n-----"
        )

    if bump_framework_template:
        message_content = message_content + (
            "\n\nYou will be using the bump framework below to construct the message - follow the instructions carefully to construct the message:\nBump Framework:\n----\n "
            + bump_framework_template.raw_prompt
            + "\n-----"
        )

    if client and client.tagline:
        message_content = message_content + (
            "\nThis is what " + client.company + " does:\n" + client.tagline + "\n"
        )

    if bump_framework and bump_framework.human_feedback:
        message_content = message_content + (
            "\n\nIMPORTANT: The user you're working with reviewed what you produced and had this feedback:\n"
            + bump_framework.human_feedback
            + "\n\n"
        )

    # if bump_framework and bump_framework.additional_context:
    #     message_content = message_content + (
    #         "\n\nHere is some additional context to keep in mind when writing the message:\n-----\n"
    #         + bump_framework.additional_context
    #         + "\n-----"
    #     )

    conversation_length_1_and_message_from_me = (
        len(convo_history) == 1 and convo_history[0].connection_degree == "You"
    )
    conversation_length_greater_than_1_and_messages_only_from_me = len(
        convo_history
    ) > 1 and all([x.connection_degree == "You" for x in convo_history])

    if conversation_length_1_and_message_from_me:
        message_content = message_content + (
            "\n\nImportant Context: This person has just accepted your connection request.\n"
        )
    elif conversation_length_greater_than_1_and_messages_only_from_me:
        message_content = message_content + (
            "\n\nImportant Context: This person has not responded to your message so you are writing a follow up message.\n"
        )

    message_content = message_content + (
        "\n\nNote that this is part of a chat conversation so write one follow up message based on the previous conversation.\n"
    )

    # if archetype and archetype.persona_contact_objective:
    #     message_content = (
    #         message_content
    #         + f"\n\nThe goal of this conversation of chatting with this person is the following: `{archetype.persona_contact_objective}`"
    #     )

    response = get_text_generation(
        [
            {"role": "system", "content": message_content},
            {"role": "user", "content": content},
        ],
        max_tokens=200,
        model="gpt-4",
        type="LI_MSG_OTHER",
        prospect_id=prospect_id,
        client_sdr_id=prospect.client_sdr_id,
        use_cache=use_cache,
    )

    if client_sdr.message_generation_captivate_mode:
        instruction = "Please re-write the following message in a way that adds more humor and human touch. Keep the length approximately the same. Ensure it's a complete sentence."
        if client_sdr.client_id == 17:  # monday.com
            instruction = """Make slight adjustments to edit this message. Use this list of adjustments only to make it slightly more british.
    1. Instead of "Saw you've," use "Noticed you've."
    2. Instead of "No harm in benchmarking against," use "No harm in comparing with."
    3. Instead of "I'd love to show you," use "I'd be delighted to demonstrate."
    4. Instead of "Qualities that I’m sure have served you well," use "Qualities that I'm certain have stood you in good stead."
    5. Instead of "Seeing as you're," use "Considering you're."
    6. Instead of "That's big," use "That's quite an achievement."
    7. Instead of "Have you heard of," use "Are you familiar with."
    8. Instead of "Y'all," use "You all" or "You folks."
    9. Use words like 'cheers', 'brilliant', 'lovely', 'spot on', 'brilliant', 'splendid', 'jolly good'

Ensure the length is similar.
            """
        response = get_text_generation(
            [
                {
                    "role": "user",
                    "content": instruction,
                },
                {"role": "user", "content": response},
            ],
            max_tokens=200,
            model="gpt-4",
            type="LI_MSG_OTHER",
            prospect_id=prospect_id,
            client_sdr_id=prospect.client_sdr_id,
            use_cache=use_cache,
        )

    return response, content


def wizard_of_oz_send_li_message(
    new_message: str, client_sdr_id: int, prospect_id: int
):
    client_sdr: ClientSDR = ClientSDR.query.filter_by(id=client_sdr_id).first()
    client_sdr_name = client_sdr.name
    prospect: Prospect = Prospect.query.filter_by(id=prospect_id).first()
    prospect_name: str = prospect.full_name
    prospect_id: str = str(prospect.id)
    conversation_url = prospect.li_conversation_thread_id

    send_slack_message(
        message="🤖 Manually send a message to {prospect_name} (#{prospect_id}) out of `{client_sdr_name}`'s inbox.\n*message:*\n{message}\n\n*LI Link:* {link}\n".format(
            prospect_name=prospect_name,
            prospect_id=prospect_id,
            message=new_message,
            link=conversation_url,
            client_sdr_name=client_sdr_name,
        ),
        webhook_urls=[URL_MAP["operations-csm-mailman"]],
    )


def backfill_all_prospects():
    data = db.session.execute(
        """
        SELECT
            prospect.id,
            prospect.full_name,
            prospect.status,
            prospect.li_should_deep_scrape,
            client_sdr.name,
            client_sdr.id client_sdr_id,
            prospect.li_should_deep_scrape,
            prospect.li_conversation_thread_id,
            count(DISTINCT linkedin_conversation_entry.id)
        FROM
            prospect
            LEFT JOIN client_sdr ON client_sdr.id = prospect.client_sdr_id
            LEFT JOIN client ON client.id = client_sdr.client_id
            LEFT JOIN linkedin_conversation_entry ON linkedin_conversation_entry.conversation_url = prospect.li_conversation_thread_id
        WHERE
            prospect.li_conversation_thread_id IS NOT NULL
            AND client.active
        GROUP BY
            1,
            2,
            3,
            4,
            5,
            6
        HAVING
            count(DISTINCT linkedin_conversation_entry.id) = 0;
    """
    ).fetchall()
    prospects = []
    for row in tqdm(data):
        id = row[0]
        p = Prospect.query.get(id)
        p.li_should_deep_scrape = True
        prospects.append(p)
    db.session.bulk_save_objects(prospects)
    db.session.commit()


def get_li_conversation_entries(hours: Optional[int] = 168) -> list[dict]:
    """Gets the last `hours` hours of LinkedIn conversation entries.

    This method returns more than just the raw conversation entry, it also returns information
    about the ClientSDR, the Client, and the Prospect. This will also, for now, only return
    conversation entries that belong to Prospects that are in the `ACTIVE_CONVO` status.

    Args:
        hours (Optional[int], optional): The number of hours in the past, from now, to see. Defaults to 168.
    """
    from model_import import Prospect, Client

    data = []

    # Get all the conversation entries that are in the past `hours` hours and are not from the user
    past_entries: list[
        LinkedinConversationEntry
    ] = LinkedinConversationEntry.query.filter(
        LinkedinConversationEntry.created_at > datetime.now() - timedelta(hours=hours),
        LinkedinConversationEntry.connection_degree != "You",
    )

    # Parse the entries to get meaningful data
    for entry in past_entries:
        conversation_url = entry.conversation_url
        prospect: Prospect = Prospect.query.filter(
            Prospect.li_conversation_thread_id.isnot(None),
            or_(
                Prospect.li_conversation_thread_id == conversation_url,
                Prospect.li_conversation_thread_id.ilike("%" + conversation_url + "%"),
            ),
        ).first()
        if prospect:
            client_sdr: ClientSDR = ClientSDR.query.get(prospect.client_sdr_id)
            client: Client = Client.query.get(client_sdr.client_id)
            if client_sdr.active and client.active:
                data.append(
                    {
                        "linkedin_conversation_entry_id": entry.id,
                        "conversation_url": entry.conversation_url,
                        "author": entry.author,
                        "connection_degree": entry.connection_degree,
                        "date": entry.date,
                        "message": entry.message,
                        "sdr_name": client_sdr.name,
                        "sdr_auth_token": client_sdr.auth_token,
                        "client_name": client.company,
                        "prospect_name": prospect.full_name,
                        "prospect_status": prospect.status.value,
                    }
                )

    return data


scrape_time_offset = 30 * 60  # 30 minutes in seconds


@celery.task
def scrape_conversations_inbox():
    client_sdr: List[ClientSDR] = ClientSDR.query.filter(
        ClientSDR.active == True,
        ClientSDR.li_at_token is not None,
        ClientSDR.li_at_token != "INVALID",
        ClientSDR.scrape_time is not None,
        ClientSDR.next_scrape < datetime.utcnow(),
    ).all()

    for sdr in client_sdr:
        # Scrape every 3 hours instead #

        # Sent the next scrape to be 1 day from now (+/- scrape_time_offset)
        # scrape_datetime = datetime.combine(datetime.utcnow().date(), sdr.scrape_time)

        # new_date = datetime.utcnow() + timedelta(days=1)
        next_time = (
            datetime.utcnow()
            + timedelta(hours=3)
            + timedelta(seconds=random.randint(-scrape_time_offset, scrape_time_offset))
        )
        next_datetime = datetime(
            next_time.year,
            next_time.month,
            next_time.day,
            next_time.hour,
            next_time.minute,
            next_time.second,
        )

        sdr.next_scrape = next_datetime
        db.session.add(sdr)
        db.session.commit()

        # Get the conversations
        api = LinkedIn(sdr.id)
        convos = api.get_conversations(120)
        if convos is None:
            continue
        for convo in convos:
            last_msg_urn_id = convo.get("events")[0]["dashEntityUrn"].replace(
                "urn:li:fsd_message:", ""
            )
            convo_entry = LinkedinConversationEntry.query.filter_by(
                urn_id=last_msg_urn_id
            ).first()
            convo_urn_id = convo.get("dashEntityUrn").replace(
                "urn:li:fsd_conversation:", ""
            )
            if len(convo.get("participants", [])) != 1:
                continue  # Skip group conversations
            profile_urn_id = (
                convo.get("participants")[0]
                .get("com.linkedin.voyager.messaging.MessagingMember", {})
                .get("miniProfile", {})
                .get("entityUrn", "")
                .replace("urn:li:fs_miniProfile:", "")
            )
            profile_public_id = (
                convo.get("participants")[0]
                .get("com.linkedin.voyager.messaging.MessagingMember", {})
                .get("miniProfile", {})
                .get("publicIdentifier", "")
            )
            if (
                not convo_entry
                and not db.session.query(LinkedinConversationScrapeQueue)
                .filter_by(conversation_urn_id=convo_urn_id)
                .first()
            ):
                prospect: Prospect = Prospect.query.filter(
                    Prospect.li_urn_id == profile_urn_id
                ).first()
                if prospect is None:
                    # Fill in the prospect's urn_id if it's not in the database
                    prospect = Prospect.query.filter(
                        Prospect.linkedin_url.like(f"%/in/{profile_public_id}%")
                    ).first()
                    if prospect is not None:
                        prospect.li_urn_id = profile_urn_id
                        db.session.add(prospect)
                if prospect is None:
                    continue  # Skip if prospect is not in the database
                if prospect.client_sdr_id != sdr.id:
                    continue  # Skip if prospect is not assigned to this SDR

                scrape = LinkedinConversationScrapeQueue(
                    conversation_urn_id=convo_urn_id,
                    client_sdr_id=sdr.id,
                    prospect_id=prospect.id,
                    scrape_time=(
                        datetime.utcnow()
                        + timedelta(seconds=random.randint(0, scrape_time_offset))
                    ),
                )
                db.session.add(scrape)
                db.session.commit()

                send_slack_message(
                    message=f"Scheduled scrape for convo between SDR {sdr.name} (#{sdr.id}) and prospect {prospect.full_name} (#{prospect.id}) at {scrape.scrape_time} UTC 👌",
                    webhook_urls=[URL_MAP["operations-linkedin-scraping-with-voyager"]],
                )


@celery.task
def scrape_conversation_queue():
    from src.voyager.services import update_conversation_entries
    from src.client.services import populate_prospect_events

    scrape_queue: List[
        LinkedinConversationScrapeQueue
    ] = LinkedinConversationScrapeQueue.query.filter(
        LinkedinConversationScrapeQueue.scrape_time < datetime.utcnow()
    ).all()

    for scrape in scrape_queue:
        # try:
        client_sdr_id = scrape.client_sdr_id
        prospect_id = scrape.prospect_id
        conversation_urn_id = scrape.conversation_urn_id

        db.session.delete(scrape)
        db.session.commit()

        api = LinkedIn(client_sdr_id)
        prospect: Prospect = Prospect.query.get(prospect_id)
        if prospect is None:
            continue

        status, msg = update_conversation_entries(api, conversation_urn_id, prospect_id)

        sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
        prospect: Prospect = Prospect.query.get(prospect_id)
        send_slack_message(
            message=f"••• Scraping convo between SDR {sdr.name} (#{sdr.id}) and prospect {prospect.full_name} (#{prospect.id}) 🤖\nResult: {status}, {msg}",
            webhook_urls=[URL_MAP["operations-linkedin-scraping-with-voyager"]],
        )

        # Update calendar events
        populate_prospect_events(client_sdr_id, prospect_id)

        # except Exception as e:
        #     send_slack_message(
        #         message=f"🛑 Error scraping convo between SDR #{scrape.client_sdr_id} and prospect #{scrape.prospect_id}\nMsg: {exception_to_str()}",
        #         webhook_urls=[URL_MAP["operations-linkedin-scraping-with-voyager"]],
        #     )
        #     continue


@celery.task
def send_autogenerated_bumps(override_sdr_id: Optional[int] = None):
    """Grabs active SDRs with autobump enabled and sends the oldest unsent autobump message to the oldest prospect in ACCEPTED or BUMPED status."""
    # Get current time
    utc = pytz.UTC
    now = utc.localize(datetime.utcnow())

    # Get SDRs with active autobump
    autobumpable_sdrs: List[ClientSDR] = ClientSDR.query.filter(
        ClientSDR.active == True,
        ClientSDR.auto_bump == True,
        ClientSDR.li_at_token is not None,
        ClientSDR.li_at_token != "INVALID",
    ).all()
    sdr_ids = [sdr.id for sdr in autobumpable_sdrs]

    if override_sdr_id is not None:
        sdr_ids = [override_sdr_id]

    for sdr_id in sdr_ids:
        sdr: ClientSDR = ClientSDR.query.get(sdr_id)

        # Default timezone to PST
        timezone = sdr.timezone or "America/Los_Angeles"

        start_time, end_time = get_working_hours_in_utc(timezone)
        # Skip if not in working hours
        if now < start_time or now > end_time or is_weekend(timezone):
            continue

        # Get messages that haven't been sent yet and belong to Prospects that are in ACCEPTED or BUMPED status
        oldest_auto_message = (
            db.session.query(
                Prospect.id.label("prospect_id"),
                GeneratedMessageAutoBump.id.label("auto_bump_message_id"),
            )
            .select_from(GeneratedMessageAutoBump)
            .join(Prospect, Prospect.id == GeneratedMessageAutoBump.prospect_id)
            .filter(
                Prospect.client_sdr_id == sdr.id,
                Prospect.overall_status.in_(
                    [ProspectOverallStatus.ACCEPTED, ProspectOverallStatus.BUMPED]
                ),
                # Minimum length of 15 characters
                func.length(GeneratedMessageAutoBump.message) > 14,
                or_(Prospect.hidden_until == None, Prospect.hidden_until < now),
                GeneratedMessageAutoBump.bump_framework_id != None,
                GeneratedMessageAutoBump.bump_framework_title != None,
                GeneratedMessageAutoBump.bump_framework_description != None,
                GeneratedMessageAutoBump.bump_framework_length != None,
                GeneratedMessageAutoBump.account_research_points != None,
                GeneratedMessageAutoBump.send_status == SendStatus.IN_QUEUE,
            )
            .order_by(GeneratedMessageAutoBump.id.desc())
            .first()
        )

        if oldest_auto_message is None:
            continue

        prospect: Prospect = Prospect.query.get(oldest_auto_message.prospect_id)

        # Skip auto sending if disabled settings are enabled
        if (
            prospect is None
            # or (
            #     prospect.li_last_message_from_sdr is not None
            #     and sdr.disable_ai_on_message_send
            # )
            or (
                prospect.li_last_message_from_prospect is not None
                and sdr.disable_ai_on_prospect_respond
            )
        ):
            continue

        # Check to see if the conversation ever includes a message from the SDR that wasn't AI generated
        if sdr.disable_ai_on_message_send:
            convo: List[
                LinkedinConversationEntry
            ] = LinkedinConversationEntry.li_conversation_thread_by_prospect_id(
                oldest_auto_message.prospect_id
            )
            human_sent_msg = next(
                (
                    msg
                    for msg in convo
                    if not msg.ai_generated and msg.connection_degree == "You"
                ),
                None,
            )
            if human_sent_msg is not None:
                continue

        # Send the message
        # 0. Sleep for a random amount of time to avoid LinkedIn bot detection
        delay = random.randint(30, 90)
        status = send_autogenerated_bump.apply_async(
            [
                oldest_auto_message.prospect_id,
                sdr.id,
                oldest_auto_message.auto_bump_message_id,
            ],
            countdown=delay,
            priority=1,
        )
        # send_autogenerated_bump(
        #     oldest_auto_message.prospect_id,
        #     sdr.id,
        #     oldest_auto_message.auto_bump_message_id,
        # )

    return


@celery.task
def send_autogenerated_bump(
    prospect_id: int, client_sdr_id: int, generated_message_auto_bump_id: int
) -> bool:
    """Sends an autogenerated bump message to a prospect.

    Args:
        prospect_id (int): ID of the prospect
        client_sdr_id (int): ID of the SDR
        generated_message_auto_bump_id (int): ID of the autogenerated bump message

    Returns:
        bool: True if message was sent successfully, False otherwise
    """
    try:
        from src.message_generation.services import add_generated_msg_queue
        from src.voyager.services import get_profile_urn_id, fetch_conversation

        sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)

        # Pre-check: Mark the message as being sent
        message: GeneratedMessageAutoBump = GeneratedMessageAutoBump.query.get(
            generated_message_auto_bump_id
        )
        if message is None:
            return False
        if message.send_status == SendStatus.PROCESSING:
            send_slack_message(
                message=f"Avoided Celery race condition for *{sdr.name}* (#{sdr.id}). Message #{message.id} is in PROCESSING state.",
                webhook_urls=[URL_MAP["operations-autobump"]],
            )
            return False
        message.send_status = SendStatus.PROCESSING
        db.session.commit()

        # 1. Refresh the conversation
        api = LinkedIn(client_sdr_id)
        if not api.is_valid():
            send_slack_message(
                message=f"🚨 URGENT 🚨: SDR {sdr.name} (#{sdr.id}) has invalid Linkedin Cookies. Please reset in order to use Voyager.",
                webhook_urls=[URL_MAP["operations-autobump"]],
            )
            return False

        latest_convos, _ = fetch_conversation(api, prospect_id, True)

        # 2. Get the last message
        last_message: dict = latest_convos[0]

        # 3. Make sure that the generated message is valid
        message: GeneratedMessageAutoBump = GeneratedMessageAutoBump.query.get(
            generated_message_auto_bump_id
        )
        if (
            message is None
            or message.prospect_id != prospect_id
            or message.bump_framework_id is None
            or message.bump_framework_title is None
            or message.bump_framework_description is None
            or message.bump_framework_length is None
            or message.account_research_points is None
        ):
            raise Exception("Invalid autogenerated bump message fed into AI sender")

        # 4. Make sure that the Prospect is in a valid state
        prospect: Prospect = Prospect.query.get(prospect_id)
        if (
            prospect.overall_status
            not in [
                ProspectOverallStatus.ACCEPTED,
                ProspectOverallStatus.BUMPED,
            ]
            and not prospect.active
        ):
            db.session.delete(message)
            db.session.commit()
            return False

        # 4a. Check if the prospect has deactivated AI engagement
        if prospect.deactivate_ai_engagement:
            db.session.delete(message)
            db.session.commit()
            return False

        # 5. Check that this bump is responding to the last message, else discard
        if last_message is None or message.latest_li_message_id != last_message.get(
            "id"
        ):
            db.session.delete(message)
            db.session.commit()
            send_slack_message(
                message=f"••• 🚨🔄 SDR {sdr.name} (#{sdr.id}): Will not send because cached bump is out of date. Autogenerated bump message #{message.id} for prospect {prospect.full_name} (#{prospect.id}) discarded because it's not responding to the last message in the thread 🤖\nLast message: {last_message.get('message')}\nMessage: {message.message}",
                webhook_urls=[URL_MAP["operations-autobump"]],
                blocks=[
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": f"🚨🔄 SDR {sdr.name} (#{sdr.id}): Will not send because cached bump is out of date",
                            "emoji": True,
                        },
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"--- Conversation with prospect *{prospect.full_name}* (#{prospect.id}) ---",
                        },
                    },
                    {"type": "divider"},
                    {
                        "type": "context",
                        "elements": [
                            {
                                "type": "mrkdwn",
                                "text": "*Most recent message*: "
                                + last_message.get("message"),
                            },
                        ],
                    },
                    {
                        "type": "context",
                        "elements": [
                            {
                                "type": "mrkdwn",
                                "text": f"*Autobump Message* (#{message.id}): *{message.message}*",
                            },
                        ],
                    },
                ],
            )
            return False

        # 5a. Run the stale message check
        success, _ = rule_no_stale_message(generated_message_auto_bump_id, [])
        if not success:
            db.session.delete(message)
            db.session.commit()
            send_slack_message(
                message=f"••• 🚨🔥 SDR {sdr.name} (#{sdr.id}): Will not send because the message is stale. Autogenerated bump message #{message.id} for prospect {prospect.full_name} (#{prospect.id}) discarded because it's stale 🤖. Will retry.",
                webhook_urls=[URL_MAP["operations-autobump"]],
            )
            send_autogenerated_bumps.apply_async([sdr.id], priority=1)
            return False

        # 5b. Run the full firewall on the bump message
        success, violations = run_autobump_firewall(generated_message_auto_bump_id)
        if not success:
            db.session.delete(message)
            db.session.commit()
            send_slack_message(
                message=f"••• 🚨🔥 SDR {sdr.name} (#{sdr.id}): Firewall killed the bump. Autogenerated bump message #{message.id} for prospect {prospect.full_name} (#{prospect.id}) discarded because it violates the firewall 🤖\nLast message: {last_message.get('message')}\nMessage: {message.message}\nViolations: {violations}",
                webhook_urls=[URL_MAP["operations-autobump"]],
                blocks=[
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": f"🚨🔥 SDR {sdr.name} (#{sdr.id}): Bump blocked by firewall",
                            "emoji": True,
                        },
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"--- Conversation with prospect *{prospect.full_name}* (#{prospect.id}) ---",
                        },
                    },
                    {"type": "divider"},
                    {
                        "type": "context",
                        "elements": [
                            {
                                "type": "mrkdwn",
                                "text": "*Most recent message*: "
                                + last_message.get("message"),
                            },
                        ],
                    },
                    {
                        "type": "context",
                        "elements": [
                            {
                                "type": "mrkdwn",
                                "text": f"*Autobump Message* (#{message.id}): *{message.message}*",
                            },
                        ],
                    },
                    {
                        "type": "context",
                        "elements": [
                            {
                                "type": "mrkdwn",
                                "text": "*Violations*:\n-"
                                + "\n-".join([violation for violation in violations]),
                            },
                        ],
                    },
                ],
            )
            return False

        # 6. Check that we are not bumping too soon, else discard
        bump: BumpFramework = BumpFramework.query.get(message.bump_framework_id)
        utc = pytz.UTC
        now = utc.localize(datetime.utcnow())
        last_message_date = last_message.get("date") or last_message.get("created_at")
        last_message_date = utc.localize(last_message_date)
        bump_delay_seconds = (
            bump.bump_delay_days * 60 * 60 if bump.bump_delay_days else 48 * 60 * 60
        )
        if (
            now - last_message_date
        ).total_seconds() < bump_delay_seconds and prospect.status != ProspectStatus.ACCEPTED:
            formatted_last_message_date = last_message_date.strftime(
                "%m/%d/%Y %H:%M:%S"
            )
            formatted_now = now.strftime("%m/%d/%Y %H:%M:%S")
            send_slack_message(
                message=f'••• 🚨⏳ SDR {sdr.name} (#{sdr.id}): Will not send because last message was less than bump delay hours ago. Autogenerated bump message #{message.id} for prospect {prospect.full_name} (#{prospect.id}) discarded because the last message in the thread was less than 48 hours ago 🤖\nLast message: {last_message.get("message")}\nMessage: {message.message}',
                webhook_urls=[URL_MAP["operations-autobump"]],
                blocks=[
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": f"🚨⏳ SDR {sdr.name} (#{sdr.id}): Will not send because last message was within the bump's waiting period",
                            "emoji": True,
                        },
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"--- Conversation with prospect *{prospect.full_name}* (#{prospect.id}) ---",
                        },
                    },
                    {
                        "type": "divider",
                    },
                    {
                        "type": "context",
                        "elements": [
                            {
                                "type": "mrkdwn",
                                "text": f"*Most recent message* ({formatted_last_message_date}): "
                                + last_message.get("message"),
                            },
                        ],
                    },
                    {
                        "type": "context",
                        "elements": [
                            {
                                "type": "mrkdwn",
                                "text": f"*Autobump Message* ({formatted_now}) (#{message.id}): *{message.message}*",
                            },
                        ],
                    },
                ],
            )
            # Delete the message and remark Prospect hidden until
            if (
                prospect.overall_status != ProspectOverallStatus.ACCEPTED
                and prospect.overall_status != ProspectOverallStatus.PROSPECTED
                and prospect.overall_status != ProspectOverallStatus.SENT_OUTREACH
            ):
                prospect.hidden_until = last_message_date + timedelta(days=2)
                prospect.hidden_reason = ProspectHiddenReason.RECENTLY_BUMPED
                db.session.delete(message)
                db.session.commit()
            return False

        # 7. Send message
        time.sleep(2)
        api = LinkedIn(client_sdr_id)
        urn_id = get_profile_urn_id(prospect_id, api)
        msg_urn_id = api.send_message(message.message, recipients=[urn_id])
        if isinstance(msg_urn_id, str):
            if isinstance(message.bump_framework_length, BumpLength):
                _ = add_generated_msg_queue(
                    client_sdr_id=prospect.client_sdr_id,
                    li_message_urn_id=msg_urn_id,
                    bump_framework_id=message.bump_framework_id,
                    bump_framework_title=message.bump_framework_title,
                    bump_framework_description=message.bump_framework_description,
                    bump_framework_length=message.bump_framework_length.value,
                    account_research_points=message.account_research_points,
                )
            else:
                _ = add_generated_msg_queue(
                    client_sdr_id=prospect.client_sdr_id,
                    li_message_urn_id=msg_urn_id,
                    bump_framework_id=message.bump_framework_id,
                    bump_framework_title=message.bump_framework_title,
                    bump_framework_description=message.bump_framework_description,
                    bump_framework_length=message.bump_framework_length,
                    account_research_points=message.account_research_points,
                )
            db.session.commit()

        # 8. Send to purgatory
        bump_delay_days = bump.bump_delay_days or 2
        send_to_purgatory(
            prospect_id, bump_delay_days, ProspectHiddenReason.RECENTLY_BUMPED
        )

        # 7-8a. Send Slack message
        archetype: ClientArchetype = ClientArchetype.query.get(prospect.archetype_id)
        send_slack_message(
            message=f"•••: ✅ SDR {sdr.name} (#{sdr.id}): Sending autogenerated bump message to prospect {prospect.full_name} (#{prospect.id}) 🤖\nLast Message: {last_message.get('message')}\nMessage: {message.message}",
            webhook_urls=[URL_MAP["operations-autobump"]],
            blocks=[
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"✅ SDR {sdr.name} (#{sdr.id}): Sending autogenerated bump message",
                        "emoji": True,
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"--- *Archetype*: {archetype.archetype}, (#{archetype.id}) ---",
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"--- Conversation with prospect *{prospect.full_name}* (#{prospect.id}) ---",
                    },
                },
                {"type": "divider"},
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": "*Most recent message*: "
                            + last_message.get("message"),
                        },
                    ],
                },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": f"*Autobump Message* (#{message.id}): *{message.message}*",
                        },
                    ],
                },
                {"type": "divider"},
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"--- Using Bump Framework *{message.bump_framework_title}* (#{message.bump_framework_id}) ---",
                    },
                },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": f"{message.bump_framework_description}",
                        },
                    ],
                },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": f"With account research points:\n {message.account_research_points}",
                        },
                    ],
                },
            ],
        )
        message.send_status = SendStatus.SENT
        db.session.commit()

        # 9. Refetch conversation to update statuses, then process generated message queue
        api = LinkedIn(client_sdr_id)
        _, _ = fetch_conversation(api, prospect_id, True)

        # 10. Delete message
        message: GeneratedMessageAutoBump = GeneratedMessageAutoBump.query.get(
            generated_message_auto_bump_id
        )
        db.session.delete(message)
        db.session.commit()

        return True
    except Exception as e:
        # Pre-check: Mark the message as being sent
        message: GeneratedMessageAutoBump = GeneratedMessageAutoBump.query.get(
            generated_message_auto_bump_id
        )
        if message is None:
            return False

        send_slack_message(
            message=f"Runtime error occurred. Error: \n```{e}```",
            webhook_urls=[URL_MAP["operations-autobump"]],
        )

        if message.send_status == SendStatus.PROCESSING:
            message.send_status = SendStatus.IN_QUEUE
            db.session.commit()
            send_slack_message(
                message=f"Runtime error occurred. Reset message status to 'in_queue' for message #{generated_message_auto_bump_id}",
                webhook_urls=[URL_MAP["operations-autobump"]],
                blocks=[
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"Runtime error occurred. Reset message status to 'in_queue' for message #{generated_message_auto_bump_id}",
                        },
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"Error: {e}",
                        },
                    },
                ],
            )
        return False


def ai_initial_li_msg_prompt(
    client_sdr_id: int,
    prospect_id: int,
    template: str,
    additional_instructions: str,
    research_points: list[str],
) -> str:
    """Generate an AI LinkedIn Prompt given a prospect. Uses the prospect's sequence step template, otherwise uses a default SellScale template.

    If a test template is provided, it will use that instead of the sequence step template.

    Args:
        client_sdr_id (int): The client SDR ID
        prospect_id (int): The prospect ID

    Returns:
        str: The AI LinkedIn Prompt

    """

    # from src.message_generation.services_stack_ranked_configurations import get_sample_prompt_from_config_details

    # client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    # client: Client = Client.query.get(client_sdr.client_id)
    prospect: Prospect = Prospect.query.get(prospect_id)
    # client_archetype: ClientArchetype = ClientArchetype.query.get(
    #     prospect.archetype_id)

    # prompt, _, _, _, _, _ = get_sample_prompt_from_config_details(
    #     generated_message_type="LINKEDIN",
    #     research_point_types=[x.value for x in ResearchPointType],
    #     configuration_type="DEFAULT",
    #     client_id=client_sdr.client_id,
    #     archetype_id=prospect.archetype_id,
    #     override_prospect_id=prospect_id,
    # )

    # Grab 3 random points from the research points
    random_sample_points = random.sample(research_points, min(len(research_points), 3))
    found_points = get_prospect_research_points(prospect_id, random_sample_points)

    name = prospect.full_name
    industry = prospect.industry
    title = (
        prospect.colloquialized_title
        if prospect.colloquialized_title
        else prospect.title
    )
    company = (
        prospect.colloquialized_company
        if prospect.colloquialized_company
        else prospect.company
    )
    notes = "\n".join([point.get("value") for point in found_points])

    # parts = prompt.split("<>")
    # for part in parts:
    #     if part.startswith('name: '):
    #         name = part.replace('name: ', '')
    #     elif part.startswith('industry: '):
    #         industry = part.replace('industry: ', '')
    #     elif part.startswith('title: '):
    #         title = part.replace('title: ', '')
    #     elif part.startswith('company: '):
    #         company = part.replace('company: ', '')
    #     elif part.startswith('notes: '):
    #         notes = part.replace('notes: ', '')

    prompt = f"""
You are a sales development representative writing on behalf of the salesperson.

Please write an initial LinkedIn connection message using the template and only include the information if is in the template. Stick to the template strictly.

Note - you do not need to include all info.

Prospect info --
Prospect Name: {name}
Prospect Title: {title}
Prospect Industry: {industry}
Prospect Company Name: {company}
Prospect Notes:
"{notes}"

Final instructions
- Do not put generalized fluff, such as "I couldn't help but notice" or  "I noticed"
- The output message needs to be less than 300 characters.
{additional_instructions}

Here's the template, everything in brackets should be replaced by you. For example: [[prospect_name]] should be replaced by the prospect's name.

IMPORTANT:
Stick to the template very strictly. Do not change this template at all.  Similar to madlibs, only fill in text where there's a double bracket (ex. [[personalization]] ).
--- START TEMPLATE ---
{template}
--- END TEMPLATE ---
    Output:"""

    return prompt


def detect_template_research_points(client_sdr_id: int, template: str):
    from src.research.services import get_all_research_point_types

    all_research_points = get_all_research_point_types(client_sdr_id, names_only=True)
    points_str = "\n".join(all_research_points)

    prompt = f"""

I have message template and I want to detect the research points that should be utilized in order to fill in the template.
The prospect name, prospect title, prospect industry, and prospect company name are provided by default. No need to include them in the research points.


### Template
{template}

### Research Points
{points_str}

Please only respond with a JSON array of the research points that should be used. Write the research points exactly as they are written above.
    """

    completion = get_text_generation(
        [{"role": "user", "content": prompt}],
        max_tokens=300,
        model="gpt-4",
        type="RESEARCH",
        prospect_id=None,
        client_sdr_id=None,
        use_cache=False,
    )

    # Parse JSON string
    try:
        research_points = yaml.safe_load(completion)
    except:
        research_points = None

    return research_points
