from typing import Optional
from app import db

from src.client.models import Client, ClientArchetype, ClientSDR
from src.ml.services import mark_queued_and_classify
from src.prospecting.models import Prospect
from src.utils.slack import URL_MAP, send_slack_message


def get_archetypes_custom(
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
    if client_wide:
        sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
        archetypes: list[ClientArchetype] = ClientArchetype.query.filter(
            ClientArchetype.client_id == sdr.client_id,
            ClientArchetype.active == True if active_only else ClientArchetype.active == ClientArchetype.active,
        ).all()
    else:
        archetypes: list[ClientArchetype] = ClientArchetype.query.filter(
            ClientArchetype.client_sdr_id == client_sdr_id,
            ClientArchetype.active == True if active_only else ClientArchetype.active == ClientArchetype.active,
        ).all()

    payload = []
    for archetype in archetypes:
        sdr: ClientSDR = ClientSDR.query.get(archetype.client_sdr_id)
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
            "contact_count": contact_count,
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
