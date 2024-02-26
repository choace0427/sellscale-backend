from model_import import LinkedinConversationEntry
from app import db, celery
import datetime


@celery.task
def backfill_last_reply_dates_for_conversations_in_last_day():
    conversations_in_last_day = LinkedinConversationEntry.query.filter(
        LinkedinConversationEntry.date
        > datetime.datetime.now() - datetime.timedelta(days=1)
    ).all()

    conversation_urls = set([c.conversation_url for c in conversations_in_last_day])

    for conversation_url in conversation_urls:
        conversation_entries = (
            LinkedinConversationEntry.query.filter(
                LinkedinConversationEntry.conversation_url == conversation_url
            )
            .order_by(LinkedinConversationEntry.date)
            .all()
        )

        for i, conversation_entry in enumerate(conversation_entries):
            backfill_last_reply_date(conversation_entry.id)


def backfill_last_reply_date(li_conversation_entry_id: int):
    conversation_entry: LinkedinConversationEntry = LinkedinConversationEntry.query.get(
        li_conversation_entry_id
    )

    if conversation_entry is None:
        print(f"Conversation entry with id {li_conversation_entry_id} not found")
        return

    conversation_url = conversation_entry.conversation_url
    date = conversation_entry.date

    first_response_from_me_in_conversation_after_date = (
        LinkedinConversationEntry.query.filter(
            LinkedinConversationEntry.conversation_url == conversation_url,
            LinkedinConversationEntry.date > date,
            LinkedinConversationEntry.connection_degree == "You",
        )
        .order_by(LinkedinConversationEntry.date)
        .first()
    )

    if first_response_from_me_in_conversation_after_date is not None:
        print(
            f"First response from me in conversation after {date} is {first_response_from_me_in_conversation_after_date.date}"
        )
        conversation_entry.latest_reply_from_sdr_date = (
            first_response_from_me_in_conversation_after_date.date
        )
        db.session.add(conversation_entry)
        db.session.commit()
