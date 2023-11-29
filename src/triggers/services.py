import datetime
import json
import os
import time
import requests
from model_import import (
    ClientSDR,
)

from src.utils.slack import URL_MAP, send_slack_message
from src.triggers.models import ActionType, Block, FilterBlock, FilterCriteria, MetaDataRecord, PipelineCompany, PipelineData, ActionBlock, PipelineProspect, SourceBlock, SourceType, Trigger, convertBlocksToDict, convertDictToBlocks
from app import db
from src.ml.openai_wrappers import (wrapped_chat_gpt_completion,)
from src.research.website.serp_helpers import search_google_news_raw
from src.research.linkedin.services import research_personal_profile_details
from src.utils.abstract.attr_utils import deep_get

def createTrigger(client_sdr_id: int, client_archetype_id: int):
  
    source_block_1 = SourceBlock(
        source=SourceType.GOOGLE_COMPANY_NEWS,
        data={
            'company_query': 'data leak',
        },
    )
    action_block_1 = ActionBlock(
        action=ActionType.SEND_SLACK_MESSAGE,
        data={
            'slack_message': "Found [[METADATA.SOURCE_COMPANIES_FOUND]] companies for [[METADATA.SOURCE_COMPANY_TYPE]] search with query: [[METADATA.SOURCE_COMPANY_QUERY]]",
            'slack_webhook_urls': [URL_MAP["eng-sandbox"]],
        },
    )
    filter_block_1 = FilterBlock(
        criteria=FilterCriteria(
            company_query="Does this company relate to IT?",
        ),
    )
    source_block_2 = SourceBlock(
        source=SourceType.EXTRACT_PROSPECTS_FROM_COMPANIES,
        data={
            'prospect_titles': ['CEO', 'CTO', 'CFO', 'COO', 'VP', 'Director', 'Manager'],
        },
    )
    action_block_2 = ActionBlock(
        action=ActionType.SEND_SLACK_MESSAGE,
        data={
            'slack_message': "Prospects found after filter: [[METADATA.CURRENT_PROSPECTS_FOUND]].",
            'slack_webhook_urls': [URL_MAP["eng-sandbox"]],
        },
    )
    action_block_3 = ActionBlock(
        action=ActionType.UPLOAD_PROSPECTS,
        data={},
    )
    action_block_4 = ActionBlock(
        action=ActionType.SEND_SLACK_MESSAGE,
        data={
            'slack_message': "Uploaded [[METADATA.PROSPECTS_UPLOADED]] prospects!",
            'slack_webhook_urls': [URL_MAP["eng-sandbox"]],
        },
    )
  
    trigger = Trigger(
        name='New Trigger',
        description='',
        client_sdr_id=client_sdr_id,
        client_archetype_id=client_archetype_id,
        active=True,
        blocks=convertBlocksToDict([
            source_block_1,
            action_block_1,
            filter_block_1,
            source_block_2,
            action_block_2,
            action_block_3,
            action_block_4,
        ]),
    )
    db.session.add(trigger)
    db.session.commit()
    
    return trigger.id
  
  
def runTrigger(trigger_id: int):
    trigger: Trigger = Trigger.query.get(trigger_id)
    
    blocks = convertDictToBlocks(trigger.blocks or [])
    
    pipeline_data = PipelineData([], [], {})
    for block in blocks:
        pipeline_data = runBlock(trigger.client_sdr_id, trigger.client_archetype_id, block, pipeline_data)
    
    # Update blacklist, by removing old entries and adding new ones
    blacklist = trigger.keyword_blacklist or {}
    current_date = datetime.datetime.utcnow()
    two_weeks_ago = datetime.datetime.utcnow() - datetime.timedelta(days=14)

    # Use a dictionary comprehension to filter out old entries
    blacklist = {
        key: value
        for key, value in blacklist.items()
        if datetime.datetime.utcfromtimestamp(value['date']) > two_weeks_ago
    }
    print(blacklist)
    
    for company in pipeline_data.companies:
        if not blacklist[company.company_name]:
            blacklist[company.company_name] = { "word": company.company_name, "date": current_date }
    
    for prospect in pipeline_data.prospects:
        name = f"{prospect.first_name} {prospect.last_name}"
        if not blacklist[name]:
            blacklist[name] = { "word": name, "date": current_date }
        
    print(blacklist)
        
    return True, len(blocks), pipeline_data.to_dict()


