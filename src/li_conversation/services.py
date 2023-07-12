from typing import List, Union, Optional
from src.client.models import ClientArchetype
from src.li_conversation.autobump_helpers.services_firewall import run_autobump_firewall
from src.message_generation.models import GeneratedMessageAutoBump
from src.prospecting.models import (
    ProspectHiddenReason,
    ProspectOverallStatus,
    ProspectStatus,
)

from src.li_conversation.models import LinkedInConvoMessage
from src.bump_framework.models import BumpLength
from src.prospecting.services import send_to_purgatory
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
)
from src.automation.models import PhantomBusterAgent
from src.ml.openai_wrappers import wrapped_create_completion
from src.utils.slack import URL_MAP
from src.utils.slack import send_slack_message
from datetime import datetime, timedelta
from tqdm import tqdm
from src.ml.openai_wrappers import wrapped_chat_gpt_completion
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

    direct_link = "https://app.sellscale.com/authenticate?stytch_token_type=direct&token={auth_token}&redirect=contacts/{prospect_id}".format(
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

    # Flag as urgent if message is new and mentions something urgent
    if not duplicate_exists and client_sdr_id != -1 and connection_degree != "You":
        if (
            "tomorrow" in message.lower()
            or "today" in message.lower()
            or "@" in message.lower()
            or "week" in message.lower()
            or "month" in message.lower()
            or "monday" in message.lower()
            or "tuesday" in message.lower()
            or "wednesday" in message.lower()
            or "thursday" in message.lower()
            or "friday" in message.lower()
            or "saturday" in message.lower()
            or "sunday" in message.lower()
        ):
            sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
            send_slack_message(
                message=f"""
                {author} wrote to {sdr.name} with the message:
                ```
                {message}
                ```
                Time-sensitive keyword was detected.

                Take appropriate action then mark this message as ✅

                *Direct Link:* {direct_link}
                """,
                webhook_urls=[URL_MAP["csm-urgent-alerts"]],
            )

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
            db.session.add(prospect)

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
):
    for _ in range(max_retries):
        try:
            return generate_chat_gpt_response_to_conversation_thread_helper(
                prospect_id=prospect_id,
                convo_history=convo_history,
                bump_framework_id=bump_framework_id,
                account_research_copy=account_research_copy,
                override_bump_length=override_bump_length,
            )
        except Exception as e:
            time.sleep(2)
            continue


