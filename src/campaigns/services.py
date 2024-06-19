from http import client
from app import db, celery
from sqlalchemy import and_, or_, nullslast
from typing import Optional

from src.campaigns.models import *
from model_import import (
    Prospect,
    Client,
    ClientSDR,
    GeneratedMessageCTA,
    GeneratedMessage,
    ProspectEmail,
    ProspectEmailOutreachStatus,
    ProspectEmailStatus,
    ProspectStatus,
    ProspectOverallStatus,
    OutboundCampaign,
    OutboundCampaignStatus,
    GeneratedMessageType,
    ClientArchetype,
    Segment,
)
from sqlalchemy.sql.expression import func
from src.client.models import EmailToLinkedInConnection
from src.editor.models import Editor, EditorTypes
from src.email_outbound.services import (
    batch_mark_prospects_in_email_campaign_queued,
    get_approved_prospect_email_by_id,
)
from tqdm import tqdm
from src.message_generation.services import (
    wipe_prospect_email_and_generations_and_research,
    generate_outreaches_for_prospect_list_from_multiple_ctas,
    create_and_start_email_generation_jobs,
)
from src.prospecting.services import mark_prospects_as_queued_for_outreach
from src.research.linkedin.services import reset_prospect_research_and_messages
from src.message_generation.services_few_shot_generations import (
    can_generate_with_patterns,
)
from src.utils.random_string import generate_random_alphanumeric
from src.utils.slack import send_slack_message, URL_MAP

import datetime


NUM_DAYS_AFTER_GENERATION_TO_EDIT = 1


def get_outbound_campaign_details(
    client_sdr_id: int,
    campaign_id: int,
    get_messages: Optional[bool] = False,
    shallow_details: Optional[bool] = False,
) -> dict:
    """Gets the details of an outbound campaign.

    Args:
        client_sdr_id (int): The ID of the SDR.
        campaign_id (int): The ID of the campaign to get.

    Returns:
        dict: A dictionary containing campaign details, status code, and message.
    """
    from src.client.services import get_cta_stats

    oc: OutboundCampaign = OutboundCampaign.query.get(campaign_id)
    if not oc:
        return {"message": "Campaign not found", "status_code": 404}
    if oc and oc.client_sdr_id != client_sdr_id:
        return {"message": "This campaign does not belong to you", "status_code": 403}

    # If we are getting shallow_details, do not return the prospects, ctas, or client_archetype.
    if shallow_details:
        return {
            "campaign_details": {
                "campaign_raw": oc.to_dict(),
                "campaign_analytics": get_outbound_campaign_analytics(campaign_id),
            },
            "message": "Success",
            "status_code": 200,
        }

    # Get the table values for the available ids. If ids are not available, return empty lists or None.
    prospects: list[Prospect] = (
        Prospect.query.filter(Prospect.id.in_(oc.prospect_ids)).all()
        if oc.prospect_ids
        else []
    )
    prospects = (
        [
            p.to_dict(
                return_messages=get_messages, return_message_type=oc.campaign_type.value
            )
            for p in prospects
        ]
        if prospects
        else []
    )
    ctas: list[GeneratedMessageCTA] = (
        GeneratedMessageCTA.query.filter(GeneratedMessageCTA.id.in_(oc.ctas)).all()
        if oc.ctas
        else []
    )
    ctas_dicts = []
    for cta in ctas:
        raw_cta = cta.to_dict()
        raw_cta["performance"] = get_cta_stats(cta.id)
        ctas_dicts.append(raw_cta)
    client_archetype: ClientArchetype = (
        ClientArchetype.query.get(oc.client_archetype_id)
        if oc.client_archetype_id
        else None
    )
    client_archetype = client_archetype.to_dict() if client_archetype else None

    return {
        "campaign_details": {
            "campaign_raw": oc.to_dict(),
            "campaign_analytics": get_outbound_campaign_analytics(campaign_id),
            "prospects": prospects,
            "ctas": ctas_dicts,
            "client_archetype": client_archetype,
        },
        "message": "Success",
        "status_code": 200,
    }


def get_outbound_campaign_details_for_edit_tool_linkedin(
    client_sdr_id: int, campaign_id: int, approved_filter: Optional[bool] = None
):
    oc: OutboundCampaign = OutboundCampaign.query.get(campaign_id)
    # Get join of prospect and message
    joined_prospect_message = (
        db.session.query(
            Prospect.id.label("prospect_id"),
            Prospect.full_name.label("full_name"),
            GeneratedMessage.id.label("message_id"),
            GeneratedMessage.ai_approved.label("ai_approved"),
            GeneratedMessage.completion.label("completion"),
            GeneratedMessage.problems.label("problems"),
            GeneratedMessage.blocking_problems.label("blocking_problems"),
            GeneratedMessage.highlighted_words.label("highlighted_words"),
        )
        .join(
            GeneratedMessage,
            Prospect.approved_outreach_message_id == GeneratedMessage.id,
        )
        .filter(Prospect.id.in_(oc.prospect_ids))
        # .order_by(nullslast(GeneratedMessage.problems.desc()))
    )

    # Filter by approved messages if filter is set
    if approved_filter is False:
        joined_prospect_message = joined_prospect_message.filter(
            or_(
                GeneratedMessage.ai_approved == False,
                GeneratedMessage.ai_approved == None,
            )
        )
    elif approved_filter is True:
        joined_prospect_message = joined_prospect_message.filter(
            GeneratedMessage.ai_approved == True
        )
    joined_prospect_message = joined_prospect_message.all()

    # Get information from the joined table
    prospects = []
    for p in joined_prospect_message:
        prospects.append(
            {
                "prospect_id": p.prospect_id,
                "full_name": p.full_name,
                "message_id": p.message_id,
                "ai_approved": p.ai_approved,
                "completion": p.completion,
                "problems": p.problems,
                "blocking_problems": p.blocking_problems,
                "highlighted_words": p.highlighted_words,
            }
        )

    client_archetype: ClientArchetype = (
        ClientArchetype.query.get(oc.client_archetype_id)
        if oc.client_archetype_id
        else None
    )
    client_archetype = client_archetype.to_dict() if client_archetype else None

    return {
        "campaign_details": {
            "campaign_raw": oc.to_dict(),
            "campaign_analytics": get_outbound_campaign_analytics(campaign_id),
            "prospects": prospects,
            "client_archetype": client_archetype,
        },
        "message": "Success",
        "status_code": 200,
    }


def get_outbound_campaign_details_for_edit_tool_email(
    campaign_id: int, approved_filter: Optional[bool] = None
):
    oc: OutboundCampaign = OutboundCampaign.query.get(campaign_id)
    data = db.session.execute(
        """
        select
            prospect.id "prospect_id",
            prospect.full_name "full_name",

        --	personalized_subject_line
            case when prospect_email.personalized_subject_line = subject_line.id
                then subject_line.id
                else null
            end "personalized_subject_line_message_id",
            case when prospect_email.personalized_subject_line = subject_line.id
                then subject_line.ai_approved
                else null
            end "personalized_subject_line_ai_approved",
            case when prospect_email.personalized_subject_line = subject_line.id
                then subject_line.completion
                else null
            end "personalized_subject_line_completion",
            case when prospect_email.personalized_subject_line = subject_line.id
                then subject_line.problems
                else null
            end "personalized_subject_line_problems",
            case when prospect_email.personalized_subject_line = subject_line.id
                then subject_line.highlighted_words
                else null
            end "personalized_subject_line_highlighted_words",
            case when prospect_email.personalized_subject_line = subject_line.id
            	then subject_line.prompt
            	else null
            end "personalized_subject_line_prompt",
            case when prospect_email.personalized_subject_line = subject_line.id
            	then subject_line.few_shot_prompt
            	else null
            end "personalized_subject_line_few_shot_prompt",


        -- personalized_body
            case when prospect_email.personalized_body = body.id
                then body.id
                else null
            end "personalized_body_message_id",
            case when prospect_email.personalized_body = body.id
                then body.ai_approved
                else null
            end "personalized_body_ai_approved",
            case when prospect_email.personalized_body = body.id
                then body.completion
                else null
            end "personalized_body_completion",
            case when prospect_email.personalized_body = body.id
                then body.problems
                else null
            end "personalized_body_problems",
            case when prospect_email.personalized_body = body.id
                then body.highlighted_words
                else null
            end "personalized_body_highlighted_words",

        -- general prospect email stuff
            prospect_email.id "prospect_email_id",

        -- blocking problems
            case when prospect_email.personalized_subject_line = subject_line.id
                then subject_line.blocking_problems
                else null
            end "personalized_subject_line_blocking_problems",
            case when prospect_email.personalized_body = body.id
                then body.blocking_problems
                else null
            end "personalized_body_blocking_problems"

        from outbound_campaign
            join prospect on prospect.id = any(outbound_campaign.prospect_ids)
            join prospect_email on prospect_email.id = prospect.approved_prospect_email_id
            join generated_message subject_line
                on subject_line.id = prospect_email.personalized_subject_line
            join generated_message body
                on body.id = prospect_email.personalized_body
        where outbound_campaign.id = {campaign_id}
            and prospect.overall_status in ('PROSPECTED', 'SENT_OUTREACH');
    """.format(
            campaign_id=campaign_id
        )
    ).fetchall()

    prospects = []
    for entry in data:
        prospect_id = entry[0]
        full_name = entry[1]
        personalized_subject_line_message_id = entry[2]
        personalized_subject_line_ai_approved = entry[3]
        personalized_subject_line_completion = entry[4]
        personalized_subject_line_problems = entry[5] if entry[5] else []
        personalized_subject_line_highlighted_words = entry[6]
        personalized_subject_line_prompt = entry[7]
        personalized_subject_line_few_shot_prompt = entry[8]
        personalized_body_message_id = entry[9]
        personalized_body_ai_approved = entry[10]
        personalized_body_completion = entry[11]
        personalized_body_problems = entry[12] if entry[12] else []
        personalized_body_highlighted_words = entry[13]
        prospect_email_id = entry[14]
        personalized_subject_line_blocking_problems = entry[15] if entry[15] else []
        personalized_body_blocking_problems = entry[16] if entry[16] else []
        prospects.append(
            {
                "prospect_id": prospect_id,
                "full_name": full_name,
                "message_id": personalized_subject_line_message_id,
                "ai_approved": personalized_subject_line_ai_approved,
                "completion": personalized_subject_line_completion,
                "problems": personalized_subject_line_problems
                + personalized_body_problems,
                "blocking_problems": personalized_subject_line_blocking_problems
                + personalized_body_blocking_problems,
                "highlighted_words": personalized_subject_line_highlighted_words,
                "prompt": personalized_subject_line_prompt,
                "few_shot_prompt": personalized_subject_line_few_shot_prompt,
                "message_id_2": personalized_body_message_id,
                "ai_approved_2": personalized_body_ai_approved,
                "completion_2": personalized_body_completion,
                "highlighted_words_2": personalized_body_highlighted_words,
                "prospect_email_id": prospect_email_id,
            }
        )

    client_archetype: ClientArchetype = (
        ClientArchetype.query.get(oc.client_archetype_id)
        if oc.client_archetype_id
        else None
    )
    client_archetype = client_archetype.to_dict() if client_archetype else None

    return {
        "campaign_details": {
            "campaign_raw": oc.to_dict(),
            "campaign_analytics": get_outbound_campaign_analytics(campaign_id),
            "prospects": prospects,
            "client_archetype": client_archetype,
        },
        "message": "Success",
        "status_code": 200,
    }


