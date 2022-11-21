from app import db
from src.campaigns.models import *

from model_import import OutboundCampaign, OutboundCampaignStatus, GeneratedMessageType
import datetime
from src.message_generation.services import (
    generate_outreaches_for_prospect_list_from_multiple_ctas,
    batch_generate_prospect_emails,
)
from typing import Optional

from model_import import ClientArchetype
from src.utils.slack import send_slack_message, URL_MAP


def create_outbound_campaign(
    prospect_ids: list,
    campaign_type: GeneratedMessageType,
    client_archetype_id: int,
    client_sdr_id: int,
    campaign_start_date: datetime,
    campaign_end_date: datetime,
    ctas: Optional[list] = None,
    email_schema_id: Optional[int] = None,
) -> OutboundCampaign:
    """Creates a new outbound campaign

    Args:
        name (str): Name of the campaign
        prospect_ids (list): List of prospect ids
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
    ca: ClientArchetype = ClientArchetype.query.get(client_archetype_id)
    name = (
        ca.archetype + ", " + str(len(prospect_ids)) + ", " + str(campaign_start_date)
    )

    if campaign_type == GeneratedMessageType.EMAIL and email_schema_id is None:
        raise Exception("Email campaign type requires an email schema id")
    if campaign_type == GeneratedMessageType.LINKEDIN and ctas is None:
        raise Exception("LinkedIn campaign type requires a list of CTAs")

    campaign = OutboundCampaign(
        name=name,
        prospect_ids=prospect_ids,
        campaign_type=campaign_type,
        ctas=ctas,
        email_schema_id=email_schema_id,
        client_archetype_id=client_archetype_id,
        client_sdr_id=client_sdr_id,
        campaign_start_date=campaign_start_date,
        campaign_end_date=campaign_end_date,
        status=OutboundCampaignStatus.PENDING,
    )
    db.session.add(campaign)
    db.session.commit()
    return campaign


def generate_campaign(campaign_id: int):
    """Generates the campaign

    Args:
        campaign_id (int): Campaign id
    """
    campaign: OutboundCampaign = OutboundCampaign.query.get(campaign_id)
    campaign.status = OutboundCampaignStatus.IN_PROGRESS
    db.session.add(campaign)
    db.session.commit()

    if campaign.campaign_type == GeneratedMessageType.EMAIL:
        batch_generate_prospect_emails(
            prospect_ids=campaign.prospect_ids, email_schema_id=campaign.email_schema_id
        )
    elif campaign.campaign_type == GeneratedMessageType.LINKEDIN:
        generate_outreaches_for_prospect_list_from_multiple_ctas(
            prospect_ids=campaign.prospect_ids,
            cta_ids=campaign.ctas,
        )


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


def mark_campaign_as_ready_to_send(campaign_id: int):
    """Marks the campaign as ready to send

    Args:
        campaign_id (int): Campaign id
    """
    change_campaign_status(campaign_id, OutboundCampaignStatus.READY_TO_SEND)

    send_slack_message(
        message="Campaign {} is ready to send".format(campaign_id),
        webhook_urls=[URL_MAP["eng-sandbox"]],
    )

    return True
