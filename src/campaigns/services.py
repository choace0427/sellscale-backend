from app import db
from src.campaigns.models import *

from model_import import OutboundCampaign, OutboundCampaignStatus, GeneratedMessageType
import datetime

from model_import import ClientArchetype


def create_outbound_campaign(
    prospect_ids: list,
    campaign_type: GeneratedMessageType,
    ctas: list,
    client_archetype_id: int,
    client_sdr_id: int,
    campaign_start_date: datetime,
    campaign_end_date: datetime,
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
    campaign = OutboundCampaign(
        name=name,
        prospect_ids=prospect_ids,
        campaign_type=campaign_type,
        ctas=ctas,
        client_archetype_id=client_archetype_id,
        client_sdr_id=client_sdr_id,
        campaign_start_date=campaign_start_date,
        campaign_end_date=campaign_end_date,
        status=OutboundCampaignStatus.PENDING,
    )
    db.session.add(campaign)
    db.session.commit()
    return campaign
