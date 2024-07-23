import datetime
import json
import os
import time
import requests
from src.prospecting.models import ProspectUploadSource
from src.sockets.services import send_socket_message
from model_import import (
    ClientSDR,
    Client,
)

from src.utils.slack import URL_MAP, send_slack_message
from src.triggers.models import (
    ActionType,
    Block,
    FilterBlock,
    FilterCriteria,
    MetaDataRecord,
    PipelineCompany,
    PipelineData,
    ActionBlock,
    PipelineProspect,
    SourceBlock,
    SourceType,
    Trigger,
    TriggerProspect,
    TriggerType,
    TriggerRun,
    convertBlocksToDict,
    convertDictToBlocks,
)
from app import db, celery
from src.ml.openai_wrappers import (
    wrapped_chat_gpt_completion,
)
from src.research.website.serp_helpers import search_google_news_raw
from src.research.linkedin.services import research_personal_profile_details
from src.utils.abstract.attr_utils import deep_get


def createTrigger(client_sdr_id: int, client_archetype_id: int) -> int:
    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client: Client = Client.query.get(sdr.client_id)
    webhook_urls = [client.pipeline_notifications_webhook_url]

    source_block_1 = SourceBlock(
        source=SourceType.GOOGLE_COMPANY_NEWS,
        data={
            "company_query": "data leak",
        },
    )
    action_block_1 = ActionBlock(
        action=ActionType.SEND_SLACK_MESSAGE,
        data={
            "slack_message": [
                {
                    "text": {
                        "text": "Found [[METADATA.SOURCE_COMPANIES_FOUND]] companies for [[METADATA.SOURCE_COMPANY_TYPE]] search with query: [[METADATA.SOURCE_COMPANY_QUERY]]",
                        "type": "mrkdwn",
                    },
                    "type": "section",
                }
            ],
            "slack_webhook_urls": webhook_urls,
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
            "prospect_titles": [
                "CEO",
                "CTO",
                "CFO",
                "COO",
                "VP",
                "Director",
                "Manager",
            ],
        },
    )
    action_block_2 = ActionBlock(
        action=ActionType.SEND_SLACK_MESSAGE,
        data={
            "slack_message": [
                {
                    "text": {
                        "text": "Prospects found after filter: [[METADATA.CURRENT_PROSPECTS_FOUND]].",
                        "type": "mrkdwn",
                    },
                    "type": "section",
                }
            ],
            "slack_webhook_urls": webhook_urls,
        },
    )
    action_block_3 = ActionBlock(
        action=ActionType.UPLOAD_PROSPECTS,
        data={},
    )
    action_block_4 = ActionBlock(
        action=ActionType.SEND_SLACK_MESSAGE,
        data={
            "slack_message": [
                {
                    "text": {
                        "text": "Uploaded [[METADATA.PROSPECTS_UPLOADED]] prospects!",
                        "type": "mrkdwn",
                    },
                    "type": "section",
                }
            ],
            "slack_webhook_urls": webhook_urls,
        },
    )

    trigger = Trigger(
        name="New Trigger",
        description="",
        client_sdr_id=client_sdr_id,
        client_archetype_id=client_archetype_id,
        active=True,
        interval_in_minutes=1440,
        blocks=convertBlocksToDict(
            [
                source_block_1,
                action_block_1,
                filter_block_1,
                source_block_2,
                action_block_2,
                action_block_3,
                action_block_4,
            ]
        ),
        trigger_type=TriggerType.NEWS_EVENT,
    )
    db.session.add(trigger)
    db.session.commit()

    return trigger.id


@celery.task
def trigger_runner(trigger_id: int):
    # from src.automation.orchestrator import add_process_for_future

    # Run the trigger #
    trigger: Trigger = Trigger.query.get(trigger_id)
    run_id = None
    if trigger.active:
        success, run_id = runTrigger(trigger_id)

        if success:
            current_datetime = datetime.datetime.utcnow()
            new_datetime = current_datetime + datetime.timedelta(
                minutes=trigger.interval_in_minutes
            )

            trigger.last_run = current_datetime
            trigger.next_run = new_datetime

            db.session.commit()

    # # Run self #
    # add_process_for_future(
    #     type="trigger_runner",
    #     args={
    #         "trigger_id": trigger_id,
    #     },
    #     minutes=trigger.interval_in_minutes or 1440,
    # )

    return True, run_id


