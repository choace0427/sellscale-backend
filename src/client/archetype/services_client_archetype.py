from datetime import datetime, timedelta
from typing import Optional
from app import db
from sqlalchemy import func

from model_import import GeneratedMessage

from src.client.models import Client, ClientArchetype, ClientSDR, SLASchedule
from src.message_generation.services import generate_li_convo_init_msg
from src.ml.services import mark_queued_and_classify
from src.notifications.models import (
    OperatorNotificationPriority,
    OperatorNotificationType,
)
from src.notifications.services import create_notification
from src.prospecting.models import Prospect
from src.utils.slack import URL_MAP, send_slack_message


def get_archetype_generation_upcoming(
    client_sdr_id: int,
    active_only: Optional[bool] = False,
    client_wide: Optional[bool] = False,
) -> list[dict]:
    """Get archetypes. Custom format for "Upcoming Generations" in the UI.

    Args:
        client_sdr_id (int): client sdr id
        active_only (Optional[bool], optional): active only. Defaults to False.
        client_wide (Optional[bool], optional): client wide. Defaults to False.

    Returns:
        list[dict]: archetypes
    """
    # Get the SDRs to return archetype information for
    sdrs = [client_sdr_id]
    if client_wide:
        sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
        sdrs: list[ClientSDR] = ClientSDR.query.filter(
            ClientSDR.client_id == sdr.client_id, ClientSDR.active == True
        ).all()

    # Loop through the SDRs
    payload = []
    for sdr in sdrs:
        # Get the archetypes for this SDR that are active and have LinkedIn active
        archetypes: list[ClientArchetype] = ClientArchetype.query.filter(
            ClientArchetype.client_sdr_id == sdr.id,
            ClientArchetype.active == True
            if active_only
            else ClientArchetype.active == ClientArchetype.active,
            ClientArchetype.linkedin_active == True,
        ).all()

        # Get the total available SLA per day for this SDR
        today = datetime.now()
        tomorrow = today + timedelta(days=1)
        sla_schedule: SLASchedule = SLASchedule.query.filter(
            SLASchedule.client_sdr_id == client_sdr_id,
            func.date(SLASchedule.start_date) <= today.date(),
            func.date(SLASchedule.end_date) >= tomorrow.date(),
        ).first()
        available_sla = sla_schedule.linkedin_volume // 5 if sla_schedule else 0
        sla_per_campaign = (
            available_sla // len(archetypes) if len(archetypes) > 0 else 0
        )
        leftover_sla = available_sla % len(archetypes) if len(archetypes) > 0 else 0

        # Calculate the SLA per archetype
        sla_counts = [sla_per_campaign] * (len(archetypes) - leftover_sla) + [
            sla_per_campaign + 1
        ] * leftover_sla

        for index, archetype in enumerate(archetypes):
            contact_count: Prospect = Prospect.query.filter(
                Prospect.archetype_id == archetype.id
            ).count()

            archetype_data = {
                "id": archetype.id,
                "archetype": archetype.archetype,
                "active": archetype.active,
                "linkedin_active": archetype.linkedin_active,
                "email_active": archetype.email_active,
                "sdr_name": sdr.name,
                "sdr_img_url": sdr.img_url,
                "contact_count": contact_count,
                "daily_sla_count": sla_counts[index],
            }
            payload.append(archetype_data)

    return payload


def bulk_action_move_prospects_to_archetype(
    client_sdr_id: int, target_archetype_id: int, prospect_ids: list[int]
):
    """Move prospects from one archetype to another.

    Args:
        client_sdr_id (int): client sdr id
        target_archetype_id (int): target archetype id

    Returns:
        bool: success
    """
    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if not sdr:
        return False

    target_archetype: ClientArchetype = ClientArchetype.query.get(target_archetype_id)
    if not target_archetype:
        return False
    if target_archetype.client_sdr_id != sdr.id:
        return False

    # Get all prospects that are in this archetype that are in the PROSPECTED state
    prospects: list[Prospect] = Prospect.query.filter(
        Prospect.id.in_(prospect_ids)
    ).all()

    for prospect in prospects:
        # Reassign the prospect to the new archetype
        prospect.archetype_id = target_archetype.id

    db.session.commit()

    # Re-classify the prospects
    for index, prospect_id in enumerate(prospect_ids):
        countdown = float(index * 6)
        mark_queued_and_classify.apply_async(
            args=[client_sdr_id, target_archetype_id, prospect_id, countdown],
            queue="ml_prospect_classification",
            routing_key="ml_prospect_classification",
            priority=5,
        )

    return True


