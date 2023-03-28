from app import db, celery
from sqlalchemy import and_, or_
from typing import Optional

from src.campaigns.models import *
from src.client.services import get_client
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
)
from sqlalchemy.sql.expression import func
from src.email_outbound.services import get_approved_prospect_email_by_id
from src.integrations.vessel import SalesEngagementIntegration
from tqdm import tqdm
from src.message_generation.services import (
    wipe_prospect_email_and_generations_and_research,
    generate_outreaches_for_prospect_list_from_multiple_ctas,
    create_and_start_email_generation_jobs,
)
from src.research.linkedin.services import reset_prospect_research_and_messages
from src.message_generation.services_few_shot_generations import (
    can_generate_with_few_shot,
)
from src.utils.random_string import generate_random_alphanumeric
from src.utils.slack import send_slack_message, URL_MAP
from src.client.services import get_cta_stats

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


def get_outbound_campaign_details_for_edit_tool(
    client_sdr_id: int, campaign_id: int, approved_filter: Optional[bool] = None
) -> dict:
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

    # Get join of prospect and message
    if oc.campaign_type.value == "LINKEDIN":
        joined_prospect_message = (
            db.session.query(
                Prospect.id.label("prospect_id"),
                Prospect.full_name.label("full_name"),
                GeneratedMessage.id.label("message_id"),
                GeneratedMessage.ai_approved.label("ai_approved"),
                GeneratedMessage.completion.label("completion"),
                GeneratedMessage.problems.label("problems"),
                GeneratedMessage.highlighted_words.label("highlighted_words"),
            )
            .join(
                GeneratedMessage,
                Prospect.approved_outreach_message_id == GeneratedMessage.id,
            )
            .filter(Prospect.id.in_(oc.prospect_ids))
        )
    if oc.campaign_type.value == "EMAIL":
        joined_prospect_message = (
            db.session.query(
                Prospect.id.label("prospect_id"),
                Prospect.full_name.label("full_name"),
                GeneratedMessage.id.label("message_id"),
                GeneratedMessage.ai_approved.label("ai_approved"),
                GeneratedMessage.completion.label("completion"),
                GeneratedMessage.problems.label("problems"),
                GeneratedMessage.highlighted_words.label("highlighted_words"),
            )
            .join(
                ProspectEmail, Prospect.approved_prospect_email_id == ProspectEmail.id
            )
            .join(
                GeneratedMessage,
                ProspectEmail.personalized_first_line == GeneratedMessage.id,
            )
            .filter(Prospect.id.in_(oc.prospect_ids))
        )

    # Filter by approved messages if filter is set
    if approved_filter is False:
        joined_prospect_message = joined_prospect_message.filter(or_(GeneratedMessage.ai_approved == False, GeneratedMessage.ai_approved == None))
    elif approved_filter is True:
        joined_prospect_message = joined_prospect_message.filter(GeneratedMessage.ai_approved == True)
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
) -> dict[int, list[OutboundCampaign]]:
    """Gets outbound campaigns belonging to the SDR, with optional query and filters.

    Authorization required.

    Args:
        client_sdr_id: The ID of the SDR.
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

    Returns:
        OutboundCampaign: The newly created outbound campaign
    """
    # Smart get prospects to use
    if num_prospects > len(prospect_ids):
        top_prospects = smart_get_prospects_for_campaign(
            client_archetype_id, num_prospects - len(prospect_ids), campaign_type
        )
        prospect_ids.extend(top_prospects)
        pass

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
        and not can_generate_with_few_shot(prospect1.id)
        and len(prospect_ids) > 10
        and campaign_type == GeneratedMessageType.LINKEDIN.value
    ):
        raise Exception(
            "Cannot generate Linkedin campaign of more than 10 prospects without few shot generation enabled. Enable few shot first!"
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
    )
    db.session.add(campaign)
    db.session.commit()
    return campaign


