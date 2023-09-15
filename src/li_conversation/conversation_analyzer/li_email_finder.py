from app import db, celery
from model_import import Prospect
from src.utils.slack import URL_MAP, send_slack_message


class LiEmailFinder:
    def __init__(
        self,
        prospect_id=None,
        prospect_full_name=None,
        prospect_current_email=None,
        prospect_message=None,
        prospect_extracted_email=None,
    ):
        self.prospect_id = prospect_id
        self.prospect_full_name = prospect_full_name
        self.prospect_current_email = prospect_current_email
        self.prospect_message = prospect_message
        self.prospect_extracted_email = prospect_extracted_email

    def to_dict(self):
        return {
            "prospect_id": self.prospect_id,
            "prospect_full_name": self.prospect_full_name,
            "prospect_current_email": self.prospect_current_email,
            "prospect_message": self.prospect_message,
            "prospect_extracted_email": self.prospect_extracted_email,
        }


def get_raw_email_data() -> list[LiEmailFinder]:
    query = """
    select 
        prospect.id "Prospect ID",
        prospect.full_name,
        prospect.email "Current Email",
        message "LI Message from Prospect",
        lower(substring(message FROM '[a-zA-Z0-9._%-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,4}')) "Extracted Email"

    from linkedin_conversation_entry
        join prospect on prospect.li_conversation_thread_id = linkedin_conversation_entry.conversation_url
        join client on client.id = prospect.client_id
        join client_sdr on client_sdr.id = prospect.client_sdr_id
    where message ilike '%@%.%'
        and client.active 
        and client_sdr.active
        and linkedin_conversation_entry.connection_degree <> 'You'
        and (
            linkedin_conversation_entry.message ilike concat('%', prospect.first_name, '%') 
            or linkedin_conversation_entry.message ilike concat('%', prospect.last_name, '%') 
        )
        and (
            prospect.email is null 
            or lower(substring(message FROM '[a-zA-Z0-9._%-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,4}')) <> lower(prospect.email)
        );"""

    data = db.session.execute(query).fetchall()

    formatted_data = []
    for row in data:
        formatted_data.append(
            LiEmailFinder(
                prospect_id=row[0],
                prospect_full_name=row[1],
                prospect_current_email=row[2],
                prospect_message=row[3],
                prospect_extracted_email=row[4],
            )
        )

    return formatted_data


def update_prospect_email(prospect_id, new_email, message):
    prospect: Prospect = Prospect.query.get(prospect_id)
    if not prospect:
        return

    old_email = prospect.email
    prospect.email = new_email
    db.session.add(prospect)
    db.session.commit()

    send_slack_message(
        f"📧🔎 *Email Update from LI Conversation*\nUpdated prospect *{prospect.full_name}* (#{prospect.id}) email from `{old_email}` to `{new_email}`.\nFound email in Linkedin convo from this message:\n```{message}```",
        webhook_urls=[URL_MAP["ops-email-detected"]],
    )
    return True


@celery.task
def update_all_outstanding_prospect_emails():
    send_slack_message(
        f"📧🔎 *Email Update from LI Conversation*\nUpdating all outstanding prospect emails from LI conversations.",
        webhook_urls=[URL_MAP["ops-email-detected"]],
    )
    data: list[LiEmailFinder] = get_raw_email_data()
    for row in data:
        update_prospect_email(
            row.prospect_id, row.prospect_extracted_email, row.prospect_message
        )