def generate_chat_gpt_response_to_conversation_thread_helper(
    prospect_id: int,
    convo_history: List[LinkedInConvoMessage],
    bump_framework_id: Optional[int] = None,
    account_research_copy: str = "",
    override_bump_length: Optional[BumpLength] = None,
):
    from model_import import Prospect

    # First the first message from the SDR
    msg = next(filter(lambda x: x.connection_degree == "You", convo_history), None)
    if not msg:
        raise Exception("No message from SDR found in convo_history")
    sender = msg.author

    transcript = "\n\n".join(
        [x.author + " (" + str(x.date)[0:10] + "): " + x.message for x in convo_history]
    )
    content = transcript + "\n\n" + sender + " (" + str(datetime.now())[0:10] + "):"

    prospect: Prospect = Prospect.query.get(prospect_id)
    client_sdr: ClientSDR = ClientSDR.query.get(prospect.client_sdr_id)
    archetype: ClientArchetype = ClientArchetype.query.get(prospect.archetype_id)

    details = ""
    if random.random() < 0.5:
        details = "\nFor some context, {first_name} is a {title} at {company}. Use these details when personalizing.".format(
            first_name=prospect.first_name,
            title=prospect.title,
            company=prospect.company,
        )

    # message_content = (
    #     "You are a helpful assistant helping the user write their next reply in a message thread. Keep responses friendly and concise while also adding personalization from the first message. Write from the perspective of "
    #     + sender
    #     + "."
    #     + "\n------\n"
    #     + details
    # )
    message_content = (
        "You are "
        + sender
        + " who is writing a follow up response to a message thread. Keep responses friendly and concise while also adding personalization where relevant.\n"
        + "\n------\n"
        + details
    )

    if bump_framework_id:
        bump_framework: Optional[BumpFramework] = BumpFramework.query.get(
            bump_framework_id
        )
    else:
        bump_framework = None

    if account_research_copy:
        message_content = message_content + (
            "\n\nNaturally integrate pieces of information from this account research into the messaging:\n-----\n"
            + account_research_copy
            + "\n-----\n"
        )

    if override_bump_length == BumpLength.SHORT or (
        bump_framework and bump_framework.bump_length == BumpLength.SHORT
    ):
        message_content = message_content + ("\nLength: 1-2 sentences.")
    elif override_bump_length == BumpLength.MEDIUM or (
        bump_framework and bump_framework.bump_length == BumpLength.MEDIUM
    ):
        message_content = message_content + ("\nLength: 2-4 sentences")
    elif override_bump_length == BumpLength.LONG or (
        bump_framework and bump_framework.bump_length == BumpLength.LONG
    ):
        message_content = message_content + (
            "\nLength: 2 paragraphs. Separate with line breaks."
        )

    if bump_framework:
        message_content = message_content + (
            "\n\nYou will be using the bump framework below to construct the message - follow the instructions carefully to construct the message:\nBump Framework:\n----\n "
            + bump_framework.description
            + "\n-----"
        )

    if prospect.status == ProspectStatus.ACCEPTED:
        message_content = message_content + (
            "\n\nImportant Context: This person has just accepted your connection request.\n"
        )

    message_content = message_content + (
        "\n\nNote that this is part of a chat conversation so write one follow up message based on the previous conversation.\n"
    )

    # if archetype and archetype.persona_contact_objective:
    #     message_content = (
    #         message_content
    #         + f"\n\nThe goal of this conversation of chatting with this person is the following: `{archetype.persona_contact_objective}`"
    #     )

    response = wrapped_chat_gpt_completion(
        [
            {"role": "system", "content": message_content},
            {"role": "user", "content": content},
        ],
        max_tokens=200,
        model="gpt-4",
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
        response = wrapped_chat_gpt_completion(
            [
                {
                    "role": "user",
                    "content": instruction,
                },
                {"role": "user", "content": response},
            ],
            max_tokens=200,
            model="gpt-4",
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
        ClientSDR.li_cookies is not None,
        ClientSDR.li_cookies != "INVALID",
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
        try:
            client_sdr_id = scrape.client_sdr_id
            prospect_id = scrape.prospect_id
            conversation_urn_id = scrape.conversation_urn_id

            db.session.delete(scrape)
            db.session.commit()

            api = LinkedIn(client_sdr_id)
            prospect: Prospect = Prospect.query.get(prospect_id)
            if prospect is None:
                continue

            status, msg = update_conversation_entries(
                api, conversation_urn_id, prospect_id
            )

            sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
            prospect: Prospect = Prospect.query.get(prospect_id)
            send_slack_message(
                message=f"••• Scraping convo between SDR {sdr.name} (#{sdr.id}) and prospect {prospect.full_name} (#{prospect.id}) 🤖\nResult: {status}, {msg}",
                webhook_urls=[URL_MAP["operations-linkedin-scraping-with-voyager"]],
            )

            # Update calendar events
            populate_prospect_events(client_sdr_id, prospect_id)

        except Exception as e:
            send_slack_message(
                message=f"🛑 Error scraping convo between SDR #{scrape.client_sdr_id} and prospect #{scrape.prospect_id}\nMsg: {exception_to_str()}",
                webhook_urls=[URL_MAP["operations-linkedin-scraping-with-voyager"]],
            )
            continue


@celery.task
def send_autogenerated_bumps():
    """Grabs active SDRs with autobump enabled and sends the oldest unsent autobump message to the oldest prospect in ACCEPTED or BUMPED status."""
    # Get current time
    utc = pytz.UTC
    now = utc.localize(datetime.utcnow())

    # Get SDRs with active autobump
    autobumpable_sdrs: List[ClientSDR] = ClientSDR.query.filter(
        ClientSDR.active == True,
        ClientSDR.auto_bump == True,
        ClientSDR.li_cookies is not None,
        ClientSDR.li_cookies != "INVALID",
    ).all()

    for sdr in autobumpable_sdrs:
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
            )
            .order_by(GeneratedMessageAutoBump.id.asc())
            .first()
        )

        if oldest_auto_message is None:
            continue

        prospect: Prospect = Prospect.query.get(oldest_auto_message.prospect_id)

        # Skip auto sending if disabled settings are enabled
        if (
            prospect is None
            or (
                prospect.li_last_message_from_sdr is not None
                and sdr.disable_ai_on_message_send
            )
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
        status = send_autogenerated_bump.apply_async(
            [
                oldest_auto_message.prospect_id,
                sdr.id,
                oldest_auto_message.auto_bump_message_id,
            ],
            priority=1,
        )
        # send_autogenerated_bump(oldest_auto_message.prospect_id, sdr.id, oldest_auto_message.auto_bump_message_id)

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
    from src.message_generation.services import add_generated_msg_queue
    from src.voyager.services import get_profile_urn_id, fetch_conversation

    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)

    # 0. Sleep for a random amount of time to avoid LinkedIn bot detection
    time.sleep(random.randint(30, 90))

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
    if prospect.overall_status not in [
        ProspectOverallStatus.ACCEPTED,
        ProspectOverallStatus.BUMPED,
    ]:
        db.session.delete(message)
        db.session.commit()
        return False

    # 5. Check that this bump is responding to the last message, else discard
    if last_message is None or message.latest_li_message_id != last_message.get("id"):
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

    # 5a. Run the firewall on the bump message
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
                            + {"\n-".join([violation for violation in violations])},
                        },
                    ],
                },
            ],
        )
        return False

    # 5b. Check that the bump (reference DB) is set to default, else discard
    bump: BumpFramework = BumpFramework.query.get(message.bump_framework_id)
    if bump is None or not bump.default:
        db.session.delete(message)
        db.session.commit()
        send_slack_message(
            message=f"••• 🚨❌ SDR {sdr.name} (#{sdr.id}): Will not send because the bump is not set to default. Autogenerated bump message #{message.id} for prospect {prospect.full_name} (#{prospect.id}) discarded because the bump is not set to default 🤖\nLast message: {last_message.get('message')}\nMessage: {message.message}",
            webhook_urls=[URL_MAP["operations-autobump"]],
            blocks=[
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"🚨❌ SDR {sdr.name} (#{sdr.id}): Will not send because the BumpFramework is not set to default",
                        "emoji": True,
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"BumpFramework: *{bump.title}* (#{bump.id}) is not set to default",
                    },
                },
            ],
        )

    # 6. Check that the generated message has at least 15 characters, else discard
    if len(message.message) < 15:
        db.session.delete(message)
        db.session.commit()
        send_slack_message(
            message=f"••• 🚨📏 SDR {sdr.name} (#{sdr.id}): Will not send because generated message is too short. Autogenerated bump message #{message.id} for prospect {prospect.full_name} (#{prospect.id}) discarded because the last message in the thread is too short 🤖\nLast message: {last_message.get('message')}\nMessage: {message.message}",
            webhook_urls=[URL_MAP["operations-autobump"]],
            blocks=[
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"🚨📏 SDR {sdr.name} (#{sdr.id}): Will not send because generated message is too short",
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

    # 6.b. Check that the last message was more than 48 hours ago, else discard
    utc = pytz.UTC
    now = utc.localize(datetime.utcnow())
    last_message_date = last_message.get("date") or last_message.get("created_at")
    last_message_date = utc.localize(last_message_date)
    bump_delay_seconds = (
        bump.bump_delay_days * 60 * 60 if bump.bump_delay_days else 48 * 60 * 60
    )
    if (now - last_message_date).total_seconds() < bump_delay_seconds:
        formatted_last_message_date = last_message_date.strftime("%m/%d/%Y %H:%M:%S")
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
                        "text": "*Most recent message*: " + last_message.get("message"),
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