@celery.task
def run_all_triggers():
    from src.automation.orchestrator import add_process_list

    # Run the trigger #
    triggers: list[Trigger] = Trigger.query.all()
    return add_process_list(
        type="trigger_runner",
        args_list=[{"trigger_id": trigger.id} for trigger in triggers],
        chunk_size=100,
        chunk_wait_minutes=30,
        buffer_wait_minutes=1,
    )


def runTrigger(trigger_id: int):
    new_run = TriggerRun(
        trigger_id=trigger_id, run_status="Running", run_at=datetime.datetime.utcnow()
    )
    db.session.add(new_run)
    db.session.commit()
    run_id = new_run.id

    # Run the trigger #

    trigger: Trigger = Trigger.query.get(trigger_id)

    blocks = convertDictToBlocks(trigger.blocks or [])

    pipeline_data = PipelineData([], [], {})
    for block in blocks:
        pipeline_data = runBlock(
            trigger_id,
            run_id,
            trigger.client_sdr_id,
            trigger.client_archetype_id,
            trigger.keyword_blacklist or [],
            block,
            pipeline_data,
        )

    # Update blacklist, by removing old entries and adding new ones
    blacklist = trigger.keyword_blacklist or {}
    current_date = datetime.datetime.utcnow()
    two_weeks_ago = datetime.datetime.utcnow() - datetime.timedelta(days=14)

    blacklist = {
        key: value
        for key, value in blacklist.items()
        if datetime.datetime.utcfromtimestamp(value["date"]) > two_weeks_ago
    }

    for company in pipeline_data.companies:
        if not (company.company_name in blacklist):
            blacklist[company.company_name] = {
                "word": company.company_name,
                "date": current_date.timestamp(),
            }

    for prospect in pipeline_data.prospects:
        name = f"{prospect.first_name} {prospect.last_name}"
        if not (name in blacklist):
            blacklist[name] = {"word": name, "date": current_date.timestamp()}

    trigger.keyword_blacklist = blacklist

    new_run.run_status = "Completed"
    new_run.completed_at = datetime.datetime.utcnow()
    db.session.commit()

    # Send slack notif
    send_finished_slack_message(trigger.client_sdr_id, trigger.id, pipeline_data)

    send_socket_message(
        "trigger-log",
        {"message": f"Done!"},
        f"trigger-{trigger_id}",
    )

    return True, run_id


def runBlock(
    trigger_id: int,
    run_id: int,
    client_sdr_id: int,
    client_archetype_id: int,
    blacklist: list,
    block: Block,
    pipeline_data: PipelineData,
) -> PipelineData:
    if isinstance(block, SourceBlock):
        return runSourceBlock(trigger_id, blacklist, block, pipeline_data)
    elif isinstance(block, FilterBlock):
        return runFilterBlock(trigger_id, block, pipeline_data)
    elif isinstance(block, ActionBlock):
        return runActionBlock(
            trigger_id, run_id, client_sdr_id, client_archetype_id, block, pipeline_data
        )
    else:
        raise Exception("Unknown block type: {}".format(type(block)))


def runSourceBlock(
    trigger_id: int, blacklist: list, block: SourceBlock, pipeline_data: PipelineData
) -> PipelineData:
    prospects = pipeline_data.prospects or []
    companies = pipeline_data.companies or []
    meta_data = pipeline_data.meta_data or {}

    if block.source == SourceType.GOOGLE_COMPANY_NEWS:
        query = block.data.get("company_query", "")

        companies = source_companies_from_google_news(trigger_id, blacklist, query)

        # Update meta data accordingly
        meta_data[MetaDataRecord.SOURCE_COMPANY_QUERY.name] = query
        meta_data[MetaDataRecord.SOURCE_COMPANY_TYPE.name] = block.source.name
        meta_data[MetaDataRecord.SOURCE_COMPANIES_FOUND.name] = len(companies)
        meta_data[MetaDataRecord.CURRENT_COMPANIES_FOUND.name] = len(companies)

    elif block.source == SourceType.EXTRACT_PROSPECTS_FROM_COMPANIES:
        titles = block.data.get("prospect_titles", [])

        prospects = source_prospects_from_companies(
            trigger_id, blacklist, companies, titles
        )

        # Update meta data accordingly
        meta_data[MetaDataRecord.SOURCE_PROSPECTS_FOUND.name] = len(prospects)
        meta_data[MetaDataRecord.CURRENT_PROSPECTS_FOUND.name] = len(prospects)

    return PipelineData(
        prospects=prospects,
        companies=companies,
        meta_data=meta_data,
    )