def bulk_action_withdraw_prospect_invitations(
    client_sdr_id: int, prospect_ids: list[int]
) -> tuple[bool, str]:
    """Withdraw prospect invitations.

    Args:
        client_sdr_id (int): client sdr id
        archetype_id (int): archetype id
        prospect_ids (list[int]): prospect ids

    Returns:
        tuple[bool, str]: success, message
    """
    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if not sdr:
        return False, "Invalid Client SDR"

    client: Client = Client.query.get(sdr.client_id)

    from src.voyager.services import queue_withdraw_li_invites
    from model_import import ProspectStatus, ProspectOverallStatus

    prospects: list[Prospect] = Prospect.query.filter(
        Prospect.id.in_(prospect_ids)
    ).all()

    archetype: ClientArchetype = ClientArchetype.query.filter(
        ClientArchetype.client_sdr_id == client_sdr_id,
        ClientArchetype.is_unassigned_contact_archetype == True,
    ).first()

    for prospect in prospects:
        prospect.status = ProspectStatus.PROSPECTED
        prospect.overall_status = ProspectOverallStatus.PROSPECTED

        if archetype:
            prospect.archetype_id = archetype.id

    db.session.commit()

    # TODO: Perform QUEUEing for PhantomBuster
    # https://www.notion.so/sellscale/PB-LinkedIn-Withdrawal-3ffa2898c3464432afaf36d5db96e1f2?pvs=4
    # Send Slack Notification:
    # "Go to these instructions"
    send_slack_message(
        message="{} has withdrawn {} prospect invitations. Please follow the instructions on Notion.".format(
            sdr.name, len(prospect_ids)
        ),
        webhook_urls=[
            URL_MAP["operations-withdraw-invite"],
            client.pipeline_notifications_webhook_url,
        ],
        blocks=[
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "👌🏽 {} is withdrawing {} invitations".format(
                        sdr.name, str(len(prospect_ids))
                    ),
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "{amt} Profiles Withdrawn Include:\n```{li_list}\n\n{end_message}``` ".format(
                        amt=len(prospects),
                        li_list="\n".join(
                            [prospect.linkedin_url for prospect in prospects][0:10]
                        ),
                        end_message="...and {} more".format(len(prospects) - 10)
                        if len(prospects) > 10
                        else "",
                    ),
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "Note: This process may take a few days to complete as there's a 50 profile withdrawal limit per day.",
                },
            },
        ],
    )

    # Send out queue of phantom buster withdraws
    processes = queue_withdraw_li_invites(client_sdr_id, prospect_ids)

    return True, "Success"


def send_slack_campaign_message(
    sequence_name,
    example_prospect_name,
    example_prospect_linkedin_url,
    example_prospect_title,
    example_prospect_company,
    example_first_generation,
    client_sdr_name,
    campaign_id,
    webhook_url,
    direct_link,
):
    """
    Send a Slack message for a new campaign.

    :param sequence_name: Name of the sequence.
    :param example_prospect_name: Name of the example prospect.
    :param example_prospect_linkedin_url: LinkedIn URL of the example prospect.
    :param example_prospect_title: Title of the example prospect.
    :param example_prospect_company: Company of the example prospect.
    :param example_first_generation: Example first generation message.
    :param client_sdr_name: Name of the client SDR.
    :param campaign_id: ID of the campaign.
    :param webhook_url: Slack webhook URL for sending the message.
    """
    send_slack_message(
        message="SellScale AI activated a new campaign",
        blocks=[
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "SellScale AI activated a new campaign 🚀",
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Sequence Preview*: {}".format(sequence_name),
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Example Prospect*: <{}|{}> ({} @ {})".format(
                        "https://www." + example_prospect_linkedin_url,
                        example_prospect_name,
                        example_prospect_title,
                        example_prospect_company,
                    ),
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "> 👥 {client_sdr_name} | Example message\n> _{example_first_generation}_".format(
                        client_sdr_name=client_sdr_name,
                        example_first_generation=example_first_generation,
                    ),
                },
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": " "},
                "accessory": {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "View Campaign",
                        "emoji": True,
                    },
                    "value": direct_link,
                    "url": direct_link,
                    "action_id": "button-action",
                },
            },
        ],
        webhook_urls=[webhook_url],
    )


