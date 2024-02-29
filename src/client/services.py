from enum import Enum
import random

import sqlalchemy
from src.automation.orchestrator import add_process_for_future
from src.client.sdr.email.models import EmailType
from src.client.sdr.email.services_email_bank import create_sdr_email_bank
from src.client.sdr.services_client_sdr import (
    LINKEDIN_WARM_THRESHOLD,
    deactivate_sla_schedules,
    load_sla_schedules,
)
from sqlalchemy import cast, String
from src.company.models import Company
from src.domains.services import setup_managed_inboxes
from src.email_scheduling.services import (
    create_calendar_link_needed_operator_dashboard_card,
)
from src.email_sequencing.models import EmailSequenceStep
from src.bump_framework.default_frameworks.services import (
    create_default_bump_frameworks,
)
from src.operator_dashboard.models import (
    OperatorDashboardEntryPriority,
    OperatorDashboardEntryStatus,
    OperatorDashboardTaskType,
)
from src.operator_dashboard.services import create_operator_dashboard_entry
from src.slack.models import SlackNotificationType
from src.slack.slack_notification_center import (
    create_and_send_slack_notification_class_message,
    subscribe_sdr_to_all_notifications,
)
from src.vision.services import attempt_chat_completion_with_vision
from src.individual.models import Individual
from src.prospecting.icp_score.services import update_icp_scoring_ruleset
from src.prospecting.models import ProspectEvent

from model_import import DemoFeedback, BumpFramework
from sqlalchemy import func
from sqlalchemy.orm import aliased
from src.client.models import (
    ClientAssetType,
    ClientAssets,
    ClientProduct,
    ClientAssetArchetypeReasonMapping,
)
from sqlalchemy import or_
from click import Option
from src.client.models import DemoFeedback
from src.automation.models import PhantomBusterConfig, PhantomBusterType
from src.automation.models import PhantomBusterAgent
from app import celery, db
from flask import jsonify
from datetime import datetime
import pytz
import time
import json
from datetime import datetime, timedelta
from sqlalchemy.orm.attributes import flag_modified
from nylas import APIClient
from src.analytics.services import add_activity_log

from src.ml.openai_wrappers import (
    OPENAI_CHAT_GPT_3_5_TURBO_MODEL,
    OPENAI_CHAT_GPT_4_MODEL,
    wrapped_chat_gpt_completion,
    wrapped_create_completion,
)
from src.ml.models import GNLPModel, GNLPModelType, ModelProvider
from src.prospecting.models import (
    ProspectOverallStatus,
    ProspectUploadsRawCSV,
    ProspectUploads,
)
from src.client.models import Client, ClientArchetype, ClientSDR
from src.message_generation.models import (
    GeneratedMessageCTA,
    GeneratedMessage,
    GeneratedMessageStatus,
)
from src.onboarding.services import create_sight_onboarding
from src.utils.hasher import generate_uuid
from src.utils.random_string import generate_random_alphanumeric
from src.prospecting.models import Prospect, ProspectStatus, ProspectChannels
from model_import import StackRankedMessageGenerationConfiguration
from typing import List, Optional
from src.ml.fine_tuned_models import get_latest_custom_model
from src.utils.slack import URL_MAP, send_slack_message
import os
import requests
from sqlalchemy import func, case, distinct

from src.voyager.services import (
    create_add_pre_filters_operator_dashboard_card,
    create_linkedin_connection_needed_operator_dashboard_card,
    create_slack_connection_needed_operator_dashboard_card,
)

STYTCH_PROJECT_ID = os.environ.get("STYTCH_PROJECT_ID")
STYTCH_SECRET = os.environ.get("STYTCH_SECRET")
STYTCH_BASE_URL = os.environ.get("STYTCH_BASE_URL")


def get_client(client_id: int):
    c: Client = Client.query.get(client_id)
    return c


def create_client(
    company: str,
    company_website: str,
    contact_name: str,
    contact_email: str,
    linkedin_outbound_enabled: bool,
    email_outbound_enabled: bool,
    tagline: Optional[str] = None,
    description: Optional[str] = None,
):
    c: Client = Client.query.filter_by(company=company).first()
    if c:
        return {"client_id": c.id}

    # Get the full company_website URL
    if not company_website.startswith("http://"):
        company_website = "http://" + company_website
    response = requests.get(company_website, allow_redirects=True)
    company_website = response.url

    c: Client = Client(
        company=company,
        domain=company_website,
        contact_name=contact_name,
        contact_email=contact_email,
        active=True,
        notification_allowlist=[
            ProspectStatus.SCHEDULING,
            ProspectStatus.DEMO_SET,
            ProspectStatus.ACTIVE_CONVO,
            ProspectStatus.ACCEPTED,
            ProspectStatus.ACTIVE_CONVO_SCHEDULING,
        ],
        linkedin_outbound_enabled=linkedin_outbound_enabled,
        email_outbound_enabled=email_outbound_enabled,
        tagline=tagline,
        description=description,
        do_not_contact_keywords_in_company_names=[],
        do_not_contact_company_names=[],
        do_not_contact_industries=[],
        do_not_contact_location_keywords=[],
        do_not_contact_titles=[],
        do_not_contact_prospect_location_keywords=[],
        do_not_contact_people_names=[],
        do_not_contact_emails=[],
        auto_generate_li_messages=True,
    )
    db.session.add(c)
    db.session.commit()
    c.regenerate_uuid()

    # create_client_sdr(
    #     client_id=c.id,
    #     name=contact_name,
    #     email=contact_email,
    # )

    return {"client_id": c.id}


def update_client_details(
    client_id: int,
    company: Optional[str] = None,
    company_website: Optional[str] = None,
    tagline: Optional[str] = None,
    description: Optional[str] = None,
    value_prop_key_points: Optional[str] = None,
    tone_attributes: Optional[list[str]] = None,
    mission: Optional[str] = None,
    case_study: Optional[str] = None,
    contract_size: Optional[int] = None,
):
    c: Client = Client.query.get(client_id)
    if not c:
        return None

    if company:
        c.company = company
    if company_website:
        # Get the full company_website URL
        if not company_website.startswith("http://"):
            company_website = "http://" + company_website
        response = requests.get(company_website, allow_redirects=True)
        company_website = response.url
        c.domain = company_website
    if tagline:
        c.tagline = tagline
    if description:
        c.description = description
    if value_prop_key_points:
        c.value_prop_key_points = value_prop_key_points
    if tone_attributes:
        c.tone_attributes = tone_attributes
    if mission:
        c.mission = mission
    if case_study:
        c.case_study = case_study
    if contract_size:
        c.contract_size = contract_size
        # propagate_contract_value(client_id, contract_size)

    db.session.add(c)
    db.session.commit()

    return True


def update_client_sdr_details(
    client_sdr_id: int,
    name: Optional[str] = None,
    title: Optional[str] = None,
    disable_ai_on_prospect_respond: Optional[bool] = None,
    disable_ai_on_message_send: Optional[bool] = None,
    ai_outreach: Optional[bool] = None,
    browser_extension_ui_overlay: Optional[bool] = None,
    auto_archive_convos: Optional[bool] = None,
    meta_data: Optional[dict] = None,
):
    csdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if not csdr:
        return None

    if name:
        csdr.name = name
    if title:
        csdr.title = title
    if disable_ai_on_prospect_respond is not None:
        csdr.disable_ai_on_prospect_respond = disable_ai_on_prospect_respond
    if disable_ai_on_message_send is not None:
        csdr.disable_ai_on_message_send = disable_ai_on_message_send
    if ai_outreach is not None:
        csdr.active = ai_outreach
    if browser_extension_ui_overlay is not None:
        csdr.browser_extension_ui_overlay = browser_extension_ui_overlay
    if auto_archive_convos is not None:
        csdr.auto_archive_convos = auto_archive_convos
    if meta_data:
        csdr.meta_data = {**(csdr.meta_data or {}), **meta_data}

    db.session.add(csdr)
    db.session.commit()

    return True


def complete_client_sdr_onboarding(
    client_sdr_id: int,
):
    csdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if not csdr:
        return None

    csdr.onboarded = True

    db.session.add(csdr)
    db.session.commit()

    return True


def toggle_is_onboarding(
    client_sdr_id: int,
):
    csdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if not csdr:
        return None

    csdr.is_onboarding = not csdr.is_onboarding

    db.session.add(csdr)
    db.session.commit()

    return True


def get_client_archetypes(client_sdr_id: int, query: Optional[str] = "") -> list:
    """Gets a list of all Client Archetypes, with a search filter on the archetype name

    Args:
        client_sdr_id (int): The ID of the Client SDR
        query (str): The search query

    Returns:
        list: The list of Client Archetypes
    """
    fetch = ClientArchetype.query.filter(
        ClientArchetype.client_sdr_id == client_sdr_id,
    )
    if query:
        fetch = ClientArchetype.query.filter(
            ClientArchetype.archetype.ilike(f"%{query}%"),
        )

    client_archetypes: list[ClientArchetype] = fetch.all()

    client_archetype_dicts = []
    for ca in client_archetypes:
        performance = get_client_archetype_performance(client_sdr_id, ca.id, False)
        merged_dicts = {**ca.to_dict(), **{"performance": performance}}
        client_archetype_dicts.append(merged_dicts)

    return [ca.to_dict() for ca in client_archetypes]


def get_client_archetype_prospects(
    client_sdr_id: int, archetype_id: int, query: Optional[str] = ""
) -> list:
    """Gets the prospects in an archetype

    Hard limit to 10 prospects

    Args:
        client_sdr_id (int): The ID of the Client SDR
        archetype_id (int): The ID of the Client Archetype
        query (str): The search query

    Returns:
        list: The list of prospects
    """
    prospects: list[Prospect] = (
        Prospect.query.filter(
            Prospect.client_sdr_id == client_sdr_id,
            Prospect.archetype_id == archetype_id,
            Prospect.full_name.ilike(f"%{query}%"),
        )
        .order_by(Prospect.icp_fit_score.desc())
        .limit(10)
        .all()
    )

    return [p.to_dict(shallow_data=True) for p in prospects]


def get_client_archetype_performance(
    client_sdr_id: int, client_archetype_id: int, simple: bool = False
) -> dict:
    """Gets the performance of a Client Archetype

    Args:
        client_archetype_id (int): The ID of the Client Archetype
        simple (bool): Whether to return a simple dict (just the total) or a full dict

    Returns:
        dict: Client Archetype and performance statistics
    """

    if simple:
        # Optimized query for just the total prospects
        total_count: int = (
            db.session.query(func.count(Prospect.id))
            .filter(
                Prospect.client_sdr_id == client_sdr_id,
                Prospect.archetype_id == client_archetype_id,
            )
            .scalar()
        )
        return {"total_prospects": total_count, "status_map": {}}

    # Get Prospects and find total_count and status_count
    archetype_prospects: list[Prospect] = Prospect.query.filter(
        Prospect.client_sdr_id == client_sdr_id,
        Prospect.archetype_id == client_archetype_id,
    ).all()
    status_map = {}
    for p in archetype_prospects:
        if p.overall_status is None:
            continue

        if p.overall_status.value in status_map:
            status_map[p.overall_status.value] += 1
        else:
            status_map[p.overall_status.value] = 1
    total_prospects = len(archetype_prospects)

    performance = {"total_prospects": total_prospects, "status_map": status_map}

    return performance


def get_client_archetype(client_archetype_id: int):
    ca: ClientArchetype = ClientArchetype.query.get(client_archetype_id)
    return ca


def create_client_archetype(
    client_id: int,
    client_sdr_id: int,
    archetype: str,
    filters: any,
    base_archetype_id: Optional[int] = None,
    disable_ai_after_prospect_engaged: bool = False,
    persona_fit_reason: str = "",
    icp_matching_prompt: str = "",
    persona_contact_objective: str = "",
    is_unassigned_contact_archetype: bool = False,
    active: bool = True,
    persona_contract_size: Optional[int] = None,
    cta_blanks_company: Optional[str] = None,
    cta_blanks_persona: Optional[str] = None,
    cta_blanks_solution: Optional[str] = None,
    persona_filters: Optional[str] = None,
    common_use_cases: Optional[str] = None,
    lookalike_1: Optional[str] = None,
    lookalike_2: Optional[str] = None,
    lookalike_3: Optional[str] = None,
    lookalike_4: Optional[str] = None,
    lookalike_5: Optional[str] = None,
    template_mode: Optional[bool] = False,
):
    c: Client = get_client(client_id=client_id)
    if not c:
        return None

    client_archetype = ClientArchetype(
        client_id=client_id,
        client_sdr_id=client_sdr_id,
        archetype=archetype,
        filters=filters,
        disable_ai_after_prospect_engaged=disable_ai_after_prospect_engaged,
        persona_fit_reason=persona_fit_reason,
        icp_matching_prompt=icp_matching_prompt,
        persona_contact_objective=persona_contact_objective,
        is_unassigned_contact_archetype=is_unassigned_contact_archetype,
        active=active,
        email_blocks_configuration=[
            "Personalize the title to their company and or the prospect",
            "Include a greeting with Hi, Hello, or Hey with their first name",
            "Personalized 1-2 lines. Mentioned details about them, their role, their company, or other relevant pieces of information. Use personal details about them to be natural and personal.",
            "Mention what we do and offer and how it can help them based on their background, company, and key details.",
            "Use the objective for a call to action",
            "End with Best, (new line) (My Name) (new line) (Title)",
        ],
        contract_size=persona_contract_size or c.contract_size,
        li_bump_amount=0,
        persona_cta_framework_company=cta_blanks_company,
        persona_cta_framework_persona=cta_blanks_persona,
        persona_cta_framework_action=cta_blanks_solution,
        persona_use_cases=common_use_cases,
        persona_filters=persona_filters,
        persona_lookalike_profile_1=lookalike_1,
        persona_lookalike_profile_2=lookalike_2,
        persona_lookalike_profile_3=lookalike_3,
        persona_lookalike_profile_4=lookalike_4,
        persona_lookalike_profile_5=lookalike_5,
        template_mode=template_mode,
    )
    db.session.add(client_archetype)
    db.session.commit()
    archetype_id = client_archetype.id

    client: Client = Client.query.get(client_id)
    webhook_url: str = client.pipeline_notifications_webhook_url
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    campaign_url = (
        "https://app.sellscale.com/authenticate?stytch_token_type=direct&token="
        + client_sdr.auth_token
        + "&redirect=campaigns"
    )
    # send_slack_message(
    #     message="New campaign created",
    #     blocks=[
    #         {
    #             "type": "header",
    #             "text": {
    #                 "type": "plain_text",
    #                 "text": "⭐️ New Campaign Created",
    #                 "emoji": True,
    #             },
    #         },
    #         {
    #             "type": "section",
    #             "text": {
    #                 "type": "mrkdwn",
    #                 "text": "SellScale AI just created a new campaign for *{}*.\n".format(
    #                     archetype
    #                 ),
    #             },
    #         },
    #         {
    #             "type": "section",
    #             "text": {
    #                 "type": "mrkdwn",
    #                 "text": "> User: *{}*\n_Finding new prospects shortly_.".format(
    #                     client_sdr.name
    #                 ),
    #             },
    #         },
    #         {
    #             "type": "section",
    #             "text": {"type": "mrkdwn", "text": " "},
    #             "accessory": {
    #                 "type": "button",
    #                 "text": {
    #                     "type": "plain_text",
    #                     "text": "View Campaign →",
    #                     "emoji": True,
    #                 },
    #                 "url": campaign_url,
    #                 "action_id": "button-action",
    #             },
    #         },
    #         {"type": "divider"},
    #     ],
    #     webhook_urls=[webhook_url] if webhook_url else [],
    # )

    if base_archetype_id:
        _, model_id = get_latest_custom_model(base_archetype_id, GNLPModelType.OUTREACH)
        base_model: GNLPModel = GNLPModel.query.get(model_id)
        model = GNLPModel(
            model_provider=base_model.model_provider,
            model_type=base_model.model_type,
            model_description="baseline_model_{}".format(archetype),
            model_uuid=base_model.model_uuid,
            archetype_id=archetype_id,
        )
        db.session.add(model)
        db.session.commit()
    else:
        model: GNLPModel = GNLPModel(
            model_provider=ModelProvider.OPENAI_GPT3,
            model_type=GNLPModelType.OUTREACH,
            model_description="baseline_model_{}".format(archetype),
            model_uuid="davinci:ft-personal-2022-07-23-19-55-19",
            archetype_id=archetype_id,
        )
        db.session.add(model)
        db.session.commit()

    # Create default bump frameworks for this Archetype
    create_default_bump_frameworks(
        client_sdr_id=client_sdr_id,
        client_archetype_id=archetype_id,
    )

    predict_archetype_emoji(
        archetype_id=archetype_id,
    )

    titles = predict_titles_from_archetype_name(archetype)
    update_icp_scoring_ruleset(
        client_archetype_id=archetype_id,
        included_individual_title_keywords=titles,
        excluded_individual_title_keywords=[],
        included_individual_industry_keywords=[],
        excluded_individual_industry_keywords=[],
        individual_years_of_experience_start=0,
        individual_years_of_experience_end=100,
        included_individual_skills_keywords=[],
        excluded_individual_skills_keywords=[],
        included_individual_locations_keywords=[],
        excluded_individual_locations_keywords=[],
        included_individual_generalized_keywords=[],
        excluded_individual_generalized_keywords=[],
        included_company_name_keywords=[],
        excluded_company_name_keywords=[],
        included_company_locations_keywords=[],
        excluded_company_locations_keywords=[],
        company_size_start=0,
        company_size_end=10000000,
        included_company_industries_keywords=[],
        excluded_company_industries_keywords=[],
        included_company_generalized_keywords=[],
        excluded_company_generalized_keywords=[],
        included_individual_education_keywords=[],
        excluded_individual_education_keywords=[],
        included_individual_seniority_keywords=[],
        excluded_individual_seniority_keywords=[],
    )

    # Add an activity log
    add_activity_log(
        client_sdr_id=client_sdr_id,
        type="CAMPAIGN-CREATED",
        name="Campaign Created",
        description=f"Created a new campaign for {archetype}",
    )

    # TODO: Create bump frameworks if the SDR specified bump frameworks to create

    return {"client_archetype_id": client_archetype.id}


def predict_titles_from_archetype_name(archetype: str, retries=3):
    try:
        completion = wrapped_create_completion(
            prompt=f"You are about to insert a new archetype named {archetype}. What is a list of 4-5 generic titles you would use to search for this archetype on LinkedIn? Return a JSON object with the key, 'titles', and a list of titles as the value.".format(
                archetype
            ),
            model=OPENAI_CHAT_GPT_4_MODEL,
            temperature=0.7,
            max_tokens=100,
        )

        obj = json.loads(completion)
        titles = obj["titles"]
        return titles
    except Exception as e:
        if retries > 0:
            return predict_titles_from_archetype_name(archetype, retries - 1)
        else:
            return []