def runFilterBlock(
    trigger_id: int, block: FilterBlock, pipeline_data: PipelineData
) -> PipelineData:
    prospects = pipeline_data.prospects or []
    companies = pipeline_data.companies or []
    meta_data = pipeline_data.meta_data or {}

    companies = filter_companies(trigger_id, companies, block.criteria, meta_data)
    prospects = filter_prospects(trigger_id, prospects, block.criteria, meta_data)

    meta_data[MetaDataRecord.CURRENT_COMPANIES_FOUND.name] = len(companies)
    meta_data[MetaDataRecord.CURRENT_PROSPECTS_FOUND.name] = len(prospects)

    return PipelineData(
        prospects=prospects,
        companies=companies,
        meta_data=meta_data,
    )


def runActionBlock(
    trigger_id: int,
    run_id: int,
    client_sdr_id: int,
    client_archetype_id: int,
    block: ActionBlock,
    pipeline_data: PipelineData,
) -> PipelineData:
    prospects = pipeline_data.prospects or []
    companies = pipeline_data.companies or []
    meta_data = pipeline_data.meta_data or {}

    if block.action == ActionType.SEND_SLACK_MESSAGE:
        message = block.data.get("slack_message", [])
        webhook_urls = block.data.get("slack_webhook_urls", [])
        if True:  # not webhook_urls or len(webhook_urls) == 0:
            sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
            client: Client = Client.query.get(sdr.client_id)
            webhook_urls = [client.pipeline_notifications_webhook_url]

        success = action_send_slack_message(
            trigger_id, message, webhook_urls, meta_data
        )

    elif block.action == ActionType.UPLOAD_PROSPECTS:
        amount = action_upload_prospects(
            trigger_id, prospects, run_id, client_sdr_id, client_archetype_id
        )

        meta_data[MetaDataRecord.PROSPECTS_UPLOADED.name] = amount

    return PipelineData(
        prospects=prospects,
        companies=companies,
        meta_data=meta_data,
    )


####################################################################################################
#                                        Utility Functions                                         #
####################################################################################################


def action_send_slack_message(
    trigger_id: int, blocks: list, webhook_urls: list[str], meta_data: dict
):
    json_string = json.dumps(blocks)
    json_string = replace_metadata(json_string, meta_data)
    parsed_blocks = json.loads(json_string)

    # send_socket_message(
    #     "trigger-log",
    #     {"message": f"Sending slack message for trigger {trigger_id}"},
    #     f"trigger-{trigger_id}",
    # )

    return send_slack_message(
        message="Slack message",
        blocks=parsed_blocks,
        webhook_urls=webhook_urls,
    )


def action_upload_prospects(
    trigger_id: int,
    prospects: list[PipelineProspect],
    run_id: int,
    client_sdr_id: int,
    client_archetype_id: int,
):
    send_socket_message(
        "trigger-log",
        {"message": f"Uploading {len(prospects)} prospects..."},
        f"trigger-{trigger_id}",
    )

    if len(prospects) == 0:
        return 0

    payload = []
    for prospect in prospects:
        if not prospect.linkedin_url:
            continue
        payload.append(prospect.to_dict())

    from src.prospecting.controllers import add_prospect_from_csv_payload

    response = add_prospect_from_csv_payload(
        client_sdr_id=client_sdr_id,
        archetype_id=client_archetype_id,
        csv_payload=payload,
        allow_duplicates=False,
        source=ProspectUploadSource.TRIGGERS,
    )
    print(response)

    # Create trigger prospect records after upload
    for prospect in prospects:
        trigger_prospect = TriggerProspect(
            trigger_run_id=run_id,
            first_name=prospect.first_name,
            last_name=prospect.last_name,
            title=prospect.title,
            company=prospect.company,
            linkedin_url=prospect.linkedin_url,
            custom_data=json.dumps(prospect.custom_data),
        )
        db.session.add(trigger_prospect)
    db.session.commit()

    return len(prospects)


def replace_metadata(message: str, meta_data: dict):
    for key, value in meta_data.items():
        placeholder = f"[[METADATA.{key}]]"
        message = message.replace(placeholder, str(value))
    return message