def generate_notification_for_campaign_active(archetype_id: int):
    client_archetype: ClientArchetype = ClientArchetype.query.get(archetype_id)
    random_prospects: Prospect = (
        Prospect.query.order_by(func.random())
        .filter(Prospect.archetype_id == archetype_id)
        .filter(Prospect.icp_fit_score <= 4)
        .order_by(Prospect.icp_fit_score.desc())
        .limit(3)
        .all()
    )
    random_prospect: Prospect = random_prospects[0]
    num_prospects: int = Prospect.query.filter(
        Prospect.archetype_id == archetype_id
    ).count()
    client_sdr: ClientSDR = ClientSDR.query.get(client_archetype.client_sdr_id)
    client: Client = Client.query.get(client_sdr.client_id)
    print("Fetched random prospect named {}".format(random_prospect.full_name))

    li_msg, metadata = generate_li_convo_init_msg(
        prospect_id=random_prospect.id,
    )
    print("Generated LI message: {}".format(li_msg))

    client_sdr_id = client_sdr.id
    sequence_name = client_archetype.archetype
    example_prospect_name = random_prospect.full_name
    example_prospect_linkedin_url = random_prospect.linkedin_url
    example_prospect_title = random_prospect.title
    example_prospect_company = random_prospect.company
    example_first_generation = li_msg
    client_sdr_name = client_sdr.name
    campaign_id = client_archetype.id
    webhook_url = client.pipeline_notifications_webhook_url
    direct_link = "https://app.sellscale.com/authenticate?stytch_token_type=direct&token={auth_token}&redirect=setup/email?campaign_id={campaign_id}".format(
        auth_token=client_sdr.auth_token, campaign_id=client_archetype.id
    )

    print("Sending Slack message to {}".format(webhook_url))

    result = send_slack_campaign_message(
        sequence_name,
        example_prospect_name,
        example_prospect_linkedin_url,
        example_prospect_title,
        example_prospect_company,
        example_first_generation,
        client_sdr_name,
        campaign_id,
        webhook_url,
        direct_link,
    )
    print("Sent Slack message: {}".format(result))

    create_notification(
        client_sdr_id=client_sdr_id,
        title="Review New Campaign",
        subtitle="Launched {}".format(datetime.now().strftime("%b %d")),
        stars=0,
        cta="View and Mark as Complete",
        data={
            "campaign_name": sequence_name,
            "example_message": example_first_generation,
            "render_message_as_html": False,
            "random_prospects": [
                {
                    "full_name": p.full_name,
                    "linkedin_url": p.linkedin_url,
                    "img_url": p.img_url,
                    "title": p.title,
                    "company": p.company,
                    "icp_fit_score": p.icp_fit_score,
                }
                for p in random_prospects
            ],
            "num_prospects": num_prospects,
            "linkedin_active": client_archetype.linkedin_active,
            "email_active": client_archetype.email_active,
            "archetype_id": client_archetype.id,
        },
        priority=OperatorNotificationPriority.HIGH,
        notification_type=OperatorNotificationType.REVIEW_NEW_CAMPAIGN,
    )


def send_slack_notif_campaign_active(client_sdr_id: int, archetype_id: int, type: str):
    archetype: ClientArchetype = ClientArchetype.query.get(archetype_id)
    prospects: list[Prospect] = Prospect.query.filter(
        Prospect.archetype_id == archetype_id
    ).all()
    client = Client.query.get(archetype.client_id)
    webhook_url: str = client.pipeline_notifications_webhook_url
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    campaign_url = (
        "https://app.sellscale.com/authenticate?stytch_token_type=direct&token="
        + client_sdr.auth_token
        + "&redirect=campaigns"
    )

    next_day = datetime.utcnow() + timedelta(days=1)
    formatted_next_day = next_day.strftime("%b %d, %Y")

    # next_message = GeneratedMessage.query.filter(
    #     GeneratedMessage.message_status == 'QUEUED_FOR_OUTREACH',
    #     GeneratedMessage. > datetime.utcnow()
    # ).order_by(GeneratedMessage.message_date).first()

    # send_slack_message(
    #     message=f"New [{type}] campaign activated! 🚀",
    #     blocks=[
    #         {
    #             "type": "header",
    #             "text": {
    #                 "type": "plain_text",
    #                 "text": f"New [{type}] campaign activated! 🚀",
    #                 "emoji": True,
    #             },
    #         },
    #         {
    #             "type": "section",
    #             "text": {
    #                 "type": "mrkdwn",
    #                 "text": f"*Persona:* {archetype.archetype}\n",
    #             },
    #         },
    #         {
    #             "type": "section",
    #             "text": {
    #                 "type": "mrkdwn",
    #                 "text": f"*Contacts:* {len(prospects)}\n",
    #             },
    #         },
    #         {
    #             "type": "section",
    #             "text": {
    #                 "type": "mrkdwn",
    #                 "text": f"*Steps:* {len(archetype.email_blocks_configuration) if type == 'email' else archetype.li_bump_amount+1} steps\n",
    #             },
    #         },
    #         {
    #             "type": "section",
    #             "text": {
    #                 "type": "mrkdwn",
    #                 "text": f"*Sending on:* {formatted_next_day} (+1 day)\n",
    #             },
    #         },
    #         {
    #             "type": "section",
    #             "text": {
    #                 "type": "mrkdwn",
    #                 "text": f"Please review in operator dashboard\n",
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
