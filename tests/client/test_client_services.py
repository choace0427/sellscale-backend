from app import app, db
from decorators import use_app_context
from model_import import (
    Client,
    ClientArchetype,
    ClientSDR,
    GNLPModel,
    ProspectOverallStatus,
)
from test_utils import (
    test_app,
    basic_client,
    get_login_token,
    basic_client_sdr,
    basic_prospect,
    basic_archetype,
    basic_gnlp_model,
    basic_generated_message_cta_with_text,
    basic_generated_message,
    basic_generated_message_cta,
)
from src.client.services import (
    create_client,
    get_client,
    create_client_archetype,
    get_ctas,
    get_client_archetypes,
    get_client_archetype_performance,
    get_cta_stats,
    get_cta_by_archetype_id,
    get_client_sdr,
    get_sdr_available_outbound_channels,
    nylas_exchange_for_authorization_code,
)
import json
import mock


@use_app_context
def test_get_client_sdr():
    client = basic_client()
    client_sdr = basic_client_sdr(client)

    result = get_client_sdr(client_sdr.id)
    assert result.get("sdr_name") == "Test SDR"


@use_app_context
def test_get_client_archetypes():
    client = basic_client()
    client_sdr = basic_client_sdr(client)
    client_sdr_id = client_sdr.id
    archetype = basic_archetype(client, client_sdr)
    p = basic_prospect(client, archetype, client_sdr)

    result = get_client_archetypes(client_sdr.id)
    assert len(result) == 1
    assert result[0].get("performance").get("status_map").get("PROSPECTED") == 1

    archetype_2 = basic_archetype(client, client_sdr)
    result = get_client_archetypes(client_sdr.id)
    assert len(result) == 2

    archetype_3 = basic_archetype(client, client_sdr)
    archetype_3.archetype = "Another testing archetype"
    db.session.add(archetype_3)
    db.session.commit()
    result = get_client_archetypes(client_sdr_id, "Another")
    assert len(result) == 1


@use_app_context
def test_get_client_archetype_performance():
    client = basic_client()
    client_sdr = basic_client_sdr(client)
    archetype = basic_archetype(client, client_sdr)
    prospect = basic_prospect(client, archetype, client_sdr)
    prospect_2 = basic_prospect(
        client, archetype, client_sdr, overall_status=ProspectOverallStatus.DEMO
    )

    result = get_client_archetype_performance(client_sdr.id, archetype.id)
    assert result.get("status_map").get("PROSPECTED") == 1
    assert result.get("status_map").get("DEMO") == 1
    assert result.get("total_prospects") == 2


@use_app_context
def test_add_client_and_archetype():
    response = app.test_client().get("client/")
    assert response.status_code == 200

    create_client(
        company="testing",
        contact_name="testing",
        contact_email="testing",
        linkedin_outbound_enabled=True,
        email_outbound_enabled=True,
    )
    clients: list = Client.query.all()
    assert len(clients) == 1

    response = app.test_client().post(
        "client/",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "company": "testing",
                "contact_name": "testing",
                "contact_email": "testing",
                "linkedin_outbound_enabled": True,
                "email_outbound_enabled": True,
            }
        ),
    )
    assert response.status_code == 200

    clients: list = Client.query.all()
    assert len(clients) == 1

    c: Client = get_client(clients[0].id)
    assert c.id == clients[0].id
    assert len(c.notification_allowlist) == 4
    assert c.linkedin_outbound_enabled == True
    assert c.email_outbound_enabled == True
    c_sdr: ClientSDR = basic_client_sdr(c)

    response = app.test_client().post(
        "client/archetype",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {get_login_token()}",
        },
        data=json.dumps(
            {
                "archetype": "testing",
                "filters": {},
                "disable_ai_after_prospect_engaged": True,
            }
        ),
    )
    assert response.status_code == 200

    client_archetypes: list = ClientArchetype.query.all()
    assert len(client_archetypes) == 1
    archetype = client_archetypes[0]
    assert archetype.client_id == c.id
    assert archetype.client_sdr_id == c_sdr.id
    assert archetype.archetype == "testing"
    assert archetype.filters == {}
    assert archetype.active == True
    assert archetype.disable_ai_after_prospect_engaged == True
    archetype_id = archetype.id

    response = app.test_client().patch(
        "client/archetype/toggle_active",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "client_archetype_id": archetype_id,
            }
        ),
    )
    assert response.status_code == 200
    archetype = ClientArchetype.query.get(archetype_id)
    assert archetype.active == False

    gnlp_models: list = GNLPModel.query.all()
    assert len(gnlp_models) == 1

    gnlp_model: GNLPModel = gnlp_models[0]
    gnlp_model.model_uuid = "TESTING_NEW_UUID"
    db.session.add(gnlp_model)
    db.session.commit()

    response = app.test_client().patch(
        "client/archetype",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "client_archetype_id": client_archetypes[0].id,
                "new_name": "testing2",
            }
        ),
    )
    assert response.status_code == 200
    archetype = ClientArchetype.query.get(client_archetypes[0].id)
    assert archetype.archetype == "testing2"
    archetype_id = archetype.id

    response = app.test_client().post(
        "client/archetype",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {get_login_token()}",
        },
        data=json.dumps(
            {
                "archetype": "testing",
                "filters": {},
                "base_archetype_id": archetype_id,
                "disable_ai_after_prospect_engaged": False,
            }
        ),
    )
    assert response.status_code == 200
    new_archetype_id = json.loads(response.data)["client_archetype_id"]

    new_archetype_gnlp_model: GNLPModel = GNLPModel.query.filter(
        GNLPModel.archetype_id == new_archetype_id
    ).first()
    assert new_archetype_gnlp_model is not None
    assert new_archetype_gnlp_model.model_uuid == "TESTING_NEW_UUID"

    client_archetypes: list = ClientArchetype.query.all()
    assert len(client_archetypes) == 2
    archetype_ai_not_disabled = client_archetypes[1]
    assert archetype_ai_not_disabled.client_id == c.id
    assert archetype_ai_not_disabled.disable_ai_after_prospect_engaged == False