def get_outbound_campaign_details_for_edit_tool(
    client_sdr_id: int, campaign_id: int, approved_filter: Optional[bool] = None
):
    """Gets the details of an outbound campaign, specific for the editing tool.

    Args:
        client_sdr_id (int): The ID of the SDR.
        campaign_id (int): The ID of the campaign to get.
        approved_filter (bool, optional): Whether to filter by approved or not. Defaults to None. None = no filter (all). False = not approved. True = approved.

    Returns:
        dict: A dictionary containing campaign details, status code, and message.
    """
    oc: OutboundCampaign = OutboundCampaign.query.get(campaign_id)
    if not oc:
        return {"message": "Campaign not found", "status_code": 404}
    if oc and oc.client_sdr_id != client_sdr_id:
        return {"message": "This campaign does not belong to you", "status_code": 403}

    if oc.campaign_type.value == "LINKEDIN":
        return get_outbound_campaign_details_for_edit_tool_linkedin(
            client_sdr_id, campaign_id, approved_filter
        )
    if oc.campaign_type.value == "EMAIL":
        return get_outbound_campaign_details_for_edit_tool_email(
            campaign_id, approved_filter
        )


def get_outbound_campaigns(
    client_sdr_id: int,
    query: Optional[str] = "",
    campaign_start_date: Optional[str] = None,
    campaign_end_date: Optional[str] = None,
    campaign_type: Optional[list[str]] = None,
    status: Optional[list[str]] = None,
    limit: Optional[int] = 10,
    offset: Optional[int] = 0,
    filters: Optional[list[dict[str, int]]] = [],
    archetype_id: Optional[int] = None,
) -> dict[int, list[OutboundCampaign]]:
    """Gets outbound campaigns belonging to the SDR, with optional query and filters.

    Authorization required.

    Args:
        client_sdr_id: The ID of the SDR.
        archetype_id: The ID of the archetype to get campaigns for.
        query: The query to search for. Can search for name only.
        campaign_start: The start date of the campaign to search for.
        campaign_end: The end date of the campaign to search for.
        campaign_type: The type of campaign to search for.
        status: The status of the campaign to search for.
        limit: The number of campaigns to return.
        offset: The offset to start returning campaigns from.
        filters: The filters to apply to the query.

    Returns:
        A dictionary containing the total number of campaigns and the campaigns themselves.

    Ordering logic is as follows
        The filters list should have the following tuples:
            - name: 1 or -1, indicating ascending or descending order
            - campaign_type: 1 or -1, indicating ascending or descending order
            - status: 1 or -1, indicating ascending or descending order
            - campaign_start_date: 1 or -1, indicating ascending or descending order
            - campaign_end_date: 1 or -1, indicating ascending or descending order
        The query will be ordered by these fields in the order provided
    """
    # Construct ordering array
    ordering = []
    for filt in filters:
        filter_name = filt.get("field")
        filter_direction = filt.get("direction")
        if filter_name == "name":
            if filter_direction == 1:
                ordering.append(OutboundCampaign.name.asc())
            elif filter_direction == -1:
                ordering.append(OutboundCampaign.name.desc())
        elif filter_name == "campaign_type":
            if filter_direction == 1:
                ordering.append(OutboundCampaign.campaign_type.asc())
            elif filter_direction == -1:
                ordering.append(OutboundCampaign.campaign_type.desc())
        elif filter_name == "status":
            if filter_direction == 1:
                ordering.append(OutboundCampaign.status.asc())
            elif filter_direction == -1:
                ordering.append(OutboundCampaign.status.desc())
        elif filter_name == "campaign_start_date":
            if filter_direction == 1:
                ordering.append(OutboundCampaign.campaign_start_date.asc())
            elif filter_direction == -1:
                ordering.append(OutboundCampaign.campaign_start_date.desc())
        elif filter_name == "campaign_end_date":
            if filter_direction == 1:
                ordering.append(OutboundCampaign.campaign_end_date.asc())
            elif filter_direction == -1:
                ordering.append(OutboundCampaign.campaign_end_date.desc())
        else:
            ordering.insert(0, None)

    # Pad ordering array with None values, set to number of ordering options: 4
    while len(ordering) < 5:
        ordering.insert(0, None)

    # Set status filter.
    filtered_status = status
    if status is None:
        filtered_status = OutboundCampaignStatus.all_statuses()

    # Set campaign type filter.
    filtered_campaign_type = campaign_type
    if campaign_type is None:
        filtered_campaign_type = GeneratedMessageType.all_types()

    # Set date filter. If no date is provided, set to default values.
    campaign_start_date = campaign_start_date or datetime.datetime(
        datetime.MINYEAR, 1, 1
    ).strftime("%Y-%m-%d")
    campaign_end_date = campaign_end_date or datetime.datetime(
        datetime.MAXYEAR, 1, 1
    ).strftime("%Y-%m-%d")

    # Construct query
    outbound_campaigns = (
        OutboundCampaign.query.filter(
            and_(
                OutboundCampaign.campaign_start_date >= campaign_start_date,
                OutboundCampaign.campaign_end_date <= campaign_end_date,
            )
        )
        .filter((OutboundCampaign.campaign_type.in_(filtered_campaign_type)))
        .filter((OutboundCampaign.status.in_(filtered_status)))
        .filter(
            OutboundCampaign.client_sdr_id == client_sdr_id,
            OutboundCampaign.name.ilike(f"%{query}%"),
        )
        .filter(
            (OutboundCampaign.client_archetype_id == archetype_id)
            if archetype_id
            else True
        )
        .order_by(ordering[0])
        .order_by(ordering[1])
        .order_by(ordering[2])
        .order_by(ordering[3])
        .order_by(ordering[4])
    )
    total_count = outbound_campaigns.count()
    outbound_campaigns = outbound_campaigns.limit(limit).offset(offset).all()

    return {"total_count": total_count, "outbound_campaigns": outbound_campaigns}


def create_outbound_campaign(
    prospect_ids: list,
    num_prospects: int,
    campaign_type: GeneratedMessageType,
    client_archetype_id: int,
    client_sdr_id: int,
    campaign_start_date: datetime,
    campaign_end_date: datetime,
    ctas: Optional[list] = None,
    priority_rating: Optional[int] = 0,
    warm_emails: Optional[bool] = False,
    is_daily_generation: Optional[bool] = False,
) -> OutboundCampaign:
    """Creates a new outbound campaign

    Prospects to use are "smart calculated" by the campaign

    Args:
        name (str): Name of the campaign
        prospect_ids (list): List of prospect ids
        num_prospects (int): Number of prospects to use
        campaign_type (GeneratedMessageType): Type of campaign
        ctas (list): List of CTA ids
        client_archetype_id (int): Client archetype id
        client_sdr_id (int): Client SDR id
        campaign_start_date (datetime): Start date of the campaign
        campaign_end_date (datetime): End date of the campaign
        status (OutboundCampaignStatus): Status of the campaign
        priority_rating (int): Priority level of the campaign
        warm_emails (bool): Whether to send emails to warm prospects or not
        is_daily_generation (bool): Whether this campaign is a daily generation or not

    Returns:
        OutboundCampaign: The newly created outbound campaign
    """
    # If number of prospects is over 500, do not generate
    if num_prospects > 500:
        raise Exception("Number of prospects must not be greater than 500")

    # check if the client has reached their weekly cap
    archetype = ClientArchetype.query.get(client_archetype_id)
    num_messages_sent_this_week = db.session.execute(
        """
        select
            count(distinct prospect.id)
        from
            prospect
            left join generated_message on generated_message.id = prospect.approved_outreach_message_id
            left join prospect_email on prospect_email.id = prospect.approved_prospect_email_id
        where
            prospect.archetype_id = :archetype_id and
            (
                generated_message.created_at >= date_trunc('week', NOW()) or
                prospect_email.created_at >= date_trunc('week', NOW())
            );
        """,
        {"archetype_id": client_archetype_id},
    ).scalar()

    if (
        num_messages_sent_this_week > 0
        and archetype.testing_volume < num_messages_sent_this_week
    ):
        raise Exception("This client has reached their weekly cap for outreach")

    # Smart get prospects to use
    if num_prospects > len(prospect_ids):
        top_prospects = smart_get_prospects_for_campaign(
            client_archetype_id=client_archetype_id,
            num_prospects=num_prospects - len(prospect_ids),
            campaign_type=campaign_type,
            warm_emails=warm_emails,
        )
        prospect_ids.extend(top_prospects)
        # Add a check that the number of prospects is correct
        if len(prospect_ids) > num_prospects:
            raise Exception(
                "Incorrect number of prospects returned from smart_get_prospects_for_campaign"
            )
        pass

    # DO NOT create a campaign if there are no Prospect IDs
    if len(prospect_ids) == 0:
        raise Exception("Cannot generate an empty campaign (no Prospects)")

    ca: ClientArchetype = ClientArchetype.query.get(client_archetype_id)
    ocs: list[OutboundCampaign] = OutboundCampaign.query.filter(
        OutboundCampaign.client_archetype_id == client_archetype_id
    ).all()
    num_campaigns = len(ocs)
    name = ca.archetype + " #" + str(num_campaigns + 1)
    canonical_name = (
        ca.archetype + ", " + str(num_prospects) + ", " + str(campaign_start_date)
    )
    if campaign_type == GeneratedMessageType.LINKEDIN and ctas is None:
        raise Exception("LinkedIn campaign type requires a list of CTAs")

    uuid = generate_random_alphanumeric(32)

    prospect1 = Prospect.query.get(prospect_ids[0])
    if (
        prospect1
        and not can_generate_with_patterns(client_sdr_id)
        and len(prospect_ids) > 10
        and campaign_type == GeneratedMessageType.LINKEDIN.value
    ):
        raise Exception(
            "This client needs their baseline configuration. Contact Engineer."
        )

    campaign = OutboundCampaign(
        name=name,
        canonical_name=canonical_name,
        prospect_ids=prospect_ids,
        campaign_type=campaign_type,
        ctas=ctas,
        client_archetype_id=client_archetype_id,
        client_sdr_id=client_sdr_id,
        campaign_start_date=campaign_start_date,
        campaign_end_date=campaign_end_date,
        status=OutboundCampaignStatus.PENDING,
        uuid=uuid,
        priority_rating=priority_rating,
        is_daily_generation=is_daily_generation,
    )
    db.session.add(campaign)
    db.session.commit()
    return campaign


