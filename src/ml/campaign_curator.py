from typing import Optional
from model_import import ClientSDR, Client
from src.ml.openai_wrappers import wrapped_chat_gpt_completion
from src.onboarding.onboarding_generation import get_summary_from_website
from src.research.website.serp_helpers import search_google_news_raw
from datetime import datetime
from app import db
import json

from src.sockets.services import send_socket_message

CAMPAIGN_CURATOR_PROMPT = """
You are Selina, SellScale's AI assistant for ideating on new campaigns to create. I am going to give you context about a business including:
- basic company information: name, tagline, industry, description
- basic user information: information about the sales person we are helping
- website information: products, key points, new offers, etc
- recent company news: 3-4 recent pieces of news about the company
- top colleague campaigns: Campaigns that the colleagues of our user has run that have worked well for replies + demos
- campaigns I already ran: a list of campaigns that I've already run in the past with basic performance indicators.

Using this information, respond with 1 new campaign idea that we can run for our User.

---------

## BASIC COMPANY INFORMATION
- Company Name: {company_name}
- Company Tagline: {tagline}
- Company Description: {description}

## BASIC USER INFORMATION
- Name: {user_name}
- Role: {user_role}

## WEBSITE INFORMATION
{website_info}

## RECENT COMPANY NEWS
{recent_news}

## TOP COLLEAGUE CAMPAIGNS
{top_colleague_campaigns}

## CAMPAIGNS I'VE ALREADY RAN
{past_campaigns}

----------


Leverage the information provided above to come up with compelling strategy for me.

Generate 1 new campaign idea for me. Respond with a JSON object. in the object, the keys should be:
- emoji (str): come up with one simple emoji to describe this campaign
- campaign_title (str): a 5-7 word title describing the campaign. (ex. "Healthcare Executives in Louisiana - Coffee Chat"). Generally structure is "[2-3 words about customer profile] ([other details]) - [offer / strategy]"
- icp_target (str): be hyper descriptive about the ICP. Include company location, titles, seniority, types of companies (or exact company names), company size, and other relevant details in 2-3 sentences.
- strategy (str): in 2-3 sentences, describe the strategy. What is the offer / angle / approach we should use to get a response/demo. Be creative and interesting here.
- assets (list[str]): A list of 'tags' highlighting where the strategy originated from in the data provided. Something like "Website Info: [detail]", "Past Campaign: [Campaign Title]", "Top Colleague Campaign: [Campaign Title]", "Recent News: [News Title]", "User Info: [User Role]". This will help us track the performance of the campaign.
- reason (str): in 1-2 sentences, describe why you think this campaign will work. What is the unique insight or angle that you are leveraging?

Additional Instructions:
{additional_instructions}
- Be as creative as possible. Think outside the box.

Output:"""

def campaign_curator_prompt(company_name, tagline, description, user_name, user_role, website_info, recent_news, top_colleague_campaigns, past_campaigns, additional_instructions):
    return CAMPAIGN_CURATOR_PROMPT.format(
        company_name=company_name,
        tagline=tagline,
        description=description,
        user_name=user_name,
        user_role=user_role,
        website_info=website_info,
        recent_news=recent_news,
        top_colleague_campaigns=top_colleague_campaigns,
        past_campaigns=past_campaigns,
        additional_instructions=additional_instructions
    )

def get_website_info(domain):
    website_summary = get_summary_from_website(domain)
    return website_summary

def get_recent_news(query):
    news = search_google_news_raw(query, 'nws')

    results = ''
    MAX_COUNT = 5
    for entry in news['news_results']:
        title = entry['title']
        date = entry['date']
        source = entry['source']
        snippet = entry['snippet']

        results += f'- {title} ({date}) - {source}: {snippet}\n'

        MAX_COUNT -= 1
        if MAX_COUNT == 0:
            break

    todays_date = datetime.today().strftime('%Y-%m-%d')
    results += "\nNOTE: Today's date is " + todays_date + ".\n"

    return results

def get_top_colleague_campaigns(client_sdr_id):
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client_id = client_sdr.client_id
    query = """
    with d as (
        with temp as (
            select 
                client_archetype.archetype,
                client_sdr.name client_sdr_name,
                cast(count(distinct prospect.id) filter (where prospect_status_records.to_status = 'SENT_OUTREACH' or prospect_email_status_records.to_status = 'SENT_OUTREACH') as float) "num_sent",
                cast(count(distinct prospect.id) filter (where prospect_status_records.to_status = 'ACCEPTED' or prospect_email_status_records.to_status = 'EMAIL_OPENED') as float) "num_opens",
                cast(count(distinct prospect.id) filter (where prospect_status_records.to_status = 'ACTIVE_CONVO' or prospect_email_status_records.to_status = 'ACTIVE_CONVO') as float) "num_replies",
                cast(count(distinct prospect.id) filter (where prospect_status_records.to_status = 'DEMO_SET' or prospect_email_status_records.to_status = 'DEMO_SET') as float) "num_demos"
            from client
                join client_sdr on client_sdr.client_id = client.id
                join client_archetype on client_archetype.client_sdr_id = client_sdr.id
                join prospect on prospect.archetype_id = client_archetype.id
                left join prospect_status_records on prospect_status_records.prospect_id = prospect.id
                left join prospect_email on prospect_email.prospect_id = prospect.id
                left join prospect_email_status_records on prospect_email_status_records.prospect_email_id = prospect_email.id
            where client.id = {client_id} and client_sdr.id != {client_sdr_id}
                and client_archetype.is_unassigned_contact_archetype is False
            group by 1,2
        )
        select 
            archetype,
            client_sdr_name,
            num_sent,
            round(100 * num_opens / (0.0001 + num_sent)) open_rate,
            round(100 * num_replies / (0.0001 + num_opens)) reply_rate,
            num_demos
        from temp
    )
    select 
        concat(
            client_sdr_name,
            ' ran a campaign called "',
            archetype,
            '": Sent: ',
            num_sent, 
            ' outreaches, Open% :',
            open_rate,
            '%, Reply%: ',
            reply_rate,
            '%, Demos: ',
            num_demos,
            ' demos'
        )
    from d
    where num_sent > 10
    order by num_demos desc, reply_rate desc, open_rate desc
    limit 10;
    """.format(client_id=client_id, client_sdr_id=client_sdr_id)

    results = db.session.execute(query)
    
    past_campaigns = ''
    for row in results:
        past_campaigns += f'- {row[0]}\n'

    return past_campaigns

    