def filter_companies(
    trigger_id: int,
    companies: list[PipelineCompany],
    filter_criteria: FilterCriteria,
    meta_data: dict,
):
    if filter_criteria.company_query:
        companies = qualify_companies(
            trigger_id,
            companies,
            replace_metadata(filter_criteria.company_query, meta_data),
        )
    if filter_criteria.company_names:
        companies = qualify_company_names(
            trigger_id, companies, filter_criteria.company_names
        )

    return companies


def filter_prospects(
    trigger_id: int,
    prospects: list[PipelineProspect],
    filter_criteria: FilterCriteria,
    meta_data: dict,
):
    if filter_criteria.prospect_query:
        prospects = qualify_prospects(
            trigger_id,
            prospects,
            replace_metadata(filter_criteria.prospect_query, meta_data),
        )
    if filter_criteria.company_names:
        prospects = qualify_prospect_company_names(
            trigger_id, prospects, filter_criteria.company_names
        )
    if filter_criteria.prospect_titles:
        prospects = qualify_prospect_titles(
            trigger_id, prospects, filter_criteria.prospect_titles
        )

    return prospects


def qualify_company_names(
    trigger_id: int, companies: list[PipelineCompany], names: list[str]
):
    lowercase_names = [name.lower() for name in names]

    result_companies = []

    for row in companies:
        if row.company_name.lower() in lowercase_names:
            result_companies.append(row)

    return result_companies


def qualify_prospect_company_names(
    trigger_id: int, prospects: list[PipelineProspect], names: list[str]
):
    lowercase_names = [name.lower() for name in names]

    result_prospects = []

    for row in prospects:
        if row.company.lower() in lowercase_names:
            result_prospects.append(row)

    return result_prospects


def qualify_prospect_titles(
    trigger_id: int, prospects: list[PipelineProspect], titles: list[str]
):
    result_prospects = []

    for row in prospects:
        # Prepare the message for Chat GPT to check the role
        chat_message = [
            {
                "role": "user",
                "content": f"Does the role '{row.title}' match any of these roles: {titles}?\nOnly respond with 'True' or 'false'.\nResponse:",
            }
        ]

        # Get the role match response using Chat GPT
        role_match_response = wrapped_chat_gpt_completion(chat_message)

        # Determine if the role matches (True/False)
        correct_role = "True" in role_match_response.lower()
        if correct_role:
            result_prospects.append(row)

    return result_prospects


def source_prospects_from_companies(
    trigger_id: int,
    blacklist: list,
    companies: list[PipelineCompany],
    titles: list[str],
):
    profiles_data = extract_linkedin_profiles(trigger_id, companies, titles)
    return enrich_linkedin_profiles(trigger_id, blacklist, profiles_data)


def extract_linkedin_profiles(
    trigger_id: int, companies: list[PipelineCompany], titles: list[str]
):
    send_socket_message(
        "trigger-log",
        {"message": f"Fetching {len(companies)*len(titles)*10} leads..."},
        f"trigger-{trigger_id}",
    )

    profiles_data = []

    # Loop through each company and title
    for company in companies:
        for title in titles:
            # Construct the Google search query
            query = f'site:linkedin.com/in/ "{company.company_name}" "- {title}"'

            # send_socket_message(
            #     "trigger-log",
            #     {"message": f"Gathering prospects from SERP query: '{query}'"},
            #     f"trigger-{trigger_id}",
            # )

            # Perform the Google search
            search_results = search_google_news_raw(
                query
            )  # Use your search_google_news function
            organic_results = search_results.get("organic_results", [])

            # Process search results
            for profile in organic_results[:10]:
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
                    "sourced": f"{company.company_name} was recently in the news titled '{company.article_title}' posted {company.article_date}. The article summary is: '{company.article_snippet}'",
                }
                profiles_data.append(profile_data)

    send_socket_message(
        "trigger-log",
        {"message": f"Found {len(profiles_data)} prospects"},
        f"trigger-{trigger_id}",
    )

    return profiles_data


def enrich_linkedin_profiles(trigger_id: int, blacklist: list, profiles: list):
    MAX_NUM_PROFILES_TO_PROCESS = 5

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

        # If the profile is already in the blacklist, skip it
        if f"{first_name} {last_name}" in blacklist:
            continue

        # Prepare the enriched row
        prospect = PipelineProspect(
            first_name=first_name,
            last_name=last_name,
            title=title,
            company=company,
            linkedin_url=profile_url,
            custom_data={
                "sourced": row["sourced"],
            },
        )

        # Don't add if the prospect is already in the list
        if prospect in prospects:
            continue

        prospects.append(prospect)

    return prospects


