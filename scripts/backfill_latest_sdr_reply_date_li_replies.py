exec(
    """
from model_import import LinkedinConversationEntry
from app import db
import datetime

query = '''
select array_agg(distinct linkedin_conversation_entry.id order by linkedin_conversation_entry.id desc) 
from linkedin_conversation_entry 
join prospect on prospect.li_conversation_urn_id = linkedin_conversation_entry.thread_urn_id 
join client_sdr on client_sdr.id = prospect.client_sdr_id 
join client on client.id = client_sdr.client_id 
where client.active and client_sdr.active and linkedin_conversation_entry.latest_reply_from_sdr_date is null;
'''

ids = db.session.execute(query).fetchone()[0]

def backfill_last_reply_dates_for_conversations_in_last_day():
    conversations_in_last_day = LinkedinConversationEntry.query.filter(
        LinkedinConversationEntry.date > datetime.datetime.now() - datetime.timedelta(days=1)
    ).all()

    conversation_urls = set([c.conversation_url for c in conversations_in_last_day])

    for conversation_url in conversation_urls:
        conversation_entries = LinkedinConversationEntry.query.filter(
            LinkedinConversationEntry.conversation_url == conversation_url
        ).order_by(LinkedinConversationEntry.date).all()

        for i, conversation_entry in enumerate(conversation_entries):
            backfill_last_reply_date(conversation_entry.id)
        

def backfill_last_reply_date(li_conversation_entry_id: int):
    conversation_entry: LinkedinConversationEntry = LinkedinConversationEntry.query.get(li_conversation_entry_id)

    if conversation_entry is None:
        print(f"Conversation entry with id {li_conversation_entry_id} not found")
        return

    conversation_url = conversation_entry.conversation_url
    date = conversation_entry.date

    first_response_from_me_in_conversation_after_date = LinkedinConversationEntry.query.filter(
        LinkedinConversationEntry.conversation_url == conversation_url,
        LinkedinConversationEntry.date > date,
        LinkedinConversationEntry.connection_degree == 'You'
    ).order_by(LinkedinConversationEntry.date).first()


    if first_response_from_me_in_conversation_after_date is not None:
        print(f"First response from me in conversation after {date} is {first_response_from_me_in_conversation_after_date.date}")
        conversation_entry.latest_reply_from_sdr_date = first_response_from_me_in_conversation_after_date.date
        db.session.add(conversation_entry)
        db.session.commit()

backfill_last_reply_dates_for_conversations_in_last_day()

# for i in ids:
#     backfill_last_reply_date(i)
"""
)