def get_past_campaigns(client_sdr_id):
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client_id = client_sdr.client_id
    query = """
    with d as (
        with temp as (
            select 
                client_archetype.archetype,
                client_sdr.name client_sdr_name,
                cast(count(distinct prospect.id) filter (where prospect_status_records.to_status = 'SENT_OUTREACH' or prospect_email_status_records.to_status = 'SENT_OUTREACH') as float) "num_sent",
                cast(count(distinct prospect.id) filter (where prospect_status_records.to_status = 'ACCEPTED' or prospect_email_status_records.to_status = 'EMAIL_OPENED') as float) "num_opens",
                cast(count(distinct prospect.id) filter (where prospect_status_records.to_status = 'ACTIVE_CONVO' or prospect_email_status_records.to_status = 'ACTIVE_CONVO') as float) "num_replies",
                cast(count(distinct prospect.id) filter (where prospect_status_records.to_status = 'DEMO_SET' or prospect_email_status_records.to_status = 'DEMO_SET') as float) "num_demos"
            from client
                join client_sdr on client_sdr.client_id = client.id
                join client_archetype on client_archetype.client_sdr_id = client_sdr.id
                join prospect on prospect.archetype_id = client_archetype.id
                left join prospect_status_records on prospect_status_records.prospect_id = prospect.id
                left join prospect_email on prospect_email.prospect_id = prospect.id
                left join prospect_email_status_records on prospect_email_status_records.prospect_email_id = prospect_email.id
            where client.id = {client_id} and client_sdr.id = {client_sdr_id}
                and client_archetype.is_unassigned_contact_archetype is False
            group by 1,2
        )
        select 
            archetype,
            client_sdr_name,
            num_sent,
            round(100 * num_opens / (0.0001 + num_sent)) open_rate,
            round(100 * num_replies / (0.0001 + num_opens)) reply_rate,
            num_demos
        from temp
    )
    select 
        concat(
            client_sdr_name,
            ' ran a campaign called "',
            archetype,
            '": Sent: ',
            num_sent, 
            ' outreaches, Open% :',
            open_rate,
            '%, Reply%: ',
            reply_rate,
            '%, Demos: ',
            num_demos,
            ' demos'
        )
    from d
    where num_sent > 10
    order by num_demos desc, reply_rate desc, open_rate desc
    limit 10;
    """.format(client_id=client_id, client_sdr_id=client_sdr_id)

    results = db.session.execute(query)
    
    past_campaigns = ''
    for row in results:
        past_campaigns += f'- {row[0]}\n'

    return past_campaigns

def curate_campaigns(
    client_sdr_id: int,
    additional_instructions: str,
    room_id: Optional[str] = None
):
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client_id = client_sdr.client_id
    client: Client = Client.query.get(client_id)

    company_name = client.company
    tagline = client.tagline
    description = client.description

    user_name = client_sdr.name
    user_role = client_sdr.title

    try:
        website_info = get_website_info(client.domain)
    except Exception as e:
        website_info = ""
    recent_news = get_recent_news('"' + client.domain.replace('https://', '').replace('http://', '') + '"')
    top_colleague_campaigns = get_top_colleague_campaigns(client_sdr_id)
    past_campaigns = get_past_campaigns(client_sdr_id)

    prompt = campaign_curator_prompt(
        company_name=company_name,
        tagline=tagline,
        description=description,
        user_name=user_name,
        user_role=user_role,
        website_info=website_info,
        recent_news=recent_news,
        top_colleague_campaigns=top_colleague_campaigns,
        past_campaigns=past_campaigns,
        additional_instructions=additional_instructions
    )

    result = []

    for i in range(0,5):
        print(f"Running campaign curator for {client_sdr_id} iteration {i}")
        try: 
            response = wrapped_chat_gpt_completion(
                max_tokens=3000,
                messages=[
                    {
                        'role': 'system',
                        'content': prompt
                    }
                ],
                model='gpt-4o'
            )
            response = response.replace('```', '').replace('json', '').strip()
            response = json.loads(response)
            if room_id:
                response['room_id'] = room_id
                print(f"Sending message to room {room_id}")
                send_socket_message('stream-answers', response, room_id)
            result.append(response)

        except Exception as e:
            print(f"Error in campaign curator: {e}")

    if (room_id):
        send_socket_message('stream-answers', {"message":"done", "room_id": room_id}, room_id)

    return {
        'response': result,
        'data': {
            'company_name': company_name,
            'tagline': tagline,
            'description': description,
            'user_name': user_name,
            'user_role': user_role,
            'website_info': website_info,
            'recent_news': recent_news,
            'top_colleague_campaigns': top_colleague_campaigns,
            'past_campaigns': past_campaigns,
            'additional_instructions': additional_instructions
        },
        'raw_prompt': prompt
    }