@use_app_context
def test_add_client_and_archetype_and_sdr():

    create_client(
        company="testing",
        contact_name="testing",
        contact_email="testing",
        linkedin_outbound_enabled=True,
        email_outbound_enabled=True,
    )
    clients: list = Client.query.all()
    assert len(clients) == 1

    create_client(
        company="testing",
        contact_name="testing",
        contact_email="testing",
        linkedin_outbound_enabled=True,
        email_outbound_enabled=True,
    )
    clients: list = Client.query.all()
    assert len(clients) == 1

    c: Client = get_client(clients[0].id)
    assert c.id == clients[0].id
    c_sdr: ClientSDR = basic_client_sdr(c)

    create_client_archetype(
        client_id=c.id, client_sdr_id=c_sdr.id, archetype="testing", filters={}
    )
    client_archetypes: list = ClientArchetype.query.all()
    assert len(client_archetypes) == 1
    assert client_archetypes[0].client_sdr_id == c_sdr.id

    response = app.test_client().post(
        "client/sdr",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "client_id": c.id,
                "name": "testing",
                "email": "testing",
            }
        ),
    )
    assert response.status_code == 200

    client_sdrs: list = ClientSDR.query.all()
    assert len(client_sdrs) == 2

    response = app.test_client().post(
        "client/reset_client_sdr_auth_token",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "client_sdr_id": client_sdrs[1].id,
            }
        ),
    )
    assert response.status_code == 200
    client_sdrs: ClientSDR = ClientSDR.query.get(client_sdrs[1].id)
    assert client_sdrs.auth_token is not None

    client_archetypes: list = ClientArchetype.query.all()
    client_sdrs: list = ClientSDR.query.all()
    assert len(client_archetypes) == len(client_sdrs)


@use_app_context
def test_update_client_sdr_scheduling_link_endpoint():
    client = basic_client()
    client_sdr = basic_client_sdr(client=client)
    client_sdr_id = client_sdr.id

    assert client_sdr.scheduling_link is None

    response = app.test_client().patch(
        "client/sdr/update_scheduling_link",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "client_sdr_id": client_sdr_id,
                "scheduling_link": "TESTING_LINK",
            }
        ),
    )
    assert response.status_code == 200
    client_sdrs: ClientSDR = ClientSDR.query.get(client_sdr_id)
    assert client_sdrs.scheduling_link == "TESTING_LINK"


@use_app_context
def test_update_client_sdr_email_endpoint():
    client = basic_client()
    client_sdr = basic_client_sdr(client=client)
    client_sdr_id = client_sdr.id

    assert client_sdr.email == "test@test.com"

    response = app.test_client().patch(
        "client/sdr/update_email",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "client_sdr_id": client_sdr_id,
                "email": "test@testinco.com",
            }
        ),
    )
    assert response.status_code == 200
    client_sdrs: ClientSDR = ClientSDR.query.get(client_sdr_id)
    assert client_sdrs.email == "test@testinco.com"