def runBlock(client_sdr_id: int, client_archetype_id: int, block: Block, pipeline_data: PipelineData) -> PipelineData:
    if isinstance(block, SourceBlock):
        return runSourceBlock(block, pipeline_data)
    elif isinstance(block, FilterBlock):
        return runFilterBlock(block, pipeline_data)
    elif isinstance(block, ActionBlock):
        return runActionBlock(client_sdr_id, client_archetype_id, block, pipeline_data)
    else:
        raise Exception("Unknown block type: {}".format(type(block)))
    

def runSourceBlock(block: SourceBlock, pipeline_data: PipelineData) -> PipelineData:
    prospects = pipeline_data.prospects or []
    companies = pipeline_data.companies or []
    meta_data = pipeline_data.meta_data or {}
    
    if block.source == SourceType.GOOGLE_COMPANY_NEWS:
        query = block.data.get("company_query", "")
      
        companies = source_companies_from_google_news(query)
        
        # Update meta data accordingly
        meta_data[MetaDataRecord.SOURCE_COMPANY_QUERY.name] = query
        meta_data[MetaDataRecord.SOURCE_COMPANY_TYPE.name] = block.source.name
        meta_data[MetaDataRecord.SOURCE_COMPANIES_FOUND.name] = len(companies)
        meta_data[MetaDataRecord.CURRENT_COMPANIES_FOUND.name] = len(companies)
        
    elif block.source == SourceType.EXTRACT_PROSPECTS_FROM_COMPANIES:
        titles = block.data.get("prospect_titles", [])
      
        prospects = source_prospects_from_companies(companies, titles)
        
        # Update meta data accordingly
        meta_data[MetaDataRecord.SOURCE_PROSPECTS_FOUND.name] = len(prospects)
        meta_data[MetaDataRecord.CURRENT_PROSPECTS_FOUND.name] = len(prospects)
    
    
    return PipelineData(
      prospects=prospects,
      companies=companies,
      meta_data=meta_data,
    )
        
        
def runFilterBlock(block: FilterBlock, pipeline_data: PipelineData) -> PipelineData:
    prospects = pipeline_data.prospects or []
    companies = pipeline_data.companies or []
    meta_data = pipeline_data.meta_data or {}
    
    companies = filter_companies(companies, block.criteria, meta_data)
    prospects = filter_prospects(prospects, block.criteria, meta_data)
    
    meta_data[MetaDataRecord.CURRENT_COMPANIES_FOUND.name] = len(companies)
    meta_data[MetaDataRecord.CURRENT_PROSPECTS_FOUND.name] = len(prospects)
    
    return PipelineData(
      prospects=prospects,
      companies=companies,
      meta_data=meta_data,
    )


def runActionBlock(client_sdr_id: int, client_archetype_id: int, block: ActionBlock, pipeline_data: PipelineData) -> PipelineData:
    prospects = pipeline_data.prospects or []
    companies = pipeline_data.companies or []
    meta_data = pipeline_data.meta_data or {}
    
    if block.action == ActionType.SEND_SLACK_MESSAGE:
      
        message = block.data.get("slack_message", "")
        webhook_urls = block.data.get("slack_webhook_urls", [])
        success = action_send_slack_message(message, webhook_urls, meta_data)
        
    elif block.action == ActionType.UPLOAD_PROSPECTS:
      
        amount = action_upload_prospects(prospects, client_sdr_id, client_archetype_id)
        
        meta_data[MetaDataRecord.PROSPECTS_UPLOADED.name] = amount
    
    return PipelineData(
      prospects=prospects,
      companies=companies,
      meta_data=meta_data,
    )


####################################################################################################
#                                        Utility Functions                                         #
####################################################################################################


def action_send_slack_message(message: str, webhook_urls: list[str], meta_data: dict):  
    return send_slack_message(
        message=replace_metadata(message, meta_data),
        webhook_urls=webhook_urls,
    )
    

