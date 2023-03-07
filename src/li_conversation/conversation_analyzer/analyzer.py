from app import db, celery
from sqlalchemy import or_

from src.ml.openai_wrappers import wrapped_create_completion
from src.utils.slack import send_slack_message, URL_MAP
from model_import import (
    LinkedinConversationEntry,
    ClientSDR,
    Prospect,
    ProspectOverallStatus,
)


@celery.task(bind=True, max_retries=3, default_retry_delay=10)
def run_all_conversation_analyzers(self) -> tuple[bool, int]:
    """Runs all conversation analyzers on the conversation entries that have not been processed

    Returns:
        tuple[bool, int]: (True, number of conversation_urls processed)
    """
    try:
        # Gets conversation_urls of Conversation Entries that have not been processed
        conversation_entries: list[LinkedinConversationEntry] = (
            LinkedinConversationEntry.query.filter(
                or_(
                    LinkedinConversationEntry.entry_processed == False,
                    LinkedinConversationEntry.entry_processed == None,
                )
            )
            .distinct(LinkedinConversationEntry.conversation_url)
            .all()
        )
        conversation_urls: list[str] = [
            entry.conversation_url for entry in conversation_entries
        ]

        # Runs the conversation analyzers on the thread_urls
        run_li_scheduling_conversation_detector(conversation_urls)

        # Updates the Conversation Entries to a TRUE processed state
        LinkedinConversationEntry.query.filter(
            LinkedinConversationEntry.conversation_url.in_(conversation_urls)
        ).update({"entry_processed": True}, synchronize_session=False)
        db.session.commit()

        # Send a Slack message
        send_slack_message(
            message="🤖 Conversation analyzers ran",
            webhook_urls=[URL_MAP["eng-sandbox"]],
        )

        return True, len(conversation_urls)
    except Exception as e:
        db.session.rollback()
        raise self.retry(exc=e, countdown=2**self.request.retries)


def run_li_scheduling_conversation_detector(conversation_urls: list[str]):
    """Runs the scheduling conversation detector on a list of conversation_urls

    Args:
        conversation_urls (list[str]): List of conversation_urls to analyze
    """
    # Get all prospects with active conversations
    prospects: list[Prospect] = Prospect.query.filter(
        Prospect.li_conversation_thread_id.in_(conversation_urls),
        Prospect.overall_status == ProspectOverallStatus.ACTIVE_CONVO,
    ).all()

    # Run the conversation analyzer on each prospect
    for prospect in prospects:
        result = detect_scheduling_conversation(prospect.id)
        scheduling = result.get("scheduling")
        conversation = result.get("conversation")

        # If prospect is scheduling a meeting, update the prospect
        # TODO: Update the prospect's overall status
        if scheduling:
            sdr: ClientSDR = ClientSDR.query.get(prospect.client_sdr_id)

            # Send a Slack message
            # TODO: Replace this with auto status change
            send_slack_message(
                message=f"Prospect {prospect.full_name} is scheduling a meeting with {sdr.name}!",
                webhook_urls=[URL_MAP["autodetect-scheduling"]],
                blocks=[
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": f"Prospect {prospect.full_name} is scheduling a meeting with {sdr.name}!",
                        },
                    },
                    {
                        "type": "context",
                        "elements": [
                            {
                                "type": "plain_text",
                                "text": "Autodected using AI from the following conversation:",
                            },
                        ],
                    },
                    {
                        "type": "context",
                        "elements": [
                            {
                                "type": "plain_text",
                                "text": message,
                            }
                            for message in conversation
                        ],
                    },
                ],
            )


def detect_scheduling_conversation(prospect_id: int) -> dict:
    """Detects if a prospect is scheduling a meeting with the SDR

    Args:
        prospect_id (int): ID of the Prospect to analyze

    Returns:
        dict: Dictionary of scheduling status and conversation thread
    """
    entries: list[
        LinkedinConversationEntry
    ] = LinkedinConversationEntry.li_conversation_thread_by_prospect_id(prospect_id)
    prospect: Prospect = Prospect.query.get(prospect_id)
    sdr: ClientSDR = ClientSDR.query.get(prospect.client_sdr_id)

    # Reconstruct the conversation thread, with oldest message first
    conversation = []
    for entry in entries[:4]:  # Only check the first 4 entries
        clean_message = entry.message.replace("\n", " ").strip()
        conversation.insert(0, f"{entry.author}: '{clean_message}'")

    # Create the prompt
    prompt_template = f"conversation thread\n"
    for message in conversation:
        prompt_template += f"{message}\n"
    prompt = f"prompt: Is {prospect.full_name} scheduling a time to meet with {sdr.name}? Answer with 'Yes' or 'No'."
    full_prompt = prompt_template + "\n\n" + prompt + "\n\ncompletion:"

    # Run the prompt through the model
    response = wrapped_create_completion(
        model="text-davinci-003",
        prompt=full_prompt,
        max_tokens=5,
        temperature=0,
    ).lower()

    if response == "yes":
        return {"scheduling": True, "conversation": conversation}
    else:
        return {"scheduling": False, "conversation": conversation}