def get_client_sdr(client_sdr_id: int) -> dict:
    """Gets and returns Client SDR information

    Args:
        client_sdr_id (int): The ID of the Client SDR

    Returns:
        dict: The Client SDR information
    """
    csdr: ClientSDR = ClientSDR.query.get(client_sdr_id)

    return csdr.to_dict()


def create_client_sdr(
    client_id: int,
    name: str,
    email: str,
    create_managed_inboxes: bool = False,
    include_connect_li_card: bool = False,
    include_connect_slack_card: bool = False,
    include_input_pre_filters_card: bool = False,
    include_add_dnc_filters_card: bool = False,
    include_add_calendar_link_card: bool = False,
):
    from src.client.services_unassigned_contacts_archetype import (
        create_unassigned_contacts_archetype,
    )

    c: Client = get_client(client_id=client_id)
    if not c:
        return None

    print("Creating client sdr")
    sdr = ClientSDR(
        client_id=client_id,
        name=name,
        email=email,
        weekly_li_outbound_target=LINKEDIN_WARM_THRESHOLD,
        weekly_email_outbound_target=0,
        notification_allowlist=[
            ProspectStatus.SCHEDULING,
            ProspectStatus.DEMO_SET,
            ProspectStatus.ACTIVE_CONVO,
            ProspectStatus.ACCEPTED,
            ProspectStatus.ACTIVE_CONVO_SCHEDULING,
        ],
        scrape_time="13:27:21",
        next_scrape="2023-06-08 13:27:21.493957",
        auth_token=generate_random_alphanumeric(32),
        auto_generate_messages=True,
        analytics_activation_date=datetime.utcnow(),
        auto_bump=True,
        is_onboarding=True,
        do_not_contact_keywords_in_company_names=[],
        do_not_contact_company_names=[],
        do_not_contact_industries=[],
        do_not_contact_location_keywords=[],
        do_not_contact_titles=[],
        do_not_contact_prospect_location_keywords=[],
        do_not_contact_people_names=[],
        do_not_contact_emails=[],
        autopilot_enabled=True,
        auto_send_linkedin_campaign=True,
        auto_send_email_campaign=True,
    )
    db.session.add(sdr)
    db.session.commit()
    sdr_id = sdr.id

    sdr: ClientSDR = ClientSDR.query.get(sdr_id)
    sdr.regenerate_uuid()

    # Create the managed inboxes
    if create_managed_inboxes:
        setup_managed_inboxes.delay(client_sdr_id=sdr_id)

    # Create the operator dashboard cards
    if include_connect_li_card:
        create_linkedin_connection_needed_operator_dashboard_card(sdr_id)
    if include_add_calendar_link_card:
        create_calendar_link_needed_operator_dashboard_card(sdr_id)
    if include_connect_slack_card:
        create_slack_connection_needed_operator_dashboard_card(sdr_id)
    if include_input_pre_filters_card:
        create_add_pre_filters_operator_dashboard_card(sdr_id)
    if include_add_dnc_filters_card:
        create_do_not_contact_filters_operator_dashboard_card(sdr_id)

    # create_sight_onboarding(sdr.id)

    print("Creating unassigned contacts archetype")
    create_unassigned_contacts_archetype(sdr.id)

    print("Creating the anchor email")
    create_sdr_email_bank(
        client_sdr_id=sdr.id,
        email_address=email,
        email_type=EmailType.ANCHOR,
    )

    print("Subscribe to all notifications")
    subscribe_sdr_to_all_notifications(
        client_sdr_id=sdr.id,
    )

    return {"client_sdr_id": sdr.id}


def deactivate_client_sdr(client_sdr_id: int, email: str) -> bool:
    """Deactives a Client SDR and sets their SLAs to 0

    Args:
        client_sdr_id (int): The ID of the Client SDR
        email (str): The email of the Client SDR

    Returns:
        bool: Whether or not the Client SDR was deactivated
    """
    sdr: ClientSDR = ClientSDR.query.filter(
        ClientSDR.id == client_sdr_id,
        ClientSDR.email == email,
    ).first()
    if not sdr:
        return False

    sdr.active = False
    sdr.autopilot_enabled = False
    deactivate_sla_schedules(sdr.id)
    # sdr.weekly_li_outbound_target = 0
    # sdr.weekly_email_outbound_target = 0

    db.session.commit()

    # Set the launch volume to 0 (stop sending outreach)
    update_phantom_buster_launch_schedule(client_sdr_id=client_sdr_id, custom_volume=0)

    client_archetypes: list = ClientArchetype.query.filter(
        ClientArchetype.client_sdr_id == client_sdr_id,
    ).all()
    for ca in client_archetypes:
        ca.active = False
        db.session.add(ca)
    db.session.commit()

    return True


def activate_client_sdr(
    client_sdr_id: int,
    li_target: Optional[int] = None,
    email_target: Optional[int] = None,
) -> bool:
    """Activates a Client SDR and sets their SLAs

    Args:
        client_sdr_id (int): The ID of the Client SDR
        li_target (int): The LI outbound target
        email_target (int): The email outbound target

    Returns:
        bool: Whether or not the Client SDR was activated
    """
    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if not sdr:
        return False

    sdr.active = True
    if li_target:
        sdr.weekly_li_outbound_target = li_target
    if email_target:
        sdr.weekly_email_outbound_target = email_target

    db.session.add(sdr)
    db.session.commit()

    load_sla_schedules(sdr.id)

    update_phantom_buster_launch_schedule(client_sdr_id)

    return True


def toggle_client_sdr_autopilot_enabled(client_sdr_id: int):
    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if not sdr:
        return None

    sdr.autopilot_enabled = not sdr.autopilot_enabled
    db.session.add(sdr)
    db.session.commit()

    return {"autopilot_enabled": sdr.autopilot_enabled}


def toggle_client_sdr_auto_bump(client_sdr_id: int):
    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if not sdr:
        return None

    sdr.auto_bump = not sdr.auto_bump
    db.session.add(sdr)
    db.session.commit()

    return True


def toggle_client_sdr_auto_send_linkedin_campaign(client_sdr_id: int):
    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if not sdr:
        return None

    sdr.auto_send_linkedin_campaign = not sdr.auto_send_linkedin_campaign
    db.session.add(sdr)
    db.session.commit()

    return True


def toggle_client_sdr_auto_send_email_campaign(
    client_sdr_id: int, enabled: bool
) -> bool:
    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if not sdr:
        return False

    sdr.auto_send_email_campaign = enabled
    db.session.add(sdr)
    db.session.commit()

    return True


def reset_client_sdr_sight_auth_token(client_sdr_id: int):
    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if not sdr:
        return None

    sdr.auth_token = generate_random_alphanumeric(32)
    db.session.commit()

    return {"token": sdr.auth_token}


def get_sdr_available_outbound_channels(client_sdr_id: int) -> dict:
    """Gets the available outbound channels for a Client SDR

    Args:
        client_sdr_id (int): The ID of the Client SDR

    Returns:
        dict: The available outbound channels
    """

    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if not client_sdr:
        return None

    # Get all channels
    all_channels = ProspectChannels.to_dict_verbose()

    # Get the channels that are available to the SDR
    sdr_channels = {}
    li_enabled = client_sdr.weekly_li_outbound_target is not None
    if li_enabled:
        sdr_channels[ProspectChannels.LINKEDIN.value] = all_channels.get(
            ProspectChannels.LINKEDIN.value
        )
    email_enabled = client_sdr.weekly_email_outbound_target is not None
    if email_enabled:
        sdr_channels[ProspectChannels.EMAIL.value] = all_channels.get(
            ProspectChannels.EMAIL.value
        )
    if li_enabled or email_enabled:
        sdr_channels[ProspectChannels.SELLSCALE.value] = all_channels.get(
            ProspectChannels.SELLSCALE.value
        )

    return sdr_channels


def rename_archetype(new_name: str, client_archetype_id: int):
    """
    Rename an archetype
    """
    ca: ClientArchetype = ClientArchetype.query.get(client_archetype_id)
    if not ca:
        return None

    ca.archetype = new_name
    db.session.add(ca)
    db.session.commit()

    return True


def toggle_archetype_active(archetype_id: int):
    """
    Toggle an archetype's active status
    """
    ca: ClientArchetype = ClientArchetype.query.get(archetype_id)
    if not ca:
        return None

    ca.active = not ca.active
    db.session.add(ca)
    db.session.commit()

    return True


def update_client_sdr_scheduling_link(client_sdr_id: int, scheduling_link: str):
    """
    Update the scheduling link for a Client SDR
    """
    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if not sdr:
        return None

    sdr.scheduling_link = scheduling_link
    db.session.add(sdr)
    db.session.commit()

    return True


def update_client_pipeline_notification_webhook(client_id: int, webhook: str):
    """
    Update the Slack pipeline notification webhook for a Client
    """
    c: Client = Client.query.get(client_id)
    if not c:
        return None

    c.pipeline_notifications_webhook_url = webhook
    db.session.add(c)
    db.session.commit()

    return True


def test_client_pipeline_notification_webhook(client_id: int):
    """
    Test the Slack pipeline notification webhook for a Client
    """
    c: Client = Client.query.get(client_id)
    if not c:
        return None

    if not c.pipeline_notifications_webhook_url:
        return None

    send_slack_message(
        message="(Example message): Elon Musk accepted your LinkedIn invitation!",
        webhook_urls=[c.pipeline_notifications_webhook_url],
    )

    return True


def update_client_sdr_pipeline_notification_webhook(client_sdr_id: int, webhook: str):
    """Update the Slack pipeline notification webhook for a Client SDR

    Args:
        client_sdr_id (int): ID of the Client SDR
        webhook (str): Webhook URL

    Returns:
        bool: True if successful, None otherwise
    """
    csdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if not csdr:
        return None

    csdr.pipeline_notifications_webhook_url = webhook

    db.session.add(csdr)
    db.session.commit()

    return True


def test_client_sdr_pipeline_notification_webhook(client_sdr_id: int):
    """Test the Slack pipeline notification webhook for a Client SDR

    Args:
        client_sdr_id (int): ID of the Client SDR

    Returns:
        bool: True if successful, None otherwise
    """
    csdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if not csdr:
        return None

    if not csdr.pipeline_notifications_webhook_url:
        return None

    send_slack_message(
        message="(Example message): Elon Musk accepted your LinkedIn invitation!",
        webhook_urls=[csdr.pipeline_notifications_webhook_url],
    )

    return True


def make_stytch_call(email: str):
    from stytch import Client

    client = Client(
        project_id=STYTCH_PROJECT_ID,
        secret=STYTCH_SECRET,
        environment="live",
    )
    client.magic_links.email.login_or_create(
        email=email,
        login_magic_link_url=STYTCH_BASE_URL,
    )


def authenticate_stytch_client_sdr_token(token: str):
    from stytch import Client

    client = Client(
        project_id=STYTCH_PROJECT_ID,
        secret=STYTCH_SECRET,
        environment="live",
    )
    return client.magic_links.authenticate(token).json()


def send_stytch_magic_link(client_sdr_email: str):
    """Send a Stytch magic link to a Client SDR"""
    sdr: ClientSDR = ClientSDR.query.filter_by(email=client_sdr_email).first()
    if not sdr:
        return None

    email = sdr.email
    try:
        make_stytch_call(email)
    except:
        return False
    return True


def approve_stytch_client_sdr_token(client_sdr_email: str, token: str):
    """Authenticate a Stytch token and return a SellScale Sight auth token"""
    try:
        stytch_response = authenticate_stytch_client_sdr_token(token)
    except Exception as e:
        return jsonify({"error_type": "Stytch failed", "message": e.error_message}), 400

    emails = stytch_response.get("user").get("emails")
    if not emails or len(emails) == 0:
        return None
    email_found = False
    for email in emails:
        if (email.get("email")).lower() == client_sdr_email.lower():
            email_found = True

    if not email_found:
        return jsonify({"message": "Email not found in Stytch response"}), 400

    client_sdr: ClientSDR = ClientSDR.query.filter_by(email=client_sdr_email).first()
    reset_client_sdr_sight_auth_token(client_sdr.id)

    client_sdr: ClientSDR = ClientSDR.query.filter_by(email=client_sdr_email).first()
    token = client_sdr.auth_token

    return jsonify({"message": "Success", "token": token}), 200


def verify_client_sdr_auth_token(auth_token: str):
    """Verify a Client SDR auth token"""
    client_sdr: ClientSDR = ClientSDR.query.filter_by(auth_token=auth_token).first()
    if not client_sdr:
        return None

    return True


def update_client_sdr_manual_warning_message(client_sdr_id: int, manual_warning: str):
    """Update the manual warning text value for a Client SDR

    Args:
        client_sdr_id (int): ID of the Client SDR
        manual_warning_message (str): Manual warning text

    Returns:
        bool: True if successful, None otherwise
    """
    csdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if not csdr:
        return None

    csdr.manual_warning_message = manual_warning
    db.session.add(csdr)
    db.session.commit()

    return True


# DEPRECATED: THIS IS NOT HOW SLAS WORK ANYMORE
# def update_client_sdr_weekly_li_outbound_target(
#     client_sdr_id: int, weekly_li_outbound_target: int
# ):
#     """Update the weekly LinkedIn outbound target for a Client SDR

#     Args:
#         client_sdr_id (int): ID of the Client SDR
#         weekly_li_outbound_target (int): Weekly LinkedIn outbound target

#     Returns:
#         bool: True if successful, None otherwise
#     """
#     csdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
#     if not csdr:
#         return None

#     update_sdr_linkedin_sla(client_sdr_id, weekly_li_outbound_target)

#     return True


# DEPRECATED: THIS IS NOT HOW SLAS WORK ANYMORE
# def update_client_sdr_weekly_email_outbound_target(
#     client_sdr_id: int, weekly_email_outbound_target: int
# ):
#     """Update the weekly email outbound target for a Client SDR

#     Args:
#         client_sdr_id (int): ID of the Client SDR
#         weekly_email_outbound_target (int): Weekly email outbound target

#     Returns:
#         bool: True if successful, None otherwise
#     """
#     csdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
#     if not csdr:
#         return None

#     csdr.weekly_email_outbound_target = weekly_email_outbound_target
#     db.session.add(csdr)
#     db.session.commit()

#     return True


def get_ctas(client_archetype_id: int):
    """Get all CTAs for a Client Archetype

    Args:
        client_archetype_id (int): ID of the Client Archetype

    Returns:
        list: List of CTAs
    """
    ctas = GeneratedMessageCTA.query.filter_by(archetype_id=client_archetype_id).all()
    return ctas


def get_cta_by_archetype_id(client_sdr_id: int, archetype_id: int) -> dict:
    """Get CTAs belonging to an Archetype, alongside stats.

    This function is authenticated.

    Args:
        client_sdr_id (int): ID of the Client SDR
        archetype_id (int): ID of the Archetype

    Returns:
        dict: Dict containing the CTAs and their stats, message, and status code
    """
    # Get Archetype
    archetype: ClientArchetype = ClientArchetype.query.get(archetype_id)
    if not archetype:
        return {"message": "Archetype not found", "status_code": 404}
    elif archetype.client_sdr_id != client_sdr_id:
        return {"message": "Archetype does not belong to you", "status_code": 403}

    # Get CTAs belonging to the Archetype
    ctas: list[GeneratedMessageCTA] = GeneratedMessageCTA.query.filter(
        GeneratedMessageCTA.archetype_id == archetype_id
    )

    # Convert to dict and calculate stats
    cta_dicts = []
    for cta in ctas:
        raw_cta = cta.to_dict()
        raw_cta["performance"] = get_cta_stats(cta.id)
        cta_dicts.append(raw_cta)

    return {"message": "Success", "status_code": 200, "ctas": cta_dicts}


def get_prospect_upload_stats_by_upload_id(
    client_sdr_id: int, prospect_uploads_raw_csv_id: int
) -> dict:
    """Get the basic stats for a prospect upload

    This function is authenticated.

    Args:
        client_sdr_id (int): ID of the Client SDR
        prospect_uploads_raw_csv_id (int): ID of the upload

    Returns:
        dict: Dict containing the upload stats
    """

    # Validate parameters
    prospect_uploads_raw_csv: ProspectUploadsRawCSV = ProspectUploadsRawCSV.query.get(
        prospect_uploads_raw_csv_id
    )
    if not prospect_uploads_raw_csv:
        return {"message": "Upload not found", "status_code": 404}
    elif prospect_uploads_raw_csv.client_sdr_id != client_sdr_id:
        return {"message": "Not authorized", "status_code": 401}

    # Get stats for the upload
    upload_stats = db.session.execute(
        """
        select
          count(status) FILTER (WHERE status = 'UPLOAD_COMPLETE') success,
          count(status) FILTER (WHERE status = 'UPLOAD_IN_PROGRESS') in_progress,
          count(status) FILTER (WHERE status = 'UPLOAD_QUEUED') queued,
          count(status) FILTER (WHERE status = 'UPLOAD_NOT_STARTED') not_started,
          count(status) FILTER (WHERE status = 'DISQUALIFIED') disqualified,
          count(status) FILTER (WHERE status = 'UPLOAD_FAILED') failed,
          count(status) total
        from prospect_uploads
        where prospect_uploads.prospect_uploads_raw_csv_id = {upload_id} and prospect_uploads.client_sdr_id = {client_sdr_id}
        """.format(
            upload_id=prospect_uploads_raw_csv_id, client_sdr_id=client_sdr_id
        )
    ).fetchall()

    # index to status map
    status_map = {
        0: "success",
        1: "in_progress",
        2: "queued",
        3: "not_started",
        4: "disqualified",
        5: "failed",
        6: "total",
    }

    # Convert and format output
    upload_stats = [tuple(row) for row in upload_stats][0]
    upload_stats = {
        status_map.get(i, "unknown"): row for i, row in enumerate(upload_stats)
    }

    return {"message": "Success", "status_code": 200, "stats": upload_stats}