def action_upload_prospects(prospects: list[PipelineProspect], client_sdr_id: int, client_archetype_id: int):
    if len(prospects) == 0: return 0
    
    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    
    payload = []
    for prospect in prospects:
        payload.append(
            prospect.to_dict()
        )

    api_url = os.environ.get("SELLSCALE_API_URL")
    url = "{api_url}/prospect/add_prospect_from_csv_payload".format(api_url=api_url)
    payload = json.dumps(
        {
            "archetype_id": client_archetype_id,
            "csv_payload": payload,
            "allow_duplicates": False,
        }
    )
    headers = {
        "accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": "Bearer {userToken}".format(userToken=sdr.auth_token),
    }
    response = requests.request("POST", url, headers=headers, data=payload)
    
    return len(prospects)


def replace_metadata(message: str, meta_data: dict):
    for key, value in meta_data.items():
        placeholder = f"[[METADATA.{key}]]"
        message = message.replace(placeholder, str(value))
    return message


def filter_companies(companies: list[PipelineCompany], filter_criteria: FilterCriteria, meta_data: dict):
    
    if filter_criteria.company_query:
        companies = qualify_companies(companies, replace_metadata(filter_criteria.company_query, meta_data))
    if filter_criteria.company_names:
        companies = qualify_company_names(companies, filter_criteria.company_names)
        
    return companies


def filter_prospects(prospects: list[PipelineProspect], filter_criteria: FilterCriteria, meta_data: dict):
    
    if filter_criteria.prospect_query:
        prospects = qualify_prospects(prospects, replace_metadata(filter_criteria.prospect_query, meta_data))
    if filter_criteria.company_names:
        prospects = qualify_prospect_company_names(prospects, filter_criteria.company_names)
    if filter_criteria.prospect_titles:
        prospects = qualify_prospect_titles(prospects, filter_criteria.prospect_titles)
    
    return prospects


def qualify_company_names(companies: list[PipelineCompany], names: list[str]):
    lowercase_names = [name.lower() for name in names]

    result_companies = []

    for row in companies:
        if row.company_name.lower() in lowercase_names:
            result_companies.append(row)
            
    return result_companies


def qualify_prospect_company_names(prospects: list[PipelineProspect], names: list[str]):
    lowercase_names = [name.lower() for name in names]

    result_prospects = []

    for row in prospects:
        if row.company.lower() in lowercase_names:
            result_prospects.append(row)
            
    return result_prospects


def qualify_prospect_titles(prospects: list[PipelineProspect], titles: list[str]):
  
    result_prospects = []

    for row in prospects:

        # Prepare the message for Chat GPT to check the role
        chat_message = [
            {
                "role": "user",
                "content": f"Does the role '{row.title}' match any of these roles: {titles}?\nOnly respond with 'true' or 'false'.\nResponse:",
            }
        ]

        # Get the role match response using Chat GPT
        role_match_response = wrapped_chat_gpt_completion(chat_message)

        # Determine if the role matches (True/False)
        correct_role = "true" in role_match_response.lower()
        if correct_role:
            result_prospects.append(row)

    return result_prospects


def source_prospects_from_companies(companies: list[PipelineCompany], titles: list[str]):
  
    profiles_data = extract_linkedin_profiles(
        companies, titles
    )
    return enrich_linkedin_profiles(profiles_data)


def extract_linkedin_profiles(companies: list[PipelineCompany], titles: list[str]):

    profiles_data = []

    # Loop through each company and title
    for company in companies:
        for title in titles:
            # Construct the Google search query
            query = f'site:linkedin.com/in/ "{company.company_name}" "- {title}"'

            # Perform the Google search
            search_results = search_google_news_raw(
                query
            )  # Use your search_google_news function
            organic_results = search_results.get("organic_results", [])

            # Process search results
            for profile in organic_results:
                # Extract relevant profile details
                profile_data = {
                    "img_url": company.img_url,  # Original data
                    "original_title": company.article_title,  # Original data
                    "snippet": company.article_snippet,  # Original data
                    "original_link": company.article_link,  # Original data
                    "date": company.article_date,  # Original data
                    "company_name": company.company_name,  # Original data
                    "linkedin_title": title,  # LinkedIn profile title
                    "profile_url": profile.get("link"),  # LinkedIn profile URL
                }
                profiles_data.append(profile_data)

    return profiles_data