def smart_get_prospects_for_campaign(
    client_archetype_id: int,
    num_prospects: int,
    campaign_type: GeneratedMessageType,
    warm_emails: Optional[bool] = False,
) -> list[int]:
    """Smartly gets prospects for a campaign

    Top priority: ICP intent score
    Second priority: Health check
    Third priority: random

    If warm_emails is True, then the top priority are Prospects that have ACCEPTED or BUMPED for LinkedIn status.

    Args:
        client_archetype_id (int): Client archetype id
        num_prospects (int): Number of prospects to get
        campaign_type (GeneratedMessageType): Type of campaign
        warm_emails (bool): Whether to send emails to warm prospects or not

    Returns:
        list[int]: List of prospect ids
    """
    remaining_num_prospects = num_prospects

    # If warm_emails is True and campaign_type is EMAIL, get warmed prospects
    warmed_prospects = []
    if warm_emails and campaign_type == GeneratedMessageType.EMAIL:
        warmed_prospects = get_warmed_prospects(
            client_archetype_id=client_archetype_id,
            num_prospects=num_prospects,
            campaign_type=campaign_type,
        )
        remaining_num_prospects = num_prospects - len(warmed_prospects)
        if remaining_num_prospects < 0:
            raise Exception(
                "Incorrect number of prospects returned from get_warmed_prospects"
            )

        # Since we are targeting warmed prospects, we can return early
        return warmed_prospects

    # Get prospects with highest ICP intent score
    top_intent_prospects = get_top_intent_prospects(
        client_archetype_id=client_archetype_id,
        num_prospects=remaining_num_prospects,
        campaign_type=campaign_type,
    )
    remaining_num_prospects = num_prospects - len(top_intent_prospects)
    if remaining_num_prospects < 0:
        raise Exception(
            "Incorrect number of prospects returned from get_top_intent_prospects"
        )

    # Get prospects with highest health check score
    top_healthscore_prospects = get_top_healthscore_prospects(
        client_archetype_id=client_archetype_id,
        num_prospects=remaining_num_prospects,
        campaign_type=campaign_type,
        blacklist=top_intent_prospects,
    )
    remaining_num_prospects = remaining_num_prospects - len(top_healthscore_prospects)
    if remaining_num_prospects < 0:
        raise Exception(
            "Incorrect number of prospects returned from get_top_healthscore_prospects"
        )

    # Get prospects randomly
    random_prospects = get_random_prospects(
        client_archetype_id=client_archetype_id,
        num_prospects=remaining_num_prospects,
        campaign_type=campaign_type,
        blacklist=top_intent_prospects + top_healthscore_prospects,
    )
    remaining_num_prospects = remaining_num_prospects - len(random_prospects)
    if remaining_num_prospects < 0:
        raise Exception(
            "Incorrect number of prospects returned from get_top_healthscore_prospects"
        )

    prospect_ids: list[int] = (
        top_intent_prospects + top_healthscore_prospects + random_prospects
    )

    # Filter Based on Omni Rules for Linkedin
    if campaign_type == GeneratedMessageType.LINKEDIN:
        client_archetype: ClientArchetype = ClientArchetype.query.get(
            client_archetype_id
        )
        email_opened_prospects_query = """
        select
            array_agg(distinct prospect.id) filter (where prospect_email_status_records.to_status = 'SENT_OUTREACH') "prospects_sent_outreach",
            array_agg(distinct prospect.id) filter (where prospect_email_status_records.to_status = 'EMAIL_OPENED') "prospects_email_opened",
            array_agg(distinct prospect.id) filter (where prospect_email_status_records.to_status = 'ACCEPTED') "prospects_clicked"
        from prospect
            left join prospect_email on prospect_email.id = prospect.approved_prospect_email_id
            left join prospect_email_status_records on prospect_email_status_records.prospect_email_id = prospect_email.id
        where archetype_id = {client_archetype_id}
            and prospect.overall_status in ('SENT_OUTREACH', 'PROSPECTED', 'BUMPED', 'ACCEPTED');
        """
        email_opened_prospects = db.session.execute(
            email_opened_prospects_query.format(client_archetype_id=client_archetype_id)
        ).fetchone()
        if (
            client_archetype.email_to_linkedin_connection is None
            or client_archetype.email_to_linkedin_connection
            == EmailToLinkedInConnection.RANDOM
        ):
            # do nothing
            pass
        elif (
            client_archetype.email_to_linkedin_connection
            == EmailToLinkedInConnection.ALL_PROSPECTS
        ):
            # Filter prospect ids for prospects that have been sent outreach
            if email_opened_prospects["prospects_sent_outreach"] is not None:
                prospect_ids = list(
                    set(prospect_ids).intersection(
                        email_opened_prospects["prospects_sent_outreach"]
                    )
                )
            else:
                prospect_ids = []
        elif (
            client_archetype.email_to_linkedin_connection
            == EmailToLinkedInConnection.OPENED_EMAIL_PROSPECTS_ONLY
        ):
            # Filter prospect ids for prospects that have opened emails
            if email_opened_prospects["prospects_email_opened"] is not None:
                prospect_ids = list(
                    set(prospect_ids).intersection(
                        email_opened_prospects["prospects_email_opened"]
                    )
                )
            else:
                prospect_ids = []
        elif (
            client_archetype.email_to_linkedin_connection
            == EmailToLinkedInConnection.CLICKED_LINK_PROSPECTS_ONLY
        ):
            # Filter prospect ids for prospects that have clicked emails
            if email_opened_prospects["prospects_clicked"] is not None:
                prospect_ids = list(
                    set(prospect_ids).intersection(
                        email_opened_prospects["prospects_clicked"]
                    )
                )
            else:
                prospect_ids = []
    else:
        client_archetype = ClientArchetype.query.get(client_archetype_id)

    # check against the daily limit, if we want to send more than, we need to cut down
    weekday = datetime.datetime.now().weekday()
    if weekday == 0:  # Monday
        days_until_friday = 5
    elif weekday == 1:  # Tuesday
        days_until_friday = 4
    elif weekday == 2:  # Wednesday
        days_until_friday = 3
    elif weekday == 3:  # Thursday
        days_until_friday = 2
    elif weekday == 4:  # Friday
        days_until_friday = 1
    else:  # Saturday or Sunday
        days_until_friday = 7 - weekday + 4

    if len(prospect_ids) > client_archetype.testing_volume / days_until_friday:
        rounded = int(client_archetype.testing_volume / days_until_friday)
        prospect_ids = prospect_ids[:rounded]
    return prospect_ids


def get_warmed_prospects(
    client_archetype_id: int,
    num_prospects: int,
    campaign_type: GeneratedMessageType,
) -> list[int]:
    """Gets warmed prospects for a campaign

    Top priority: Prospects that have ACCEPTED or BUMPED for LinkedIn status.

    Args:
        client_archetype_id (int): Client archetype id
        num_prospects (int): Number of prospects to get
        campaign_type (GeneratedMessageType): Type of campaign

    Returns:
        list[int]: List of prospect ids
    """
    if campaign_type != GeneratedMessageType.EMAIL:
        return False

    # Get prospects that have a status in either ACCEPTED or BUMPED
    warmed_prospects = (
        Prospect.query.filter(
            Prospect.archetype_id == client_archetype_id,
            Prospect.approved_prospect_email_id == None,
            Prospect.status.in_(
                [ProspectStatus.ACCEPTED.value, ProspectStatus.RESPONDED.value]
            ),
            Prospect.overall_status.in_(
                [
                    ProspectOverallStatus.ACCEPTED.value,
                    ProspectOverallStatus.BUMPED.value,
                ]
            ),
        )
        .limit(num_prospects)
        .all()
    )

    prospect_ids: list[int] = [p.id for p in warmed_prospects]
    return prospect_ids


def get_top_intent_prospects(
    client_archetype_id: int,
    num_prospects: int,
    campaign_type: GeneratedMessageType,
    blacklist: Optional[list[int]] = [],
) -> list[int]:
    """Gets the top prospects using intent score (LinkedIn or Email)

    Args:
        client_archetype_id (int): Client archetype id
        num_prospects (int): Number of prospects to get
        campaign_type (GeneratedMessageType): Type of campaign
        blacklist (list[int]): List of prospect ids to exclude

    Returns:
        list[int]: List of prospect ids
    """
    if num_prospects <= 0:
        return []

    # Get prospects that are available for outreach
    prospects = Prospect.query.filter(
        Prospect.archetype_id == client_archetype_id,
        or_(
            Prospect.overall_status == ProspectOverallStatus.PROSPECTED.value,
            Prospect.overall_status == ProspectOverallStatus.SENT_OUTREACH.value,
            Prospect.overall_status == ProspectOverallStatus.BUMPED.value,
            Prospect.overall_status == ProspectOverallStatus.ACCEPTED.value,
        ),
        Prospect.id.notin_(blacklist),
    )

    # Filter prospects based on the campaign type
    if campaign_type == GeneratedMessageType.EMAIL:
        prospects = (
            prospects.filter(
                Prospect.email_intent_score != None,
                Prospect.approved_prospect_email_id == None,
                Prospect.email.isnot(None),
                Prospect.overall_status != ProspectOverallStatus.BUMPED.value,
            )
            .order_by(Prospect.email_intent_score.desc(), func.random())
            .limit(num_prospects)
            .all()
        )
    elif campaign_type == GeneratedMessageType.LINKEDIN:
        prospects = (
            prospects.filter(
                Prospect.li_intent_score != None,
                Prospect.approved_outreach_message_id == None,
            )
            .order_by(Prospect.li_intent_score.desc(), func.random())
            .limit(num_prospects)
            .all()
        )

    prospect_ids: list[int] = [p.id for p in prospects]
    return prospect_ids