def get_transformers_by_archetype_id(
    client_sdr_id: int, archetype_id: int, email: bool
) -> dict:
    """Gets all transformers belonging to an Archetype, alongside stats.

    This function is authenticated.

    Args:
        client_sdr_id (int): ID of the Client SDR
        archetype_id (int): ID of the archetype

    Returns:
        dict: Dict containing the transformer stats
    """

    # Validate parameters
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    archetype: ClientArchetype = ClientArchetype.query.get(archetype_id)
    if not archetype:
        return {"message": "Archetype not found", "status_code": 404}
    elif archetype.client_id != client_sdr.client_id:
        return {"message": "Not authorized", "status_code": 401}

    # Get transformer stats
    transformer_stats = db.session.execute(
        """
        select
          client_archetype.archetype,
          research_point.research_point_type,
          count(distinct prospect.id) num_prospects,
          count(distinct prospect.id) filter (where prospect_status_records.to_status = 'ACCEPTED') num_accepted_prospects,
          count(distinct prospect.id) filter (where prospect_status_records.to_status = 'ACCEPTED') / cast(count(distinct prospect.id) as float) percent_accepted
        from prospect
          join client_archetype on client_archetype.id = prospect.archetype_id
          join generated_message on generated_message.prospect_id = prospect.id
          join research_point on research_point.id = any(generated_message.research_points)
          join prospect_status_records on prospect_status_records.prospect_id = prospect.id
          {email_join}
        where prospect.archetype_id = {archetype_id} {email_filter}
        group by 1,2
        order by 5 desc
        """.format(
            archetype_id=archetype_id,
            email_join=(
                "left outer join prospect_email on prospect.id = prospect_email.prospect_id"
                if email
                else ""
            ),
            email_filter="and prospect_email.prospect_id is null" if email else "",
        )
    ).fetchall()

    # index to column
    column_map = {
        0: "archetype",
        1: "research_point_type",
        2: "num_prospects",
        3: "num_accepted_prospects",
        4: "percent_accepted",
    }

    # Convert and format output
    transformer_stats = [
        {column_map.get(i, "unknown"): value for i, value in enumerate(tuple(row))}
        for row in transformer_stats
    ]

    return {"message": "Success", "status_code": 200, "stats": transformer_stats}


def get_prospect_upload_details_by_upload_id(
    client_sdr_id: int, prospect_uploads_raw_csv_id: int
) -> dict:
    """Get the individual prospect details of the prospect upload

    This function is authenticated.

    Args:
        client_sdr_id (int): ID of the Client SDR
        prospect_uploads_raw_csv_id (int): ID of the upload

    Returns:
        dict: Dict containing the upload details
    """

    # Validate parameters
    prospect_uploads_raw_csv: ProspectUploadsRawCSV = ProspectUploadsRawCSV.query.get(
        prospect_uploads_raw_csv_id
    )
    if not prospect_uploads_raw_csv:
        return {"message": "Upload not found", "status_code": 404}
    elif prospect_uploads_raw_csv.client_sdr_id != client_sdr_id:
        return {"message": "Not authorized", "status_code": 401}

    # Get all prospect details of the upload
    all_prospect_details = (
        ProspectUploads.query.filter_by(
            prospect_uploads_raw_csv_id=prospect_uploads_raw_csv_id,
            client_sdr_id=client_sdr_id,
        )
        .order_by(ProspectUploads.updated_at.desc())
        .all()
    )

    return {
        "message": "Success",
        "status_code": 200,
        "uploads": [x.to_dict() for x in all_prospect_details],
    }


def get_all_uploads_by_archetype_id(client_sdr_id: int, archetype_id: int) -> dict:
    """Get all uploads for an Archetype

    This function is authenticated.

    Args:
        client_sdr_id (int): ID of the Client SDR
        archetype_id (int): ID of the Archetype

    Returns:
        dict: Dict containing the archetype's upload data
    """

    # Validate parameters
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    archetype: ClientArchetype = ClientArchetype.query.get(archetype_id)
    if not archetype:
        return {"message": "Archetype not found", "status_code": 404}
    elif archetype.client_id != client_sdr.client_id:
        return {"message": "Not authorized", "status_code": 401}

    # Get all uploads
    all_uploads = (
        ProspectUploadsRawCSV.query.filter_by(
            client_archetype_id=archetype_id,
            client_sdr_id=client_sdr_id,
        )
        .order_by(ProspectUploadsRawCSV.created_at.desc())
        .all()
    )

    return {
        "message": "Success",
        "status_code": 200,
        "uploads": [x.to_dict() for x in all_uploads],
    }


def get_cta_stats(cta_id: int) -> dict:
    """Get stats for a CTA.

    Args:
        cta_id (int): ID of the CTA

    Returns:
        dict: Dict containing the stats and total count
    """
    # Get GeneratedMessages
    generated_messages: list[GeneratedMessage] = GeneratedMessage.query.filter(
        GeneratedMessage.message_cta == cta_id,
        GeneratedMessage.message_status == GeneratedMessageStatus.SENT,
    ).all()

    num_sent_and_converted_pair = db.session.execute(
        """
        select
            count(distinct generated_message.prospect_id) filter (where prospect_status_records.to_status = 'SENT_OUTREACH') num_converted,
            count(distinct generated_message.prospect_id) filter (where prospect_status_records.to_status = 'ACCEPTED') num_converted
        from generated_message
            join prospect_status_records on generated_message.prospect_id = prospect_status_records.prospect_id
        where message_cta = {cta_id} and message_status = 'SENT'
        """.format(
            cta_id=cta_id
        )
    ).fetchall()
    num_sent = num_sent_and_converted_pair[0][0]
    num_converted = num_sent_and_converted_pair[0][1]

    # Get Prospect IDs
    prospect_id_set = set()
    for message in generated_messages:
        prospect_id_set.add(message.prospect_id)

    # Get Prospect
    prospects: list[Prospect] = Prospect.query.filter(
        Prospect.id.in_(prospect_id_set)
    ).all()
    statuses_map = {}
    for prospect in prospects:
        if prospect.overall_status is None:
            continue
        if prospect.overall_status.value not in statuses_map:
            statuses_map[prospect.overall_status.value] = 1
        else:
            statuses_map[prospect.overall_status.value] += 1

    return {
        "status_map": statuses_map,
        "total_count": len(prospects),
        "num_sent": num_sent,
        "num_converted": num_converted,
    }


def check_nylas_status(client_sdr_id: int) -> bool:
    """Check if Nylas is connected

    Args:
        client_sdr_id (int): ID of the Client SDR

    Returns:
        bool: True if connected, False otherwise
    """
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    return client_sdr.nylas_active


def clear_nylas_tokens(client_sdr_id: int):
    """Clears Nylas tokens

    Args:
        client_sdr_id (int): ID of the client SDR

    Returns:
        status_code (int), message (str): HTTP status code
    """

    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if not sdr:
        return "No client sdr found with this id", 400

    nylas = APIClient(
        os.environ.get("NYLAS_CLIENT_ID"),
        os.environ.get("NYLAS_CLIENT_SECRET"),
    )
    account = next(
        (a for a in nylas.accounts.all() if a.get("email") == sdr.email), None
    )

    if account:
        account.downgrade()
    else:
        "Error clearing tokens", 500

    sdr.nylas_auth_code = None
    sdr.nylas_account_id = None
    sdr.nylas_active = False

    db.session.add(sdr)
    db.session.commit()

    send_slack_message(
        message=f"🔗❌ Nylas Disconnected\n {sdr.name} (# {sdr.id}) just disconnected his Nylas account from Sight.\nEmail disconnected: {sdr.email}",
        webhook_urls=[URL_MAP["operations-nylas-connection"]],
    )

    return "Cleared tokens", 200


def nylas_account_details(client_sdr_id: int):
    """Wrapper for https://api.nylas.com/account

    Returns:
        dict: Dict containing the response
    """

    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)

    response = requests.get(
        "https://api.nylas.com/account",
        headers={
            "Accept": "application/json",
            "Authorization": "Bearer {secret}".format(
                secret=client_sdr.nylas_auth_code
            ),
            "Content-Type": "application/json",
        },
    )
    if response.status_code != 200:
        return {"message": "Error getting account details", "status_code": 500}

    return response.json()


