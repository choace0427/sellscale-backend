from app import db, celery

from model_import import LinkedinConversationEntry, ClientSDR, Prospect
from src.automation.models import PhantomBusterAgent
from src.ml.openai_wrappers import wrapped_create_completion
from src.utils.slack import URL_MAP
from src.utils.slack import send_slack_message
from datetime import datetime
from tqdm import tqdm
from src.ml.openai_wrappers import wrapped_chat_gpt_completion
from src.utils.slack import send_slack_message


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
):
    """
    Check for duplicates and return True if duplicate exists
    """
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
):
    """
    Check for duplicates and duplicate does not exist, create a new LinkedinConversationEntry
    """
    duplicate_exists = check_for_duplicate_linkedin_conversation_entry(
        conversation_url=conversation_url,
        author=author,
        message=message,
    )
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
            connection_degree=connection_degree,
            li_url=li_url,
            message=message,
        )
        return new_linkedin_conversation_entry
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


def generate_chat_gpt_response_to_conversation_thread(conversation_url: str):
    query = """
        with d as (
            select 
                *
            from linkedin_conversation_entry 
            where conversation_url = '{conversation_url}'
            order by date desc
            limit 10
        )
        select string_agg(
                concat(author, ': ', trim(message))
                ,'\n\n'
                order by date
            ),
            max(author) filter (where connection_degree = 'You') sender
        from d;
    """.format(
        conversation_url=conversation_url
    )
    data = db.session.execute(query).fetchall()
    transcript = data[0][0]
    sender = data[0][1]
    content = transcript + "\n\n" + sender + ":"

    response = wrapped_chat_gpt_completion(
        [
            {
                "role": "system",
                "content": "You are a helpful assistant helping the user write their next reply in a message thread. Keep responses friendly and concise. Write from the perspective of "
                + sender
                + ". If there are no messages from the other person who is not "
                + sender
                + " write a follow-up, 'bump' message.",
            },
            {"role": "user", "content": content},
        ],
        max_tokens=200,
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
        message="🤖 Manually send a message to {prospect_name} (#{prospect_id}) out of *{client_sdr_name}'s inbox.\n*message:*\n{message}\n\nLI Link: {link}\n".format(
            prospect_name=prospect_name,
            prospect_id=prospect_id,
            message=new_message,
            link=conversation_url,
            client_sdr_name=client_sdr_name,
        ),
        webhook_urls=[URL_MAP["operations-csm-mailman"]],
    )