def smart_get_prospects_for_campaign(
    client_archetype_id: int, num_prospects: int, campaign_type: str
) -> list[int]:
    """Smartly gets prospects for a campaign (based on health check score)

    Args:
        client_archetype_id (int): Client archetype id
        num_prospects (int): Number of prospects to get

    Returns:
        list[int]: List of prospect ids
    """
    prospects_query = Prospect.query.filter(
        Prospect.archetype_id == client_archetype_id,
        Prospect.health_check_score != None,
    )
    if campaign_type == GeneratedMessageType.LINKEDIN.value:
        prospects_query = prospects_query.filter(
            Prospect.approved_outreach_message_id == None
        )
    elif campaign_type == GeneratedMessageType.EMAIL.value:
        prospects_query = prospects_query.filter(
            Prospect.approved_prospect_email_id == None,
            Prospect.email.isnot(None),
        )

    prospects = (
        prospects_query.order_by(Prospect.health_check_score.desc(), func.random())
        .limit(num_prospects)
        .all()
    )

    if len(prospects) < num_prospects:
        additional_prospects_query = Prospect.query.filter(
            Prospect.archetype_id == client_archetype_id,
            Prospect.health_check_score == None,
        )
        if campaign_type == GeneratedMessageType.LINKEDIN.value:
            additional_prospects_query = additional_prospects_query.filter(
                Prospect.approved_outreach_message_id == None
            )
        elif campaign_type == GeneratedMessageType.EMAIL.value:
            additional_prospects_query = additional_prospects_query.filter(
                Prospect.approved_prospect_email_id == None,
                Prospect.email.isnot(None),
            )
        additional_prospects = (
            additional_prospects_query.order_by(func.random())
            .limit(num_prospects - len(prospects))
            .all()
        )
        prospects.extend(additional_prospects)

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
        create_and_start_email_generation_jobs.apply_async(args=[campaign_id])
    elif campaign.campaign_type == GeneratedMessageType.LINKEDIN:
        generate_outreaches_for_prospect_list_from_multiple_ctas.apply_async(
            args=[campaign.prospect_ids, campaign.ctas, campaign_id]
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

    campaign: OutboundCampaign = OutboundCampaign.query.get(campaign_id)
    sdr: ClientSDR = ClientSDR.query.get(campaign.client_sdr_id)
    sdr_name = sdr.name
    client_id = sdr.client_id
    client_company = get_client(client_id).company

    campaign_name = campaign.name.split(",")[0]
    campaign_type = campaign.campaign_type.value

    if status == OutboundCampaignStatus.COMPLETE.value:
        send_slack_message(
            message="{} - {}'s Campaign #{} is complete! :tada::tada::tada:".format(
                client_company, sdr_name, campaign_id
            ),
            blocks=[
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "{} - {}'s Campaign #{} is `{}`! :tada::tada::tada:".format(
                            client_company, sdr_name, campaign_id, status
                        ),
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
                        "text": "*Campaign Type #:* {}".format(campaign_type),
                    },
                },
            ],
            webhook_urls=[URL_MAP["operations-ready-campaigns"]],
        )

    return True


def mark_campaign_as_ready_to_send(campaign_id: int):
    """Marks the campaign as ready to send

    Args:
        campaign_id (int): Campaign id
    """
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

    send_slack_message(
        message="{} - {}'s Campaign #{} is ready to send! :tada:".format(
            client_company, sdr_name, campaign_id
        ),
        blocks=[
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "{} - {}'s Campaign #{} is ready to send! :tada:".format(
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
                    "text": {
                        "type": "plain_text",
                        "text": "Go to {}'s Sight".format(sdr_name),
                        "emoji": True,
                    },
                    "value": "https://sight.sellscale.com/?token={}".format(sdr_auth)
                    or "https://sight.sellscale.com/sight",
                    "url": "https://sight.sellscale.com/?token={}".format(sdr_auth)
                    or "https://sight.sellscale.com/sight",
                    "action_id": "button-action,",
                },
            },
        ],
        webhook_urls=[URL_MAP["operations-ready-campaigns"]],
    )

    return True