def get_nylas_all_events(client_sdr_id: int):
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    response = requests.get(
        # Only events in the next 70 days
        f"https://api.nylas.com/events?starts_after={int(time.time())}&starts_before={int(time.time()+6048000)}&limit=200",
        headers={
            "Authorization": f"Bearer {client_sdr.nylas_auth_code}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    if response.status_code != 200:
        return {"message": "Error getting events"}, 500

    result = response.json()

    return {"message": "Success", "data": result}, 200


def get_nylas_single_event(client_sdr_id: int, nylas_event_id: str):
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    response = requests.get(
        # Only events in the next 70 days
        f"https://api.nylas.com/events?event_id={nylas_event_id}",
        headers={
            "Authorization": f"Bearer {client_sdr.nylas_auth_code}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    if response.status_code != 200:
        return {"message": "Error getting event"}, 500

    result = response.json()

    return {"message": "Success", "data": result}, 200


def invite_firefly_to_event(prospect_event_id: int):
    """event: ProspectEvent = ProspectEvent.query.get(prospect_event_id)
    if not event: return {"message": "Failed to find event"}, 400
    sdr: ClientSDR = ClientSDR.query.get(event.client_sdr_id)

    response = requests.put(
        f"https://{sdr.nylas_auth_code}:@api.nylas.com/events/{event.nylas_event_id}?notify_participants=false",
        json={
            "where": event.title,
            "participants": [
                {
                    "comment": "null",
                    "email": "fireflywoz@outlook.com",
                    "name": "Firefly WoZ",
                }
            ],
            "description": "Invite"
        }
    )
    if response.status_code != 200:
        return {"message": "Error sending invite"}, 500

    result = response.json()"""

    return {"message": "Success", "data": ""}, 200  # result


def find_sdr_events(client_sdr_id: int) -> List[ProspectEvent]:
    return ProspectEvent.query.filter_by(client_sdr_id=client_sdr_id).all()


def find_prospect_events(client_sdr_id: int, prospect_id: int):
    prospect: Prospect = Prospect.query.get(prospect_id)
    if not prospect or prospect.client_sdr_id != client_sdr_id or not prospect.email:
        return None

    result, status_code = get_nylas_all_events(client_sdr_id)
    if status_code != 200:
        return None

    events = result.get("data", [])

    results = []
    for event in events:
        event_str = json.dumps(event)

        # Check primary email
        if prospect.email.strip().lower() in event_str.lower():
            results.append(event)
            continue

        # Check extra emails as well
        if prospect.email_additional:
            for extra_email in prospect.email_additional:
                if extra_email.get("email", "").strip().lower() in event_str.lower():
                    results.append(event)
                    continue

    return results


def populate_single_prospect_event(nylas_account_id: str, nylas_event_id: str):
    sdr: ClientSDR = ClientSDR.query.filter_by(
        nylas_account_id=nylas_account_id
    ).first()
    if not sdr or not sdr.auto_calendar_sync:
        return False

    existing_event: ProspectEvent = ProspectEvent.query.filter_by(
        nylas_event_id=nylas_event_id
    ).first()
    # print(existing_event)

    result, status_code = get_nylas_single_event(sdr.id, nylas_event_id)

    # print(result)
    if status_code != 200:
        return False

    if len(result.get("data", [])) == 0:
        return False
    event = result.get("data", [])[0]
    if isinstance(event, str):
        return False

    # Update existing event
    if existing_event:
        if existing_event.nylas_data_raw == event:
            return False

        existing_event.title = event.get("title", "No Title")

        start_time, end_time = convert_nylas_date(event)
        existing_event.start_time = datetime.fromtimestamp(start_time)
        existing_event.end_time = datetime.fromtimestamp(end_time)

        existing_event.status = event.get("status", "")
        existing_event.meeting_info = event.get("conferencing", {})
        existing_event.nylas_data_raw = event

        db.session.add(existing_event)
        db.session.commit()

    else:
        prospect_id = get_prospect_id_from_nylas_event(sdr.id, event)
        if not prospect_id:
            return False

        start_time, end_time = convert_nylas_date(event)

        prospect_event = ProspectEvent(
            prospect_id=prospect_id,
            client_sdr_id=sdr.id,
            nylas_event_id=event.get("id"),
            nylas_calendar_id=event.get("calendar_id"),
            title=event.get("title", "No Title"),
            start_time=datetime.fromtimestamp(start_time),
            end_time=datetime.fromtimestamp(end_time),
            status=event.get("status", ""),
            meeting_info=event.get("conferencing", {}),
            nylas_data_raw=event,
        )
        db.session.add(prospect_event)
        db.session.commit()

        # Make sure a firefly is invited
        response, code = invite_firefly_to_event(prospect_event.id)
        # print(response, code)

    # TODO: Update the demo date for the prospect

    return True


def get_prospect_id_from_nylas_event(client_sdr_id, nylas_event):
    event_str = json.dumps(nylas_event)
    prospects: List[Prospect] = Prospect.query.filter_by(
        client_sdr_id=client_sdr_id
    ).all()

    for prospect in prospects:
        if not prospect.email:
            continue

        # Check primary email
        if prospect.email.strip().lower() in event_str.lower():
            return prospect.id

        # Check extra emails as well
        if prospect.email_additional:
            for extra_email in prospect.email_additional:
                if extra_email.get("email", "").strip().lower() in event_str.lower():
                    return prospect.id

    return None


def populate_prospect_events(client_sdr_id: int, prospect_id: int):
    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if not sdr.auto_calendar_sync:
        return 0, 0

    prospect_events: List[ProspectEvent] = ProspectEvent.query.filter_by(
        prospect_id=prospect_id
    ).all()

    updated_count = 0
    added_count = 0
    calendar_events = find_prospect_events(client_sdr_id, prospect_id) or []
    soonest_event = None
    for event in calendar_events:
        # Find soonest event
        if soonest_event:
            s_start_time, s_end_time = convert_nylas_date(soonest_event)
            e_start_time, e_end_time = convert_nylas_date(event)

            current_time = int(time.time())
            if (
                s_start_time != 0
                and e_start_time != 0
                and s_start_time > e_start_time
                and s_start_time > current_time
            ):
                soonest_event = event
        else:
            soonest_event = event

        # Check if event already exists
        if event.get("id") in [x.nylas_event_id for x in prospect_events]:
            # Update existing event
            existing_event = next(
                (e for e in prospect_events if e.nylas_event_id == event.get("id")),
                None,
            )
            if existing_event:
                if existing_event.nylas_data_raw == event:
                    continue

                existing_event.title = event.get("title", "No Title")

                start_time, end_time = convert_nylas_date(event)
                existing_event.start_time = datetime.fromtimestamp(start_time)
                existing_event.end_time = datetime.fromtimestamp(end_time)

                existing_event.status = event.get("status", "")
                existing_event.meeting_info = event.get("conferencing", {})
                existing_event.nylas_data_raw = event

                db.session.add(existing_event)
                db.session.commit()
                updated_count += 1

        else:
            start_time, end_time = convert_nylas_date(event)

            prospect_event = ProspectEvent(
                prospect_id=prospect_id,
                client_sdr_id=client_sdr_id,
                nylas_event_id=event.get("id"),
                nylas_calendar_id=event.get("calendar_id"),
                title=event.get("title", "No Title"),
                start_time=datetime.fromtimestamp(start_time),
                end_time=datetime.fromtimestamp(end_time),
                status=event.get("status", ""),
                meeting_info=event.get("conferencing", {}),
                nylas_data_raw=event,
            )
            db.session.add(prospect_event)
            db.session.commit()
            added_count += 1

            # Make sure a firefly is invited
            response, code = invite_firefly_to_event(prospect_event.id)
            print(response, code)

    # Update prospect's demo date with soonest event date
    if soonest_event:
        prospect: Prospect = Prospect.query.get(prospect_id)
        prospect.demo_date = datetime.fromtimestamp(
            soonest_event.get("when", {}).get("start_time", 0)
        )
        db.session.add(prospect)
        db.session.commit()

    return added_count, updated_count


def convert_nylas_date(event):
    start_time = event.get("when", {}).get("start_time", 0)
    end_time = event.get("when", {}).get("end_time", 0)
    if event.get("when", {}).get("date"):
        date_object = datetime.strptime(event.get("when", {}).get("date"), "%Y-%m-%d")
        start_time = int(date_object.timestamp())
        end_time = start_time

    if event.get("when", {}).get("start_date") and event.get("when", {}).get(
        "end_date"
    ):
        date_object_start = datetime.strptime(
            event.get("when", {}).get("start_date"), "%Y-%m-%d"
        )
        start_time = int(date_object_start.timestamp())

        date_object_end = datetime.strptime(
            event.get("when", {}).get("end_date"), "%Y-%m-%d"
        )
        end_time = int(date_object_end.timestamp())

    return start_time, end_time


def get_sdr_calendar_availability(client_sdr_id: int, start_time: int, end_time: int):
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    response = requests.post(
        "https://api.nylas.com/calendars/free-busy",
        headers={
            "Authorization": f"Bearer {client_sdr.nylas_auth_code}",
            "Content-Type": "application/json",
        },
        json={
            "start_time": str(start_time),
            "end_time": str(end_time),
            "emails": [client_sdr.email],
        },
    )
    if response.status_code != 200:
        return {"message": "Error getting calendar availability"}, 500

    result = response.json()

    return {"message": "Success", "data": result}, 200


def get_unused_linkedin_and_email_prospect_for_persona(client_archetype_id: int):
    unused_linkedin_prospects = Prospect.query.filter(
        Prospect.archetype_id == client_archetype_id,
        Prospect.linkedin_url != None,
        Prospect.approved_outreach_message_id == None,
    ).count()

    unused_email_prospects = Prospect.query.filter(
        Prospect.archetype_id == client_archetype_id,
        Prospect.email != None,
        Prospect.approved_prospect_email_id == None,
        or_(
            Prospect.overall_status == ProspectOverallStatus.PROSPECTED.value,
            Prospect.overall_status == ProspectOverallStatus.SENT_OUTREACH.value,
            Prospect.overall_status == ProspectOverallStatus.BUMPED.value,
        ),
    ).count()

    return {
        "unused_linkedin_prospects": unused_linkedin_prospects,
        "unused_email_prospects": unused_email_prospects,
    }


def update_persona_brain_details(
    client_sdr_id: int,
    client_archetype_id: int,
    updated_persona_name: Optional[str],
    updated_persona_fit_reason: Optional[str],
    updated_persona_icp_matching_prompt: Optional[str],
    updated_persona_contact_objective: Optional[str],
    updated_persona_contract_size: Optional[int],
    updated_cta_framework_company: Optional[str],
    updated_cta_framework_persona: Optional[str],
    updated_cta_framework_action: Optional[str],
    updated_use_cases: Optional[str],
    updated_filters: Optional[str],
    updated_lookalike_profile_1: Optional[str],
    updated_lookalike_profile_2: Optional[str],
    updated_lookalike_profile_3: Optional[str],
    updated_lookalike_profile_4: Optional[str],
    updated_lookalike_profile_5: Optional[str],
):
    client_archetype: ClientArchetype = ClientArchetype.query.get(client_archetype_id)
    if not client_archetype or client_archetype.client_sdr_id != client_sdr_id:
        return False

    if updated_persona_name:
        client_archetype.archetype = updated_persona_name
    if updated_persona_fit_reason:
        client_archetype.persona_fit_reason = updated_persona_fit_reason
    if updated_persona_icp_matching_prompt:
        client_archetype.icp_matching_prompt = updated_persona_icp_matching_prompt
    if updated_persona_contact_objective:
        client_archetype.persona_contact_objective = updated_persona_contact_objective
    if updated_persona_contract_size:
        client_archetype.contract_size = updated_persona_contract_size
    if updated_cta_framework_company:
        client_archetype.persona_cta_framework_company = updated_cta_framework_company
    if updated_cta_framework_persona:
        client_archetype.persona_cta_framework_persona = updated_cta_framework_persona
    if updated_cta_framework_action:
        client_archetype.persona_cta_framework_action = updated_cta_framework_action
    if updated_use_cases:
        client_archetype.persona_use_cases = updated_use_cases
    if updated_filters:
        client_archetype.persona_filters = updated_filters
    if updated_lookalike_profile_1:
        client_archetype.persona_lookalike_profile_1 = updated_lookalike_profile_1
    if updated_lookalike_profile_2:
        client_archetype.persona_lookalike_profile_2 = updated_lookalike_profile_2
    if updated_lookalike_profile_3:
        client_archetype.persona_lookalike_profile_3 = updated_lookalike_profile_3
    if updated_lookalike_profile_4:
        client_archetype.persona_lookalike_profile_4 = updated_lookalike_profile_4
    if updated_lookalike_profile_5:
        client_archetype.persona_lookalike_profile_5 = updated_lookalike_profile_5

    db.session.add(client_archetype)
    db.session.commit()

    return True


def update_sdr_conversion_percentages(
    client_sdr_id: int,
    active_convo: float,
    scheduling: float,
    demo_set: float,
    demo_won: float,
    not_interested: float,
):
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if not client_sdr:
        return False

    client_sdr.conversion_percentages = {
        "active_convo": active_convo,
        "scheduling": scheduling,
        "demo_set": demo_set,
        "demo_won": demo_won,
        "not_interested": not_interested,
    }

    db.session.add(client_sdr)
    db.session.commit()

    return True


def predict_persona_fit_reason(
    client_sdr_id: int, client_archetype_id: int
) -> tuple[bool, str]:
    """
    Based on the company's name, archetype's name, company's tagline, and company's description, predict the reason why the archetype would purchase the product
    from the company.

    returns:
        (success: bool, message: str)
    """
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client_archetype: ClientArchetype = ClientArchetype.query.get(client_archetype_id)
    client: Client = Client.query.get(client_sdr.client_id)
    if (
        not client_sdr
        or not client_archetype
        or client_archetype.client_sdr_id != client_sdr.id
    ):
        return False, "Unauthorized access"

    # Get company name, archetype name, company tagline, and company description
    company_name = client.company
    archetype_name = client_archetype.archetype
    company_tagline = client.tagline
    company_description = client.description

    # create prompt
    prompt = f"Based on the company's name, archetype's name, company's tagline, and company's description, predict the reason why the archetype would purchase the product from the company.\n\nCompany Name: {company_name}\nArchetype Name: {archetype_name}\nCompany Tagline: {company_tagline}\nCompany Description: {company_description}\n\nWhy would they buy the product?:"
    response = wrapped_create_completion(
        model=OPENAI_CHAT_GPT_3_5_TURBO_MODEL, prompt=prompt, max_tokens=200
    )
    if response == False:
        return False, "Error generating prediction"

    return True, response


def generate_persona_buy_reason_helper(client_sdr_id: int, persona_name: str):
    """
    Generate a persona buy reason for a persona

    Args:
        client_sdr_id (int): ID of the client SDR
        persona_name (str): Name of the persona

    Returns:
        str: Generated persona buy reason
    """
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client: Client = Client.query.get(client_sdr.client_id)

    company_name = client.company
    company_tagline = client.tagline
    company_description = client.description

    prompt = f"You are a sales researcher for {company_name}. You are tasked with understanding a new persona target which is called '{persona_name}'. Given the company's name, company's tagline, and company's description, generate a reason why this persona would buy your company's product or offering.\n\nCompany Name: {company_name}\nCompany Tagline: {company_tagline}\nCompany Description: {company_description}\n\nPersona Buy Reason:"
    return wrapped_create_completion(
        model=OPENAI_CHAT_GPT_3_5_TURBO_MODEL, prompt=prompt, max_tokens=200
    )


def generate_persona_buy_reason(
    client_sdr_id: int, persona_name: str, retries: int = 3
):
    """
    Generate a persona buy reason for a persona

    Args:
        client_sdr_id (int): ID of the client SDR
        persona_name (str): Name of the persona
        retries (int): Number of retries to attempt

    Returns:
        str: Generated persona buy reason
    """
    for _ in range(retries):
        try:
            buy_reason = generate_persona_buy_reason_helper(client_sdr_id, persona_name)
            if buy_reason:
                return buy_reason
        except:
            pass
    return ""


def generate_persona_icp_matching_prompt_helper(
    client_sdr_id: int,
    persona_name: str,
    persona_buy_reason: str = "",
):
    """
    Generate a persona ICP matching prompt for a persona

    Args:
        client_sdr_id (int): ID of the client SDR
        persona_name (str): Name of the persona
        persona_buy_reason (str): Buy reason of the persona

    Returns:
        str: Generated persona buy reason
    """
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client: Client = Client.query.get(client_sdr.client_id)

    company_name = client.company
    company_tagline = client.tagline
    company_description = client.description

    prompt = """
You are a sales research assistant for {company_name}. {company_name}'s tagline is {company_tagline}. Here is a quick description of what {company_name} does: {company_description}

Given the company name, persona name, persona description, and persona fit reason, create an ICP Scoring Prompt. An ICP scoring prompt contains the following:

Role(s): which types of roles would this comprise of
Seniority(s): what is the seniority level of this persona
Location(s): what is the scope of locations (if any)
Other Note(s): bullet point list of notes to keep in mind
Tier List: bullet point list of Tiers and what would need to match to fit in that Tier. Tier 1 is VERY HIGH, Tier 5 is VERY LOW.

Here is the information about the persona we want to create an ICP Scoring Prompt for:
Persona: {persona_name}
Persona Fit Reason: {persona_fit_reason}

ICP Scoring Prompt:
    """.format(
        company_name=company_name,
        company_tagline=company_tagline,
        company_description=company_description,
        persona_name=persona_name,
        persona_fit_reason=persona_buy_reason,
    )
    return wrapped_create_completion(
        model=OPENAI_CHAT_GPT_4_MODEL, prompt=prompt, max_tokens=400
    )


def generate_persona_icp_matching_prompt(
    client_sdr_id: int,
    persona_name: str,
    persona_buy_reason: str = "",
    retries: int = 3,
):
    """
    Generate a persona ICP matching prompt for a persona

    Args:
        client_sdr_id (int): ID of the client SDR
        persona_name (str): Name of the persona
        persona_buy_reason (str): Buy reason of the persona
        retries (int): Number of retries to attempt

    Returns:
        str: Generated persona buy reason
    """
    for _ in range(retries):
        try:
            icp_matching_prompt = generate_persona_icp_matching_prompt_helper(
                client_sdr_id, persona_name, persona_buy_reason
            )
            if icp_matching_prompt:
                return icp_matching_prompt
        except:
            pass
    return ""


@celery.task()
def daily_pb_launch_schedule_update():
    # Get the IDs of all active Clients
    active_client_ids: list[int] = [
        client.id for client in Client.query.filter_by(active=True).all()
    ]

    # Get all active SDRs
    sdrs: list[ClientSDR] = ClientSDR.query.filter(
        ClientSDR.active == True, ClientSDR.client_id.in_(active_client_ids)
    ).all()
    sdr_ids = [sdr.id for sdr in sdrs]

    # Update PB launch schedule for each SDR
    for sdr_id in sdr_ids:
        update_phantom_buster_launch_schedule.delay(sdr_id)

    return


@celery.task()
def update_phantom_buster_launch_schedule(
    client_sdr_id: int, custom_volume: Optional[int] = None
):
    # Get the ClientSDR
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)

    # Update the PhantomBuster to reflect the new SLA target
    config: PhantomBusterConfig = PhantomBusterConfig.query.filter(
        PhantomBusterConfig.client_sdr_id == client_sdr_id,
        PhantomBusterConfig.pb_type == PhantomBusterType.OUTBOUND_ENGINE,
    ).first()
    if not config:
        send_slack_message(
            message="PhantomBuster config not found for *{}* (#{})".format(
                client_sdr.name,
                client_sdr.id,
            ),
            webhook_urls=[URL_MAP["operations-sla-updater"]],
        )
        return False, "PhantomBuster config not found"
    pb_agent: PhantomBusterAgent = PhantomBusterAgent(id=config.phantom_uuid)
    result = pb_agent.update_launch_schedule(custom_volume=custom_volume)

    if result:
        send_slack_message(
            message="PhantomBuster *{}* (#{}) updated according to SLA schedule. Outbound: {}. Warmup target {}: {}".format(
                client_sdr.name,
                client_sdr.id,
                result.get("actual_target"),
                (
                    "✅"
                    if result.get("actual_target")
                    >= client_sdr.weekly_li_outbound_target
                    else "❌"
                ),
                client_sdr.weekly_li_outbound_target,
            ),
            webhook_urls=[URL_MAP["operations-sla-updater"]],
        )
        return True, "PhantomBuster launch schedule updated"

    send_slack_message(
        message="🚨 PhantomBuster *{}* (#{}) failed to update. Investigate.".format(
            client_sdr.name, client_sdr.id, result.get("actual_target")
        ),
        webhook_urls=[URL_MAP["operations-sla-updater"]],
    )
    return False, "PhantomBuster launch schedule failed to update"


def update_do_not_contact_filters(
    client_id: int,
    do_not_contact_keywords_in_company_names: list[str],
    do_not_contact_company_names: list[str],
    do_not_contact_industries: list[str],
    do_not_contact_location_keywords: list[str],
    do_not_contact_titles: list[str],
    do_not_contact_prospect_location_keywords: list[str],
    do_not_contact_people_names: list[str],
    do_not_contact_emails: list[str],
):
    """Update the do not contact keywords list for a Client

    Args:
        client_id (int): ID of the Client
        do_not_contact_keywords (list[str]): List of do not contact keywords

    Returns:
        bool: True if successful, None otherwise
    """
    client: Client = Client.query.get(client_id)
    if not client:
        return None

    client.do_not_contact_keywords_in_company_names = (
        do_not_contact_keywords_in_company_names
    )
    client.do_not_contact_company_names = do_not_contact_company_names
    client.do_not_contact_industries = do_not_contact_industries
    client.do_not_contact_location_keywords = do_not_contact_location_keywords
    client.do_not_contact_titles = do_not_contact_titles
    client.do_not_contact_prospect_location_keywords = (
        do_not_contact_prospect_location_keywords
    )
    client.do_not_contact_people_names = do_not_contact_people_names
    client.do_not_contact_emails = do_not_contact_emails

    db.session.add(client)
    db.session.commit()

    return True


def get_do_not_contact_filters(client_id: int):
    """Get the do not contact keywords list for a Client

    Args:
        client_id (int): ID of the Client

    Returns:
        list[str]: List of do not contact keywords
    """
    client: Client = Client.query.get(client_id)
    if not client:
        return None

    return {
        "do_not_contact_keywords_in_company_names": client.do_not_contact_keywords_in_company_names,
        "do_not_contact_company_names": client.do_not_contact_company_names,
        "do_not_contact_industries": client.do_not_contact_industries,
        "do_not_contact_location_keywords": client.do_not_contact_location_keywords,
        "do_not_contact_titles": client.do_not_contact_titles,
        "do_not_contact_prospect_location_keywords": client.do_not_contact_prospect_location_keywords,
        "do_not_contact_people_names": client.do_not_contact_people_names,
        "do_not_contact_emails": client.do_not_contact_emails,
    }


def update_sdr_do_not_contact_filters(
    client_sdr_id: int,
    do_not_contact_keywords_in_company_names: list[str],
    do_not_contact_company_names: list[str],
    do_not_contact_industries: list[str],
    do_not_contact_location_keywords: list[str],
    do_not_contact_titles: list[str],
    do_not_contact_prospect_location_keywords: list[str],
    do_not_contact_people_names: list[str],
    do_not_contact_emails: list[str],
):
    """Update the do not contact keywords list for a Client SDR

    Args:
        client_sdr_id (int): ID of the Client SDR
        do_not_contact_keywords (list[str]): List of do not contact keywords

    Returns:
        bool: True if successful, None otherwise
    """
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if not client_sdr:
        return None

    client_sdr.do_not_contact_keywords_in_company_names = (
        do_not_contact_keywords_in_company_names
    )
    client_sdr.do_not_contact_company_names = do_not_contact_company_names
    client_sdr.do_not_contact_industries = do_not_contact_industries
    client_sdr.do_not_contact_location_keywords = do_not_contact_location_keywords
    client_sdr.do_not_contact_titles = do_not_contact_titles
    client_sdr.do_not_contact_prospect_location_keywords = (
        do_not_contact_prospect_location_keywords
    )
    client_sdr.do_not_contact_people_names = do_not_contact_people_names
    client_sdr.do_not_contact_emails = do_not_contact_emails

    db.session.add(client_sdr)
    db.session.commit()

    return True


def get_sdr_do_not_contact_filters(client_sdr_id: int):
    """Get the do not contact keywords list for a Client SDR

    Args:
        client_sdr_id (int): ID of the Client SDR

    Returns:
        list[str]: List of do not contact keywords
    """
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if not client_sdr:
        return None

    return {
        "do_not_contact_keywords_in_company_names": client_sdr.do_not_contact_keywords_in_company_names,
        "do_not_contact_company_names": client_sdr.do_not_contact_company_names,
        "do_not_contact_industries": client_sdr.do_not_contact_industries,
        "do_not_contact_location_keywords": client_sdr.do_not_contact_location_keywords,
        "do_not_contact_titles": client_sdr.do_not_contact_titles,
        "do_not_contact_prospect_location_keywords": client_sdr.do_not_contact_prospect_location_keywords,
        "do_not_contact_people_names": client_sdr.do_not_contact_people_names,
        "do_not_contact_emails": client_sdr.do_not_contact_emails,
    }


def submit_demo_feedback(
    client_sdr_id: int,
    client_id: int,
    prospect_id: int,
    status: str,
    rating: str,
    feedback: str,
    next_demo_date: Optional[datetime] = None,
    ai_adjustments: Optional[str] = None,
):
    """Submits demo feedback.

    If this is not the first demo feedback and contains a next demo, update prospect accordingly

    Args:
        client_sdr_id (int): Client SDR ID
        client_id (int): Client ID
        prospect_id (int): Prospect ID
        status (str): Demo status
        rating (str): Demo rating
        feedback (str): Actual demo feedback
        ai_adjustments (Optional[str], optional): AI adjustments. Defaults to None.

    Returns:
        bool: Whether it was successful or not
    """
    # Get the demo date that this feedback is referring to, otherwise use today
    prospect: Prospect = Prospect.query.get(prospect_id)
    demo_date = prospect.demo_date
    if not demo_date:
        demo_date = datetime.now()

    # Create a new DemoFeedback object
    demo_feedback = DemoFeedback(
        client_id=client_id,
        client_sdr_id=client_sdr_id,
        prospect_id=prospect_id,
        status=status,
        rating=rating,
        feedback=feedback,
        demo_date=demo_date,
        next_demo_date=next_demo_date,
        ai_adjustments=ai_adjustments,
    )

    # If next_demo_date is specified, update the prospect
    if next_demo_date:
        prospect.demo_date = next_demo_date
        db.session.add(prospect)

    db.session.add(demo_feedback)
    db.session.commit()

    return True


@celery.task
def send_demo_reminders():
    send_demo_feedback_reminder()
    send_upcoming_demo_reminder()
    pass


def send_demo_feedback_reminder():
    prospects: list[Prospect] = Prospect.query.filter(
        Prospect.demo_date != None,
        Prospect.demo_date <= datetime.now() - timedelta(days=1),
        Prospect.demo_date >= datetime.now() - timedelta(days=2),
    ).all()

    for prospect in prospects:
        sdr: ClientSDR = ClientSDR.query.get(prospect.client_sdr_id)

        # TODO(Aakash) - delete if not needed after Jan 5th, 2024
        # send_slack_message(
        #     message="New question for Demo Feedback",
        #     webhook_urls=[
        #         URL_MAP["csm-urgent-alerts"],
        #         # client.pipeline_notifications_webhook_url,
        #     ],
        #     blocks=[
        #         {
        #             "type": "header",
        #             "text": {
        #                 "type": "plain_text",
        #                 "text": f"New question for @{sdr.name}: Demo Feedback",
        #                 "emoji": True,
        #             },
        #         },
        #         {
        #             "type": "section",
        #             "text": {
        #                 "type": "mrkdwn",
        #                 "text": f"_How did the demo go with `{prospect.full_name}` on `{prospect.demo_date}`?_",
        #             },
        #         },
        #         {"type": "divider"},
        #         {
        #             "type": "context",
        #             "elements": [
        #                 {
        #                     "type": "mrkdwn",
        #                     "text": f"> ✅ *Happened:* Please rate 1/5\n> 🔴 *No show:* Would you like us to reschedule?\n> ⏳ *Rescheduled:* What date did it reschedule for?",
        #                 }
        #             ],
        #         },
        #         {
        #             "type": "section",
        #             "text": {
        #                 "type": "mrkdwn",
        #                 "text": "Answers used to improve targeting | Prospect ➡️",
        #             },
        #             "accessory": {
        #                 "type": "button",
        #                 "text": {"type": "plain_text", "text": "Link", "emoji": True},
        #                 "value": f"https://app.sellscale.com/?prospect_id={prospect.id}",
        #                 "action_id": "button-action",
        #             },
        #         },
        #     ],
        # )

        send_demo_feedback_email_reminder(prospect.id, "team@sellscale.com")


def send_demo_feedback_email_reminder(prospect_id: int, email: str):
    from src.automation.resend import send_email

    prospect: Prospect = Prospect.query.get(prospect_id)
    client_sdr: ClientSDR = ClientSDR.query.get(prospect.client_sdr_id)

    client_sdr_first_name = client_sdr.name.split(" ")[0]
    prospect_first_name = prospect.first_name
    prospect_full_name = prospect.full_name
    prospect_company = prospect.company
    prospect_demo_date_formatted = prospect.demo_date.strftime("%B %d, %Y")
    prospect_linkedin_url = prospect.linkedin_url
    if (
        "https://" not in prospect_linkedin_url
        or "http://" not in prospect_linkedin_url
    ):
        prospect_linkedin_url = f"https://{prospect_linkedin_url}"

    send_email(
        html=f"""
            <table style="width: 80%; margin: 0 auto; background-color: white;">
                <p>
                    Hi {client_sdr_first_name},
                </p>
                <p>
                    <b>I saw you had a call scheduled with {prospect_full_name} from {prospect_company} on {prospect_demo_date_formatted}.</b>
                </p>
                <table style="width: 100%; border-collapse: collapse; border: 2px solid #ccc;">
                    <p><b><i>*Can you please respond with feedback on the meeting? This will be recorded for the AI.</i></b></p>
                    <ul>
                        <li>
                            <p><b><i><u>1. 🎯 Happened</u></i></b> - please rate from one to five stars / any feedback</p>
                        </li>
                        <li>
                            <p><b><i><u>2. 👻 No show</u></i></b> - please let us know if you'd like us to reschedule</p>
                        </li>
                        <li>
                            <p><b><i><u>3.  Rescheduled</u></i></b> - please let us know what date it rescheduled to</p>
                        </li>
                    </ul>
                </table>

                <p>
                    <u>More context</u>
                    <ul>
                        <li>We saw you had a meeting set with <a href="{prospect_linkedin_url}">{prospect_first_name} from {prospect_company}</a> on {prospect_demo_date_formatted}.</li>
                        <li>Any feedback you give will be used to help for future sets</li>
                        <li>This feedback is critical to improve the AI/services
                    </ul>
                </p>

                <p>
                    SellScale AI
                </p>
            </table>
        """,
        title="demo feedback request".format(
            prospect_full_name=prospect_full_name,
            prospect_first_name=prospect_first_name,
            prospect_company=prospect_company,
            prospect_demo_date_formatted=prospect_demo_date_formatted,
            prospect_linkedin_url=prospect_linkedin_url,
        ),
        to_emails=[email],
    )

    create_operator_dashboard_entry(
        client_sdr_id=prospect.client_sdr_id,
        urgency=OperatorDashboardEntryPriority.MEDIUM,
        tag="demo_feedback_{prospect_id}".format(prospect_id=prospect_id),
        emoji="📋",
        title="Requesting demo feedback",
        subtitle="How did the demo with {prospect_full_name} on {prospect_demo_date_formatted} go?".format(
            prospect_full_name=prospect_full_name,
            prospect_demo_date_formatted=prospect_demo_date_formatted,
        ),
        cta="Give feedback",
        cta_url="/prospects/{prospect_id}".format(prospect_id=prospect_id),
        status=OperatorDashboardEntryStatus.PENDING,
        due_date=datetime.now() + timedelta(days=5),
        task_type=OperatorDashboardTaskType.DEMO_FEEDBACK_NEEDED,
        task_data={
            "prospect_id": prospect_id,
            "prospect_full_name": prospect_full_name,
            "prospect_demo_date_formatted": prospect_demo_date_formatted,
        },
    )


def send_upcoming_demo_reminder():
    prospects: list[Prospect] = Prospect.query.filter(
        Prospect.demo_date != None,
        Prospect.demo_date > datetime.now(),
        Prospect.demo_date <= datetime.now() + timedelta(days=1),
        Prospect.send_reminder == True,
    ).all()

    for prospect in prospects:
        sdr: ClientSDR = ClientSDR.query.get(prospect.client_sdr_id)
        send_slack_message(
            message="Demo reminder",
            webhook_urls=[
                URL_MAP["csm-urgent-alerts"],
                # client.pipeline_notifications_webhook_url,
            ],
            blocks=[
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"Demo reminder with {prospect.full_name}",
                        "emoji": True,
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"_SellScale AI just sent a demo reminder message to {prospect.full_name} for their demo on {prospect.demo_date.strftime('%B %d, %Y')}._",
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*SDR*: {sdr.name}",
                    },
                },
                {"type": "divider"},
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "Prospect ➡️",
                    },
                    "accessory": {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Link", "emoji": True},
                        "value": f"https://app.sellscale.com/?prospect_id={prospect.id}",
                        "action_id": "button-action",
                    },
                },
            ],
        )

        client_sdr_id: int = prospect.client_sdr_id
        prospect_id: int = prospect.id
        first_name: str = prospect.first_name
        add_process_for_future(
            type="send_scheduled_linkedin_message",
            args={
                "client_sdr_id": client_sdr_id,
                "prospect_id": prospect_id,
                "message": "Hi {first_name}, just a quick reminder about our call tomorrow. Looking forward to it!".format(
                    first_name=first_name
                ),
                "ai_generated": True,
            },
            relative_time=datetime.utcnow(),
        )


