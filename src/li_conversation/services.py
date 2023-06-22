from typing import List, Union, Optional

from src.li_conversation.models import LinkedInConvoMessage
from src.bump_framework.models import BumpLength

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
import random
import time


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
    print("saving objects ...")
    bulk_objects = [obj for obj in bulk_objects if obj]
    db.session.bulk_save_objects(bulk_objects)
    db.session.commit()
    print("Done saving!")


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
):
    if message.strip() == "":
        return None

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
            print(e)
            print("Retrying...")
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
    msg = next(filter(lambda x: x.connection_degree == 'You', convo_history), None)
    if not msg:
        raise Exception("No message from SDR found in convo_history")

    transcript = msg.message
    sender = msg.author
    content = transcript + "\n\n" + sender + ":"

    prospect: Prospect = Prospect.query.get(prospect_id)
    client_sdr: ClientSDR = ClientSDR.query.get(prospect.client_sdr_id)

    details = ""
    if random.random() < 0.5:
        details = "For some context, {first_name} is a {title} at {company}. Use these details when personalizing.".format(
            first_name=prospect.first_name,
            title=prospect.title,
            company=prospect.company,
        )

    message_content = (
        "You are a helpful assistant helping the user write their next reply in a message thread, with the goal of getting the prospect on a call. Keep responses friendly and concise while also adding personalization from the first message. Write from the perspective of "
        + sender
        + ". If there are no messages from the other person who is not "
        + sender
        + " write a follow-up, 'bump' message that includes personalization from the original message."
        + details
    )

    if bump_framework_id:
        bump_framework: Optional[BumpFramework] = BumpFramework.query.get(bump_framework_id)
        if bump_framework:
            message_content = message_content + (
                "\nHere are other relevant details you can use to make the message better: "
                + bump_framework.description
            )
    else:
        bump_framework = None

    if account_research_copy:
        message_content = message_content + (
            "\nUse what you think is relevant from this account research: "
            + account_research_copy
        )

    if override_bump_length == BumpLength.SHORT or (
        bump_framework and bump_framework.bump_length == BumpLength.SHORT
    ):
        message_content = message_content + (
            "\n\nPlease keep this message between 1-3 sentences."
        )
    elif override_bump_length == BumpLength.MEDIUM or (
        bump_framework and bump_framework.bump_length == BumpLength.MEDIUM
    ):
        message_content = message_content + (
            "\n\nPlease keep this message between 3-5 sentences. Separate into paragraphs with line breaks when needed."
        )
    elif override_bump_length == BumpLength.LONG or (
        bump_framework and bump_framework.bump_length == BumpLength.LONG
    ):
        message_content = message_content + (
            "\n\nPlease keep this message between 5-7 sentences. Separate into paragraphs with line breaks when needed."
        )

    response = wrapped_chat_gpt_completion(
        [
            {"role": "system", "content": message_content},
            {"role": "user", "content": content},
        ],
        max_tokens=200,
        model="gpt-4-0314",
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
            db.session.delete(scrape)
            db.session.commit()

            api = LinkedIn(scrape.client_sdr_id)
            prospect: Prospect = Prospect.query.get(scrape.prospect_id)
            if prospect is None:
                continue
            status, msg = update_conversation_entries(
                api, scrape.conversation_urn_id, prospect.id
            )

            # print(f"••• Scraping convo between SDR {api.client_sdr.name} (#{api.client_sdr.id}) and prospect {prospect.full_name} (#{prospect.id}) 🤖\nResult: {status}, {msg}")
            send_slack_message(
                message=f"••• Scraping convo between SDR {api.client_sdr.name} (#{api.client_sdr.id}) and prospect {prospect.full_name} (#{prospect.id}) 🤖\nResult: {status}, {msg}",
                webhook_urls=[URL_MAP["operations-linkedin-scraping-with-voyager"]],
            )

            # Update calendar events
            populate_prospect_events(prospect.client_sdr_id, prospect.id)

        except Exception as e:
            continue
