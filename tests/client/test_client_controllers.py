from model_import import Client, ClientArchetype, ClientSDR, GNLPModel
from decorators import use_app_context
from test_utils import test_app, basic_client, basic_client_sdr, basic_archetype, basic_generated_message_cta
from app import app, db
import json
import mock
from model_import import ResearchPointType


@use_app_context
@mock.patch("src.client.services.make_stytch_call")
def test_send_magic_link(make_stytch_call_mock):
    """Test that we can send a magic link to a client SDR."""
    client: Client = basic_client()
    client_sdr: ClientSDR = basic_client_sdr(client=client)

    response = app.test_client().post(
        "client/send_magic_link_login",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "client_sdr_email": client_sdr.email,
            }
        ),
    )
    assert response.status_code == 200
    assert make_stytch_call_mock.called


@use_app_context
@mock.patch(
    "src.client.services.authenticate_stytch_client_sdr_token",
    return_value={"user": {"emails": [{"email": "test@test.com"}]}},
)
def test_approve_auth_token(authenticate_stytch_client_sdr_token_mock):
    """Test that we can approve an auth token after getting from Stytch provider"""
    client: Client = basic_client()
    client_sdr: ClientSDR = basic_client_sdr(client=client)
    client_sdr_email: str = client_sdr.email

    response = app.test_client().post(
        "client/approve_auth_token",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "client_sdr_email": client_sdr_email,
                "token": "1234",
            }
        ),
    )
    assert response.status_code == 200
    client_sdr: ClientSDR = ClientSDR.query.filter_by(email=client_sdr_email).first()
    assert len(client_sdr.auth_token) > 10

    assert authenticate_stytch_client_sdr_token_mock.call_count == 1

    response = app.test_client().post(
        "client/verify_client_sdr_auth_token",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "auth_token": client_sdr.auth_token,
            }
        ),
    )
    assert response.status_code == 200


@use_app_context
def test_post_update_sdr_manual_warning_message():
    """Test that we can update the manual warning message for an SDR"""
    client = basic_client()
    client_sdr = basic_client_sdr(client=client)

    assert client_sdr.manual_warning_message is None

    response = app.test_client().post(
        "client/update_sdr_manual_warning_message",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "client_sdr_id": client_sdr.id,
                "manual_warning_message": "This is a test",
            }
        ),
    )
    assert response.status_code == 200

    client_sdr = ClientSDR.query.filter_by(id=client_sdr.id).first()
    assert client_sdr.manual_warning_message == "This is a test"


@use_app_context
def test_patch_update_sdr_weekly_li_outbound_target():
    """Test that we can update the weekly li outbound target for an SDR"""
    client = basic_client()
    client_sdr = basic_client_sdr(client=client)

    assert client_sdr.weekly_li_outbound_target is None

    response = app.test_client().patch(
        "client/sdr/update_weekly_li_outbound_target",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "client_sdr_id": client_sdr.id,
                "weekly_li_outbound_target": 10,
            }
        ),
    )
    assert response.status_code == 200

    client_sdr = ClientSDR.query.filter_by(id=client_sdr.id).first()
    assert client_sdr.weekly_li_outbound_target == 10


@use_app_context
def test_patch_update_sdr_weekly_email_outbound_target():
    """Test that we can update the weekly email outbound target for an SDR"""
    client = basic_client()
    client_sdr = basic_client_sdr(client=client)

    assert client_sdr.weekly_email_outbound_target is None

    response = app.test_client().patch(
        "client/sdr/update_weekly_email_outbound_target",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "client_sdr_id": client_sdr.id,
                "weekly_email_outbound_target": 10,
            }
        ),
    )
    assert response.status_code == 200

    client_sdr = ClientSDR.query.filter_by(id=client_sdr.id).first()
    assert client_sdr.weekly_email_outbound_target == 10


@use_app_context
def test_post_archetype_set_transformer_blocklist():
    client = basic_client()
    client_archetype = basic_archetype(client=client)
    client_archetype_id = client_archetype.id

    assert client_archetype.transformer_blocklist == None

    response = app.test_client().post(
        "client/archetype/set_transformer_blocklist",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "client_archetype_id": client_archetype_id,
                "new_blocklist": [
                    "CURRENT_EXPERIENCE_DESCRIPTION",
                    "RECENT_RECOMMENDATIONS",
                ],
            }
        ),
    )
    assert response.status_code == 200

    client_archetype = ClientArchetype.query.filter_by(id=client_archetype_id).first()
    assert client_archetype.transformer_blocklist == [
        ResearchPointType.CURRENT_EXPERIENCE_DESCRIPTION,
        ResearchPointType.RECENT_RECOMMENDATIONS,
    ]

    new_client_archetype = basic_archetype(client=client)
    new_client_archetype_id = new_client_archetype.id

    assert new_client_archetype.transformer_blocklist == None

    response = app.test_client().post(
        "client/archetype/replicate_transformer_blocklist",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "source_client_archetype_id": client_archetype_id,
                "destination_client_archetype_id": new_client_archetype_id,
            }
        ),
    )
    assert response.status_code == 200

    new_client_archetype = ClientArchetype.query.filter_by(
        id=new_client_archetype_id
    ).first()
    assert new_client_archetype.transformer_blocklist == [
        ResearchPointType.CURRENT_EXPERIENCE_DESCRIPTION,
        ResearchPointType.RECENT_RECOMMENDATIONS,
    ]

@use_app_context
def test_get_ctas_endpoint():
    client = basic_client()
    client_archetype = basic_archetype(client=client)
    cta = basic_generated_message_cta(client_archetype)

    response = app.test_client().post(
        "client/archetype/get_ctas",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "client_archetype_id": client_archetype.id,
            }
        ),
    )
    assert response.status_code == 200
    assert response.json == [{
        "id": cta.id,
        "archetype_id": client_archetype.id,
        "text_value": "test_cta",
        "active": True,
    }]
