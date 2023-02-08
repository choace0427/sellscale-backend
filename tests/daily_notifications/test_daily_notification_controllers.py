from decorators import use_app_context
from test_utils import test_app, basic_client, basic_client_sdr, basic_daily_notification
from src.daily_notifications.models import DailyNotification
from app import app, db
import json

@use_app_context
def test_daily_notification_fetch_all():
    """Test that we can fetch all daily notification for a given client_sdr."""
    client = basic_client()
    client_sdr = basic_client_sdr(client=client)

    response = app.test_client().get(
        "/daily_notifications/"+str(client_sdr.id),
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 200

    # TODO: Fix this test 
    #assert len(response.data) == len(DailyNotification.query.filter(
    #    DailyNotification.client_sdr_id == client_sdr.id,
    #    DailyNotification.status == "PENDING",
    #).all())

@use_app_context
def test_daily_notification_status_update():
    """Test that we can update the status of a daily notification."""
    client = basic_client()
    client_sdr = basic_client_sdr(client=client)
    daily_notification = basic_daily_notification(client_sdr=client_sdr, status='PENDING')

    response = app.test_client().put(
        "/daily_notifications/update_status",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "id": daily_notification.id,
                "status": "COMPLETE",
            }
        ),
    )
    assert response.status_code == 200