def get_all_demo_feedback(client_sdr_id: int):
    """Gets all demo feedback for a client SDR

    Args:
        client_sdr_id (int): Client SDR ID

    Returns:
        DemoFeedback[]: List of demo feedbacks
    """

    demo_feedback: List[DemoFeedback] = DemoFeedback.query.filter(
        DemoFeedback.client_sdr_id == client_sdr_id
    ).all()

    return demo_feedback


def get_demo_feedback(client_sdr_id: int, prospect_id: int) -> list[DemoFeedback]:
    """Get demo feedback for a prospect

    Args:
        client_sdr_id (int): Client SDR ID
        prospect_id (int): Prospect ID

    Returns:
        list[DemoFeedback}: List of Demo feedback
    """

    demo_feedback: list[DemoFeedback] = (
        DemoFeedback.query.filter(
            DemoFeedback.client_sdr_id == client_sdr_id,
            DemoFeedback.prospect_id == prospect_id,
        )
        .order_by(DemoFeedback.id.asc())
        .all()
    )

    return demo_feedback


def edit_demo_feedback(
    client_sdr_id: int,
    demo_feedback_id: int,
    status: Optional[str] = None,
    rating: Optional[str] = None,
    feedback: Optional[str] = None,
    next_demo_date: Optional[datetime] = None,
    ai_adjustments: Optional[str] = None,
) -> bool:
    """Edit demo feedback

    Args:
        client_sdr_id (int): Client SDR ID
        demo_feedback_id (int): Demo feedback ID
        status (Optional[str], optional): Demo status. Defaults to None.
        rating (Optional[str], optional): Demo rating. Defaults to None.
        feedback (Optional[str], optional): Demo feedback. Defaults to None.
        next_demo_date (Optional[datetime], optional): Next demo date. Defaults to None.
        ai_adjustments (Optional[str], optional): AI adjustments. Defaults to None.

    Returns:
        bool: Whether it was successful or not
    """
    demo_feedback: DemoFeedback = DemoFeedback.query.get(demo_feedback_id)
    if not demo_feedback:
        return False

    if status:
        demo_feedback.status = status
    if rating:
        demo_feedback.rating = rating
    if feedback:
        demo_feedback.feedback = feedback
    if next_demo_date:
        demo_feedback.next_demo_date = next_demo_date
    if ai_adjustments:
        demo_feedback.ai_adjustments = ai_adjustments

    # If next_demo_date is specified, and this feedback is the most recent, update the prospect
    if next_demo_date:
        most_recent_demo_feedback: DemoFeedback = (
            DemoFeedback.query.filter(
                DemoFeedback.client_sdr_id == client_sdr_id,
                DemoFeedback.prospect_id == demo_feedback.prospect_id,
            )
            .order_by(DemoFeedback.id.desc())
            .first()
        )
        if most_recent_demo_feedback.id == demo_feedback.id:
            prospect: Prospect = Prospect.query.get(demo_feedback.prospect_id)
            prospect.demo_date = next_demo_date
            db.session.add(prospect)

    db.session.add(demo_feedback)
    db.session.commit()

    return True


@celery.task
def scrape_for_demos() -> int:
    """Recurring job which will scrape for Prospects that have a demo_date set but no demo feedback

    Returns:
        int: Number of demos scraped
    """
    # Initialize missing count
    missing_count = 0

    # If it is currently the weekend, return
    if datetime.now().weekday() >= 5:
        return missing_count

    # Get all prospects that have a demo_date set (in the past) but no demo feedback
    prospects = (
        db.session.query(Prospect.id.label("prospect_id"))
        .outerjoin(DemoFeedback, Prospect.id == DemoFeedback.prospect_id)
        .outerjoin(ClientSDR, Prospect.client_sdr_id == ClientSDR.id)
        .outerjoin(Client, Prospect.client_id == Client.id)
        .filter(
            DemoFeedback.prospect_id == None,
            Prospect.demo_date != None,
            Prospect.demo_date > datetime.now() - timedelta(days=7),
            ClientSDR.active == True,
            Client.active == True,
        )
    ).all()

    if len(prospects) == 0:
        send_slack_message(
            message="🎉 No missing feedback, yay!",
            webhook_urls=[URL_MAP["csm-demo-date"]],
        )
        return missing_count

    # Send message to Slack
    for prospect in prospects:
        prospect_id = prospect.prospect_id
        prospect: Prospect = Prospect.query.get(prospect_id)
        if not prospect:
            continue
        sdr: ClientSDR = ClientSDR.query.get(prospect.client_sdr_id)
        if not sdr:
            continue
        client: Client = Client.query.get(sdr.client_id)
        if not client:
            continue

        missing_count += 1

        direct_link = "https://app.sellscale.com/authenticate?stytch_token_type=direct&token={auth_token}&redirect=prospects/{prospect_id}".format(
            auth_token=sdr.auth_token,
            prospect_id=prospect_id,
        )

        # Send message to Slack
        send_slack_message(
            message="📅 {sdr_name} - Demo feedback missing for {prospect_name}".format(
                sdr_name=sdr.name, prospect_name=prospect.full_name
            ),
            webhook_urls=[URL_MAP["csm-demo-date"]],
            blocks=[
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "📅 ⏰ {sdr_name} - Demo feedback missing for {prospect_name}".format(
                            sdr_name=sdr.name, prospect_name=prospect.full_name
                        ),
                        "emoji": True,
                    },
                },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": "*{sdr_name}* (*{client_name}*) scheduled demo for *{date}*".format(
                                sdr_name=sdr.name,
                                client_name=client.company,
                                date=prospect.demo_date.strftime("%b %d, %Y"),
                            ),
                        },
                    ],
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "Collect feedback through #sdr-concierge or reschedule.\n<{direct_link}|Click here to go to the prospect's page>".format(
                            direct_link=direct_link
                        ),
                    },
                },
            ],
        )

    return missing_count


def list_prospects_caught_by_client_filters(client_sdr_id: int):
    """Get the prospects caught by the do not contact filters for a Client.
    Checks if the prospect's company's name is not ilike any of the do not contact companies
    and checks if the company name is not ilike any of the do not contact keywords.
    """
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client_id = client_sdr.client_id

    client: Client = Client.query.get(client_id)
    if not client:
        return None

    if (
        not client.do_not_contact_company_names
        and not client.do_not_contact_keywords_in_company_names
        and not client.do_not_contact_industries
        and not client.do_not_contact_location_keywords
        and not client.do_not_contact_titles
        and not client.do_not_contact_prospect_location_keywords
        and not client.do_not_contact_people_names
        and not client.do_not_contact_emails
    ):
        return []

    allStatuses = [status.name for status in ProspectOverallStatus]
    # allStatuses.remove(ProspectOverallStatus.REMOVED.name)
    allStatuses.remove(ProspectOverallStatus.DEMO.name)

    prospects_with_locations: list = (
        Prospect.query.filter(
            Prospect.client_id == client_id,
            Prospect.overall_status.in_(allStatuses),
            or_(
                *(
                    [
                        Prospect.company.ilike(f"%{company}%")
                        for company in client.do_not_contact_company_names
                    ]
                    + [
                        Prospect.company.ilike(f"%{keyword}%")
                        for keyword in client.do_not_contact_keywords_in_company_names
                    ]
                    + [
                        Prospect.industry.ilike(f"%{industry}%")
                        for industry in client.do_not_contact_industries or []
                    ]
                    + [
                        Prospect.title.ilike(f"%{title}%")
                        for title in client.do_not_contact_titles or []
                    ]
                    + [
                        Prospect.company_location.ilike(f"%{location}%")
                        for location in client.do_not_contact_location_keywords or []
                    ]
                    + [
                        Prospect.prospect_location.ilike(f"%{location}%")
                        for location in client.do_not_contact_prospect_location_keywords
                        or []
                    ]
                    + [
                        Prospect.email.ilike(f"%{email}%")
                        for email in client.do_not_contact_emails or []
                    ]
                    + [
                        Prospect.full_name.ilike(f"%{name}%")
                        for name in client.do_not_contact_people_names or []
                    ]
                )
            ),
        )
        .order_by(Prospect.id.desc())
        .all()
    )

    # add another column to every entry called 'matched filter' and set it to the filter(s) that matched in an array.
    #   also mentioned which specific word matched
    prospect_dicts = []
    for p in prospects_with_locations:
        prospect: Prospect = p
        prospect_dict = prospect.simple_to_dict()

        # Your existing logic to add matched filters
        matched_filters = []
        matched_filter_words = []
        if client.do_not_contact_company_names:
            for company in client.do_not_contact_company_names:
                if (
                    prospect_dict["company"]
                    and company
                    and company.lower() in prospect_dict["company"].lower()
                ):
                    matched_filters.append("Company Name")
                    matched_filter_words.append("Company: " + company)
        if client.do_not_contact_keywords_in_company_names:
            for keyword in client.do_not_contact_keywords_in_company_names:
                if (
                    prospect_dict["company"]
                    and keyword
                    and keyword.lower() in prospect_dict["company"].lower()
                ):
                    matched_filters.append("Company Keyword")
                    matched_filter_words.append("Keyword: " + keyword)
        if client.do_not_contact_industries:
            for industry in client.do_not_contact_industries:
                if (
                    prospect_dict["industry"]
                    and industry
                    and industry.lower() in prospect_dict["industry"].lower()
                ):
                    matched_filters.append("Industry")
                    matched_filter_words.append("Industry: " + industry)
        if client.do_not_contact_titles:
            for title in client.do_not_contact_titles:
                if (
                    prospect_dict["title"]
                    and title
                    and title.lower() in prospect_dict["title"].lower()
                ):
                    matched_filters.append("Title")
                    matched_filter_words.append("Title: " + title)
        if client.do_not_contact_location_keywords:
            for location in client.do_not_contact_location_keywords:
                if (
                    prospect_dict["company_location"]
                    and location.lower() in prospect_dict["company_location"].lower()
                ):
                    matched_filters.append("Location")
                    matched_filter_words.append("Company Location: " + location)
        if client.do_not_contact_prospect_location_keywords:
            for location in client.do_not_contact_prospect_location_keywords:
                if (
                    prospect_dict["prospect_location"]
                    and location.lower() in prospect_dict["prospect_location"].lower()
                ):
                    matched_filters.append("Prospect Location")
                    matched_filter_words.append("Prospect Location: " + location)
        if client.do_not_contact_emails:
            for email in client.do_not_contact_emails:
                if (
                    prospect_dict["email"]
                    and email
                    and email.lower() in prospect_dict["email"].lower()
                ):
                    matched_filters.append("Email")
                    matched_filter_words.append("Email: " + email)
        if client.do_not_contact_people_names:
            for name in client.do_not_contact_people_names:
                if (
                    prospect_dict["full_name"]
                    and name
                    and name.lower() in prospect_dict["full_name"].lower()
                ):
                    matched_filters.append("Name")
                    matched_filter_words.append("Name: " + name)
        prospect_dict["matched_filters"] = matched_filters
        prospect_dict["matched_filter_words"] = matched_filter_words

        prospect_dicts.append(prospect_dict)

    return prospect_dicts


@celery.task
def remove_prospects_caught_by_filters(client_sdr_id: int):
    remove_prospects_caught_by_client_filters(client_sdr_id)
    remove_prospects_caught_by_sdr_client_filters(client_sdr_id)


@celery.task
def mark_prospect_removed(prospect_id: int):
    prospect: Prospect = Prospect.query.get(prospect_id)
    prospect.overall_status = ProspectOverallStatus.REMOVED
    prospect.status = ProspectStatus.NOT_QUALIFIED

    db.session.add(prospect)
    db.session.commit()

    return True


def remove_prospects_caught_by_client_filters(client_sdr_id: int):
    """Remove the prospects caught by the do not contact filters for a Client.
    Checks if the prospect's company's name is not ilike any of the do not contact companies
    and checks if the company name is not ilike any of the do not contact keywords.
    """
    prospect_dicts = list_prospects_caught_by_client_filters(client_sdr_id)
    prospect_ids = (
        [prospect["id"] for prospect in prospect_dicts] if prospect_dicts else []
    )
    for prospect_id in prospect_ids:
        mark_prospect_removed.delay(prospect_id)

    return True


def list_prospects_caught_by_sdr_client_filters(client_sdr_id: int):
    """Get the prospects caught by the do not contact filters for a Client SDR.
    Checks if the prospect's company's name is not ilike any of the do not contact companies
    and checks if the company name is not ilike any of the do not contact keywords.
    """
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)

    if (
        not client_sdr.do_not_contact_company_names
        and not client_sdr.do_not_contact_keywords_in_company_names
        and not client_sdr.do_not_contact_industries
        and not client_sdr.do_not_contact_location_keywords
        and not client_sdr.do_not_contact_titles
        and not client_sdr.do_not_contact_prospect_location_keywords
        and not client_sdr.do_not_contact_people_names
        and not client_sdr.do_not_contact_emails
    ):
        return []

    allStatuses = [status.name for status in ProspectOverallStatus]
    # allStatuses.remove(ProspectOverallStatus.REMOVED.name)
    allStatuses.remove(ProspectOverallStatus.DEMO.name)
    prospects_with_locations: list = Prospect.query.filter(
        Prospect.client_sdr_id == client_sdr_id,
        Prospect.overall_status.in_(allStatuses),
        or_(
            *(
                [
                    Prospect.company.ilike(f"%{company}%")
                    for company in client_sdr.do_not_contact_company_names
                ]
                + [
                    Prospect.company.ilike(f"%{keyword}%")
                    for keyword in client_sdr.do_not_contact_keywords_in_company_names
                ]
                + [
                    Prospect.industry.ilike(f"%{industry}%")
                    for industry in client_sdr.do_not_contact_industries or []
                ]
                + [
                    Prospect.title.ilike(f"%{title}%")
                    for title in client_sdr.do_not_contact_titles or []
                ]
                + [
                    Prospect.company_location.ilike(f"%{location}%")
                    for location in client_sdr.do_not_contact_location_keywords or []
                ]
                + [
                    Prospect.prospect_location.ilike(f"%{location}%")
                    for location in client_sdr.do_not_contact_prospect_location_keywords
                    or []
                ]
                + [
                    Prospect.email.ilike(f"%{email}%")
                    for email in client_sdr.do_not_contact_emails or []
                ]
                + [
                    Prospect.full_name.ilike(f"%{name}%")
                    for name in client_sdr.do_not_contact_people_names or []
                ]
            )
        ),
    ).all()

    # add another column to every entry called 'matched filter' and set it to the filter(s) that matched in an array.
    #   also mentioned which specific word matched
    prospect_dicts = []
    for prospect in prospects_with_locations:
        prospect_dict = prospect.simple_to_dict()

        matched_filters = []
        matched_filter_words = []
        if client_sdr.do_not_contact_company_names:
            for company in client_sdr.do_not_contact_company_names:
                if company.lower() in prospect_dict["company"].lower():
                    matched_filters.append("Company Name")
                    matched_filter_words.append(company)
        if client_sdr.do_not_contact_keywords_in_company_names:
            for keyword in client_sdr.do_not_contact_keywords_in_company_names:
                if keyword.lower() in prospect_dict["company"].lower():
                    matched_filters.append("Company Keyword")
                    matched_filter_words.append(keyword)
        if client_sdr.do_not_contact_industries:
            for industry in client_sdr.do_not_contact_industries:
                if industry.lower() in prospect_dict["industry"].lower():
                    matched_filters.append("Industry")
                    matched_filter_words.append(industry)
        if client_sdr.do_not_contact_titles:
            for title in client_sdr.do_not_contact_titles:
                if title.lower() in prospect_dict["title"].lower():
                    matched_filters.append("Title")
                    matched_filter_words.append(title)
        if client_sdr.do_not_contact_location_keywords:
            for location in client_sdr.do_not_contact_location_keywords:
                if (
                    prospect_dict["company_location"]
                    and location.lower() in prospect_dict["company_location"].lower()
                ):
                    matched_filters.append("Location")
                    matched_filter_words.append(location)
        if client_sdr.do_not_contact_prospect_location_keywords:
            for location in client_sdr.do_not_contact_prospect_location_keywords:
                if (
                    prospect_dict["prospect_location"]
                    and location.lower() in prospect_dict["prospect_location"].lower()
                ):
                    matched_filters.append("Prospect Location")
                    matched_filter_words.append(location)
        if client_sdr.do_not_contact_emails:
            for email in client_sdr.do_not_contact_emails:
                if email.lower() in prospect_dict["email"].lower():
                    matched_filters.append("Email")
                    matched_filter_words.append(email)
        if client_sdr.do_not_contact_people_names:
            for name in client_sdr.do_not_contact_people_names:
                if name.lower() in prospect_dict["full_name"].lower():
                    matched_filters.append("Name")
                    matched_filter_words.append(name)
        prospect_dict["matched_filters"] = matched_filters
        prospect_dict["matched_filter_words"] = matched_filter_words

        prospect_dicts.append(prospect_dict)

    return prospect_dicts