def source_companies_from_google_news(
    trigger_id: int, blacklist: list, query: str
) -> list[PipelineCompany]:
    send_socket_message(
        "trigger-log",
        {"message": f"Fetching companies..."},
        f"trigger-{trigger_id}",
    )

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

        # If company name is in the blacklist, skip the article
        if company_name in blacklist:
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

    send_socket_message(
        "trigger-log",
        {"message": f"Found {len(result_data)} companies with news event '{query}'"},
        f"trigger-{trigger_id}",
    )

    return result_data


def qualify_companies(
    trigger_id: int, companies: list[PipelineCompany], qualifying_question: str
):
    send_socket_message(
        "trigger-log",
        {"message": f"Qualifying companies"},
        f"trigger-{trigger_id}",
    )

    results = []
    for row in companies:
        # Prepare the message for Chat GPT
        chat_message = [
            {
                "role": "user",
                "content": f"{qualifying_question}\n Event: {row.article_title}. Company: {row.company_name}.\nOnly respond with 'True' or 'false'.\nResponse:",
            }
        ]

        # Get qualification response using Chat GPT
        qualification_response = wrapped_chat_gpt_completion(chat_message)

        # Determine qualification (True/False)
        qualified = "True" in qualification_response.lower()

        if qualified:
            results.append(row)

    return results


def qualify_prospects(
    trigger_id: int, prospects: list[PipelineProspect], qualifying_question: str
):
    send_socket_message(
        "trigger-log",
        {"message": f"Qualifying leads"},
        f"trigger-{trigger_id}",
    )

    results = []
    for row in prospects:
        # Prepare the message for Chat GPT
        chat_message = [
            {
                "role": "user",
                "content": f"{qualifying_question}\n Prospect title: {row.title}. Company: {row.company}.\nOnly respond with 'True' or 'false'.\nResponse:",
            }
        ]

        # Get qualification response using Chat GPT
        qualification_response = wrapped_chat_gpt_completion(chat_message)

        # Determine qualification (True/False)
        qualified = "True" in qualification_response.lower()

        if qualified:
            results.append(row)

    return results


