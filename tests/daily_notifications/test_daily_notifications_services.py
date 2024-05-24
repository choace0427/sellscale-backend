from app import db
from tests.test_utils.decorators import use_app_context
from tests.test_utils.test_utils import (
    test_app,
    basic_client,
    basic_client_sdr,
    basic_archetype,
    basic_prospect,
    basic_engagement_feed_item,
)
from src.daily_notifications.services import (
    fill_in_daily_notifications,
    clear_daily_notifications,
    create_engagement_feed_item,
    get_engagement_feed_items_for_sdr,
)
from src.li_conversation.models import LinkedinConversationEntry
from src.daily_notifications.models import DailyNotification, EngagementFeedItem
from datetime import datetime, timedelta
from model_import import ProspectStatus
from freezegun import freeze_time


@use_app_context
def test_fill_in_daily_notifications():
    populate_db()
    fill_in_daily_notifications()

    assert len(DailyNotification.query.all()) == 1


@use_app_context
def test_clear_daily_notifications():
    """Clears all daily notifications that are more than 7 days old."""

    with freeze_time(datetime.now() - timedelta(days=10)):
        populate_db()
        fill_in_daily_notifications()

        assert len(DailyNotification.query.all()) == 1

    clear_daily_notifications()

    assert len(DailyNotification.query.all()) == 0


def populate_db():
    """Populate prospects for testing daily notifications"""

    client = basic_client()
    archetype = basic_archetype(client)
    client_sdr = basic_client_sdr(client)

    basic_prospect(
        client,
        archetype,
        client_sdr,
        email="test@email.com",
        li_conversation_thread_id="https://www.linkedin.com/messaging/thread/1",
        status=ProspectStatus.ACTIVE_CONVO,
    )
    basic_prospect(
        client,
        archetype,
        client_sdr,
        email="test@email.com",
        li_conversation_thread_id="https://www.linkedin.com/messaging/thread/2",
        status=ProspectStatus.ACTIVE_CONVO,
    )

    add_linkedin_conversation_entry(
        15,
        "Person 1",
        "Last",
        "1st",
        "Hello",
        "https://www.linkedin.com/messaging/thread/1",
    )
    add_linkedin_conversation_entry(
        13,
        "Person 2",
        "Last",
        "You",
        "Hello",
        "https://www.linkedin.com/messaging/thread/1",
    )

    add_linkedin_conversation_entry(
        12,
        "Person 3",
        "Last",
        "2nd",
        "Hello",
        "https://www.linkedin.com/messaging/thread/2",
    )
    add_linkedin_conversation_entry(
        15,
        "Person 4",
        "Last",
        "You",
        "Hello",
        "https://www.linkedin.com/messaging/thread/2",
    )


def add_linkedin_conversation_entry(
    day_offset: int,
    first_name: str,
    last_name: str,
    connection_degree: str,
    message: str,
    conversation_url: str,
):
    """Test create_linkedin_conversation_entry"""
    author = first_name + " " + last_name
    date = datetime.now() - timedelta(days=day_offset)
    profile_url = "https://www.linkedin.com/in/johndoe"
    headline = "Software Engineer"
    img_url = "https://media-exp1.licdn.com/dms/image/C4D03AQGz0QZ1QwZ8Rg/profile-displayphoto-shrink_800_800/0/1605817042181?e=1623283200&v=beta&t=3k0cVbH6oYJ7Rv1XQzU6Zx1Q2zW8ZJj6Z5p5H5J5y5g"
    li_url = "https://www.linkedin.com/in/johndoe"
    li_entry = LinkedinConversationEntry(
        conversation_url=conversation_url,
        author=author,
        first_name=first_name,
        last_name=last_name,
        date=date,
        profile_url=profile_url,
        headline=headline,
        img_url=img_url,
        connection_degree=connection_degree,
        li_url=li_url,
        message=message,
    )
    db.session.add(li_entry)
    db.session.commit()


@use_app_context
def test_create_engagement_feed_item():
    client = basic_client()
    client_sdr = basic_client_sdr(client)
    archetype = basic_archetype(client, client_sdr)

    prospect = basic_prospect(client, archetype, client_sdr)

    ef_id = create_engagement_feed_item(
        client_sdr_id=client_sdr.id,
        prospect_id=prospect.id,
        channel_type="LINKEDIN",
        engagement_type="SCHEDULING",
        engagement_metadata={"message": "test"},
    )
    efs: list[EngagementFeedItem] = EngagementFeedItem.query.all()
    assert len(efs) == 1
    assert efs[0].id == ef_id


@use_app_context
def test_get_engagement_feed_items_for_sdr():
    client = basic_client()
    client_sdr = basic_client_sdr(client)
    archetype = basic_archetype(client, client_sdr)

    prospect = basic_prospect(client, archetype, client_sdr)
    ef_id = basic_engagement_feed_item(
        client_sdr.id, prospect.id, "LINKEDIN", "SCHEDULING"
    )
    total_count, efs = get_engagement_feed_items_for_sdr(client_sdr.id)
    assert total_count == 1
    assert len(efs) == 1
    assert efs[0]["id"] == ef_id
