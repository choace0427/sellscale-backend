from datetime import datetime, timedelta
from typing import Optional
from app import db
from sqlalchemy import func

from model_import import GeneratedMessage
from src.bump_framework.models import (
    BumpFramework,
    BumpFrameworkToAssetMapping,
    BumpLength,
)
from src.bump_framework.services import create_bump_framework

from src.client.models import (
    Client,
    ClientArchetype,
    ClientAssetArchetypeReasonMapping,
    ClientAssets,
    ClientSDR,
    SLASchedule,
)
from src.email_outbound.email_store.services import find_email_for_prospect_id
from src.email_sequencing.models import EmailSequenceStep, EmailSubjectLineTemplate
from src.email_sequencing.services import (
    create_email_sequence_step,
    create_email_subject_line_template,
)
from src.li_conversation.models import (
    LinkedInInitialMessageToAssetMapping,
    LinkedinInitialMessageTemplate,
)
from src.message_generation.models import GeneratedMessageCTA
from src.message_generation.services import create_cta, generate_li_convo_init_msg
from src.ml.services import mark_queued_and_classify
from src.notifications.models import (
    OperatorNotificationPriority,
    OperatorNotificationType,
)
from src.notifications.services import create_notification
from src.prospecting.models import Prospect, ProspectOverallStatus, ProspectStatus
from src.research.models import ResearchPointType
from src.slack.models import SlackNotificationType
from src.slack.slack_notification_center import (
    create_and_send_slack_notification_class_message,
    slack_bot_send_message,
)
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
    channel_types = ["LINKEDIN", "EMAIL"]
    for channel in channel_types:
        for sdr in sdrs:
            # Get the archetypes for this SDR that are active and have LinkedIn active
            archetypes_query = ClientArchetype.query.filter(
                ClientArchetype.client_sdr_id == sdr.id,
                (
                    ClientArchetype.active == True
                    if active_only
                    else ClientArchetype.active == ClientArchetype.active
                ),
            )

            if channel == "EMAIL":
                archetypes_query = archetypes_query.filter(
                    ClientArchetype.email_active == True
                )
            else:
                archetypes_query = archetypes_query.filter(
                    ClientArchetype.linkedin_active == True
                )

            archetypes = archetypes_query.all()

            # Get the total available SLA per day for this SDR
            today = datetime.now()
            tomorrow = today + timedelta(days=1)
            sla_schedule: SLASchedule = SLASchedule.query.filter(
                SLASchedule.client_sdr_id == client_sdr_id,
                func.date(SLASchedule.start_date) <= today.date(),
                func.date(SLASchedule.end_date) >= tomorrow.date(),
            ).first()
            if channel == "EMAIL":
                volume = sla_schedule.email_volume if sla_schedule else 0
            else:
                volume = sla_schedule.linkedin_volume if sla_schedule else 0
            available_sla = volume // 5 if sla_schedule else 0
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
                    "archetype": archetype.archetype + " - (" + channel + ")",
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
            queue="icp_scoring",
            routing_key="icp_scoring",
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
                        end_message=(
                            "...and {} more".format(len(prospects) - 10)
                            if len(prospects) > 10
                            else ""
                        ),
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
    client_sdr_id,
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
    create_and_send_slack_notification_class_message(
        notification_type=SlackNotificationType.CAMPAIGN_ACTIVATED,
        arguments={
            "client_sdr_id": client_sdr_id,
            "campaign_id": campaign_id,
            "example_prospect_name": example_prospect_name,
            "example_prospect_title": example_prospect_title,
            "example_prospect_company": example_prospect_company,
            "example_prospect_linkedin_url": example_prospect_linkedin_url,
            "example_message": example_first_generation,
        },
    )

    # send_slack_message(
    #     message="SellScale AI activated a new campaign",
    #     blocks=[
    #         {
    #             "type": "header",
    #             "text": {
    #                 "type": "plain_text",
    #                 "text": "SellScale AI activated a new campaign 🚀",
    #                 "emoji": True,
    #             },
    #         },
    #         {
    #             "type": "section",
    #             "text": {
    #                 "type": "mrkdwn",
    #                 "text": "*Sequence Preview*: {}".format(sequence_name),
    #             },
    #         },
    #         {
    #             "type": "section",
    #             "text": {
    #                 "type": "mrkdwn",
    #                 "text": "*Example Prospect*: <{}|{}> ({} @ {})".format(
    #                     "https://www." + example_prospect_linkedin_url,
    #                     example_prospect_name,
    #                     example_prospect_title,
    #                     example_prospect_company,
    #                 ),
    #             },
    #         },
    #         {
    #             "type": "section",
    #             "text": {
    #                 "type": "mrkdwn",
    #                 "text": "> 👥 {client_sdr_name} | Example message\n> _{example_first_generation}_".format(
    #                     client_sdr_name=client_sdr_name,
    #                     example_first_generation=example_first_generation,
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
    #                     "text": "View Campaign",
    #                     "emoji": True,
    #                 },
    #                 "value": direct_link,
    #                 "url": direct_link,
    #                 "action_id": "button-action",
    #             },
    #         },
    #     ],
    #     webhook_urls=[webhook_url],
    # )


