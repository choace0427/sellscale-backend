from sqlalchemy import desc
from app import db
import requests
from src.analytics.models import ChatBotDataRepository
from src.client.models import Client, ClientSDR
from src.ml.openai_wrappers import wrapped_chat_gpt_completion

API_URL = "https://sellscale-api-prod.onrender.com/"

DATASET_DESCRIPTOR = {
    "usage_analytics_data": "This is data about # of prospects created, enriched, outbound sent, AI replies, prospects snoozed, and prospects removed. You also have timelines for each of these pieces.",
    "tam_graph_data": "This is data about the prospects ingested by SellScale on behalf of this SDR's company. You can see top titles in ther TAM, top industries, and top companies.",
    "rejection_report_data": "Whenever a prospect is marked as 'Not Interested' or 'Not Qualified', it is recorded here. You can see the top disqualification reasons as well.",
    "demo_feedback_data": "This is data about the feedback received from the prospects after a demo is given. You can see the top feedback reasons.",
    "message_analytics_data": "This is data about the messages sent by the SDRs. You can see the top message types, top message templates, and top message subjects.",
}


def backfill_chatbot_data(client_sdr_id: int):
    """Backfill chat bot data for a given client_sdr_id."""

    # Get the client_sdr
    client_sdr = ClientSDR.query.get(client_sdr_id)
    auth_token = client_sdr.auth_token

    # Get the chat bot data repository
    chat_bot_data_repository = ChatBotDataRepository.query.filter_by(
        client_sdr_id=client_sdr_id
    ).first()
    if chat_bot_data_repository is None:
        chat_bot_data_repository = ChatBotDataRepository(client_sdr_id=client_sdr_id)

    # Get the chat bot data
    try:
        usage_analytics_data_endpoint = "{API_URL}usage/".format(API_URL=API_URL)
        usage_analytics_data = requests.get(
            usage_analytics_data_endpoint,
            headers={"Authorization": f"Bearer {auth_token}"},
        ).json()
    except Exception as e:
        print("Failed to get usage analytics data: ", e)
        usage_analytics_data = {}

    try:
        tam_graph_data_endpoint = "{API_URL}client/tam_graph_data".format(
            API_URL=API_URL
        )
        tam_graph_data = requests.get(
            tam_graph_data_endpoint,
            headers={"Authorization": f"Bearer {auth_token}"},
        ).json()
    except Exception as e:
        print("Failed to get TAM graph data: ", e)
        tam_graph_data = {}

    # https://sellscale-api-prod.onrender.com/analytics/rejection_analysis?status=NOT_INTERESTED
    # https://sellscale-api-prod.onrender.com/analytics/rejection_analysis?status=NOT_QUALIFIED
    # https://sellscale-api-prod.onrender.com/analytics/rejection_report

    # combine the three rejection calls into one payload and store rejection_report_data
    try:
        rejection_report_data_endpoint = "{API_URL}analytics/rejection_report".format(
            API_URL=API_URL
        )
        rejection_report_data = requests.get(
            rejection_report_data_endpoint,
            headers={"Authorization": f"Bearer {auth_token}"},
        ).json()

        rejection_report_data["NOT_INTERESTED"] = requests.get(
            "{API_URL}analytics/rejection_analysis?status=NOT_INTERESTED".format(
                API_URL=API_URL
            ),
            headers={"Authorization": f"Bearer {auth_token}"},
        ).json()

        rejection_report_data["NOT_QUALIFIED"] = requests.get(
            "{API_URL}analytics/rejection_analysis?status=NOT_QUALIFIED".format(
                API_URL=API_URL
            ),
            headers={"Authorization": f"Bearer {auth_token}"},
        ).json()
    except Exception as e:
        print("Failed to get rejection report data: ", e)
        rejection_report_data = {}

    try:
        demo_feedback_data_endpoint = "{API_URL}client/demo_feedback".format(
            API_URL=API_URL
        )
        demo_feedback_data = requests.get(
            demo_feedback_data_endpoint,
            headers={"Authorization": f"Bearer {auth_token}"},
        ).json()
    except Exception as e:
        print("Failed to get demo feedback data: ", e)
        demo_feedback_data = {}

    try:
        message_analytics_data_endpoint = "{API_URL}client/msg_analytics_report".format(
            API_URL=API_URL
        )
        message_analytics_data = requests.get(
            message_analytics_data_endpoint,
            headers={"Authorization": f"Bearer {auth_token}"},
        ).json()
    except Exception as e:
        print("Failed to get message analytics data: ", e)
        message_analytics_data = {}

    # Update the chat bot data repository
    chat_bot_data_repository.usage_analytics_data = usage_analytics_data
    chat_bot_data_repository.tam_graph_data = tam_graph_data
    chat_bot_data_repository.rejection_report_data = rejection_report_data
    chat_bot_data_repository.demo_feedback_data = demo_feedback_data
    chat_bot_data_repository.message_analytics_data = message_analytics_data

    # Commit the changes
    db.session.add(chat_bot_data_repository)
    db.session.commit()


