from src.client.models import ClientArchetypeAssets, ClientArchetypeAssetReasonMapping
from model_import import EmailSequenceStep
from app import db, celery


class AnalyticsComponents:
    num_sends: int
    num_opens: int
    num_replies: int


def get_email_sequence_analytics(client_archetype_asset_id: int) -> AnalyticsComponents:
    query = """
    select 
        sum(email_sequence_step.times_used) times_used,
        sum(email_sequence_step.times_accepted) times_accepted,
        sum(email_sequence_step.times_replied) times_replied
    from email_sequence_step
        left join email_sequence_step_to_asset_mapping on email_sequence_step_to_asset_mapping.email_sequence_step_id = email_sequence_step.id
        left join client_archetype_assets on client_archetype_assets.id = email_sequence_step_to_asset_mapping.client_archetype_assets_id
    where 
        client_archetype_assets.id = :client_archetype_asset_id
    """

    result = db.session.execute(
        query, {"client_archetype_asset_id": client_archetype_asset_id}
    ).fetchone()

    analytics = AnalyticsComponents()
    analytics.num_sends = result[0]
    analytics.num_opens = result[1]
    analytics.num_replies = result[2]

    return analytics


def backfill_asset_analytics(client_archetype_asset_id: int):
    asset = ClientArchetypeAssets.query.get(client_archetype_asset_id)
    if asset is None:
        return

    email_sequence_analytics = get_email_sequence_analytics(client_archetype_asset_id)

    asset.num_sends = email_sequence_analytics.num_sends or 0
    asset.num_opens = email_sequence_analytics.num_opens or 0
    asset.num_replies = email_sequence_analytics.num_replies or 0

    db.session.commit()

    return asset


@celery.task
def backfill_all_assets_analytics():
    assets = ClientArchetypeAssets.query.all()
    for asset in assets:
        backfill_asset_analytics(asset.id)
