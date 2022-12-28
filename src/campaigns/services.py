from app import db
from src.campaigns.models import *
from src.client.services import get_client, get_client_sdr

from model_import import OutboundCampaign, OutboundCampaignStatus, GeneratedMessageType
import datetime
from src.message_generation.services import (
    generate_outreaches_for_prospect_list_from_multiple_ctas,
    batch_generate_prospect_emails,
)
from typing import Optional
from src.utils.random_string import generate_random_alphanumeric

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

    uuid = generate_random_alphanumeric(32)

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
        uuid=uuid,
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

    campaign: OutboundCampaign = OutboundCampaign.query.get(campaign_id)
    sdr = get_client_sdr(campaign.client_sdr_id)
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
    sdr = get_client_sdr(campaign.client_sdr_id)
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
    sdr = get_client_sdr(campaign.client_sdr_id)
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

    email_schema_ids = set([c.email_schema_id for c in campaigns])
    if len(email_schema_ids) > 1:
        raise Exception("Campaigns must be of the same email schema")

    client_archetype_ids = set([c.client_archetype_id for c in campaigns])
    if len(client_archetype_ids) > 1:
        raise Exception("Campaigns must be of the same client archetype")

    client_sdr_ids = set([c.client_sdr_id for c in campaigns])
    if len(client_sdr_ids) > 1:
        raise Exception("Campaigns must be of the same client sdr")

    campaign_statuses = set([c.status.value for c in campaigns])
    if len(campaign_statuses) > 1:
        raise Exception("Campaigns must be of the same status")

    name = "Merged - Campaigns: " + ", ".join([str(c.id) for c in campaigns])
    prospect_ids = list(set().union(*[c.prospect_ids for c in campaigns]))
    campaign_type = campaigns[0].campaign_type
    ctas = list(set().union(*[c.ctas for c in campaigns if c.ctas]))
    email_schema_id = campaigns[0].email_schema_id
    client_archetype_id = campaigns[0].client_archetype_id
    client_sdr_id = campaigns[0].client_sdr_id
    campaign_start_date = min([c.campaign_start_date for c in campaigns])
    campaign_end_date = max([c.campaign_end_date for c in campaigns])

    campaign: OutboundCampaign = create_outbound_campaign(
        prospect_ids=prospect_ids,
        campaign_type=campaign_type,
        client_archetype_id=client_archetype_id,
        client_sdr_id=client_sdr_id,
        campaign_start_date=campaign_start_date,
        campaign_end_date=campaign_end_date,
        ctas=ctas,
        email_schema_id=email_schema_id,
    )
    campaign.status = campaigns[0].status
    campaign.name = name
    db.session.add(campaign)
    db.session.commit()

    for c in campaigns:
        c.status = OutboundCampaignStatus.CANCELLED
        db.session.add(c)
        db.session.commit()

    return campaign.id


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
            campaign_payload["campaign_start_date"], "%Y-%m-%d"
        )
        campaign_end_date = datetime.datetime.strptime(
            campaign_payload["campaign_end_date"], "%Y-%m-%d"
        )
        status = campaign_payload["status"]
        campaign_name = campaign_payload["campaign_name"]

        campaign = OutboundCampaign.query.get(campaign_id)
        campaign.campaign_start_date = campaign_start_date
        campaign.campaign_end_date = campaign_end_date
        campaign.status = OutboundCampaignStatus[status]
        campaign.name = campaign_name
        db.session.add(campaign)
        db.session.commit()

    return True