def get_top_healthscore_prospects(
    client_archetype_id: int,
    num_prospects: int,
    campaign_type: GeneratedMessageType,
    blacklist: Optional[list[int]] = [],
) -> list[int]:
    """Gets the top prospects using health score (LinkedIn or Email)

    Args:
        client_archetype_id (int): Client archetype id
        num_prospects (int): Number of prospects to get
        campaign_type (GeneratedMessageType): Type of campaign
        blacklist (list[int]): List of prospect ids to exclude

    Returns:
        list[int]: List of prospect ids
    """
    # If there are no more prospects to be grabbed, return empty list
    if num_prospects <= 0:
        return []

    # Get prospects that are available for outreach
    prospects = Prospect.query.filter(
        Prospect.archetype_id == client_archetype_id,
        Prospect.health_check_score != None,
        Prospect.id.notin_(blacklist),
        or_(
            Prospect.overall_status == ProspectOverallStatus.PROSPECTED.value,
            Prospect.overall_status == ProspectOverallStatus.SENT_OUTREACH.value,
            Prospect.overall_status == ProspectOverallStatus.BUMPED.value,
            Prospect.overall_status == ProspectOverallStatus.ACCEPTED.value,
        ),
    )

    # Filter prospects based on the campaign type
    if campaign_type == GeneratedMessageType.EMAIL:
        prospects = prospects.filter(
            Prospect.email.isnot(None),
            Prospect.approved_prospect_email_id == None,
            Prospect.overall_status != ProspectOverallStatus.BUMPED.value,
        )
    elif campaign_type == GeneratedMessageType.LINKEDIN:
        prospects = prospects.filter(
            Prospect.approved_outreach_message_id == None,
        )
    prospects = (
        prospects.order_by(Prospect.health_check_score.desc(), func.random())
        .limit(num_prospects)
        .all()
    )

    prospect_ids: list[int] = [p.id for p in prospects]
    return prospect_ids


def get_random_prospects(
    client_archetype_id: int,
    num_prospects: int,
    campaign_type: GeneratedMessageType,
    blacklist: Optional[list[int]] = [],
) -> list[int]:
    """Gets a random set of prospects

    Args:
        client_archetype_id (int): Client archetype id
        num_prospects (int): Number of prospects to get
        campaign_type (GeneratedMessageType): Campaign type
        blacklist (list[int], optional): List of prospect ids to exclude. Defaults to [].

    Returns:
        list[int]: List of prospect ids
    """
    if num_prospects <= 0:
        return []

    # Get prospects that are available for outreach
    prospects = Prospect.query.filter(
        Prospect.archetype_id == client_archetype_id,
        Prospect.id.notin_(blacklist),
        or_(
            Prospect.overall_status == ProspectOverallStatus.PROSPECTED.value,
            Prospect.overall_status == ProspectOverallStatus.SENT_OUTREACH.value,
            Prospect.overall_status == ProspectOverallStatus.BUMPED.value,
            Prospect.overall_status == ProspectOverallStatus.ACCEPTED.value,
        ),
    )

    # Filter prospects based on the campaign type
    if campaign_type == GeneratedMessageType.EMAIL:
        prospects = prospects.filter(
            Prospect.email.isnot(None),
            Prospect.approved_prospect_email_id == None,
            Prospect.overall_status != ProspectOverallStatus.BUMPED.value,
        )
    elif campaign_type == GeneratedMessageType.LINKEDIN:
        prospects = prospects.filter(
            Prospect.approved_outreach_message_id == None,
        )
    prospects = prospects.order_by(func.random()).limit(num_prospects).all()

    prospect_ids: list[int] = [p.id for p in prospects]
    return prospect_ids


def generate_campaign(campaign_id: int) -> True:
    """Generates the campaign

    Args:
        campaign_id (int): Campaign id
    """
    campaign: OutboundCampaign = OutboundCampaign.query.get(campaign_id)
    campaign.status = OutboundCampaignStatus.NEEDS_REVIEW
    campaign.editing_due_date = datetime.datetime.now() + datetime.timedelta(
        days=NUM_DAYS_AFTER_GENERATION_TO_EDIT
    )
    db.session.add(campaign)
    db.session.commit()

    if campaign.campaign_type == GeneratedMessageType.EMAIL:
        create_and_start_email_generation_jobs(
            campaign_id=campaign_id,
        )
    elif campaign.campaign_type == GeneratedMessageType.LINKEDIN:
        generate_outreaches_for_prospect_list_from_multiple_ctas(
            prospect_ids=campaign.prospect_ids,
            cta_ids=campaign.ctas,
            outbound_campaign_id=campaign_id,
        )

    assign_random_editor_to_campaign(campaign_id)

    return True


def assign_random_editor_to_campaign(campaign_id: int) -> True:
    active_random_editor: Editor = (
        Editor.query.filter(
            Editor.active == True,
            Editor.editor_type == EditorTypes.SELLSCALE_EDITING_TEAM,
        )
        .order_by(func.random())
        .first()
    )

    if not active_random_editor:
        raise Exception("No active random editor found")

    editor_id: int = active_random_editor.id
    assign_editor_to_campaign(
        editor_id=editor_id,
        campaign_id=campaign_id,
    )

    return True


def adjust_editing_due_date(campaign_id: int, new_date: datetime):
    """Adjusts the due date of a campaign

    Args:
        campaign_id (int): Campaign id
        new_date (datetime): New due date
    """
    campaign: OutboundCampaign = OutboundCampaign.query.get(campaign_id)
    campaign.editing_due_date = new_date
    db.session.add(campaign)
    db.session.commit()


def change_campaign_status(campaign_id: int, status: OutboundCampaignStatus):
    """Changes the status of a campaign

    Args:
        campaign_id (int): Campaign id
        status (OutboundCampaignStatus): New status of the campaign
    """
    campaign: OutboundCampaign = OutboundCampaign.query.get(campaign_id)
    campaign.status = status
    db.session.add(campaign)
    db.session.commit()

    return True


def mark_campaign_as_ready_to_send(campaign_id: int):
    """Marks the campaign as ready to send

    Args:
        campaign_id (int): Campaign id
    """
    from src.client.services import get_client

    change_campaign_status(campaign_id, OutboundCampaignStatus.READY_TO_SEND)

    campaign: OutboundCampaign = OutboundCampaign.query.get(campaign_id)
    sdr: ClientSDR = ClientSDR.query.get(campaign.client_sdr_id)
    sdr_name = sdr.name
    sdr_auth = sdr.auth_token
    client_id = sdr.client_id
    client_company = get_client(client_id).company

    campaign_name = campaign.name.split(",")[0]
    prospect_count = len(campaign.prospect_ids)
    campaign_type = campaign.campaign_type.value
    start_date = campaign.campaign_start_date.strftime("%b %d, %Y")
    end_date = campaign.campaign_end_date.strftime("%b %d, %Y")

    # send_slack_message(
    #     message="{} - {}'s Campaign #{} is ready to send! :tada:".format(
    #         client_company, sdr_name, campaign_id
    #     ),
    #     blocks=[
    #         {
    #             "type": "header",
    #             "text": {
    #                 "type": "plain_text",
    #                 "text": "{} - {}'s Campaign #{} is ready to send! :tada:".format(
    #                     client_company, sdr_name, campaign_id
    #                 ),
    #             },
    #         },
    #         {
    #             "type": "section",
    #             "text": {
    #                 "type": "mrkdwn",
    #                 "text": "SellScale operations team has read and verified this campaign.",
    #             },
    #         },
    #         {
    #             "type": "section",
    #             "text": {
    #                 "type": "mrkdwn",
    #                 "text": "*Campaign Name:* {}".format(campaign_name),
    #             },
    #         },
    #         {
    #             "type": "section",
    #             "text": {
    #                 "type": "mrkdwn",
    #                 "text": "*Prospect #:* {} prospects".format(prospect_count),
    #             },
    #         },
    #         {
    #             "type": "section",
    #             "text": {
    #                 "type": "mrkdwn",
    #                 "text": "*Campaign Type #:* {}".format(campaign_type),
    #             },
    #         },
    #         {
    #             "type": "section",
    #             "text": {
    #                 "type": "mrkdwn",
    #                 "text": "*Date Range #:* {} - {}".format(start_date, end_date),
    #             },
    #         },
    #         {
    #             "type": "section",
    #             "text": {
    #                 "type": "mrkdwn",
    #                 "text": "Next steps: Go to {}'s Sight and send campaign".format(
    #                     sdr_name
    #                 ),
    #             },
    #             "accessory": {
    #                 "type": "button",
    #                 "text": {
    #                     "type": "plain_text",
    #                     "text": "Go to {}'s Sight".format(sdr_name),
    #                     "emoji": True,
    #                 },
    #                 "value": "https://sight.sellscale.com/?token={}".format(sdr_auth)
    #                 or "https://sight.sellscale.com/sight",
    #                 "url": "https://sight.sellscale.com/?token={}".format(sdr_auth)
    #                 or "https://sight.sellscale.com/sight",
    #                 "action_id": "button-action,",
    #             },
    #         },
    #     ],
    #     webhook_urls=[URL_MAP["operations-ready-campaigns"]],
    # )

    return True