def send_finished_slack_message(
    client_sdr_id: int, trigger_id: int, pipeline_data: PipelineData
):
    send_socket_message(
        "trigger-log",
        {"message": f"Sending completion message..."},
        f"trigger-{trigger_id}",
    )

    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client: Client = Client.query.get(sdr.client_id)
    trigger: Trigger = Trigger.query.get(trigger_id)

    count = 0
    for company in pipeline_data.companies:
        count += 1
        if count > 3:
            break

        prospects = [
            prospect
            for prospect in pipeline_data.prospects
            if prospect.company == company.company_name
        ]

        prospects_details = "\n".join(
            [
                f"> - <{prospect.linkedin_url}|*{prospect.first_name} {prospect.last_name}*> - {prospect.title}"
                for prospect in prospects[0:3]
            ]
        )

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"Trigger ⚡️: {trigger.name}",
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": """> :newspaper: *<{url}|'{title}'>*\n> {snippet}\n> _- {date}_""".format(
                        url=company.article_link,
                        title=company.article_title,
                        snippet=company.article_snippet.replace("\n", "\n> "),
                        date=company.article_date,
                    ),
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Company:* {company.company_name}",
                },
            },
            {"type": "divider"},
            {
                # context
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f":white_check_mark: Location: US",  #  :white_check_mark: Industry: {event['industry']}
                    }
                ],
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{len(prospects)} prospects found*",
                },
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": prospects_details},
            },
            {
                "type": "divider",
            },
        ]

        result = send_slack_message(
            message="hello",
            webhook_urls=[client.pipeline_notifications_webhook_url],
            blocks=blocks,
        )

def experiment_athelas_trigger():
    '''
    This is an experimental trigger we set up for Athelas.

    Source: Companies that are hiring for 'Clinical Scribe' roles
    Roles: CIO, CTO, COO, Clinical Director
    
    Returns a list of contacts, linkedin profiles, and companies.
    '''
    from src.contacts.services import apollo_get_organizations_from_company_names
    from src.contacts.services import apollo_get_contacts

    # find on Google
    TITLES = ["CIO", "CTO", "COO", "Clinical Director", "VP"]
    ROLES = ["Clinical Scribe", "Medical Scribe"]
    CLIENT_SDR_ID = 215 # Nick Jones; Athelas

    PAGES = 1
    results = []
    for i in range(PAGES):
        for role in ROLES:
            data = search_google_news_raw(role, engine="google_jobs", start=10*i)
            print("processing page", i*10)
            job_results = data.get("jobs_results", [])
            for job in job_results:
                company = job.get("company_name")
                description = job.get("description")
                extensions = job.get("extensions")
                location = job.get("location","").strip()
                title = job.get("title")
                via = job.get("via")

                company_ids = apollo_get_organizations_from_company_names(
                    client_sdr_id=CLIENT_SDR_ID,
                    company_names=[company],
                )

                contacts = apollo_get_contacts(
                    client_sdr_id=CLIENT_SDR_ID,
                    num_contacts=100,
                    person_titles=TITLES,
                    organization_ids=[company_ids[0]['id']] if company_ids else [],
                )

                total_people = contacts['contacts'] + contacts['people']
                for contact in total_people:
                    results.append({
                        "company": company,
                        "title": title,
                        "location": location,
                        # "description": description,
                        "via": via,
                        "apollo_id": company_ids[0]['id'] if company_ids else None,
                        "contact": contact,
                    })

    # return list
    return {
        'results': results,
    }

def athelas_job_listing_sonar_test():
    client: Client = Client.query.get(82)
    webhook_url = client.pipeline_notifications_webhook_url
    send_slack_message(
        message="testing",
        webhook_urls=[webhook_url],
        blocks=[
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": "🎯 SellScale Sonar: >5 Medical Scribe Listings",
                            "emoji": True
                        }
                    },
                    {
                        "type": "divider"
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "Company: *Oak Street Health*\nEmployees: *5,001 - 10,000*\nLocation: *Chicago, IL*\nConditions: *(✅ is hospital) (✅ 100 - 100k size)*"
                        },
                        "accessory": {
                            "type": "image",
                            "image_url": "https://logo.clearbit.com/oakstreethealth.com",
                            "alt_text": "oak street health logo"
                        }
                    },
                    {
                        "type": "context",
                        "elements": [
                            {
                                "type": "mrkdwn",
                                "text": "🚨 *Detected 8+ job listings for 'Medical Scribes'*"
                            }
                        ]
                    },
                    {
                        "type": "divider"
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "*Medical Scribe - Bilingual Spanish Required*\nNew York"
                        },
                        "accessory": {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "emoji": True,
                                "text": "View"
                            },
                            "url": "https://www.linkedin.com/jobs/view/3972563779"
                        }
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "*Float Medical Scribe $2k Sign on Bonus*\nNew York"
                        },
                        "accessory": {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "emoji": True,
                                "text": "View"
                            },
                            "url": "https://www.linkedin.com/jobs/view/3927501203"
                        }
                    },
                    {
                        "type": "context",
                        "elements": [
                            {
                                "type": "mrkdwn",
                                "text": "🔎 *Detected 74+ relevant professionals*"
                            }
                        ]
                    },
                    {
                        "type": "divider"
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "*Jordan Allen*\nVP, Strategy & Operations (New York)"
                        },
                        "accessory": {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "emoji": True,
                                "text": "View"
                            },
                            "url": "https://www.linkedin.com/in/jordan-allen-9106022b"
                        }
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "*Carlibi Mha/Mba/Fsa*\nSr Practice Manager (New York)"
                        },
                        "accessory": {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "emoji": True,
                                "text": "View"
                            },
                            "url": "https://www.linkedin.com/in/carlibirojas"
                        }
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "*Charlotte Turovsky*\nVP, Clinical Operations (New York)"
                        },
                        "accessory": {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "emoji": True,
                                "text": "View"
                            },
                            "url": "https://www.linkedin.com/in/charlotte-turovsky-0267a544"
                        }
                    },
                    {
                        "type": "divider"
                    },
                    {
                        "type": "actions",
                        "elements": [
                            {
                                "type": "button",
                                "text": {
                                    "type": "plain_text",
                                    "text": "Engage with contacts",
                                    "emoji": True
                                },
                                "url": "https://app.sellscale.com",
                                "action_id": "actionId-0"
                            }
                        ]
                    }
                ]
    )