def get_data_source_type(query: str):
    context = """
    You are SellScale AI chatbot. Your goal is to answer questions the SDRs have about their sales data analytics.

    Here are the data sources you have access to:
    1. Usage Analytics - This is data about # of prospects created, enriched, outbound sent, AI replies, prospects snoozed, and prospects removed. You also have timelines for each of these pieces.
    2. TAM (Total Addressable Market) - This is data about the prospects ingested by SellScale on behalf of this SDR's company. You can see top titles in ther TAM, top industries, and top companies.
    3. Rejection Analysis - Whenever a prospect is marked as 'Not Interested' or 'Not Qualified', it is recorded here. You can see the top disqualification reasons as well.
    4. Demo Feedback - This is data about the feedback received from the prospects after a demo is given. You can see the top feedback reasons.
    5. Message Analytics - This is data about the messages sent by the SDRs. You can see the top message types, top message templates, and top message subjects.

    Your first job is to tell me which data source you want acccess to based on the query.

    Respond with the following:
    1. Usage Analytics -> 'usage_analytics_data'
    2. TAM -> 'tam_graph_data'
    3. Rejection Analysis -> 'rejection_report_data'
    4. Demo Feedback -> 'demo_feedback_data'
    5. Message Analytics -> 'message_analytics_data'

    Important, ONLY respond with the data source you want access to. Do not include any other information in your response. Do not include any punctuation or capitalization or quotes in your response.

    Query: {query}

    Output:"""

    completion = wrapped_chat_gpt_completion(
        messages=[{"role": "system", "content": context.format(query=query)}],
        max_tokens=100,
    )

    return completion


def process_data_and_answer(
    data: dict, client_sdr_id: int, query: str, description: str
):
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client: Client = Client.query.get(client_sdr.client_id)

    system_prompt = """
    You are SellScale AI chatbot. Your goal is to answer questions the SDRs have about their sales data analytics.
    Here is who you are talking to:
    Name: {client_sdr.name}
    Title: {client_sdr.title}

    This is the company that the SDR works for:
    Name: {client.company}
    Tagline: {client.tagline}
    Description: {client.description}

    Your job is to answer the question the SDR has about their sales data analytics based on the data, data description, and context about the business.

    Rules:
    1. Answer the question the SDR has about their sales data analytics succinctly and clearly.
    2. Personalize the response with their name and details about their company.
    3. Be polite and professional.
    4. IMPORTANT: Be data oriented. If there are graphs or charts, be sure to mention those details in your response.
    5. Use line breaks and bullet points to make the response easy to read.
    6. IMPORTANT: Do not mention anything about 'data provided'. Just answer the question directly.
    7. Do not have any 'salutations' or 'endings' in your response. You are a chatbot! Simply respond to the question correctly."""

    prompt = """
    Here is the question I want to answer: {query}

    Data
    {data}

    Description about the data source:
    {description}

    Output:"""

    completion = wrapped_chat_gpt_completion(
        messages=[
            {
                "role": "system",
                "content": system_prompt.format(
                    client_sdr=client_sdr,
                    client=client,
                ),
            },
            {
                "role": "user",
                "content": prompt.format(
                    query=query,
                    data=data,
                    description=description,
                ),
            },
        ],
        max_tokens=400,
        model="gpt-4",
    )

    return completion


def answer_question(client_sdr_id: int, query: str):
    chatbot_data: ChatBotDataRepository = ChatBotDataRepository.query.filter_by(
        client_sdr_id=client_sdr_id
    ).first()
    if chatbot_data is None:
        return "Sorry! We haven't processed your data (yet...). Please try again later."

    source_type = get_data_source_type(query)
    description = DATASET_DESCRIPTOR.get(source_type, "")
    # print("source_type: ", source_type)

    data = getattr(chatbot_data, source_type)
    data = str(data)[:4000]
    # print("data: ", data)

    answer = process_data_and_answer(data, client_sdr_id, query, description)

    return answer