def mark_campaign_as_initial_review_complete(campaign_id: int):
    """Marks the campaign as initial edit is complete

    Args:
        campaign_id (int): Campaign id
    """
    from src.client.services import get_client

    campaign: OutboundCampaign = OutboundCampaign.query.get(campaign_id)
    if campaign.status == OutboundCampaignStatus.READY_TO_SEND:
        return False

    change_campaign_status(campaign_id, OutboundCampaignStatus.INITIAL_EDIT_COMPLETE)

    campaign: OutboundCampaign = OutboundCampaign.query.get(campaign_id)
    sdr: ClientSDR = ClientSDR.query.get(campaign.client_sdr_id)
    sdr_name = sdr.name
    sdr_auth = sdr.auth_token
    client_id = sdr.client_id
    client_company = get_client(client_id).company

    campaign_name = campaign.name.split(",")[0]
    campaign_uuid = campaign.uuid
    prospect_count = len(campaign.prospect_ids)
    campaign_type = campaign.campaign_type.value
    start_date = campaign.campaign_start_date.strftime("%b %d, %Y")
    end_date = campaign.campaign_end_date.strftime("%b %d, %Y")

    prospect_ids = campaign.prospect_ids
    client_sdr_id = campaign.client_sdr_id

    send_slack_message(
        message="{} - {}'s Campaign #{} has been reviewed by an editor! :black_joker:".format(
            client_company, sdr_name, campaign_id
        ),
        blocks=[
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "{} - {}'s Campaign #{} has been reviewed by an editor! :black_joker:".format(
                        client_company, sdr_name, campaign_id
                    ),
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "SellScale operations team has read and verified this campaign.",
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Campaign Name:* {}".format(campaign_name),
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Prospect #:* {} prospects".format(prospect_count),
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Campaign Type #:* {}".format(campaign_type),
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Date Range #:* {} - {}".format(start_date, end_date),
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "Next steps: Go to {}'s Sight and send campaign".format(
                        sdr_name
                    ),
                },
                "accessory": {
                    "type": "button",
                    "text": "Edit Campaign in Admin Tool",
                    "value": "https://sellscale.retool.com/apps/2b24b894-c513-11ed-bcd9-af1af2d4669d/Editing%20Engine/Campaign%20Editor%20Portal%20V2%20(Admin)#campaign_uuid="
                    + campaign_uuid,
                    "action_id": "button-action,",
                },
            },
        ],
        webhook_urls=[URL_MAP["operations-ready-campaigns"]],
    )

    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if campaign.campaign_type == GeneratedMessageType.LINKEDIN:
        mark_prospects_as_queued_for_outreach(
            prospect_ids=prospect_ids,
            client_sdr_id=client_sdr_id,
        )

    if campaign.campaign_type == GeneratedMessageType.EMAIL:
        batch_mark_prospects_in_email_campaign_queued(
            campaign_id=campaign_id,
        )

    return True


def email_analytics(client_sdr_id: int) -> dict:
    """Get email analytics by sequence

    This function is authenticated.

    Args:
        client_sdr_id (int): ID of the Client SDR

    Returns:
        dict: Dict containing the upload stats
    """

    # Get data about email analytics
    results = db.session.execute(
        """
        select
          count(distinct prospect.company) filter (where prospect.overall_status in ('DEMO')) num_demos,
          outbound_campaign.id campaign_id,
          outbound_campaign.campaign_start_date,
          outbound_campaign.campaign_end_date,
          client_archetype.archetype,
          count(distinct prospect.id) num_prospects,
          concat('(', string_agg(distinct prospect.company, '), (') filter (where prospect_email.outreach_status in ('DEMO_SET', 'DEMO_LOST', 'DEMO_WON')), ')') demos,
          concat('(', string_agg(distinct prospect.company, '), (') filter (where prospect_email.outreach_status in ('ACTIVE_CONVO', 'SCHEDULING', 'NOT_INTERESTED', 'DEMO_SET', 'DEMO_WON', 'DEMO_LOST')), ')') replies,
          round(count(distinct prospect.id) filter (where prospect_email.outreach_status in ('EMAIL_OPENED', 'ACCEPTED', 'ACTIVE_CONVO', 'SCHEDULING', 'NOT_INTERESTED', 'DEMO_SET', 'DEMO_WON', 'DEMO_LOST')) / cast(count(distinct prospect.id) as float) * 1000) / 10 open_percent,
          round(count(distinct prospect.id) filter (where prospect_email.outreach_status in ('ACTIVE_CONVO', 'SCHEDULING', 'NOT_INTERESTED', 'DEMO_SET', 'DEMO_WON', 'DEMO_LOST')) / cast(count(distinct prospect.id) as float) * 1000) / 10 reply_percent,
          round(count(distinct prospect.id) filter (where prospect_email.outreach_status in ('DEMO_SET', 'DEMO_WON', 'DEMO_LOST')) / cast(count(distinct prospect.id) as float) * 1000) / 10 demo_percent
        from outbound_campaign
          left join prospect on prospect.id = any(outbound_campaign.prospect_ids)
          left join client_archetype on client_archetype.id = prospect.archetype_id
          left join prospect_email on prospect_email.id = prospect.approved_prospect_email_id
          left join client on client.id = prospect.client_id
        where outbound_campaign.client_sdr_id = {client_sdr_id}
            and outbound_campaign.campaign_type = 'EMAIL'
          and outbound_campaign.status = 'COMPLETE'
        group by 3,4,5,6
        order by count(distinct prospect.company) filter (where prospect_email.outreach_status in ('DEMO_SET', 'DEMO_LOST', 'DEMO_WON')) desc;
        """.format(
            client_sdr_id=client_sdr_id
        )
    ).fetchall()

    # index to column
    column_map = {
        0: "num_demos",
        1: "sequence_name",
        2: "campaign_id",
        3: "campaign_start_date",
        4: "campaign_end_date",
        5: "archetype",
        6: "num_prospects",
        7: "demos",
        8: "replies",
        9: "open_percent",
        10: "reply_percent",
        11: "demo_percent",
    }

    # Convert and format output
    results = [
        {column_map.get(i, "unknown"): value for i, value in enumerate(tuple(row))}
        for row in results
    ]

    return {"message": "Success", "status_code": 200, "data": results}


def update_campaign_name(campaign_id: int, name: str):
    """Updates the name of the campaign

    Args:
        campaign_id (int): Campaign id
        name (str): New name of the campaign
    """
    campaign: OutboundCampaign = OutboundCampaign.query.get(campaign_id)
    campaign.name = name
    db.session.add(campaign)
    db.session.commit()


def update_campaign_receipt_link(campaign_id: int, receipt_link: str):
    """Updates the receipt link of the campaign

    Args:
        campaign_id (int): Campaign id
        receipt_link (str): New receipt link of the campaign
    """
    campaign: OutboundCampaign = OutboundCampaign.query.get(campaign_id)
    campaign.receipt_link = receipt_link
    db.session.add(campaign)
    db.session.commit()


def update_campaign_cost(campaign_id: int, cost: str):
    """Updates the cost of the campaign

    Args:
        campaign_id (int): Campaign id
        cost (str): New cost of the campaign
    """
    campaign: OutboundCampaign = OutboundCampaign.query.get(campaign_id)
    campaign.cost = cost
    db.session.add(campaign)
    db.session.commit()


def update_campaign_dates(campaign_id: int, start_date: datetime, end_date: datetime):
    """Updates the start and end dates of the campaign

    Args:
        campaign_id (int): Campaign id
        start_date (datetime): New start date of the campaign
        end_date (datetime): New end date of the campaign
    """
    campaign: OutboundCampaign = OutboundCampaign.query.get(campaign_id)
    campaign.campaign_start_date = start_date
    campaign.campaign_end_date = end_date
    db.session.add(campaign)
    db.session.commit()


def merge_outbound_campaigns(campaign_ids: list):
    """Merges multiple campaigns into one

    Args:
        campaign_ids (list): List of campaign ids to merge

    Returns:
        int: Id of the new campaign
    """
    name = "Merged Campaign - " + ", ".join([str(c) for c in campaign_ids])
    campaigns = OutboundCampaign.query.filter(
        OutboundCampaign.id.in_(campaign_ids)
    ).all()

    campaign_types = set([c.campaign_type for c in campaigns])
    if len(campaign_types) > 1:
        raise Exception("Campaigns must be of the same type")

    client_archetype_ids = set([c.client_archetype_id for c in campaigns])
    if len(client_archetype_ids) > 1:
        raise Exception("Campaigns must be of the same client archetype")

    client_sdr_ids = set([c.client_sdr_id for c in campaigns])
    if len(client_sdr_ids) > 1:
        raise Exception("Campaigns must be of the same client sdr")

    campaign_statuses = set([c.status.value for c in campaigns])
    if len(campaign_statuses) > 1:
        raise Exception("Campaigns must be of the same status")

    editor_ids = set([c.editor_id for c in campaigns])
    if len(editor_ids) > 1:
        raise Exception(
            "Campaigns must have the same editor assigned to edit! Please consolidate the editors."
        )

    name = "Merged - Campaigns: " + ", ".join([str(c.id) for c in campaigns])
    prospect_ids = list(set().union(*[c.prospect_ids for c in campaigns]))
    campaign_type = campaigns[0].campaign_type
    ctas = list(set().union(*[c.ctas for c in campaigns if c.ctas]))
    client_archetype_id = campaigns[0].client_archetype_id
    client_sdr_id = campaigns[0].client_sdr_id
    campaign_start_date = min([c.campaign_start_date for c in campaigns])
    campaign_end_date = max([c.campaign_end_date for c in campaigns])

    campaign: OutboundCampaign = create_outbound_campaign(
        prospect_ids=prospect_ids,
        num_prospects=len(prospect_ids),
        campaign_type=campaign_type,
        client_archetype_id=client_archetype_id,
        client_sdr_id=client_sdr_id,
        campaign_start_date=campaign_start_date,
        campaign_end_date=campaign_end_date,
        ctas=ctas,
    )
    campaign.status = campaigns[0].status
    campaign.editor_id = campaigns[0].editor_id
    campaign.name = name
    db.session.add(campaign)
    db.session.commit()

    for c in campaigns:
        c.status = OutboundCampaignStatus.CANCELLED
        db.session.add(c)
        db.session.commit()

    return campaign.id


def split(a, n):
    k, m = divmod(len(a), n)
    return (a[i * k + min(i, m) : (i + 1) * k + min(i + 1, m)] for i in range(n))


