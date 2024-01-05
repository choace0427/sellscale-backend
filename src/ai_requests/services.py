from datetime import datetime, timedelta
from src.ai_requests.models import AIRequest, AIRequestStatus
from app import db
from src.ml.openai_wrappers import wrapped_chat_gpt_completion
from src.utils.slack import send_slack_message, URL_MAP  # Import the Slack utility
from src.client.models import Client, ClientSDR


def create_ai_requests(client_sdr_id, description):
    try:
        # Generate title using GPT-3.5
        title = generate_title_with_gpt(description)

        # Create the new backend object in the AIRequest table
        new_request = AIRequest(
            client_sdr_id=client_sdr_id,
            title=title,
            description=description,
            percent_complete=0,
            creation_date=datetime.utcnow(),
            due_date=datetime.utcnow() + timedelta(days=1),
            status=AIRequestStatus.QUEUED,
            message="",
        )

        db.session.add(new_request)
        db.session.commit()

        # Send Slack notification for the new request
        send_slack_notification_for_new_request(client_sdr_id, new_request.id)

        return new_request
    except Exception as e:
        print(f"Error creating AI request: {e}")
        db.session.rollback()
        return None


def update_ai_requests(request_id: int, status: AIRequestStatus, hours_worked: int):
    try:
        # Fetch the AI request object
        ai_request: AIRequest = AIRequest.query.get(request_id)
        if not ai_request:
            print(f"AI Request with ID {request_id} not found")
            return None

        # Update the AI request object
        ai_request.status = status

        db.session.commit()

        # Send slack notification
        if status == AIRequestStatus.COMPLETED:
            sdr: ClientSDR = ClientSDR.query.get(ai_request.client_sdr_id)
            client: Client = Client.query.get(sdr.client_id)
            dashboard_url = (
                "https://app.sellscale.com/authenticate?stytch_token_type=direct&token="
                + sdr.auth_token
                + "&redirect=ai-request"
            )

            send_slack_message(
                message=f"New task completed!",
                blocks=[
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": f"New task completed!",
                            "emoji": True,
                        },
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"SellScale just completed a task, saving you `{hours_worked*60}` minutes.\n",
                        },
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*Task Name:* {ai_request.title}\n",
                        },
                    },
                    {
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": " "},
                        "accessory": {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "View in Dashboard →",
                                "emoji": True,
                            },
                            "url": dashboard_url,
                            "action_id": "button-action",
                        },
                    },
                    {"type": "divider"},
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*Contact:* {sdr.name} | *Date Requested:* {ai_request.creation_date} | *Date Completed:* {datetime.utcnow()}\n",
                        },
                    },
                ],
                webhook_urls=[client.pipeline_notifications_webhook_url]
                if client.pipeline_notifications_webhook_url
                else [],
            )

        return ai_request

    except Exception as e:
        print(f"Error creating AI request: {e}")
        db.session.rollback()
        return None


def send_slack_notification_for_new_request(client_sdr_id, request_id):
    """
    Send a Slack notification for a new AI request.
    """
    # Fetch client details
    request: AIRequest = AIRequest.query.get(request_id)
    client_sdr = ClientSDR.query.get(client_sdr_id)
    if not client_sdr:
        print(f"Client SDR with ID {client_sdr_id} not found")
        return

    client_name = client_sdr.name
    client_company = client_sdr.client.company

    # Formatting and send the Slack message
    message = (
        f"New AI Request from @{client_name} ({client_company})\n"
        f"```\n"
        f"Title: {request.title}\n\n"
        f"Description:\n{request.description}\n"
        f"```"
    )
    send_slack_message(message=message, webhook_urls=[URL_MAP["eng-sandbox"]])

    # Send to CSM client requests
    send_slack_message(
        message=f"New Client AI Request",
        blocks=[
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"New Client AI Request",
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Client:* {client_name}, {client_company}",
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Title:* {request.title}\n",
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Description:* {request.description}\n",
                },
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Request Date:* {request.creation_date}\n",
                },
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": " "},
                "accessory": {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "View in Retool →",
                        "emoji": True,
                    },
                    "url": "https://sellscale.retool.com/embedded/public/4534ace8-1254-4198-b230-c92adc6bb761",
                    "action_id": "button-action",
                },
            },
        ],
        webhook_urls=URL_MAP["csm-client-requests"],
    )


def generate_title_with_gpt(description):
    """
    Generates a title for the AI request using GPT-3.5-turbo.
    """
    instruction = (
        "This is a request from a user in a project management tool specializing in AI related sales campaigns for the startup SellScale."
        "Create a concise, informative title of 6 words or less that summarizes the main objective or action of the inputted request."
        "Do not add any additional characters like periods or quotations, just return alphanumeric text."
        "The most important requirement is to ensure the title does not go over 6 words, so make most titles around the range of 3-5 words"
    )
    prompt = f"{instruction}\n\nRequest Description:\n{description}"

    # Format the messages for GPT-3.5-turbo
    messages = [{"role": "user", "content": prompt}]

    # Call the wrapped GPT-3.5-turbo completion function and removing quotations, periods, and extra spaces
    response = (
        wrapped_chat_gpt_completion(messages=messages, max_tokens=60)
        .replace('"', "")
        .replace(".", "")
        .strip()
    )
    return response
