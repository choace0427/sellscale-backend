from app import db

from src.client.models import ClientArchetype, ClientSDR
from src.ml.services import mark_queued_and_classify
from src.prospecting.models import Prospect
from src.utils.slack import URL_MAP, send_slack_message


def bulk_action_move_prospects_to_archetype(
    client_sdr_id: int,
    target_archetype_id: int,
    prospect_ids: list[int]
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

    target_archetype: ClientArchetype = ClientArchetype.query.get(
        target_archetype_id)
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
    client_sdr_id: int,
    prospect_ids: list[int]
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

    prospects: list[Prospect] = Prospect.query.filter(
        Prospect.id.in_(prospect_ids)
    ).all()

    # TODO: Perform QUEUEing for PhantomBuster
    # https://www.notion.so/sellscale/PB-LinkedIn-Withdrawal-3ffa2898c3464432afaf36d5db96e1f2?pvs=4
    # Send Slack Notification:
    # "Go to these instructions"
    send_slack_message(
        message="{} has withdrawn {} prospect invitations. Please follow the instructions on Notion.".format(
            sdr.name,
            len(prospect_ids)
        ),
        webhook_urls=[URL_MAP['operations-withdraw-invite']],
        blocks=[
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "{} is withdrawing prospect invitations.".format(
                        sdr.name
                    ),
                    "emoji": True
                }
            },
            {
                'type': 'section',
                'text': {
                    'type': 'mrkdwn',
                    'text': 'Follow the steps in this <{}|Notion document>'.format(
                        "https://www.notion.so/sellscale/PB-LinkedIn-Withdrawal-3ffa2898c3464432afaf36d5db96e1f2?pvs=4"
                    )
                }
            },
            {
                'type': 'section',
                'text': {
                    'type': 'mrkdwn',
                    'text': 'LinkedIn cookie: \n```{}```'.format(
                        sdr.li_at_token
                    )
                }
            },
            {
                'type': 'section',
                'text': {
                    'type': 'mrkdwn',
                    'text': '{amt} LI\'s withdrawn:\n```{li_list}```'.format(
                        amt=len(prospects),
                        li_list="\n".join(
                            [prospect.linkedin_url for prospect in prospects])
                    )
                }
            },
            {
                'type': 'section',
                'text': {
                    'type': 'mrkdwn',
                    'text': 'Once done, please mark this task as complete ✅.'
                }
            },
        ]
    )

    return True, "Success"