def split_outbound_campaigns(original_campaign_id: int, num_campaigns: int):
    """Splits a campaign into multiple campaigns

    Returns:
        list: List of campaign ids
    """
    original_campaign: OutboundCampaign = OutboundCampaign.query.get(
        original_campaign_id
    )
    original_campaign_status = original_campaign.status
    if not original_campaign:
        raise Exception("Campaign does not exist")

    prospect_ids = original_campaign.prospect_ids
    prospect_id_batches = list(split(prospect_ids, num_campaigns))

    campaign_ids = []
    for i, prospect_id_batch in enumerate(prospect_id_batches):
        campaign: OutboundCampaign = create_outbound_campaign(
            prospect_ids=prospect_id_batch,
            num_prospects=len(prospect_id_batch),
            campaign_type=original_campaign.campaign_type,
            client_archetype_id=original_campaign.client_archetype_id,
            client_sdr_id=original_campaign.client_sdr_id,
            campaign_start_date=original_campaign.campaign_start_date,
            campaign_end_date=original_campaign.campaign_end_date,
            ctas=original_campaign.ctas,
        )
        campaign.status = original_campaign_status
        campaign.name = "Split - Batch#{i} of {num_campaigns} ({original})".format(
            i=i + 1, num_campaigns=num_campaigns, original=original_campaign.name
        )
        db.session.add(campaign)
        db.session.commit()
        campaign_ids.append(campaign.id)

    original_campaign = OutboundCampaign.query.get(original_campaign_id)
    original_campaign.status = OutboundCampaignStatus.CANCELLED
    db.session.add(original_campaign)
    db.session.commit()

    return campaign_ids


def batch_update_campaigns(payload: dict):
    """Batch update campaigns

    payload looks like
    ```
    [{"client":"Parker #14","campaign_id":148,"archetype":"Online shop owners","name":"Martin Mrozowski","campaign_specs":"#148 LINKEDIN","campaign_start_date":"2022-12-14","campaign_end_date":"2023-01-14","status":"READY_TO_SEND","uuid":"4y8idpRlNXyvNth2Iy7Ei0Z4YOl5vjnT","campaign_name":"Pierce, Bash 1, Online shop owners, 75, 2022-12-26","auth_token":"PvVELxlEfi52pcKJ5ms8GJnVcFyQgKWg","num_prospects":"75","num_generated":"73","num_edited":"73","num_sent":"2"}]
    ```

    Args:
        payload (dict): Payload containing the campaigns to update
    """
    for campaign_payload in payload:
        campaign_id = campaign_payload["campaign_id"]
        campaign_start_date = datetime.datetime.strptime(
            campaign_payload["campaign_start_date"][0:10], "%Y-%m-%d"
        )
        campaign_end_date = datetime.datetime.strptime(
            campaign_payload["campaign_end_date"][0:10], "%Y-%m-%d"
        )
        status = campaign_payload["status"]
        campaign_name = campaign_payload["campaign_name"]
        editor_id = campaign_payload["editor_id"]
        editing_due_date = campaign_payload["editing_due_date"]
        receipt_link = campaign_payload.get("receipt_link")
        cost = campaign_payload.get("cost")

        campaign = OutboundCampaign.query.get(campaign_id)
        campaign.campaign_start_date = campaign_start_date
        campaign.campaign_end_date = campaign_end_date
        campaign.status = OutboundCampaignStatus[status]
        campaign.name = campaign_name
        campaign.editor_id = editor_id
        campaign.editing_due_date = editing_due_date
        if receipt_link:
            campaign.receipt_link = receipt_link
        if cost:
            campaign.cost = cost

        db.session.add(campaign)
        db.session.commit()

    return True


def batch_update_campaign_editing_attributes(payload: dict):
    """Batch update campaigns from editing portal

    payload looks like
    ```
    [{
        "campaign_id": int,
        "reported_time_in_hours": int,
        "reviewed_feedback": bool,
        "sellscale_grade": str,
        "brief_feedback_summary": str,
        "detailed_feedback_link": str
    }]
    ```
    """
    for entry in payload:
        campaign_id = entry["campaign_id"]
        reported_time_in_hours = entry["reported_time_in_hours"]
        reviewed_feedback = entry["reviewed_feedback"]
        sellscale_grade = entry["sellscale_grade"]
        brief_feedback_summary = entry["brief_feedback_summary"]
        detailed_feedback_link = entry["detailed_feedback_link"]

        campaign = OutboundCampaign.query.get(campaign_id)
        campaign.reported_time_in_hours = reported_time_in_hours
        campaign.reviewed_feedback = reviewed_feedback
        campaign.sellscale_grade = sellscale_grade
        campaign.brief_feedback_summary = brief_feedback_summary
        campaign.detailed_feedback_link = detailed_feedback_link

        db.session.add(campaign)
        db.session.commit()
    return True


def assign_editor_to_campaign(editor_id: int, campaign_id: int):
    """Assigns an editor to a campaign

    Args:
        editor_id (int): Editor id
        campaign_id (int): Campaign id
    """
    campaign = OutboundCampaign.query.get(campaign_id)
    campaign.editor_id = editor_id
    db.session.add(campaign)
    db.session.commit()

    return True


def remove_ungenerated_prospects_from_campaign(campaign_id: int):
    """Removes ungenerated prospects from a campaign

    Args:
        campaign_id (int): Campaign id
    """
    campaign: OutboundCampaign = OutboundCampaign.query.get(campaign_id)
    prospect_ids = campaign.prospect_ids

    not_generated_prospects = []
    if campaign.campaign_type == GeneratedMessageType.EMAIL:
        not_generated_prospects = Prospect.query.filter(
            Prospect.id.in_(prospect_ids),
            Prospect.approved_prospect_email_id == None,
        ).all()
    elif campaign.campaign_type == GeneratedMessageType.LINKEDIN:
        not_generated_prospects = Prospect.query.filter(
            Prospect.id.in_(prospect_ids),
            Prospect.approved_outreach_message_id == None,
        ).all()

    not_generated_prospect_ids = [prospect.id for prospect in not_generated_prospects]

    new_list = []
    for prospect_id in prospect_ids:
        if prospect_id not in not_generated_prospect_ids:
            new_list.append(prospect_id)

    campaign = OutboundCampaign.query.get(campaign_id)
    campaign.prospect_ids = new_list
    db.session.add(campaign)
    db.session.commit()

    return True


def create_new_li_campaign_from_existing_email_campaign(email_campaign_id: int):
    """Creates a new LinkedIn campaign from an existing email campaign

    Args:
        email_campaign_id (int): Email campaign id
    """
    email_campaign = OutboundCampaign.query.get(email_campaign_id)
    if not email_campaign:
        raise Exception("Email campaign not found")
    if email_campaign.campaign_type != GeneratedMessageType.EMAIL:
        raise Exception("Campaign is not an email campaign")

    new_campaign = create_outbound_campaign(
        prospect_ids=email_campaign.prospect_ids,
        num_prospects=len(email_campaign.prospect_ids),
        campaign_type=GeneratedMessageType.LINKEDIN,
        client_archetype_id=email_campaign.client_archetype_id,
        client_sdr_id=email_campaign.client_sdr_id,
        campaign_start_date=email_campaign.campaign_start_date,
        campaign_end_date=email_campaign.campaign_end_date,
        ctas=[
            cta.id
            for cta in GeneratedMessageCTA.get_active_ctas_for_archetype(
                email_campaign.client_archetype_id
            )
        ],
    )

    return new_campaign


def get_outbound_campaign_analytics(campaign_id: int) -> dict:
    """Gets analytics for a campaign

    Gateway for getting either Email analytics or LinkedIn analytics

    Args:
        campaign_id (int): Campaign id

    Returns:
        dict: analytics metrics
    """
    campaign: OutboundCampaign = OutboundCampaign.query.get(campaign_id)

    if campaign.campaign_type == GeneratedMessageType.EMAIL:
        return get_email_campaign_analytics(campaign_id)
    elif campaign.campaign_type == GeneratedMessageType.LINKEDIN:
        return get_linkedin_campaign_analytics(campaign_id)


def get_email_campaign_analytics(campaign_id: int) -> dict:
    """Gets analytics for an email campaign

    This endpoint returns the following metrics, with the prospect ids for each:
    - Campaign ID
    - Campaign type
    - Campaign name
    - Campaign start date
    - Campaign end date
    - All prospects
    - Not sent
    - Email bounced
    - Email sent
    - Email opened
    - Email accepted
    - Email replied
    - Prospect scheduling
    - Prospect not interested
    - Prospect demo set
    - Prospect demo won

    Args:
        campaign_id (int): Campaign id

    Returns:
        dict: analytics metrics
    """
    campaign: OutboundCampaign = OutboundCampaign.query.get(campaign_id)
    if not campaign:
        raise Exception("Campaign not found")
    elif campaign.campaign_type != GeneratedMessageType.EMAIL:
        raise Exception("Campaign is not an email campaign")

    not_sent = []
    email_bounced = []

    email_sent = []
    email_opened = []
    email_accepted = []
    email_bumped = []
    email_replied = []
    prospect_scheduling = []

    prospect_not_interested = []
    prospect_demo_set = []
    prospect_demo_won = []
    prospect_demo_lost = []

    # Get all prospects that have been sent an email
    email_prospects: list[ProspectEmail] = ProspectEmail.query.filter(
        ProspectEmail.prospect_id.in_(campaign.prospect_ids),
    ).all()
    for email_prospect in email_prospects:
        if email_prospect.email_status != ProspectEmailStatus.SENT:
            not_sent.append(email_prospect.prospect_id)
            continue

        outreach_status = email_prospect.outreach_status
        if outreach_status == ProspectEmailOutreachStatus.SENT_OUTREACH:
            email_sent.append(email_prospect.prospect_id)
        elif outreach_status == ProspectEmailOutreachStatus.EMAIL_OPENED:
            email_opened.append(email_prospect.prospect_id)
        elif outreach_status == ProspectEmailOutreachStatus.ACCEPTED:
            email_accepted.append(email_prospect.prospect_id)
        elif outreach_status == ProspectEmailOutreachStatus.BUMPED:
            email_bumped.append(email_prospect.prospect_id)
        elif outreach_status == ProspectEmailOutreachStatus.ACTIVE_CONVO:
            email_replied.append(email_prospect.prospect_id)
        elif outreach_status == ProspectEmailOutreachStatus.SCHEDULING:
            prospect_scheduling.append(email_prospect.prospect_id)
        elif outreach_status == ProspectEmailOutreachStatus.NOT_INTERESTED:
            prospect_not_interested.append(email_prospect.prospect_id)
        elif outreach_status == ProspectEmailOutreachStatus.DEMO_SET:
            prospect_demo_set.append(email_prospect.prospect_id)
        elif outreach_status == ProspectEmailOutreachStatus.DEMO_WON:
            prospect_demo_won.append(email_prospect.prospect_id)
        elif outreach_status == ProspectEmailOutreachStatus.DEMO_LOST:
            prospect_demo_lost.append(email_prospect.prospect_id)

    return {
        "campaign_id": campaign_id,
        "campaign_type": campaign.campaign_type.value,
        "campaign_name": campaign.name,
        "campaign_start_date": campaign.campaign_start_date,
        "campaign_end_date": campaign.campaign_end_date,
        "all_prospects": campaign.prospect_ids,
        "not_sent": not_sent,
        "email_bounced": email_bounced,
        "email_sent": email_sent,
        "email_opened": email_opened,
        "email_accepted": email_accepted,
        "email_bumped": email_bumped,
        "email_replied": email_replied,
        "prospect_scheduling": prospect_scheduling,
        "prospect_not_interested": prospect_not_interested,
        "prospect_demo_set": prospect_demo_set,
        "prospect_demo_won": prospect_demo_won,
        "prospect_demo_lost": prospect_demo_lost,
    }


