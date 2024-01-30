from src.ml.services import wrapped_chat_gpt_completion
from app import db
from model_import import Prospect


def categorize_conversation(
    prospect_name: str,
    sales_person_name: str,
    prospect_status: str,
    conversation_transcript: str,
):
    return wrapped_chat_gpt_completion(
        messages=[
            {
                "role": "user",
                "content": f"You are an AI labeler of sales conversations. I will provide you with sales person's name, prospect's name, the prospect's status, and the conversation transcript. Your job is to categorize the conversation based on the status of the prospect and the conversation transcript.\n\nFor prospect's marked as `NOT_INTERESTED`, the label options are `No Need`, `Unconvinced`, `Timing not right`, `Unresponsive`, `Using a competitor`, `Unsubscribe`, and `Other`.\nFor prospect's marked 'NOT_QUALIFIED', the options are `Not a decision maker`, `Poor account fit`, `Contact is 'Open to work'`, `Competitor`, and `Other`.\n\nProspect name: {prospect_name}\nSales person name: {sales_person_name}\nProspect status: {prospect_status}\n\nConversation transcript: {conversation_transcript}\n\nInstruction: Please output only the disqualification reason and nothing more. Do not include any quotation marks.\nInstruction 2: If using `Other`, append `- (3-4 word short description)` to clarify the reasoning\nOutput:",
            }
        ]
    )


query = """
        SELECT 
            prospect.id,
            client_sdr.name,
            prospect.full_name,
            prospect.status,
            STRING_AGG(
                CONCAT(linkedin_conversation_entry.author, ': ', linkedin_conversation_entry.message, ' (', linkedin_conversation_entry.date, ')'),
                '\n\n' ORDER BY linkedin_conversation_entry.date
            ),
            prospect.disqualification_reason
        FROM prospect
            JOIN client_sdr ON client_sdr.id = prospect.client_sdr_id
            JOIN linkedin_conversation_entry ON linkedin_conversation_entry.thread_urn_id = prospect.li_conversation_urn_id
        WHERE prospect.status IN ('NOT_QUALIFIED', 'NOT_INTERESTED')
            AND prospect.disqualification_reason IS NULL
        GROUP BY 1,2
        order by random()
        limit 10
    """


def backfill_data():
    while True:
        results = db.engine.execute(query).fetchall()
        for row in results:
            (
                prospect_id,
                sales_person_name,
                prospect_name,
                prospect_status,
                conversation_transcript,
                _,
            ) = row

            print(prospect_id, sales_person_name, prospect_name, prospect_status)
            disqualification_reason = categorize_conversation(
                prospect_name,
                sales_person_name,
                prospect_status,
                conversation_transcript,
            )
            prospect = Prospect.query.get(prospect_id)
            prospect.disqualification_reason = disqualification_reason
            db.session.add(prospect)
            db.session.commit()
