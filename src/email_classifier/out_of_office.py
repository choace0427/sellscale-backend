from datetime import datetime
import re
from app import db, celery
from src.client.models import Client, ClientSDR
from src.email_outbound.models import ProspectEmail, ProspectEmailOutreachStatus
from src.ml.openai_wrappers import OPENAI_CHAT_GPT_4_MODEL, wrapped_chat_gpt_completion
from src.prospecting.models import Prospect
from src.prospecting.services import update_prospect_status_email
from src.slack.models import SlackNotificationType
from src.slack.slack_notification_center import (
    create_and_send_slack_notification_class_message,
)
from src.utils.datetime.dateparse_utils import convert_string_to_datetime_or_none
from src.utils.slack import URL_MAP, send_slack_message

OOO_KEYWORDS = [
    "out of office",
    "on vacation",
    "away from my desk",
    "out of the office",
    "currently out of the office",
    "out of town",
    "taking time off",
    "unavailable",
    "not in the office",
    "out of reach",
    "remote location",
    "business trip",
    "annual leave",
    "off the grid",
    "away on holiday",
    "temporarily away",
    "limited access to email",
    "checking emails intermittently",
    "responding to emails less frequently",
    "out of the country",
    "enjoying some time away",
]


@celery.task()
def detect_out_of_office(prospect_id: int, email_body: str) -> bool:
    """Detects if an email is an out of office reply.

    Args:
        prospect_id (int): ID of the prospect
        email_body (str): Body of the email

    Returns:
        bool: Whether or not the email is an out of office reply
    """
    # Try to find the OOO keywords in the email body
    found_keyword = False
    lower_email_body = email_body.lower()
    for keyword in OOO_KEYWORDS:
        if keyword in lower_email_body:
            found_keyword = True
            break

    # If we found a keyword, then the email is an OOO reply and we should try to determine the return date
    if found_keyword:
        ooo_prompt = """I have determined that the following message is an "Out of Office" message. Please find the date that the individual will be "Out of Office" until.

Instructions:
- If the message is falsely classified, please return "FAIL."
- Try to return as exact of a date as possible. For example: "November 27th, 2025."
- If the exact date is not provided, find the most logical date. For example: "Until February" implies "February 1st" and "all of February" implies "March 1st"
- The current date is {current_date}.
- ONLY RETURN "FAIL" OR THE EXACT DATE

Message:
==============
{email_body}
""".format(
            current_date=datetime.now().strftime("%B %d, %Y"),
            email_body=email_body,
        )
        completion = wrapped_chat_gpt_completion(
            messages=[{"role": "user", "content": ooo_prompt}],
            max_tokens=10,
            temperature=0.0,
            top_p=1.0,
            n=1,
            frequency_penalty=0.0,
            model=OPENAI_CHAT_GPT_4_MODEL,
        )
        if completion == "FAIL":
            return False

        # Convert the date string to a datetime object
        ooo_until = convert_string_to_datetime_or_none(content=completion)
        if not ooo_until:
            return False

        # If we found a date, then we should update the prospect's status
        prospect: Prospect = Prospect.query.get(prospect_id)
        if not prospect:
            return False
        prospect_email: ProspectEmail = ProspectEmail.query.get(
            prospect.approved_prospect_email_id
        )
        if not prospect_email:
            return False
        update_prospect_status_email(
            prospect_id=prospect_id,
            new_status=ProspectEmailOutreachStatus.ACTIVE_CONVO_OOO,
        )

        # Mark the prospect as snoozed
        prospect_email.hidden_until = ooo_until
        db.session.commit()

        # Send a Slack message to the SDR
        # client: Client = Client.query.get(prospect.client_id)
        client_sdr: ClientSDR = ClientSDR.query.get(prospect.client_sdr_id)
        # webhook_urls = [URL_MAP["eng-sandbox"]]
        # if client.pipeline_notifications_webhook_url:
        #     webhook_urls.append(client.pipeline_notifications_webhook_url)

        clean_email_body = re.sub(r"\n+", "\n>", email_body)
        clean_email_body = "\n>" + clean_email_body
        success = create_and_send_slack_notification_class_message(
            notification_type=SlackNotificationType.PROSPECT_SNOOZED,
            arguments={
                "client_sdr_id": client_sdr.id,
                "prospect_id": prospect_id,
                "prospect_message": clean_email_body,
                "ai_response": "_No response. Prospect is out of office._",
                "hidden_until": ooo_until.strftime("%B %d, %Y"),
                "outbound_channel": "Email",
            },
        )

        # send_slack_message(
        #     message="SellScale AI just snoozed a prospect to "
        #     + datetime.strftime(ooo_until, "%B %d, %Y")
        #     + "!",
        #     webhook_urls=webhook_urls,
        #     blocks=[
        #         {
        #             "type": "header",
        #             "text": {
        #                 "type": "plain_text",
        #                 "text": "⏰ SellScale AI just snoozed "
        #                 + prospect.full_name
        #                 + " to "
        #                 + datetime.strftime(ooo_until, "%B %d, %Y")
        #                 + "!",
        #                 "emoji": True,
        #             },
        #         },
        #         {
        #             "type": "section",
        #             "text": {
        #                 "type": "mrkdwn",
        #                 "text": (
        #                     "*Last Message from Prospect:*\n>{prospect_message}\n\n*SDR* {sdr_name}"
        #                 ).format(
        #                     prospect_message=email_body,
        #                     sdr_name=client_sdr.name,
        #                 ),
        #             },
        #         },
        #         {
        #             "type": "section",
        #             "text": {
        #                 "type": "mrkdwn",
        #                 "text": "Message will re-appear in SellScale inbox on "
        #                 + datetime.strftime(ooo_until, "%B %d, %Y")
        #                 + ".",
        #             },
        #             "accessory": {
        #                 "type": "button",
        #                 "text": {
        #                     "type": "plain_text",
        #                     "text": "View Convo in Sight",
        #                     "emoji": True,
        #                 },
        #                 "value": "https://app.sellscale.com/authenticate?stytch_token_type=direct&token={auth_token}&redirect=prospects/{prospect_id}".format(
        #                     auth_token=client_sdr.auth_token, prospect_id=prospect_id
        #                 )
        #                 + str(prospect_id),
        #                 "url": "https://app.sellscale.com/authenticate?stytch_token_type=direct&token={auth_token}&redirect=prospects/{prospect_id}".format(
        #                     auth_token=client_sdr.auth_token, prospect_id=prospect_id
        #                 ),
        #                 "action_id": "button-action",
        #             },
        #         },
        #     ],
        # )

        return True

    return False