def get_linkedin_campaign_analytics(campaign_id: int):
    """
    Gets analytics for a LinkedIn campaign

    This endpoint returns the following metrics, with the prospect ids for each:
    - Campaign ID
    - Campaign type
    - Campaign name
    - Campaign start date
    - Campaign end date
    - All prospects sent campaign
    - All prospects who accepted the invite
    - All prospects who replied to the invite
    - All prospects who scheduled a demo
    """
    campaign: OutboundCampaign = OutboundCampaign.query.get(campaign_id)
    if not campaign:
        raise Exception("Campaign not found")
    elif campaign.campaign_type != GeneratedMessageType.LINKEDIN:
        raise Exception("Campaign is not a LinkedIn campaign")

    data = db.session.execute(
        f"""select
        count(distinct prospect.id) filter (where prospect_status_records.to_status = 'SENT_OUTREACH') "# of Sent Outreach",
        count(distinct prospect.id) filter (where prospect_status_records.to_status = 'ACCEPTED') "# of Acceptances",
        count(distinct prospect.id) filter (where prospect_status_records.to_status = 'ACTIVE_CONVO') "# of Active Convos",
        count(distinct prospect.id) filter (where prospect_status_records.to_status = 'DEMO_SET') "# of Demo Sets",
        array_agg(distinct prospect.company) filter (where prospect_status_records.to_status = 'DEMO_SET') "Distinct Companies"
    from outbound_campaign
        join prospect on prospect.id = any(outbound_campaign.prospect_ids)
        join prospect_status_records on prospect_status_records.prospect_id = prospect.id
    where outbound_campaign.id = {campaign_id}
    group by outbound_campaign.id"""
    ).fetchone()

    analytics = {
        "Campaign ID": campaign_id,
        "Campaign Type": campaign.campaign_type.value,
        "Campaign Name": campaign.name,
        "Campaign Start date": campaign.campaign_start_date,
        "Campaign End date": campaign.campaign_end_date,
        "# Sent": data and data[0],
        "# Acceptances": data and data[1],
        "# Replies": data and data[2],
        "# Demos": data and data[3],
        "Companies Demos": data and data[4],
    }

    return analytics


@celery.task
def wipe_campaign_generations(campaign_id: int):
    """Wipes all messages generations for a campaign

    Args:
        campaign_id (int): Campaign id
    """
    campaign: OutboundCampaign = OutboundCampaign.query.get(campaign_id)
    if not campaign:
        raise Exception("Campaign not found")

    prospect_ids = campaign.prospect_ids
    if campaign.campaign_type == GeneratedMessageType.EMAIL:
        for p_id in tqdm(prospect_ids):
            wipe_prospect_email_and_generations_and_research.delay(p_id)
    elif campaign.campaign_type == GeneratedMessageType.LINKEDIN:
        for p_id in tqdm(prospect_ids):
            reset_prospect_research_and_messages.delay(p_id)


def remove_prospect_from_campaign(campaign_id: int, prospect_id: int):
    """
    Removes a prospect from a campaign
    """
    campaign: OutboundCampaign = OutboundCampaign.query.get(campaign_id)

    if not campaign:
        raise Exception("Campaign not found")

    if prospect_id not in campaign.prospect_ids:
        raise Exception("Prospect not found in campaign")

    new_prospects = []
    for p_id in campaign.prospect_ids:
        if p_id != prospect_id:
            new_prospects.append(p_id)
    campaign.prospect_ids = new_prospects

    db.session.add(campaign)
    db.session.commit()

    return True


def payout_campaigns(campaign_ids: list):
    campaigns: list[OutboundCampaign] = OutboundCampaign.query.filter(
        OutboundCampaign.id.in_(campaign_ids)
    ).all()

    for campaign in campaigns:
        campaign.calculate_cost()
        db.session.add(campaign)
        db.session.commit()

    return True


@celery.task
def detect_campaign_multi_channel_dash_card():
    sdrs: list[ClientSDR] = ClientSDR.query.filter_by(
        active=True,
        client_id=1,  # TEMP
    ).all()

    for sdr in sdrs:
        sdr_id = sdr.id
        archetypes: list[ClientArchetype] = ClientArchetype.query.filter_by(
            client_sdr_id=sdr_id,
        ).all()
        li_archetypes = [ca for ca in archetypes if ca.linkedin_active == True]
        email_archetypes = [ca for ca in archetypes if ca.email_active == True]

        if len(li_archetypes) == 0 and len(email_archetypes) > 0:
            # Make card to create li campaign
            create_campaign_ai_request(
                sdr_id=sdr_id,
                name="LinkedIn Campaign",
                description="",
                linkedin=True,
                email=False,
            )

        if len(email_archetypes) == 0 and len(li_archetypes) > 0:
            # Make card to create email campaign
            create_campaign_ai_request(
                sdr_id=sdr_id,
                name="Email Campaign",
                description="",
                linkedin=False,
                email=True,
            )


def create_campaign_ai_request(
    sdr_id: int,
    name: str,
    description: str,
    linkedin: bool,
    email: bool,
    segmentId: int = None,
):
    from src.ai_requests.models import AIRequest
    from src.ai_requests.services import create_ai_requests

    title = f"New Campaign Request: {name}"

    ai_requests: list[AIRequest] = AIRequest.query.filter(
        AIRequest.client_sdr_id == sdr_id, AIRequest.title == title
    ).all()
    if len(ai_requests) > 0:
        return False

    sdr: ClientSDR = ClientSDR.query.get(sdr_id)

    segment_name = None
    if segmentId:
        segment: Segment = Segment.query.get(segmentId)
        if segment:
            segment_name = segment.segment_title

    create_ai_requests(
        client_sdr_id=sdr_id,
        description=f"""

Segment: {segment_name}

Title: {name}

Description:
{sdr.name} is requesting a new campaign.

What do you want to say?:
{description}

Linkedin: {'True' if linkedin else 'False'}
Email: {'True' if email else 'False'}

        """.strip(),
        title=title,
        days_till_due=7,
    )

    return True


def get_client_campaign_view_data(client_sdr_id: int):
    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)

    data = db.session.execute(
        """
with d as (
	select
		client.company "Company",
		client_sdr.name "Rep",
		concat(client_archetype.emoji, ' ', client_archetype.archetype) "Campaign",
		client_archetype.active "active",
		client_archetype.linkedin_active,
		client_archetype.email_active,
		case when client_archetype.template_mode = true then 'template-mode' else 'cta-mode' end "linkedin_mode",
		count(distinct operator_dashboard_entry.id) filter (where operator_dashboard_entry.status = 'COMPLETED') "num_complete_tasks",
		count(distinct operator_dashboard_entry.id) filter (where operator_dashboard_entry.status = 'PENDING') "num_open_tasks",
		count(distinct prospect.id) "num_prospects",
		count(distinct prospect.id) filter (where prospect.email is not null) "num_prospects_with_email",
		count(distinct linkedin_initial_message_template.id) "num_templates_active",
		count(distinct generated_message_cta.id) "num_templates_active",
		count(distinct bump_framework.id) "num_templates_active",
		count(distinct email_sequence_step.id) "num_templates_active",
		count(distinct prospect_status_records.prospect_id) filter (where prospect_status_records.to_status = 'SENT_OUTREACH') "num_linkedin_sent",
		count(distinct prospect_email.prospect_id) filter (where prospect_email_status_records.to_status = 'SENT_OUTREACH') "num_email_sent"
	from client_sdr
		join client on client.id = client_sdr.client_id
		left join client_archetype
			on client_archetype.client_sdr_id = client_sdr.id and client_archetype.active and not client_archetype.is_unassigned_contact_archetype
		left join
			operator_dashboard_entry on cast(operator_dashboard_entry.task_data->>'campaign_id' as integer) = client_archetype.id
		left join
			prospect on prospect.archetype_id = client_archetype.id
		left join
			linkedin_initial_message_template on linkedin_initial_message_template.client_archetype_id = client_archetype.id and linkedin_initial_message_template.active
		left join
			generated_message_cta on generated_message_cta.archetype_id = client_archetype.id and generated_message_cta.active
		left join
			bump_framework on bump_framework.client_archetype_id = client_archetype.id and bump_framework.overall_status in ('ACCEPTED', 'BUMPED') and bump_framework.active and bump_framework.default
		left join email_sequence_step on email_sequence_step.client_archetype_id = client_archetype.id and email_sequence_step.active and email_sequence_step.default
		left join prospect_status_records on prospect_status_records.prospect_id = prospect.id
		left join prospect_email on prospect_email.prospect_id = prospect.id
		left join prospect_email_status_records on prospect_email_status_records.prospect_email_id = prospect_email.id
	where client.id = {client_id}
	group by 1,2,3,4,5,6,7
	order by 1 asc, 2 asc
)
select
	case
		when length(d."Campaign") = 1 then '5. 🔴 No Campaign Found'
		when d.active and d."num_complete_tasks" = 0 and d."num_open_tasks" = 0 and (d.num_linkedin_sent = 0 and d.num_email_sent = 0) then '4. 🗄 In Setup'
		when d.active and d."num_open_tasks" > 0 then '3. 🟡 Rep Action Needed'
		when d.active and d."num_complete_tasks" > 0 and (d.num_linkedin_sent = 0 and d.num_email_sent = 0) then '2. ⏫ Uploading to SellScale'
		when d.active and (d.num_linkedin_sent > 0 or d.num_email_sent > 0) then '1. 🟢 Campaign Active'
		when not d.active and (d.num_linkedin_sent > 0 or d.num_email_sent > 0) then '9. ☑️ Campaign Complete'
		else 'uncategorized'
	end "Status",
	d."Company",
	d."Rep",
	d."Campaign"
from d
order by 1 asc, 2 asc, 3 asc;
""".format(
            client_id=sdr.client_id
        )
    ).fetchall()

    records = []
    for entry in data:
        status = entry[0]
        company = entry[1]
        rep = entry[2]
        campaign = entry[3]
        records.append(
            {"status": status, "company": company, "rep": rep, "campaign": campaign}
        )

    return records