@use_app_context
@mock.patch("src.client.services.send_slack_message")
def test_patch_update_pipeline_webhook(mock_send_slack_message):
    client: Client = basic_client()
    client_id = client.id

    assert client.pipeline_notifications_webhook_url == None

    response = app.test_client().patch(
        "client/update_pipeline_webhook",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "client_id": client_id,
                "webhook": "TESTING_WEBHOOK",
            }
        ),
    )
    assert response.status_code == 200
    client: Client = Client.query.get(client_id)
    assert client.pipeline_notifications_webhook_url == "TESTING_WEBHOOK"

    response = app.test_client().post(
        "client/test_webhook",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "client_id": client_id,
            }
        ),
    )
    assert response.status_code == 200
    assert mock_send_slack_message.call_count == 1


@use_app_context
@mock.patch("src.client.services.send_slack_message")
def test_patch_update_pipeline_client_sdr_webhook(mock_send_slack_message):
    """Tests the updating of a Client SDR's slack webhook endpoint.

    Args:
        mock_send_slack_message (Mock): Mocks the send_slack_message function.
    """
    client: Client = basic_client()
    client_sdr: ClientSDR = basic_client_sdr(client=client)
    client_sdr_id = client_sdr.id

    assert client_sdr.pipeline_notifications_webhook_url == None

    response = app.test_client().patch(
        "client/update_pipeline_client_sdr_webhook",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "client_sdr_id": client_sdr_id,
                "webhook": "TESTING_WEBHOOK",
            }
        ),
    )
    assert response.status_code == 200
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    assert client_sdr.pipeline_notifications_webhook_url == "TESTING_WEBHOOK"

    response = app.test_client().post(
        "client/test_sdr_webhook",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "client_sdr_id": client_sdr_id,
            }
        ),
    )
    assert response.status_code == 200
    assert mock_send_slack_message.call_count == 1


@use_app_context
def test_get_ctas():
    client = basic_client()
    client_archetype = basic_archetype(client)
    cta = basic_generated_message_cta(client_archetype)

    ctas = get_ctas(client_archetype.id)
    assert len(ctas) == 1
    assert ctas[0].id == cta.id


@use_app_context
def test_get_cta_by_archetype_id():
    client = basic_client()
    client_sdr = basic_client_sdr(client)
    archetype = basic_archetype(client, client_sdr)
    gnlp = basic_gnlp_model(archetype)

    prospect = basic_prospect(client, archetype)
    cta = basic_generated_message_cta_with_text(archetype, "test_cta")
    generated_message = basic_generated_message(prospect, gnlp, cta)

    ctas = get_cta_by_archetype_id(client_sdr.id, archetype.id)
    assert len(ctas.get("ctas")) == 1


@use_app_context
def test_get_cta_stats():
    client = basic_client()
    archetype = basic_archetype(client)
    gnlp = basic_gnlp_model(archetype)
    client_sdr = basic_client_sdr(client)
    prospect = basic_prospect(client, archetype)
    cta = basic_generated_message_cta_with_text(archetype, "test_cta")
    generated_message = basic_generated_message(prospect, gnlp, cta)
    generated_message.message_status = "SENT"

    stats = get_cta_stats(cta.id)
    assert stats.get("total_count") == 1
    assert stats.get("status_map") == {"PROSPECTED": 1}


@use_app_context
def test_get_sdr_available_outbound_channels():
    client = basic_client()
    client_sdr = basic_client_sdr(client)
    client_sdr.weekly_li_outbound_target = 10

    # Only LI and SellScale (Overall)
    available_channels = get_sdr_available_outbound_channels(client_sdr.id)
    li = available_channels.get("LINKEDIN")
    assert li["name"] != None
    assert li["description"] != None
    assert li["statuses_available"] != None
    ss = available_channels.get("SELLSCALE")
    assert ss["name"] != None
    assert ss["description"] != None
    assert ss["statuses_available"] != None

    # Email as well
    client_sdr.weekly_email_outbound_target = 0
    available_channels = get_sdr_available_outbound_channels(client_sdr.id)
    email = available_channels.get("EMAIL")
    assert email["name"] != None
    assert email["description"] != None
    assert email["statuses_available"] != None


@use_app_context
@mock.patch(
    "src.client.services.post_nylas_oauth_token",
    return_value={
        "access_token": "test_token",
        "account_id": "test_id",
        "email_address": "test_email",
    },
)
def test_nylas_exchange_for_authorization_code(mock_post_nylas_oauth_token):
    client = basic_client()
    client_sdr = basic_client_sdr(client)
    sdr_id = client_sdr.id
    client_sdr.email = "test_email"

    result = nylas_exchange_for_authorization_code(client_sdr.id, "test_code")
    assert result[1] == "test_token"
    assert result[0] == True
    assert mock_post_nylas_oauth_token.call_count == 1
    client_sdr: ClientSDR = ClientSDR.query.get(sdr_id)
    assert client_sdr.nylas_account_id == "test_id"
    assert client_sdr.nylas_auth_code == "test_token"