def remove_prospects_caught_by_sdr_client_filters(client_sdr_id: int):
    """Remove the prospects caught by the do not contact filters for a Client SDR.
    Checks if the prospect's company's name is not ilike any of the do not contact companies
    and checks if the company name is not ilike any of the do not contact keywords.
    """
    prospect_dicts = list_prospects_caught_by_sdr_client_filters(client_sdr_id)
    prospect_ids = (
        [prospect["id"] for prospect in prospect_dicts] if prospect_dicts else []
    )
    prospects = Prospect.query.filter(Prospect.id.in_(prospect_ids)).all()

    bulk_updated_prospects = []

    for prospect in prospects:
        prospect.overall_status = ProspectOverallStatus.REMOVED
        prospect.status = ProspectStatus.NOT_QUALIFIED

        bulk_updated_prospects.append(prospect)

    db.session.bulk_save_objects(bulk_updated_prospects)
    db.session.commit()

    return True


def get_personas_page_details(client_sdr_id: int):
    """Gets just the details needed for the personas page

    Returns: List of details for each persona
    """

    query = (
        db.session.query(
            ClientArchetype.id,
            ClientArchetype.archetype.label("name"),
            ClientArchetype.active,
            ClientArchetype.emoji,
            ClientArchetype.icp_matching_prompt,
            ClientArchetype.icp_matching_option_filters,
            ClientArchetype.is_unassigned_contact_archetype,
            ClientArchetype.persona_fit_reason,
            ClientArchetype.persona_contact_objective,
            ClientArchetype.contract_size,
            ClientArchetype.transformer_blocklist,
            ClientArchetype.transformer_blocklist_initial,
            ClientArchetype.li_bump_amount,
            ClientArchetype.template_mode,
            ClientArchetype.persona_cta_framework_company.label(
                "cta_framework_company"
            ),
            ClientArchetype.persona_cta_framework_persona.label(
                "cta_framework_persona"
            ),
            ClientArchetype.persona_cta_framework_action.label("cta_framework_action"),
            ClientArchetype.persona_use_cases.label("use_cases"),
            ClientArchetype.persona_filters.label("filters"),
            ClientArchetype.persona_lookalike_profile_1.label("lookalike_profile_1"),
            ClientArchetype.persona_lookalike_profile_2.label("lookalike_profile_2"),
            ClientArchetype.persona_lookalike_profile_3.label("lookalike_profile_3"),
            ClientArchetype.persona_lookalike_profile_4.label("lookalike_profile_4"),
            ClientArchetype.persona_lookalike_profile_5.label("lookalike_profile_5"),
            ClientArchetype.smartlead_campaign_id,
            ClientArchetype.meta_data,
            ClientArchetype.first_message_delay_days,
            func.count(distinct(Prospect.id)).label("num_prospects"),
            func.avg(Prospect.icp_fit_score)
            .filter(Prospect.icp_fit_score.isnot(None))
            .filter(Prospect.icp_fit_score >= 0)
            .filter(Prospect.overall_status == "PROSPECTED")
            .label("avg_icp_fit_score"),
            func.count(distinct(Prospect.id))
            .filter(Prospect.approved_outreach_message_id.is_(None))
            .filter(
                Prospect.overall_status.in_(
                    [
                        ProspectOverallStatus.PROSPECTED,
                        ProspectOverallStatus.SENT_OUTREACH,
                    ]
                )
            )
            .label("num_unused_li_prospects"),
            func.count(distinct(Prospect.id))
            .filter(Prospect.approved_prospect_email_id.is_(None))
            .filter(
                Prospect.overall_status.notin_(
                    [
                        ProspectOverallStatus.PROSPECTED,
                        ProspectOverallStatus.SENT_OUTREACH,
                    ]
                )
            )
            .label("num_unused_email_prospects"),
            ClientArchetype.email_active,
            ClientArchetype.email_link_tracking_enabled,
            ClientArchetype.email_open_tracking_enabled,
            ClientArchetype.linkedin_active,
        )
        .select_from(ClientArchetype)
        .join(Prospect, Prospect.archetype_id == ClientArchetype.id, isouter=True)
        .filter(ClientArchetype.client_sdr_id == client_sdr_id)
        .group_by(
            ClientArchetype.id,
            ClientArchetype.archetype,
            ClientArchetype.active,
            ClientArchetype.is_unassigned_contact_archetype,
        )
        .order_by(ClientArchetype.active.desc(), ClientArchetype.archetype.desc())
    )

    results = query.all()

    json_results = []
    for row in results:
        row_dict = row._asdict()
        for key, value in row_dict.items():
            if isinstance(value, list):
                row_dict[key] = [x.value if isinstance(x, Enum) else x for x in value]
        json_results.append(row_dict)

    return json_results


def get_personas_page_campaigns(client_sdr_id: int) -> dict:
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client_id = client_sdr.client_id

    results = db.session.execute(
        """
        SELECT
            client_archetype.archetype,
            client_archetype.id,
            client_archetype.created_at,
            client_archetype.active,
            client_archetype.linkedin_active,
            client_archetype.email_active,
            client_sdr.name,
            client_sdr.img_url,
            client_sdr.id client_sdr_id,
            count(DISTINCT prospect.id) FILTER (WHERE prospect_email_status_records.to_status = 'SENT_OUTREACH') "EMAIL-SENT",
            count(DISTINCT prospect.id) FILTER (WHERE prospect_email_status_records.to_status = 'EMAIL_OPENED') "EMAIL-OPENED",
            count(DISTINCT prospect.id) FILTER (WHERE prospect_email_status_records.to_status = 'ACTIVE_CONVO') "EMAIL-REPLY",
            count(DISTINCT prospect.id) FILTER (WHERE prospect_status_records.to_status = 'SENT_OUTREACH') "LI-SENT",
            count(DISTINCT prospect.id) FILTER (WHERE prospect_status_records.to_status = 'ACCEPTED') "LI-OPENED",
            count(DISTINCT prospect.id) FILTER (WHERE prospect_status_records.to_status = 'ACTIVE_CONVO') "LI-REPLY",
            count(DISTINCT prospect.id) FILTER (WHERE prospect_status_records.to_status in ('DEMO_SET', 'DEMO_WON')) "LI-DEMO",
            client_archetype.emoji,
            count(DISTINCT prospect.id) FILTER (WHERE prospect_email_status_records.to_status = 'SENT_OUTREACH' OR prospect_status_records.to_status = 'SENT_OUTREACH') "TOTAL-SENT",
            count(DISTINCT prospect.id) FILTER (WHERE prospect_email_status_records.to_status = 'EMAIL_OPENED' OR prospect_status_records.to_status = 'ACCEPTED') "TOTAL-OPENED",
            count(DISTINCT prospect.id) FILTER (WHERE prospect_email_status_records.to_status = 'ACTIVE_CONVO' OR prospect_status_records.to_status = 'ACTIVE_CONVO') "TOTAL-REPLY",
            count(DISTINCT prospect.id) FILTER (WHERE prospect_status_records.to_status in ('ACTIVE_CONVO_SCHEDULING', 'ACTIVE_CONVO_NEXT_STEPS', 'ACTIVE_CONVO_QUESTION') or prospect_email_status_records.to_status in ('ACTIVE_CONVO_QUESTION', 'ACTIVE_CONVO_NEXT_STEPS', 'ACTIVE_CONVO_SCHEDULING')) "TOTAL-POS-REPLY",
            count(DISTINCT prospect.id) FILTER (WHERE prospect_email_status_records.to_status = 'DEMO_SET' OR prospect_status_records.to_status = 'DEMO_SET') "TOTAL-DEMO",
            count(DISTINCT prospect.id) "TOTAL-PROSPECTS",
            client_archetype.smartlead_campaign_id,
            client_archetype.meta_data,
            client_archetype.first_message_delay_days
        FROM
            client_archetype
            JOIN client_sdr ON client_sdr.id = client_archetype.client_sdr_id
            LEFT JOIN prospect ON prospect.archetype_id = client_archetype.id
            LEFT JOIN prospect_email ON prospect_email.id = prospect.approved_prospect_email_id
            LEFT JOIN prospect_status_records ON prospect_status_records.prospect_id = prospect.id
            LEFT JOIN prospect_email_status_records ON prospect_email_status_records.prospect_email_id = prospect_email.id
        WHERE
            client_archetype.client_id = {client_id}
        GROUP BY
            2, client_sdr.name, client_sdr.img_url, client_sdr.id, client_archetype.emoji
        """.format(
            client_id=client_id
        )
    ).fetchall()

    # index to column
    column_map = {
        0: "name",
        1: "id",
        2: "created_at",
        3: "active",
        4: "linkedin_active",
        5: "email_active",
        6: "sdr_name",
        7: "sdr_img_url",
        8: "sdr_id",
        9: "email_sent",
        10: "email_opened",
        11: "email_replied",
        12: "li_sent",
        13: "li_opened",
        14: "li_replied",
        15: "li_demo",
        16: "emoji",
        17: "total_sent",
        18: "total_opened",
        19: "total_replied",
        20: "total_pos_replied",
        21: "total_demo",
        22: "total_prospects",
        23: "smartlead_campaign_id",
        24: "meta_data",
        25: "first_message_delay_days",
    }

    # Convert and format output
    results = [
        {column_map.get(i, "unknown"): value for i, value in enumerate(tuple(row))}
        for row in results
    ]

    return {"message": "Success", "status_code": 200, "data": results}


def add_client_product(
    client_sdr_id: int,
    name: str,
    description: str,
    how_it_works: Optional[str],
    use_cases: Optional[str],
    product_url: Optional[str],
):
    """Adds a client product"""

    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)

    client_product = ClientProduct(
        client_id=client_sdr.client_id,
        name=name,
        description=description,
        how_it_works=how_it_works,
        use_cases=use_cases,
        product_url=product_url,
    )
    db.session.add(client_product)
    db.session.commit()

    return True


def update_client_product(
    client_sdr_id: int,
    client_product_id: int,
    name: Optional[str],
    description: Optional[str],
    how_it_works: Optional[str],
    use_cases: Optional[str],
    product_url: Optional[str],
):
    """Updates a client product"""

    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)

    client_product = ClientProduct.query.get(client_product_id)
    if not client_product or client_product.client_id != client_sdr.client_id:
        return False

    if name:
        client_product.name = name
    if description:
        client_product.description = description
    if how_it_works:
        client_product.how_it_works = how_it_works
    if use_cases:
        client_product.use_cases = use_cases
    if product_url:
        client_product.product_url = product_url

    db.session.add(client_product)
    db.session.commit()

    return True


def remove_client_product(client_sdr_id: int, client_product_id: int):
    """Removes a client product"""

    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)

    client_product = ClientProduct.query.get(client_product_id)
    if not client_product or client_product.client_id != client_sdr.client_id:
        return False

    db.session.delete(client_product)
    db.session.commit()

    return True


def get_client_products(client_sdr_id: int):
    """Gets all client products"""

    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)

    client_products = ClientProduct.query.filter(
        ClientProduct.client_id == client_sdr.client_id
    ).all()

    return [client_product.to_dict() for client_product in client_products]


def get_demo_feedback_for_client(client_id: int):
    """
    Given a client_id, get all demo feedback for that client
    """
    client_sdr_ids = [
        client_sdr.id for client_sdr in ClientSDR.query.filter_by(client_id=client_id)
    ]
    return get_demo_feedback_for_client_sdrs(client_sdr_ids)


def get_demo_feedback_for_client_sdrs(client_sdr_ids: list[int]):
    """
    Given a list of client_sdr_ids, get all demo feedback for those client_sdr_ids

    The demo feedback is given in the following format:
        [
            {
                prospect_id: int,
                full_name: str,
                demo_date: str,
                demo_rating: str,
                demo_feedback: str,
            }
        ]
    """
    cf = aliased(ClientSDR)

    query = (
        db.session.query(
            Prospect.id,
            Prospect.full_name,
            Prospect.demo_date,
            Prospect.company,
            func.max(DemoFeedback.rating).label("demo_rating"),
            func.max(DemoFeedback.feedback).label("demo_feedback"),
        )
        .join(cf, cf.id == Prospect.client_sdr_id)
        .outerjoin(DemoFeedback, DemoFeedback.prospect_id == Prospect.id)
        .filter(Prospect.client_sdr_id.in_(client_sdr_ids))
        .filter(Prospect.overall_status == ProspectOverallStatus.DEMO)
        .filter(DemoFeedback.rating.isnot(None))
        .filter(Prospect.demo_date.isnot(None))
        .group_by(Prospect.id, Prospect.full_name, Prospect.demo_date)
        .order_by(Prospect.demo_date.desc())
    )

    result = query.all()

    data = []
    total_demo_count = 0
    for entry in result:
        total_demo_count += 1
        data.append(
            {
                "prospect_id": entry[0],
                "full_name": entry[1],
                "demo_date": entry[2],
                "company": entry[3],
                "demo_rating": entry[4],
                "demo_feedback": entry[5],
                "total_demo_count": total_demo_count,
            }
        )

    return data


def update_client_sdr_supersight_link(client_id: int, super_sight_link: str):
    """
    Updates the supersight link for a client
    """
    client: Client = Client.query.get(client_id)
    if not client:
        return False

    client.super_sight_link = super_sight_link

    db.session.add(client)
    db.session.commit()

    return True


def onboarding_setup_completion_report(client_sdr_id: int):
    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client: Client = Client.query.get(sdr.client_id)

    archetypes: List[ClientArchetype] = ClientArchetype.query.filter(
        ClientArchetype.client_sdr_id == client_sdr_id
    ).all()

    ctas: List[GeneratedMessageCTA] = (
        db.session.query(GeneratedMessageCTA)
        .join(ClientArchetype, GeneratedMessageCTA.archetype_id == ClientArchetype.id)
        .filter(ClientArchetype.client_sdr_id == client_sdr_id)
        .all()
    )

    bump_frameworks: List[BumpFramework] = BumpFramework.query.filter(
        BumpFramework.client_sdr_id == client_sdr_id
    ).all()

    bump_frameworks_email: List[EmailSequenceStep] = EmailSequenceStep.query.filter(
        EmailSequenceStep.client_sdr_id == client_sdr_id
    ).all()

    voices: List[StackRankedMessageGenerationConfiguration] = (
        db.session.query(StackRankedMessageGenerationConfiguration)
        .join(
            ClientArchetype,
            StackRankedMessageGenerationConfiguration.archetype_id
            == ClientArchetype.id,
        )
        .filter(ClientArchetype.client_sdr_id == client_sdr_id)
        .all()
    )

    company_info = bool(
        client.company
        and client.tagline
        and client.description
        and client.mission
        and client.value_prop_key_points
        and client.tone_attributes
    )
    sdr_info = bool(sdr.name and sdr.title)
    scheduling_info = bool(sdr.scheduling_link or sdr.calendly_access_token)
    email_integration = bool(sdr.nylas_account_id is not None and sdr.nylas_active)
    linkedin_integration = bool(
        sdr.li_at_token is not None and sdr.li_at_token != "INVALID"
    )

    create_personas = len(archetypes) > 0
    linkedin_filters = False
    do_not_contact_filters = bool(
        client.do_not_contact_keywords_in_company_names is not None
        and client.do_not_contact_company_names is not None
    )

    create_linkedin_ctas = len(ctas) > 0
    voice_builder = len(voices) > 0
    bump_framework_linkedin = len(bump_frameworks) > 0
    bump_framework_email = len(bump_frameworks_email) > 0

    return {
        "general": {
            "company_info": company_info,
            "sdr_info": sdr_info,
            "scheduling_info": scheduling_info,
            "email_integration": email_integration,
            "linkedin_integration": linkedin_integration,
        },
        "persona": {
            "create_personas": create_personas,
            "linkedin_filters": linkedin_filters,
            "do_not_contact_filters": do_not_contact_filters,
        },
        "msg_gen": {
            "create_linkedin_ctas": create_linkedin_ctas,
            "voice_builder": voice_builder,
            "bump_framework_linkedin": bump_framework_linkedin,
            "bump_framework_email": bump_framework_email,
        },
    }


def get_persona_setup_status_map_for_persona(persona_id: int):
    data = db.session.execute(
        """
        select
            client_archetype.archetype,
            count(distinct prospect.id) > 10 "contacts",
            max(case when (
                client_archetype.persona_contact_objective is not null and
                client_archetype.persona_fit_reason is not null and
                client_archetype.archetype is not null
            ) then 1 else 0 end) = 1 "teach",
            count(distinct prospect.id) filter (where prospect.icp_fit_score is not null) > 1 "prioritize",
            count(distinct generated_message_cta.id) > 1 and
                count(distinct bump_framework.id) filter (where bump_framework.overall_status in ('ACCEPTED', 'BUMPED')) > 2  "linkedin",
            max(case when client_archetype.email_blocks_configuration is not null then 1 else 0 end) = 1 "email",
            count(distinct generated_message_cta.id) > 1 "linkedin-ctas",
            count(distinct bump_framework.id) filter (where bump_framework.overall_status in ('ACCEPTED', 'BUMPED')) > 2 "linkedin-bump-frameworks",
            max(case when client_archetype.email_blocks_configuration is not null then 1 else 0 end) = 1 "email-blocks"
        from client_archetype
            join prospect on prospect.archetype_id = client_archetype.id
            join generated_message_cta on generated_message_cta.archetype_id = client_archetype.id
            left join bump_framework on bump_framework.client_archetype_id = client_archetype.id and bump_framework.default
        where client_archetype.id = {persona_id}
        group by 1;
    """.format(
            persona_id=persona_id
        )
    ).fetchone()

    return {
        "contacts": data[1],
        "teach": data[2],
        "prioritize": data[3],
        "linkedin": data[4],
        "email": data[5],
        "linkedin-ctas": data[6],
        "linkedin-bump-frameworks": data[7],
        "email-blocks": data[8],
    }