def get_outbound_data(client_sdr_id: int):
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client_id: int = client_sdr.client_id
    seat_data = db.session.execute(
        f"""
        select
            count(distinct client_sdr.id) "active_seats",
            count(distinct client_archetype.client_sdr_id) filter (where client_archetype.active and (client_archetype.linkedin_active or client_archetype.email_active)) "num_used_seats"
        from client_sdr
            left join client_archetype on client_archetype.client_sdr_id = client_sdr.id
        where
            client_sdr.client_id = {client_id}
            and client_sdr.active;
        """
    ).fetchone()

    message_data = db.session.execute(
        f"""
        with d as (
            select
                sum(client_sdr.weekly_li_outbound_target) + sum(client_sdr.weekly_email_outbound_target) "num_messages",
                sum(client_sdr.weekly_li_outbound_target) filter (where client_archetype.active and (client_archetype.linkedin_active)) "num_linkedin",
                sum(client_sdr.weekly_email_outbound_target) filter (where client_archetype.active and (client_archetype.email_active)) "num_email"
            from client_sdr
                left join client_archetype on client_archetype.client_sdr_id = client_sdr.id
            where
                client_sdr.client_id = {client_id}
                and client_sdr.active
        )
        select
            num_messages,
            case when num_linkedin is not null then num_linkedin else 0 end +
                case when num_email is not null then num_email else 0 end "num_messages_used"
        from d;
        """
    ).fetchone()

    data = {
        "seat_total": seat_data[0],
        "seat_active": seat_data[1],
        "message_total": message_data[0],
        "message_active": message_data[1],
    }
    return data


def get_account_based_data(client_sdr_id: int, offset: int):
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client_id: int = client_sdr.client_id
    offset: int = offset

    count_query = """
        with helper as (
            with company_spark_helper as (
                select
                    prospect.company_id,
                    to_char(
                        case
                            when
                                (prospect_status_records.created_at is not null and prospect_status_records.to_status = 'ACCEPTED') then prospect_status_records.created_at
                            when
                                (prospect_email_status_records.created_at is not null and prospect_email_status_records.to_status = 'ACCEPTED') then prospect_email_status_records.created_at
                            else null
                    end, 'YYYY-MM-DD HH:WW') date,
                    count(distinct prospect.id) num_prospects
                from prospect
                    left join prospect_status_records on prospect_status_records.prospect_id = prospect.id
                    left join prospect_email on prospect_email.prospect_id = prospect.id
                    left join prospect_email_status_records on prospect_email_status_records.prospect_email_id = prospect_email.id
                where prospect.client_id = 47
                    and (
                        prospect_status_records.to_status in ('ACCEPTED', 'ACTIVE_CONVO', 'DEMO_SET')
                        or prospect_email_status_records.to_status in ('ACCEPTED', 'ACTIVE_CONVO', 'DEMO_SET')
                    )
                group by 1,2
                order by 2 desc
            )
            select
                company,
                prospect.company_id,
                prospect.company_url,
                array_agg(
                    distinct company_spark_helper.num_prospects
                ) filter (where company_spark_helper.num_prospects is not null) sparkline_data,
                max(company_spark_helper.num_prospects)	sparkline_max,
                min(company_spark_helper.num_prospects) sparkline_min,
                max(
                    case
                        when
                            (prospect_status_records.created_at is not null and prospect_status_records.to_status = 'ACCEPTED') then prospect_status_records.created_at
                        when
                            (prospect_email_status_records.created_at is not null and prospect_email_status_records.to_status = 'ACCEPTED') then prospect_email_status_records.created_at
                        else null
                end) latest_reply,

                count(distinct prospect.id) filter (where prospect_status_records.to_status = 'SENT_OUTREACH' or prospect_email_status_records.to_status = 'SENT_OUTREACH') num_sent,
                    count(distinct prospect.id) filter (where prospect_status_records.to_status = 'ACCEPTED' or prospect_email_status_records.to_status = 'ACCEPTED') num_accepted,
                    count(distinct prospect.id) filter (where prospect_status_records.to_status = 'ACTIVE_CONVO' or prospect_email_status_records.to_status = 'ACTIVE_CONVO') num_replied,
                    count(distinct prospect.id) filter (where prospect_status_records.to_status in ('ACTIVE_CONVO_SCHEDULING', 'ACTIVE_CONVO_NEXT_STEPS', 'ACTIVE_CONVO_QUESTION') or prospect_email_status_records.to_status = 'DEMO_SET') num_positive_reply,
                    count(distinct prospect.id) filter (where prospect_status_records.to_status = 'DEMO_SET' or prospect_email_status_records.to_status = 'DEMO_SET') num_demo
            from prospect
                left join prospect_status_records on prospect_status_records.prospect_id = prospect.id
                left join prospect_email on prospect_email.prospect_id = prospect.id
                left join prospect_email_status_records on prospect_email_status_records.prospect_email_id = prospect_email.id
                join company_spark_helper on company_spark_helper.company_id = prospect.company_id
            where prospect.client_id = 47
            group by 1,2,3
            having
                count(distinct prospect.id) filter
                    (where prospect_status_records.to_status = 'ACCEPTED' or prospect_email_status_records.to_status = 'ACCEPTED') > 0

            order by 5 desc
            offset 0
        )
        select
            count(*)
        from helper;
    """.format(
        CLIENT_ID=client_id, OFFSET=offset * 15
    )

    count_result = db.session.execute(count_query).fetchone()
    count = count_result[0] if count_result else 0

    query = """
        with helper as (
            with company_spark_helper as (
                select
                    prospect.company_id,
                    to_char(
                        case
                            when
                                (prospect_status_records.created_at is not null and prospect_status_records.to_status = 'ACCEPTED') then prospect_status_records.created_at
                            when
                                (prospect_email_status_records.created_at is not null and prospect_email_status_records.to_status = 'ACCEPTED') then prospect_email_status_records.created_at
                            else null
                    end, 'YYYY-MM-DD HH:WW') date,
                    count(distinct prospect.id) num_prospects
                from prospect
                    left join prospect_status_records on prospect_status_records.prospect_id = prospect.id
                    left join prospect_email on prospect_email.prospect_id = prospect.id
                    left join prospect_email_status_records on prospect_email_status_records.prospect_email_id = prospect_email.id
                where prospect.client_id = {CLIENT_ID}
                    and (
                        prospect_status_records.to_status in ('ACCEPTED', 'ACTIVE_CONVO', 'DEMO_SET')
                        or prospect_email_status_records.to_status in ('ACCEPTED', 'ACTIVE_CONVO', 'DEMO_SET')
                    )
                group by 1,2
                order by 2 desc
            )
            select
                company,
                prospect.company_id,
                prospect.company_url,
                array_agg(
                    distinct company_spark_helper.num_prospects
                ) filter (where company_spark_helper.num_prospects is not null) sparkline_data,
                max(company_spark_helper.num_prospects)	sparkline_max,
                min(company_spark_helper.num_prospects) sparkline_min,
                max(
                    case
                        when
                            (prospect_status_records.created_at is not null and prospect_status_records.to_status = 'ACCEPTED') then prospect_status_records.created_at
                        when
                            (prospect_email_status_records.created_at is not null and prospect_email_status_records.to_status = 'ACCEPTED') then prospect_email_status_records.created_at
                        else null
                end) latest_reply,

                count(distinct prospect.id) filter (where prospect_status_records.to_status = 'SENT_OUTREACH' or prospect_email_status_records.to_status = 'SENT_OUTREACH') num_sent,
                    count(distinct prospect.id) filter (where prospect_status_records.to_status = 'ACCEPTED' or prospect_email_status_records.to_status = 'ACCEPTED') num_accepted,
                    count(distinct prospect.id) filter (where prospect_status_records.to_status = 'ACTIVE_CONVO' or prospect_email_status_records.to_status = 'ACTIVE_CONVO') num_replied,
                    count(distinct prospect.id) filter (where prospect_status_records.to_status in ('ACTIVE_CONVO_SCHEDULING', 'ACTIVE_CONVO_NEXT_STEPS', 'ACTIVE_CONVO_QUESTION') or prospect_email_status_records.to_status = 'DEMO_SET') num_positive_reply,
                    count(distinct prospect.id) filter (where prospect_status_records.to_status = 'DEMO_SET' or prospect_email_status_records.to_status = 'DEMO_SET') num_demo
            from prospect
                left join prospect_status_records on prospect_status_records.prospect_id = prospect.id
                left join prospect_email on prospect_email.prospect_id = prospect.id
                left join prospect_email_status_records on prospect_email_status_records.prospect_email_id = prospect_email.id
                join company_spark_helper on company_spark_helper.company_id = prospect.company_id
            where prospect.client_id = {CLIENT_ID}
            group by 1,2,3
            having
                count(distinct prospect.id) filter
                    (where prospect_status_records.to_status = 'ACCEPTED' or prospect_email_status_records.to_status = 'ACCEPTED') > 0

            order by 5 desc
            limit 25
            offset {OFFSET}
        )
        select
            company,
            company_id,
            company_url,
            sparkline_data,
            case
                when sparkline_min = sparkline_max then 'LOW'
                when sparkline_max / cast(sparkline_min as float) < 5 then 'MID'
                else 'HIGH'
            end status,
            latest_reply,
            num_sent,
            num_accepted,
            num_replied,
            num_positive_reply,
            num_demo

        from helper
        order by latest_reply desc;
    """.format(
        CLIENT_ID=client_id, OFFSET=offset
    )

    results = db.session.execute(query).fetchall()

    if results is not None:
        results = [dict(row) for row in results]

    return {"count": count, "results": results}