def mark_campaign_as_initial_review_complete(campaign_id: int):
    """Marks the campaign as initial edit is complete

    Args:
        campaign_id (int): Campaign id
    """
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
    prospect_count = len(campaign.prospect_ids)
    campaign_type = campaign.campaign_type.value
    start_date = campaign.campaign_start_date.strftime("%b %d, %Y")
    end_date = campaign.campaign_end_date.strftime("%b %d, %Y")

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
                    "text": {
                        "type": "plain_text",
                        "text": "Go to {}'s Sight".format(sdr_name),
                        "emoji": True,
                    },
                    "value": "https://sight.sellscale.com/?token={}".format(sdr_auth)
                    or "https://sight.sellscale.com/sight",
                    "url": "https://sight.sellscale.com/?token={}".format(sdr_auth)
                    or "https://sight.sellscale.com/sight",
                    "action_id": "button-action,",
                },
            },
        ],
        webhook_urls=[URL_MAP["operations-ready-campaigns"]],
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
          max(vessel_sequences.name) sequence_name,
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
          left join vessel_sequences on vessel_sequences.sequence_id = cast(prospect_email.vessel_sequence_id as varchar)
        where outbound_campaign.client_sdr_id = {client_sdr_id}
            and outbound_campaign.campaign_type = 'EMAIL'
          and outbound_campaign.status = 'COMPLETE'
          and vessel_sequences.id is not null
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
        return get_linkedin_campaign_analytics()


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
        "email_replied": email_replied,
        "prospect_scheduling": prospect_scheduling,
        "prospect_not_interested": prospect_not_interested,
        "prospect_demo_set": prospect_demo_set,
        "prospect_demo_won": prospect_demo_won,
        "prospect_demo_lost": prospect_demo_lost,
    }


def get_linkedin_campaign_analytics():
    return "Not yet implemented"


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


@celery.task
def personalize_and_enroll_in_sequence(
    client_id: int, prospect_id: int, mailbox_id: int, sequence_id: Optional[int] = None
):
    sei: SalesEngagementIntegration = SalesEngagementIntegration(client_id=client_id)
    contact = sei.create_or_update_contact_by_prospect_id(prospect_id=prospect_id)
    if sequence_id:
        contact_id = contact["id"]
        sei.add_contact_to_sequence(
            mailbox_id=mailbox_id,
            sequence_id=sequence_id,
            contact_id=contact_id,
            prospect_id=prospect_id,
        )


def send_email_campaign_from_sales_engagement(
    campaign_id: int, sequence_id: Optional[int] = None
):
    """
    Sends an email campaign from a connected sales engagement tool
    """
    campaign: OutboundCampaign = OutboundCampaign.query.get(campaign_id)
    if not campaign:
        raise Exception("Campaign not found")
    if campaign.campaign_type != GeneratedMessageType.EMAIL:
        raise Exception("Campaign is not an email campaign")

    sdr: ClientSDR = ClientSDR.query.get(campaign.client_sdr_id)
    client: Client = Client.query.get(sdr.client_id)
    if not client:
        raise Exception("Client not found")
    if not client.vessel_access_token:
        raise Exception("Client does not have a connected sales engagement tool")
    if not sdr.vessel_mailbox_id:
        raise Exception("SDR does not have a connected sales engagement tool")

    for prospect_id in campaign.prospect_ids:
        prospect_email: ProspectEmail = get_approved_prospect_email_by_id(prospect_id)
        if (
            prospect_email
            and prospect_email.email_status == ProspectEmailStatus.APPROVED
        ):
            personalize_and_enroll_in_sequence.delay(
                client_id=client.id,
                prospect_id=prospect_id,
                mailbox_id=sdr.vessel_mailbox_id,
                sequence_id=sequence_id,
            )

    return True
