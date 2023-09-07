from app import db, celery
from sqlalchemy import and_, or_, nullslast
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
from src.editor.models import Editor, EditorTypes
from src.email_outbound.services import get_approved_prospect_email_by_id
from tqdm import tqdm
from src.message_generation.services import (
    wipe_prospect_email_and_generations_and_research,
    generate_outreaches_for_prospect_list_from_multiple_ctas,
    create_and_start_email_generation_jobs,
)
from src.research.linkedin.services import reset_prospect_research_and_messages
from src.message_generation.services_few_shot_generations import (
    can_generate_with_patterns,
)
from src.utils.random_string import generate_random_alphanumeric
from src.utils.slack import send_slack_message, URL_MAP
from src.client.services import get_cta_stats

import datetime


NUM_DAYS_AFTER_GENERATION_TO_EDIT = 1
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
    if not sdr.vessel_mailbox:
        raise Exception("SDR does not have a connected sales engagement tool")

    for prospect_id in campaign.prospect_ids:
        prospect_email: ProspectEmail = get_approved_prospect_email_by_id(prospect_id)
        if (
            prospect_email
            and prospect_email.email_status == ProspectEmailStatus.APPROVED
        ):
            personalize_and_enroll_in_sequence(
                client_id=client.id,
                prospect_id=prospect_id,
                mailbox_id=sdr.vessel_mailbox,
                sequence_id=sequence_id,
            )

    return True