def send_email_campaign_activated_slack_notification(
    sequence_name,
    example_prospect_name,
    example_prospect_linkedin_url,
    example_prospect_title,
    example_prospect_company,
    webhook_url,
    direct_link,
):
    """
    Send a Slack message for a new email campaign.

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
        message="SellScale AI activated a new email campaign",
        blocks=[
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "SellScale AI activated a new email campaign 🚀",
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Campaign*: {}".format(sequence_name),
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
        client_sdr_id,
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

    send_email_campaign_activated_slack_notification(
        sequence_name=archetype.emoji + " " + archetype.archetype,
        example_prospect_name=prospects[0].full_name,
        example_prospect_linkedin_url=prospects[0].linkedin_url,
        example_prospect_title=prospects[0].title,
        example_prospect_company=prospects[0].company,
        webhook_url=webhook_url,
        direct_link=campaign_url,
    )


def wipe_linkedin_sequence_steps(campaign_id: int, steps: list):
    archetype: ClientArchetype = ClientArchetype.query.get(campaign_id)
    archetype.li_bump_amount = len(steps) - 1

    # wipe archetype sequence
    initial_message_templates: list[LinkedinInitialMessageTemplate] = (
        LinkedinInitialMessageTemplate.query.filter(
            LinkedinInitialMessageTemplate.client_archetype_id == campaign_id
        ).all()
    )
    ctas: list[GeneratedMessageCTA] = GeneratedMessageCTA.query.filter(
        GeneratedMessageCTA.archetype_id == campaign_id
    ).all()
    bump_frameworks: list[BumpFramework] = BumpFramework.query.filter(
        BumpFramework.client_archetype_id == campaign_id,
        BumpFramework.overall_status.in_(["ACCEPTED", "BUMPED"]),
    ).all()

    for template in initial_message_templates:
        template.active = False
        db.session.add(template)
    for cta in ctas:
        cta.active = False
        db.session.add(cta)
    for bump_framework in bump_frameworks:
        bump_framework.active = False
        bump_framework.default = False
        db.session.add(bump_framework)
    archetype.li_bump_amount = 0
    db.session.add(archetype)

    db.session.commit()


def import_linkedin_sequence(
    campaign_id: int,
    steps: list,
    is_template_mode: bool = True,
    ctas: list = [],
    override_sequence: bool = False,
):
    """
    Import linkedin sequence steps

    Args:
        campaign_id (int): ID of the client archetype or campaign
        steps (list): List of steps
            steps is an array with [
                title: str,
                template: str
            ]
        is_template_mode (bool, optional): Whether the sequence is in template mode. Defaults to True.
        ctas (list, optional): List of CTAs. Defaults to []. Cta's should have cta_type and cta_value
    """
    if override_sequence:
        wipe_linkedin_sequence_steps(campaign_id, steps)

    # IMPORT SEQUENCE
    # setup archetype
    archetype: ClientArchetype = ClientArchetype.query.get(campaign_id)
    archetype.template_mode = is_template_mode
    archetype.li_bump_amount = len(steps) - 1
    db.session.add(archetype)
    db.session.commit()

    if len(steps) == 0:
        return

    # make initial message templates
    if is_template_mode:
        sdr: ClientSDR = ClientSDR.query.get(archetype.client_sdr_id)
        research_points = ResearchPointType.get_allowedlist_from_blocklist(
            blocklist=sdr.default_transformer_blocklist or []
        )
        initial_message_step = steps[0]
        template = LinkedinInitialMessageTemplate(
            title=initial_message_step["title"],
            message=initial_message_step["template"],
            client_sdr_id=archetype.client_sdr_id,
            client_archetype_id=archetype.id,
            active=True,
            times_used=0,
            times_accepted=0,
            sellscale_generated=True,
            research_points=research_points,
            additional_instructions="",
        )
        db.session.add(template)
        db.session.commit()

        for asset_id in initial_message_step.get("asset_ids", []):
            mapping = LinkedInInitialMessageToAssetMapping(
                linkedin_initial_message_id=template.id,
                client_assets_id=asset_id,
            )
            db.session.add(mapping)
        db.session.commit()
    else:
        for i, cta in enumerate(ctas):
            create_cta(
                archetype_id=archetype.id,
                text_value=cta["cta_value"],
                active=True,
                cta_type=cta["cta_type"],
                expiration_date=None,
                asset_ids=cta.get("asset_ids", []),
            )

    if len(steps) <= 1:
        return

    for i, step in enumerate(steps[1:]):
        status = ProspectOverallStatus.ACCEPTED
        bumped_count = 0
        if i >= 1:
            status = ProspectOverallStatus.BUMPED
            bumped_count = i
        bf_id = create_bump_framework(
            client_sdr_id=archetype.client_sdr_id,
            client_archetype_id=archetype.id,
            title=step["title"],
            description=step["template"],
            overall_status=status,
            length=BumpLength.MEDIUM,
            additional_instructions="",
            bumped_count=bumped_count,
            active=True,
            default=True,
            asset_ids=step.get("asset_ids", []),
        )

        print(
            "Created bump framework for step {} with title {} with bumped count {}".format(
                i, step["title"], bumped_count
            )
        )

    return True


def create_linkedin_initial_message_template(
    title: str,
    message: str,
    client_sdr_id: int,
    client_archetype_id: int,
    research_points: list[str],
    additional_instructions: str = "",
    asset_ids: list[int] = [],
):

    template = LinkedinInitialMessageTemplate(
        title=title,
        message=message,
        client_sdr_id=client_sdr_id,
        client_archetype_id=client_archetype_id,
        active=True,
        times_used=0,
        times_accepted=0,
        sellscale_generated=True,
        research_points=research_points,
        additional_instructions=additional_instructions,
    )
    db.session.add(template)
    db.session.commit()

    for asset_id in asset_ids:
        mapping = LinkedInInitialMessageToAssetMapping(
            linkedin_initial_message_id=template.id,
            client_assets_id=asset_id,
        )
        db.session.add(mapping)
    db.session.commit()

    return template.id


def wipe_email_sequence(campaign_id: int):
    email_sequence_steps: list[EmailSequenceStep] = EmailSequenceStep.query.filter(
        EmailSequenceStep.client_archetype_id == campaign_id
    ).all()

    for step in email_sequence_steps:
        step.active = False
        step.default = False
        db.session.add(step)

    email_subject_lines: list[EmailSubjectLineTemplate] = (
        EmailSubjectLineTemplate.query.filter(
            EmailSubjectLineTemplate.client_archetype_id == campaign_id
        ).all()
    )
    for subject_line in email_subject_lines:
        subject_line.active = False
        db.session.add(subject_line)

    db.session.commit()


def import_email_sequence(
    campaign_id: int, steps: list, subject_lines: list, override_sequence: bool = False
):
    """
    Import email sequence steps

    Args:
        campaign_id (int): ID of the client archetype or campaign
        steps (list): List of steps
            steps is an array with [
                title: str,
                template: str
            ]
        subject_lines (list): List of subject lines
            subject_lines is an array with [
                subject_line: str
            ]
    """
    # wipe email sequence
    if override_sequence:
        wipe_email_sequence(campaign_id)

    # IMPORT SEQUENCE
    archetype: ClientArchetype = ClientArchetype.query.get(campaign_id)
    for i, step in enumerate(steps):
        status = ProspectOverallStatus.PROSPECTED
        bumped_count = 0
        if i == 1:
            status = ProspectOverallStatus.ACCEPTED
            bumped_count = 0
        if i >= 2:
            status = ProspectOverallStatus.BUMPED
            bumped_count = i - 1
        create_email_sequence_step(
            client_sdr_id=archetype.client_sdr_id,
            client_archetype_id=archetype.id,
            title=step["title"],
            template=step["template"],
            overall_status=status,
            bumped_count=bumped_count,
            active=True,
            # default=True,
            mapped_asset_ids=step.get("asset_ids", []),
        )

        print(
            "Created email sequence step for step {} with title {} with bumped count {}".format(
                i, step["title"], bumped_count
            )
        )

    for i, subject_line in enumerate(subject_lines):
        create_email_subject_line_template(
            client_sdr_id=archetype.client_sdr_id,
            client_archetype_id=archetype.id,
            subject_line=subject_line,
            active=True,
        )

    # Now we should run email scraper on any Prospect that does not have an email
    prospects: list[Prospect] = Prospect.query.filter(
        Prospect.archetype_id == archetype.id,
        Prospect.email == None,
    ).all()
    for count, prospect in enumerate(prospects):
        # Incorporate a 1 second delay to avoid rate limiting
        find_email_for_prospect_id.apply_async(
            kwargs={"prospect_id": prospect.id}, countdown=count
        )

    return True


def get_archetype_assets(archetype_id: int):
    """Gets all Assets used by an archetype

    Args:
        archetype_id (int): The id of the archetype

    Returns:
        list[dict]: A list of assets
    """
    assetArchetypeMapping: list[ClientAssetArchetypeReasonMapping] = (
        ClientAssetArchetypeReasonMapping.query.filter(
            ClientAssetArchetypeReasonMapping.client_archetype_id == archetype_id
        ).all()
    )
    assets: list[ClientAssets] = ClientAssets.query.filter(
        ClientAssets.id.in_(
            [mapping.client_asset_id for mapping in assetArchetypeMapping]
        )
    ).all()

    return [asset.to_dict() for asset in assets]


def create_li_init_template_asset_mapping(
    linkedin_initial_message_id: int, client_assets_id: int
):
    mapping: LinkedInInitialMessageToAssetMapping = (
        LinkedInInitialMessageToAssetMapping(
            linkedin_initial_message_id=linkedin_initial_message_id,
            client_assets_id=client_assets_id,
        )
    )
    db.session.add(mapping)
    db.session.commit()
    return True


def delete_li_init_template_asset_mapping(
    linkedin_initial_message_to_asset_mapping_id: int,
):
    mapping: LinkedInInitialMessageToAssetMapping = (
        LinkedInInitialMessageToAssetMapping.query.get(
            linkedin_initial_message_to_asset_mapping_id
        )
    )
    if not mapping:
        return True

    db.session.delete(mapping)
    db.session.commit()
    return True


def get_all_li_init_template_assets(linkedin_initial_message_id: int):
    mappings: list[LinkedInInitialMessageToAssetMapping] = (
        LinkedInInitialMessageToAssetMapping.query.filter(
            LinkedInInitialMessageToAssetMapping.linkedin_initial_message_id
            == linkedin_initial_message_id
        ).all()
    )
    asset_ids = [mapping.client_assets_id for mapping in mappings]
    assets: list[ClientAssets] = ClientAssets.query.filter(
        ClientAssets.id.in_(asset_ids)
    ).all()
    asset_dicts = [asset.to_dict() for asset in assets]

    # add 'mapping_id' to each asset
    for i, asset in enumerate(asset_dicts):
        correct_mapping = next(
            mapping for mapping in mappings if mapping.client_assets_id == asset["id"]
        )
        asset["mapping_id"] = correct_mapping.id

    return asset_dicts