def get_client_sdr_table_info(client_sdr_id: int):
    query = f"""
      select
        client_sdr.name "SDR Name",
        client.company,
        client_sdr.auth_token,
        CONCAT('https://app.sellscale.com/authenticate?stytch_token_type=direct&token=', client_sdr.auth_token,'&redirect=all/inboxes') "SDR Sight Link",
        client_sdr.auto_bump "Autobump Enabled",
        case
          when count(distinct bump_framework.id) filter (where not bump_framework.sellscale_default_generated and bump_framework.overall_status in ('ACCEPTED', 'BUMPED')) >= 4 then TRUE else FALSE end "Bump Frameworks Set Up",
        count(distinct prospect.id) filter (where prospect.overall_status = 'ACTIVE_CONVO' and prospect.archetype_id = client_archetype.id and (client_sdr.disable_ai_on_prospect_respond or client_sdr.disable_ai_on_message_send or prospect.deactivate_ai_engagement)) "SDR Needs to Clear",
        count(distinct prospect.id) filter (where prospect.overall_status = 'ACTIVE_CONVO' and prospect.archetype_id = client_archetype.id) - (count(distinct prospect.id) filter (where prospect.overall_status = 'ACTIVE_CONVO' and (client_sdr.disable_ai_on_prospect_respond or client_sdr.disable_ai_on_message_send or prospect.deactivate_ai_engagement))) "SellScale Needs to Clear",
        count(distinct prospect.id) filter (where prospect.status = 'ACTIVE_CONVO_SCHEDULING') "Is Scheduling",
        count(distinct prospect.id) filter (where prospect.overall_status = 'ACTIVE_CONVO') "Total Messages in Inbox",
        string_agg(distinct concat('- ', prospect.full_name, '  (', prospect.company, ')', chr(13)), '') filter (where prospect.overall_status = 'ACTIVE_CONVO' and (client_sdr.disable_ai_on_prospect_respond or client_sdr.disable_ai_on_message_send)) "Names of Contacts SDR Needs to Clear",
        count(distinct prospect.id) filter (where prospect.overall_status = 'DEMO' and demo_feedback.id is null and (prospect.demo_date is null or prospect.demo_date < NOW())),
        string_agg(distinct concat('- ', prospect.full_name, '  (', prospect.company, ')', chr(13)), '') filter (where prospect.overall_status = 'DEMO' and demo_feedback.id is null) "Prospects That Need Demo Feedback",
        client_sdr.id,
        client_archetype.id
      from prospect
        join client_sdr on client_sdr.id = prospect.client_sdr_id
        join client_archetype on client_archetype.client_sdr_id = client_sdr.id
        join bump_framework on bump_framework.client_archetype_id = client_archetype.id
        join client on client.id = client_archetype.client_id
        left join demo_feedback on demo_feedback.prospect_id = prospect.id
      where
        prospect.overall_status in ('ACTIVE_CONVO', 'DEMO') and
        (prospect.hidden_until < NOW() or prospect.hidden_until is null) and
        client_sdr.id = {client_sdr_id}
      group by 1,2,3,4,5,14,15
      order by 6 desc;
    """
    data = db.session.execute(query).fetchall()

    # index to column
    column_map = {
        0: "client_sdr_name",
        1: "company",
        2: "auth_token",
        3: "sight_link",
        4: "autobump_enabled",
        5: "bump_frameworks_setup",
        6: "sdr_needs_to_clear",
        7: "sellscale_needs_to_clear",
        8: "is_scheduling",
        9: "total_messages_in_inbox",
        10: "names_of_contacts_sdr_needs_to_clear",
        11: "count",
        12: "prospects_that_need_demo_feedback",
        13: "client_sdr_id",
        14: "client_archetype_id",
    }

    # Convert and format output
    data = [
        {column_map.get(i, "unknown"): value for i, value in enumerate(tuple(row))}
        for row in data
    ]

    return data


def update_archetype_emoji(archetype_id: int, emoji: str):
    archetype: ClientArchetype = ClientArchetype.query.get(archetype_id)
    if not archetype:
        return False

    archetype.emoji = emoji
    db.session.add(archetype)
    db.session.commit()
    return True


def predict_archetype_emoji(archetype_id: int):
    emojis = [
        "✌",
        "😂",
        "😝",
        "😁",
        "😱",
        "🙌",
        "🍻",
        "🔥",
        "🌈",
        "☀",
        "🎈",
        "🌹",
        "💄",
        "🎀",
        "⚽",
        "🎾",
        "🏁",
        "😡",
        "👿",
        "🐻",
        "🐶",
        "🐬",
        "🐟",
        "🍀",
        "👀",
        "🚗",
        "🍎",
        "💝",
        "💙",
        "👌",
        "😉",
        "😓",
        "😳",
        "💪",
        "🍸",
        "🔑",
        "💖",
        "🌟",
        "🎉",
        "🌺",
        "🎶",
        "👠",
        "🏈",
        "⚾",
        "🏆",
        "👽",
        "💀",
        "🐵",
        "🐮",
        "🐩",
        "🐎",
        "💣",
        "👃",
        "👂",
        "🍓",
        "💘",
        "💜",
        "👊",
        "😜",
        "😵",
        "🙏",
        "👋",
        "🚽",
        "💃",
        "💎",
        "🚀",
        "🌙",
        "🎁",
        "⛄",
        "🌊",
        "⛵",
        "🏀",
        "🎱",
        "💰",
        "👸",
        "🐰",
        "🐷",
        "🐍",
        "🐫",
        "🔫",
        "🚲",
        "🍉",
    ]
    update_archetype_emoji(archetype_id, random.choice(emojis))


def propagate_contract_value(client_id: int, new_value: int):
    # Update all archetypes and prospects with the new contract value

    client: Client = Client.query.get(client_id)
    if not client:
        return
    archetypes: list[ClientArchetype] = ClientArchetype.query.filter_by(
        client_id=client_id
    ).all()
    prospects: list[Prospect] = Prospect.query.filter_by(client_id=client_id).all()

    for archetype in archetypes:
        archetype.contract_size = new_value
        db.session.add(archetype)

    for prospect in prospects:
        prospect.contract_size = new_value
        db.session.add(prospect)

    db.session.commit()


def write_client_pre_onboarding_survey(
    client_sdr_id: int, client_id: int, key: str, value: str, retries_left: int = 3
):
    """Writes a client pre-onboarding survey response to the database"""
    try:
        client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
        client: Client = Client.query.get(client_id)
        client.pre_onboarding_survey = client.pre_onboarding_survey or {}
        client.pre_onboarding_survey[key] = value
        flag_modified(client, "pre_onboarding_survey")

        db.session.add(client)
        db.session.commit()

        sync_field_to_db(
            client_sdr_id,
            client_id,
            key,
            value,
        )

        return True
    except Exception as e:
        if retries_left > 0:
            return write_client_pre_onboarding_survey(
                client_sdr_id, client_id, key, value, retries_left - 1
            )
        else:
            return False


def sync_field_to_db(client_sdr_id: int, client_id: int, key: str, value: str):
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client: Client = Client.query.get(client_id)
    first_persona: ClientArchetype = (
        ClientArchetype.query.filter(
            ClientArchetype.client_id == client_id,
            ClientArchetype.is_unassigned_contact_archetype == False,
        )
        .order_by(ClientArchetype.created_at.asc())
        .first()
    )
    scheduling_framework: BumpFramework = (
        BumpFramework.query.filter(
            BumpFramework.client_sdr_id == client_sdr_id,
            BumpFramework.default == True,
            BumpFramework.substatus == "ACTIVE_CONVO_SCHEDULING",
        )
        .order_by(BumpFramework.created_at.asc())
        .first()
    )

    if key == "persona_name":
        first_persona.archetype = value
    if key == "persona_buy_reason":
        first_persona.persona_fit_reason = value
    if key == "persona_contact_objective":
        first_persona.persona_contact_objective = value
    if key == "cta_blanks_company":
        first_persona.persona_cta_framework_company = value
    if key == "cta_blanks_persona":
        first_persona.persona_cta_framework_persona = value
    if key == "cta_blanks_solution":
        first_persona.persona_cta_framework_action = value
    if key == "common_use_cases":
        first_persona.persona_use_cases = value
    if key == "persona_filters":
        first_persona.persona_filters = value
    if key == "persona_lookalike_1":
        first_persona.persona_lookalike_profile_1 = value
    if key == "persona_lookalike_2":
        first_persona.persona_lookalike_profile_2 = value
    if key == "persona_lookalike_3":
        first_persona.persona_lookalike_profile_3 = value
    if key == "persona_lookalike_4":
        first_persona.persona_lookalike_profile_4 = value
    if key == "persona_lookalike_5":
        first_persona.persona_lookalike_profile_5 = value
    if key == "company_mission":
        client.mission = value
    if key == "company_tagline":
        client.tagline = value
    if key == "company_description":
        client.description = value
    if key == "company_value_prop":
        client.value_prop_key_points = value
    if key == "sequence_open_rate":
        client_sdr.conversion_open_pct = value
    if key == "sequence_reply_rate":
        client_sdr.conversion_reply_pct = value
    if key == "sequence_demo_rate":
        client_sdr.conversion_demo_pct = value
    if key == "do_not_contact":
        client.do_not_contact_company_names = [x.strip() for x in value.split(",")]
    if key == "user_full_name":
        client_sdr.name = value
    if key == "user_email":
        client_sdr.email = value
    if key == "user_scheduling_link":
        client_sdr.scheduling_link = value
    if key == "user_linkedin_url":
        client_sdr.linkedin_url = value
    if key == "scheduling_message":
        scheduling_framework.description = value
    if key == "user_timezone":
        client_sdr.timezone = value
    if key == "example_copy":
        client.example_outbound_copy = value
    if key == "company_case_studies":
        client.case_study = value
    if key == "existing_clients":
        client.existing_clients = value
    if key == "impressive_facts":
        client.impressive_facts = value
    if key == "messaging_tone":
        client.tone_attributes = [x.strip() for x in value.split(",")]
    if key == "poc_full_name":
        client.contact_name = value
    if key == "poc_email":
        client.contact_email = value

    db.session.add(client)
    db.session.add(client_sdr)
    db.session.add(first_persona)
    db.session.add(scheduling_framework)
    db.session.commit()

    db.session.add(first_persona)
    db.session.commit()

    return True


def get_all_sdrs_from_emails(emails: list[str]):
    """Gets all SDRs from a list of emails"""

    sdrs: list[ClientSDR] = ClientSDR.query.filter(ClientSDR.email.in_(emails)).all()

    # Public info, don't include auth token!
    return [
        {
            "id": sdr.id,
            "name": sdr.name,
            "email": sdr.email,
            "title": sdr.title,
            "client_id": sdr.client_id,
            "timezone": sdr.timezone,
        }
        for sdr in sdrs
    ]


def import_pre_onboarding(
    client_sdr_id: int,
):
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client: Client = Client.query.get(client_sdr.client_id)
    client_id = client.id

    client_sdr_id = client_sdr.id

    persona_name = client.pre_onboarding_survey.get("persona_name")
    persona_buy_reason = client.pre_onboarding_survey.get("persona_buy_reason")
    persona_contact_objective = client.pre_onboarding_survey.get(
        "persona_contact_objective"
    )
    cta_blanks_company = client.pre_onboarding_survey.get("cta_blanks_company")
    cta_blanks_persona = client.pre_onboarding_survey.get("cta_blanks_persona")
    cta_blanks_solution = client.pre_onboarding_survey.get("cta_blanks_solution")
    common_use_cases = client.pre_onboarding_survey.get("common_use_cases")
    persona_filters = client.pre_onboarding_survey.get("persona_filters")
    persona_lookalike_1 = client.pre_onboarding_survey.get("persona_lookalike_1")
    persona_lookalike_2 = client.pre_onboarding_survey.get("persona_lookalike_2")
    persona_lookalike_3 = client.pre_onboarding_survey.get("persona_lookalike_3")
    persona_lookalike_4 = client.pre_onboarding_survey.get("persona_lookalike_4")
    persona_lookalike_5 = client.pre_onboarding_survey.get("persona_lookalike_5")

    company_mission_statement = client.pre_onboarding_survey.get("company_mission")
    company_tagline = client.pre_onboarding_survey.get("company_tagline")
    company_description = client.pre_onboarding_survey.get("company_description")
    company_value_proposition = client.pre_onboarding_survey.get("company_value_prop")
    company_open_percent = client.pre_onboarding_survey.get("sequence_open_rate")
    company_reply_percent = client.pre_onboarding_survey.get("sequence_reply_rate")
    company_demo_percent = client.pre_onboarding_survey.get("sequence_demo_rate")
    company_do_not_contact_list = client.pre_onboarding_survey.get("do_not_contact")

    user_full_name = client.pre_onboarding_survey.get("user_full_name")
    user_email_address = client.pre_onboarding_survey.get("user_email")
    user_calendly_link = client.pre_onboarding_survey.get("user_scheduling_link")
    user_linkedin_link = client.pre_onboarding_survey.get("user_linkedin_url")
    user_scheduling_message = client.pre_onboarding_survey.get("scheduling_message")
    user_timezone = client.pre_onboarding_survey.get("user_timezone")

    messaging_outbound_copy = client.pre_onboarding_survey.get("example_copy")
    messaging_link_to_case_studies = client.pre_onboarding_survey.get(
        "company_case_studies"
    )
    messaging_existing_clients = client.pre_onboarding_survey.get("existing_clients")
    messaging_impressive_facts = client.pre_onboarding_survey.get("impressive_facts")
    messaging_tone = client.pre_onboarding_survey.get("messaging_tone")

    all_variables = [
        ("persona_name", persona_name, True),
        ("persona_buy_reason", persona_buy_reason, True),
        ("persona_contact_objective", persona_contact_objective, False),
        ("cta_blanks_company", cta_blanks_company, False),
        ("cta_blanks_persona", cta_blanks_persona, False),
        ("cta_blanks_solution", cta_blanks_solution, False),
        ("common_use_cases", common_use_cases, False),
        ("persona_filters", persona_filters, False),
        ("persona_lookalike_1", persona_lookalike_1, False),
        ("persona_lookalike_2", persona_lookalike_2, False),
        ("persona_lookalike_3", persona_lookalike_3, False),
        ("persona_lookalike_4", persona_lookalike_4, False),
        ("persona_lookalike_5", persona_lookalike_5, False),
        ("company_mission_statement", company_mission_statement, True),
        ("company_tagline", company_tagline, True),
        ("company_description", company_description, True),
        ("company_value_proposition", company_value_proposition, True),
        ("company_open_percent", company_open_percent, False),
        ("company_reply_percent", company_reply_percent, False),
        ("company_demo_percent", company_demo_percent, False),
        ("company_do_not_contact_list", company_do_not_contact_list, False),
        ("user_full_name", user_full_name, True),
        ("user_email_address", user_email_address, True),
        ("user_calendly_link", user_calendly_link, False),
        ("user_timezone", user_timezone, False),
        ("scheduling_message", user_scheduling_message, False),
        ("user_linkedin_link", user_linkedin_link, False),
        ("messaging_outbound_copy", messaging_outbound_copy, False),
        ("messaging_link_to_case_studies", messaging_link_to_case_studies, False),
        ("messaging_existing_clients", messaging_existing_clients, False),
        ("messaging_impressive_facts", messaging_impressive_facts, False),
        ("messaging_tone", messaging_tone, False),
    ]

    missing_required_variables = []
    missing_variables = []
    for variable, value, required in all_variables:
        if required and not value:
            missing_required_variables.append(variable)
        if not value:
            missing_variables.append(variable)
        print(f"Setting {variable} to {value}")

    if len(missing_required_variables) > 0:
        return False, "Missing required variables: {}".format(
            missing_required_variables
        )

    client_archetypes: list[ClientArchetype] = ClientArchetype.query.filter(
        ClientArchetype.client_sdr_id == client_sdr_id,
        ClientArchetype.is_unassigned_contact_archetype == False,
        ClientArchetype.active == True,
    ).all()
    if not client_archetypes:
        create_client_archetype(
            client_id=client_id,
            client_sdr_id=client_sdr_id,
            archetype=persona_name,
            filters={},
            persona_fit_reason=persona_buy_reason,
            persona_contact_objective=persona_contact_objective,
            cta_blanks_company=cta_blanks_company,
            cta_blanks_persona=cta_blanks_persona,
            cta_blanks_solution=cta_blanks_solution,
            common_use_cases=common_use_cases,
            persona_filters=persona_filters,
            lookalike_1=persona_lookalike_1,
            lookalike_2=persona_lookalike_2,
            lookalike_3=persona_lookalike_3,
            lookalike_4=persona_lookalike_4,
            lookalike_5=persona_lookalike_5,
        )

    scheduling_bump_frameworks: list[BumpFramework] = BumpFramework.query.filter(
        BumpFramework.client_sdr_id == client_sdr_id,
        BumpFramework.substatus == ProspectStatus.ACTIVE_CONVO_SCHEDULING.value,
    ).all()
    if len(scheduling_bump_frameworks) > 0:
        for framework in scheduling_bump_frameworks:
            framework.description = user_scheduling_message
            db.session.add(framework)
    db.session.commit()

    client: Client = Client.query.get(client_id)
    client.mission = company_mission_statement
    client.tagline = company_tagline
    client.description = company_description
    client.value_prop_key_points = company_value_proposition
    client.do_not_contact_company_names = company_do_not_contact_list
    client.example_outbound_copy = messaging_outbound_copy
    client.existing_clients = messaging_existing_clients
    client.case_study = messaging_link_to_case_studies
    client.impressive_facts = messaging_impressive_facts
    client.tone_attributes = messaging_tone and messaging_tone.split(",")
    db.session.add(client)

    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client_sdr.conversion_open_pct = company_open_percent
    client_sdr.conversion_reply_pct = company_reply_percent
    client_sdr.conversion_demo_pct = company_demo_percent
    client_sdr.linkedin_url = user_linkedin_link
    client_sdr.scheduling_link = user_calendly_link
    client_sdr.email = user_email_address
    client_sdr.timezone = user_timezone
    db.session.add(client_sdr)

    db.session.commit()

    # Create a SDREmailBank for the SDR
    create_sdr_email_bank(
        client_sdr_id=client_sdr_id,
        email_address=user_email_address,
        email_type=EmailType.ANCHOR,
    )

    if len(missing_variables) > 0:
        return (
            True,
            "Imported what we could but client has missing variables: {}".format(
                missing_variables
            ),
        )

    return True, "Successfully imported pre-onboarding survey"


