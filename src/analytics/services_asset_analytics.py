from tqdm import tqdm
from src.client.models import ClientAssets, ClientAssetArchetypeReasonMapping
from model_import import EmailSequenceStep
from app import db, celery


class AnalyticsComponents:
    num_sends: int
    num_opens: int
    num_replies: int


def get_email_sequence_analytics(client_asset_id: int) -> AnalyticsComponents:
    query = """
    select
        sum(email_sequence_step.times_used) times_used,
        sum(email_sequence_step.times_accepted) times_accepted,
        sum(email_sequence_step.times_replied) times_replied
    from email_sequence_step
        left join email_sequence_step_to_asset_mapping on email_sequence_step_to_asset_mapping.email_sequence_step_id = email_sequence_step.id
        left join client_assets on client_assets.id = email_sequence_step_to_asset_mapping.client_assets_id
    where
        client_assets.id = :client_asset_id
    """

    result = db.session.execute(query, {"client_asset_id": client_asset_id}).fetchone()

    analytics = AnalyticsComponents()
    analytics.num_sends = result[0]
    analytics.num_opens = result[1]
    analytics.num_replies = result[2]

    return analytics


def get_linkedin_initial_message_template_analytics(
    client_asset_id: int,
) -> AnalyticsComponents:
    query = """
        select
            count(distinct prospect_status_records.prospect_id) filter (where prospect_status_records.to_status = 'SENT_OUTREACH') times_used,
            count(distinct prospect_status_records.prospect_id) filter (where prospect_status_records.to_status = 'ACCEPTED') times_accepted,
            count(distinct prospect_status_records.prospect_id) filter (where prospect_status_records.to_status = 'ACTIVE_CONVO') times_replied
        from linkedin_initial_message_template
            left join linkedin_initial_message_to_asset_mapping on linkedin_initial_message_to_asset_mapping.linkedin_initial_message_id = linkedin_initial_message_template.id
            left join client_assets on client_assets.id = linkedin_initial_message_to_asset_mapping.client_assets_id
            left join generated_message on generated_message.li_init_template_id = linkedin_initial_message_template.id
            left join prospect on prospect.approved_outreach_message_id = generated_message.id
            left join prospect_status_records on prospect_status_records.prospect_id = prospect.id
        where
            client_assets.id = :client_asset_id
    """

    result = db.session.execute(query, {"client_asset_id": client_asset_id}).fetchone()

    analytics = AnalyticsComponents()
    analytics.num_sends = result[0]
    analytics.num_opens = result[1]
    analytics.num_replies = result[2]

    return analytics


def get_linkedin_generated_message_cta_template_analytics(
    client_asset_id: int,
) -> AnalyticsComponents:
    query = """
    select
        count(distinct prospect_status_records.prospect_id) filter (where prospect_status_records.to_status = 'SENT_OUTREACH') times_used,
        count(distinct prospect_status_records.prospect_id) filter (where prospect_status_records.to_status = 'ACCEPTED') times_accepted,
        count(distinct prospect_status_records.prospect_id) filter (where prospect_status_records.to_status = 'ACTIVE_CONVO') times_replied
    from generated_message_cta
        left join generated_message_cta_to_asset_mapping on generated_message_cta_to_asset_mapping.generated_message_cta_id = generated_message_cta.id
        left join client_assets on client_assets.id = generated_message_cta_to_asset_mapping.client_assets_id
        left join generated_message on generated_message.message_cta = generated_message_cta_to_asset_mapping.generated_message_cta_id
        left join prospect on prospect.approved_outreach_message_id = generated_message.id
        left join prospect_status_records on prospect_status_records.prospect_id = prospect.id
    where
        client_assets.id = :client_asset_id
    """

    result = db.session.execute(query, {"client_asset_id": client_asset_id}).fetchone()

    analytics = AnalyticsComponents()
    analytics.num_sends = result[0]
    analytics.num_opens = result[1]
    analytics.num_replies = result[2]

    return analytics


def get_bump_framework_analytics(client_asset_id: int) -> AnalyticsComponents:
    query = """
    select
        count(distinct prospect_status_records.prospect_id) filter (where prospect_status_records.to_status = 'SENT_OUTREACH') times_used,
        count(distinct prospect_status_records.prospect_id) filter (where prospect_status_records.to_status = 'ACCEPTED') times_accepted,
        count(distinct prospect_status_records.prospect_id) filter (where prospect_status_records.to_status = 'ACTIVE_CONVO') times_replied
    from bump_framework
        left join bump_framework_to_asset_mapping on bump_framework_to_asset_mapping.bump_framework_id = bump_framework.id
        left join client_assets on client_assets.id = bump_framework_to_asset_mapping.client_assets_id
        left join linkedin_conversation_entry on linkedin_conversation_entry.bump_framework_id = bump_framework.id
        left join prospect on prospect.li_conversation_urn_id = linkedin_conversation_entry.thread_urn_id
        left join prospect_status_records on prospect_status_records.prospect_id = prospect.id
    where 
        client_assets.id = 47;
    """

    result = db.session.execute(query, {"client_asset_id": client_asset_id}).fetchone()

    analytics = AnalyticsComponents()
    analytics.num_sends = result[0]
    analytics.num_opens = result[1]
    analytics.num_replies = result[2]

    return analytics


def backfill_asset_analytics(client_asset_id: int):
    asset = ClientAssets.query.get(client_asset_id)
    if asset is None:
        return

    aggregate_num_sends = 0
    aggregate_num_opens = 0
    aggregate_num_replies = 0

    # EMAIL - Email sequence analytics
    email_sequence_analytics = get_email_sequence_analytics(client_asset_id)
    aggregate_num_sends += email_sequence_analytics.num_sends or 0
    aggregate_num_opens += email_sequence_analytics.num_opens or 0
    aggregate_num_replies += email_sequence_analytics.num_replies or 0

    # LINKEDIN -  Initial message template analytics
    initial_message_template_analytics = (
        get_linkedin_initial_message_template_analytics(client_asset_id)
    )
    aggregate_num_sends += initial_message_template_analytics.num_sends or 0
    aggregate_num_opens += initial_message_template_analytics.num_opens or 0
    aggregate_num_replies += initial_message_template_analytics.num_replies or 0

    # LINKEDIN - Generated message CTA template analytics
    generated_message_cta_template_analytics = (
        get_linkedin_generated_message_cta_template_analytics(client_asset_id)
    )
    aggregate_num_sends += generated_message_cta_template_analytics.num_sends or 0
    aggregate_num_opens += generated_message_cta_template_analytics.num_opens or 0
    aggregate_num_replies += generated_message_cta_template_analytics.num_replies or 0

    # LINKEDIN -  Bump Framework analytics
    bump_framework_analytics = get_bump_framework_analytics(client_asset_id)
    aggregate_num_sends += bump_framework_analytics.num_sends or 0
    aggregate_num_opens += bump_framework_analytics.num_opens or 0
    aggregate_num_replies += bump_framework_analytics.num_replies or 0

    asset.num_sends = aggregate_num_sends
    asset.num_opens = aggregate_num_opens
    asset.num_replies = aggregate_num_replies

    db.session.commit()

    return asset


@celery.task
def backfill_all_assets_analytics():
    assets = ClientAssets.query.all()
    for asset in tqdm(assets):
        backfill_asset_analytics(asset.id)