def enrich_linkedin_profiles(profiles: list):
    MAX_NUM_PROFILES_TO_PROCESS = 100

    prospects: list[PipelineProspect] = []

    for row in profiles[0:MAX_NUM_PROFILES_TO_PROCESS]:
        # Call the iScraper API
        profile_url = row["profile_url"]
        profile_id = profile_url.split("/in/")[1]
        iscraper_response = research_personal_profile_details(
            profile_id
        )  # Assuming this function is already defined
        time.sleep(1)  # Wait for 1 second between API calls

        # Extract required fields from the iScraper response
        first_name = iscraper_response.get("first_name", "")
        last_name = iscraper_response.get("last_name", "")
        company = deep_get(
            iscraper_response,
            "position_groups.0.profile_positions.0.company",
            default="",
        )
        sub_title = iscraper_response.get("sub_title", "")
        summary = iscraper_response.get("summary", "")
        title = deep_get(
            iscraper_response, "position_groups.0.profile_positions.0.title", default=""
        )
        industry = iscraper_response.get("industry", "")
        profile_picture = iscraper_response.get("profile_picture", "")
        raw_json = json.dumps(iscraper_response)

        # Prepare the enriched row
        prospect = PipelineProspect(
            first_name=first_name,
            last_name=last_name,
            title=title,
            company=company,
            linkedin_url=profile_url,
            custom_data={},
        )

        prospects.append(prospect)

    return prospects


def source_companies_from_google_news(query: str) -> list[PipelineCompany]:
  
    # Fetch recent news articles related to the event
    news_results = search_google_news_raw(query, "nws")

    # Prepare data
    result_data = []

    for article in news_results.get("news_results", []):
        # Prepare the message for Chat GPT to extract the company name
        chat_message = [
            {
                "role": "user",
                "content": f"Which company does this news article pertain to? {article['title']} {article['snippet']}\nOnly respond with the company name. If company not found, return 'none' all lowercase.\nCompany name:",
            }
        ]

        # Extract company name using Chat GPT
        company_name = wrapped_chat_gpt_completion(chat_message)

        # If company name is not found, skip the article
        if "none" in company_name.lower():
            continue

        # Append the details to the CSV data list
        result_data.append(
            PipelineCompany(
                img_url=article.get("thumbnail"),
                article_title=article.get("title"),
                article_snippet=article.get("snippet"),
                article_link=article.get("link"),
                article_date=article.get("date"),
                company_name=company_name,
            )
        )

    return result_data
    

def qualify_companies(companies: list[PipelineCompany], qualifying_question: str):
  
    results = []
    for row in companies:
        # Prepare the message for Chat GPT
        chat_message = [
            {
                "role": "user",
                "content": f"{qualifying_question}\n Event: {row.article_title}. Company: {row.company_name}.\nOnly respond with 'true' or 'false'.\nResponse:",
            }
        ]

        # Get qualification response using Chat GPT
        qualification_response = wrapped_chat_gpt_completion(chat_message)

        # Determine qualification (True/False)
        qualified = "true" in qualification_response.lower()

        if qualified:
            results.append(row)

    return results
  
  
def qualify_prospects(prospects: list[PipelineProspect], qualifying_question: str):
  
    results = []
    for row in prospects:
        # Prepare the message for Chat GPT
        chat_message = [
            {
                "role": "user",
                "content": f"{qualifying_question}\n Prospect title: {row.title}. Company: {row.company}.\nOnly respond with 'true' or 'false'.\nResponse:",
            }
        ]

        # Get qualification response using Chat GPT
        qualification_response = wrapped_chat_gpt_completion(chat_message)

        # Determine qualification (True/False)
        qualified = "true" in qualification_response.lower()

        if qualified:
            results.append(row)

    return results
  