def update_client_sdr_cc_bcc_emails(
    client_sdr_id: int,
    cc_emails: Optional[list[str]],
    bcc_emails: Optional[list[str]],
):
    """
    Updates the CC and BCC emails for a client SDR
    """
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if cc_emails is not None:
        client_sdr.weekly_report_cc_emails = cc_emails
    if bcc_emails is not None:
        client_sdr.weekly_report_bcc_emails = bcc_emails
    db.session.add(client_sdr)
    db.session.commit()
    return True


def update_client_auto_generate_li_messages_setting(
    client_sdr_id: int,
    auto_generate_li_messages: bool,
):
    """
    Updates the auto generate LI messages setting for a client SDR
    """
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client: Client = Client.query.get(client_sdr.client_id)
    client.auto_generate_li_messages = auto_generate_li_messages
    db.session.commit()
    return True


def update_client_auto_send_li_messages(
    client_sdr_id: int,
    auto_send_li_messages: bool,
):
    """
    Updates the auto send LI messages setting for a client SDR
    """
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client: Client = Client.query.get(client_sdr.client_id)
    client.auto_send_li_messages = auto_send_li_messages
    db.session.commit()
    return True


def update_client_auto_generate_email_messages_setting(
    client_sdr_id: int,
    auto_generate_email_messages: bool,
):
    """
    Updates the auto generate email messages setting for a client SDR
    """
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client: Client = Client.query.get(client_sdr.client_id)
    client.auto_generate_email_messages = auto_generate_email_messages
    db.session.commit()
    return True


def get_tam_industry_breakdown(client_sdr_id: int):
    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)

    results = db.session.execute(
        """
        select
          industry,
          count(distinct prospect.id) filter (where prospect.overall_status <> 'PROSPECTED') "# Contacted",
          count(distinct prospect.id) filter (where prospect.overall_status = 'PROSPECTED') "# Left"
        from prospect
        where prospect.client_id = {client_id}
        group by 1
        order by
          count(distinct prospect.id) filter (where prospect.overall_status <> 'PROSPECTED') DESC
        limit 10
        """.format(
            client_id=sdr.client_id
        )
    ).fetchall()

    # index to status map
    key_map = {
        0: "industry",
        1: "num_contacted",
        2: "num_left",
    }

    # Convert and format output
    final_results = []
    for result in results:
        rows = [row for row in tuple(result)]
        rows = {key_map.get(i, "unknown"): row for i, row in enumerate(rows)}
        final_results.append(rows)

    return final_results


def get_tam_employees(client_sdr_id: int):
    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)

    results = db.session.execute(
        """
        with d as (
          select
            case
              when prospect.employee_count ilike '%None-None%' then 'No Size'
              when prospect.employee_count ilike '%10001-None%' then '10001+'
              when prospect.employee_count ilike '%-%' then prospect.employee_count
                when prospect.employee_count ilike '%+' then '10001+'

                when prospect.employee_count ilike '%None%' then 'unknown'
              else
                (
                  case
                    when cast(prospect.employee_count as integer) >= 0 and cast(prospect.employee_count as integer) <= 10 then '2-10'
                    when cast(prospect.employee_count as integer) >= 11 and cast(prospect.employee_count as integer) <= 50 then '11-50'
                    when cast(prospect.employee_count as integer) >= 51 and cast(prospect.employee_count as integer) <= 200 then '51-200'
                    when cast(prospect.employee_count as integer) >= 51 and cast(prospect.employee_count as integer) <= 200 then '51-200'
                    when cast(prospect.employee_count as integer) >= 201 and cast(prospect.employee_count as integer) <= 500 then '201-500'
                    when cast(prospect.employee_count as integer) >= 501 and cast(prospect.employee_count as integer) <= 1000 then '501-1000'
                    when cast(prospect.employee_count as integer) >= 1001 and cast(prospect.employee_count as integer) <= 5000 then '501-1000'
                    when cast(prospect.employee_count as integer) >= 5001 and cast(prospect.employee_count as integer) <= 10000 then '5001-10000'
                    else 'No Size'
                  END
                )
            end employee_count_comp,
            array_agg(distinct prospect.employee_count),
            count(distinct prospect.id) filter (where prospect.overall_status = 'PROSPECTED') "# Left",
            count(distinct prospect.id) filter (where prospect.overall_status <> 'PROSPECTED') "# Contacted",
            count(distinct prospect.id)
          from prospect
            join research_payload on research_payload.prospect_id = prospect.id
          where prospect.client_id = {client_id}

          group by 1
        )
        select
          employee_count_comp,
          "# Contacted",
          "# Left"
        from d
        order by
          case when employee_count_comp = 'No Size' then 1 else 0 end,
          case
            when employee_count_comp = '0-1' then 0
            when employee_count_comp = '2-10' then 1
            when employee_count_comp = '11-50' then 2
            when employee_count_comp = '51-200' then 3
            when employee_count_comp = '201-500' then 4
            when employee_count_comp = '501-1000' then 5
            when employee_count_comp = '1001-5000' then 6
            when employee_count_comp = '5001-10000' then 7
            when employee_count_comp = '10001+' then 8
          end
        """.format(
            client_id=sdr.client_id
        )
    ).fetchall()

    # index to status map
    key_map = {
        0: "employee_count_comp",
        1: "num_contacted",
        2: "num_left",
    }

    # Convert and format output
    final_results = []
    for result in results:
        rows = [row for row in tuple(result)]
        rows = {key_map.get(i, "unknown"): row for i, row in enumerate(rows)}
        final_results.append(rows)

    return final_results


def get_tam_stats(client_sdr_id: int):
    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)

    results = db.session.execute(
        """
        select
          count(distinct prospect.company) "# Companies",
          count(distinct prospect.id) "# Contacts",
          count(distinct prospect.company) filter (where prospect.status not in ('PROSPECTED')) "# Engaged"
        from prospect
        where prospect.client_id = {client_id}
        """.format(
            client_id=sdr.client_id
        )
    ).fetchall()

    # index to status map
    key_map = {
        0: "num_companies",
        1: "num_contacts",
        2: "num_engaged",
    }

    # Convert and format output
    final_results = []
    for result in results:
        rows = [row for row in tuple(result)]
        rows = {key_map.get(i, "unknown"): row for i, row in enumerate(rows)}
        final_results.append(rows)

    return final_results


def get_tam_titles(client_sdr_id: int):
    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)

    results = db.session.execute(
        """
        select
          title,
          count(distinct prospect.id)
        from prospect
        where prospect.client_id = {client_id}
        group by 1
        order by 2 desc
        limit 10
        """.format(
            client_id=sdr.client_id
        )
    ).fetchall()

    # index to status map
    key_map = {
        0: "title",
        1: "count",
    }

    # Convert and format output
    final_results = []
    for result in results:
        rows = [row for row in tuple(result)]
        rows = {key_map.get(i, "unknown"): row for i, row in enumerate(rows)}
        final_results.append(rows)

    return final_results


def get_tam_companies(client_sdr_id: int):
    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)

    results = db.session.execute(
        """
        select
          prospect.company,
          count(distinct prospect.id)
        from prospect
        where prospect.client_id = {client_id}
        group by 1
        order by 2 desc
        limit 10
        """.format(
            client_id=sdr.client_id
        )
    ).fetchall()

    # index to status map
    key_map = {
        0: "company",
        1: "count",
    }

    # Convert and format output
    final_results = []
    for result in results:
        rows = [row for row in tuple(result)]
        rows = {key_map.get(i, "unknown"): row for i, row in enumerate(rows)}
        final_results.append(rows)

    return final_results


def get_tam_industries(client_sdr_id: int):
    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)

    results = db.session.execute(
        """
        select
          industry,
          count(distinct prospect.id)
        from prospect
        where prospect.client_id = {client_id}
        group by 1
        order by 2 desc
        limit 10
        """.format(
            client_id=sdr.client_id
        )
    ).fetchall()

    # index to status map
    key_map = {
        0: "industry",
        1: "count",
    }

    # Convert and format output
    final_results = []
    for result in results:
        rows = [row for row in tuple(result)]
        rows = {key_map.get(i, "unknown"): row for i, row in enumerate(rows)}
        final_results.append(rows)

    return final_results


def get_tam_scraping_report(client_sdr_id: int):
    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)

    results = db.session.execute(
        """
        select
          concat(
            client_archetype.emoji,
            ' ',
            client_archetype.archetype
          ) "Upload Name",
          client_sdr.name "SDR",
          concat(
            count(distinct prospect.id),
            ' out of ',
            count(distinct prospect.id)
          ) "Scraped",
          'Complete' Status,
          to_char(prospect.created_at, 'YYYY-MM-DD') "Upload Date"
        from
          client_archetype
          join prospect on prospect.archetype_id = client_archetype.id
          join client_sdr on client_sdr.id = client_archetype.client_sdr_id
        where client_archetype.client_id = {client_id}
        group by 1,2,4,5
        order by 5 desc
        """.format(
            client_id=sdr.client_id
        )
    ).fetchall()

    # index to status map
    key_map = {
        0: "upload_name",
        1: "sdr",
        2: "scraped",
        3: "status",
        4: "upload_date",
    }

    # Convert and format output
    final_results = []
    for result in results:
        rows = [row for row in tuple(result)]
        rows = {key_map.get(i, "unknown"): row for i, row in enumerate(rows)}
        final_results.append(rows)

    return final_results


def get_tam_data(client_sdr_id: int):
    return {
        "industry_breakdown": get_tam_industry_breakdown(client_sdr_id),
        "employees": get_tam_employees(client_sdr_id),
        "stats": get_tam_stats(client_sdr_id),
        "titles": get_tam_titles(client_sdr_id),
        "companies": get_tam_companies(client_sdr_id),
        "industries": get_tam_industries(client_sdr_id),
        "scraping_report": get_tam_scraping_report(client_sdr_id),
    }


def msg_analytics_report(client_sdr_id: int):
    results = db.session.execute(
        """
        select
          bump_framework.id "id",
          client_archetype.archetype "Campaign",
          concat('Follow Up #', bump_framework.bumped_count + 1) "Step",
          bump_framework.title "Title",
          bump_framework.etl_num_times_used,
          bump_framework.etl_num_times_converted,
          round(cast(bump_framework.etl_num_times_converted as float) / (bump_framework.etl_num_times_used + 0.0001) * 1000) / 10 "Conversion%",
          bump_framework.default and bump_framework.active "Active",
          client_archetype.id "CampaignID"
        from client_archetype
          join bump_framework on bump_framework.client_archetype_id = client_archetype.id
            and bump_framework.overall_status in ('ACCEPTED', 'BUMPED')
        where
          client_archetype.client_sdr_id = """
        + str(client_sdr_id)
        + """
    """
    ).fetchall()
    return [dict(row) for row in results]


def get_available_times_via_calendly(
    calendly_url: str,
    dt: datetime,
    tz: str = "America/Los_Angeles",
    start_time: int = 8,
    end_time: int = 18,
    max_days: int = 14,
):
    """
    Returns a list of available times from a Calendly link
    """

    success, response = attempt_chat_completion_with_vision(
        message=f"""
          ## Given this image of a calendar, please list out all the available days and times for the selected day in ISO 8601 format.
          #### Your response should look something like this and follow this datetime format exactly:
          Selected Date:
          2024-01-09 09:00:00
          2024-01-09 11:30:00
          2024-01-09 12:30:00

          Other Dates:
          2024-01-05 00:00:00
          2024-01-07 00:00:00
          2024-01-10 00:00:00
          2024-01-12 00:00:00
        """,
        webpage_url=f"{calendly_url}?month={dt.strftime('%Y-%m')}&date={dt.strftime('%Y-%m-%d')}",
    )
    if not success:
        return None

    # Split the response into selected dates and other dates
    selected_dates_str, other_dates_str = response.split("\n\n")

    # Extract and convert the selected dates (now as timezone-aware UTC datetimes)
    try:
        selected_dates_utc = [
            datetime.fromisoformat(date + "+00:00")
            for date in selected_dates_str.split("\n")[1:]
        ]
    except:
        selected_dates_utc = []

    try:
        other_dates_utc = [
            datetime.fromisoformat(date + "+00:00")
            for date in other_dates_str.split("\n")[1:]
        ]
    except:
        other_dates_utc = []

    # Convert UTC dates to the given timezone
    selected_dates_tz = [
        date.astimezone(pytz.timezone(tz)) for date in selected_dates_utc
    ]
    other_dates_tz = [date.astimezone(pytz.timezone(tz)) for date in other_dates_utc]

    # Filtering selected_dates_tz for times between start_time and end_time
    selected_dates_within_hours = [
        date for date in selected_dates_tz if start_time <= date.hour < end_time
    ]

    # Calculate the date X days from now
    current_date = datetime.now(pytz.timezone(tz))
    x_days_later = current_date + timedelta(days=max_days)

    # Filter the dates
    other_dates_next_x_days = [
        date for date in other_dates_tz if current_date <= date <= x_days_later
    ]

    return {
        "times": selected_dates_within_hours,
        "other_dates": other_dates_next_x_days,
    }


def create_do_not_contact_filters_operator_dashboard_card(client_sdr_id: int):
    create_operator_dashboard_entry(
        client_sdr_id=client_sdr_id,
        urgency=OperatorDashboardEntryPriority.MEDIUM,
        tag="add_dnc_filters_{client_sdr_id}".format(client_sdr_id=client_sdr_id),
        emoji="❌",
        title="Add Do Not Contact Filters",
        subtitle="In order to ensure that SellScale doesn't reach out to any accounts you want to exclude, add keywords and exclusions to your do not contact filters.",
        cta="Add Filters",
        cta_url="/",
        status=OperatorDashboardEntryStatus.PENDING,
        due_date=datetime.now() + timedelta(days=1),
        task_type=OperatorDashboardTaskType.ADD_DNC_FILTERS,
        task_data={
            "client_sdr_id": client_sdr_id,
        },
    )

    return True


def update_client_sdr_territory_name(client_sdr_id: int, territory_name: str):
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client_sdr.territory_name = territory_name
    db.session.add(client_sdr)
    db.session.commit()

    return True


def create_archetype_asset(
    client_sdr_id: int,
    client_id: int,
    client_archetype_ids: list[int],
    asset_key: str,
    asset_value: str,
    asset_type: ClientAssetType,
    asset_tags: list[str],
    asset_raw_value: str,
):
    """
    Creates an asset for a client archetype
    """
    asset: ClientAssets = ClientAssets(
        client_id=client_id,
        client_archetype_ids=client_archetype_ids,
        asset_key=asset_key,
        asset_value=asset_value,
        asset_type=asset_type,
        asset_tags=asset_tags,
        asset_raw_value=asset_raw_value,
    )
    db.session.add(asset)
    db.session.commit()

    success = create_and_send_slack_notification_class_message(
        notification_type=SlackNotificationType.ASSET_CREATED,
        arguments={
            "client_sdr_id": client_sdr_id,
            "asset_name": asset_key,
            "asset_tags": asset_tags,
            "ai_summary": asset_value,
        },
    )

    return asset.to_dict()


def get_client_assets(client_id: int):
    """
    Gets all assets for a client
    """
    assets = (
        ClientAssets.query.filter_by(client_id=client_id)
        .order_by(ClientAssets.created_at.desc())
        .all()
    )
    return [asset.to_dict() for asset in assets]


def delete_archetype_asset(asset_id: int, client_sdr_id: int):
    """
    Deletes an asset for a client archetype
    """
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    asset = ClientAssets.query.filter_by(
        id=asset_id, client_id=client_sdr.client_id
    ).first()
    if not asset:
        return False
    db.session.delete(asset)
    db.session.commit()
    return True


def update_asset(
    asset_id: int,
    client_sdr_id: int,
    asset_key: Optional[str] = None,
    asset_value: Optional[str] = None,
    asset_type: Optional[ClientAssetType] = None,
    asset_tags: Optional[list[str]] = None,
    asset_raw_value: Optional[str] = None,
):
    """
    Updates an asset for a client archetype
    """
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    asset: ClientAssets = ClientAssets.query.filter_by(
        id=asset_id, client_id=client_sdr.client_id
    ).first()
    if not asset:
        return False
    if asset_key:
        asset.asset_key = asset_key
    if asset_value:
        asset.asset_value = asset_value
    if asset_type:
        asset.asset_type = asset_type
    if asset_tags:
        asset.asset_tags = asset_tags
    if asset_raw_value:
        asset.asset_raw_value = asset_raw_value
    db.session.add(asset)
    db.session.commit()
    return True


def delete_client_asset_archetype_mapping(
    client_archetype_id: int,
    asset_id: int,
):
    """
    Deletes an asset for a client archetype
    """
    asset = ClientAssetArchetypeReasonMapping.query.filter_by(
        client_archetype_id=client_archetype_id, client_asset_id=asset_id
    ).all()
    for a in asset:
        db.session.delete(a)
    db.session.commit()

    client_archetype: ClientArchetype = ClientArchetype.query.get(client_archetype_id)
    client_id = client_archetype.client_id

    asset: ClientAssets = ClientAssets.query.filter_by(
        id=asset_id, client_id=client_id
    ).first()
    asset.client_archetype_ids.remove(client_archetype_id)
    flag_modified(asset, "client_archetype_ids")
    db.session.add(asset)
    db.session.commit()

    return True


def create_client_archetype_reason_mapping(
    client_archetype_id: int,
    asset_id: int,
    reason: str,
):
    """
    Creates a reason for a client archetype
    """
    reason = ClientAssetArchetypeReasonMapping(
        client_archetype_id=client_archetype_id,
        client_asset_id=asset_id,
        reason=reason,
    )
    db.session.add(reason)

    client_archetype: ClientArchetype = ClientArchetype.query.get(client_archetype_id)
    client_id = client_archetype.client_id

    asset: ClientAssets = ClientAssets.query.filter_by(
        id=asset_id, client_id=client_id
    ).first()
    asset.client_archetype_ids.append(client_archetype_id)
    flag_modified(asset, "client_archetype_ids")
    db.session.add(asset)
    db.session.commit()

    return True


def modify_client_archetype_reason_mapping(
    client_asset_archetype_reason_mapping_id: int,
    new_reason: str,
) -> bool:
    """
    Modifies a reason for a client archetype
    """
    reason: ClientAssetArchetypeReasonMapping = (
        ClientAssetArchetypeReasonMapping.query.get(
            client_asset_archetype_reason_mapping_id
        )
    )
    reason.reason = new_reason
    db.session.add(reason)
    db.session.commit()
    return True
