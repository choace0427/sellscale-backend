from app import app, db
from model_import import (
    ConfigurationType,
    GeneratedMessageType,
    StackRankedMessageGenerationConfiguration,
)
from model_import import (
    Client,
    ClientArchetype,
    ClientSDR,
    ClientPod,
)
from tests.test_utils.decorators import use_app_context
from tests.test_utils.test_utils import (
    test_app,
    basic_client,
    basic_client_sdr,
    basic_archetype,
    basic_generated_message,
    basic_generated_message_cta,
    basic_generated_message_cta_with_text,
    get_login_token,
    basic_prospect,
)

import json
import mock


@use_app_context
def test_create_client():
    clients: list = Client.query.all()
    assert len(clients) == 0

    response = app.test_client().post(
        "client/",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "company": "test company",
                "contact_name": "test contact name",
                "contact_email": "test contact email",
                "linkedin_outbound_enabled": True,
                "email_outbound_enabled": True,
                "tagline": "test tagline",
                "description": "test description",
            }
        ),
    )
    assert response.status_code == 200

    client: Client = Client.query.first()
    assert client.company == "test company"
    assert client.contact_name == "test contact name"
    assert client.contact_email == "test contact email"
    assert client.linkedin_outbound_enabled == True
    assert client.email_outbound_enabled == True
    assert client.tagline == "test tagline"
    assert client.description == "test description"


@use_app_context
def test_demo_feedback():
    client = basic_client()
    client_sdr = basic_client_sdr(client)
    archetype = basic_archetype(client, client_sdr)
    prospect = basic_prospect(client, archetype, client_sdr)

    # Submit demo feedback
    response = app.test_client().post(
        "client/demo_feedback",
        headers={
            "Authorization": "Bearer {}".format(get_login_token()),
            "Content-Type": "application/json",
        },
        data=json.dumps(
            {
                "prospect_id": prospect.id,
                "status": "OCCURRED",
                "rating": "3/5",
                "feedback": "This is a test",
            }
        ),
    )
    assert response.status_code == 200

    # Check that demo feedback was created
    response = app.test_client().get(
        "client/demo_feedback",
        headers={
            "Authorization": "Bearer {}".format(get_login_token()),
        },
    )
    r_json = response.json
    assert response.status_code == 200
    assert len(r_json.get("data")) == 1

    # Check that demo feedback was created, prospect specific
    response = app.test_client().get(
        f"client/demo_feedback?prospect_id={prospect.id}",
        headers={
            "Authorization": "Bearer {}".format(get_login_token()),
        },
    )
    r_json = response.json
    assert response.status_code == 200
    assert len(r_json.get("data")) == 1


@use_app_context
def test_get_archetypes():
    client = basic_client()
    client_sdr = basic_client_sdr(client)
    archetype = basic_archetype(client, client_sdr)
    prospect = basic_prospect(client, archetype, client_sdr)

    response = app.test_client().get(
        "client/archetype/get_archetypes",
        headers={
            "Authorization": "Bearer {}".format(get_login_token()),
        },
    )
    r_json = response.json
    assert response.status_code == 200
    assert len(r_json.get("archetypes")) == 1
    assert r_json.get("archetypes")[0].get("id") == archetype.id


@use_app_context
@mock.patch("src.client.controllers.send_stytch_magic_link")
def test_send_magic_link(send_stytch_magic_link_mock):
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
    assert send_stytch_magic_link_mock.called


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
        "CURRENT_EXPERIENCE_DESCRIPTION",
        "RECENT_RECOMMENDATIONS",
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
        "CURRENT_EXPERIENCE_DESCRIPTION",
        "RECENT_RECOMMENDATIONS",
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
    assert response.json == [
        {
            "id": cta.id,
            "archetype_id": client_archetype.id,
            "text_value": "test_cta",
            "active": True,
            "expiration_date": None,
        }
    ]


@use_app_context
def test_get_cta():
    client = basic_client()
    client_sdr = basic_client_sdr(client)
    archetype = basic_archetype(client, client_sdr)

    prospect = basic_prospect(client, archetype)
    cta = basic_generated_message_cta_with_text(archetype, "test_cta")
    generated_message = basic_generated_message(prospect, cta)

    response = app.test_client().get(
        "client/archetype/{}/get_ctas".format(archetype.id),
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + get_login_token(),
        },
    )
    assert response.status_code == 200
    assert response.json.get("ctas")[0].get("id") == cta.id

    non_existent_archetype_response = app.test_client().get(
        "client/archetype/{}/get_ctas".format(archetype.id + 1),
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + get_login_token(),
        },
    )
    assert non_existent_archetype_response.status_code == 404
    assert non_existent_archetype_response.json.get("message") == "Archetype not found"

    client_sdr_2 = basic_client_sdr(client)
    archetype_2 = basic_archetype(client, client_sdr_2)
    unauthorized_response = app.test_client().get(
        "client/archetype/{}/get_ctas".format(archetype_2.id),
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + get_login_token(),
        },
    )
    assert unauthorized_response.status_code == 403
    assert (
        unauthorized_response.json.get("message") == "Archetype does not belong to you"
    )


@use_app_context
def test_get_sdr():
    client = basic_client()
    client_sdr = basic_client_sdr(client)

    response = app.test_client().get(
        "client/sdr",
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + get_login_token(),
        },
    )
    assert response.status_code == 200
    assert response.json.get("sdr_info").get("sdr_name") == "Test SDR"


@use_app_context
def test_get_sdr_available_outbound_channels_endpoint():
    client = basic_client()
    client_sdr = basic_client_sdr(client)
    client_sdr.weekly_li_outbound_target = 10

    # LI and SS only
    response = app.test_client().get(
        "client/sdr/get_available_outbound_channels",
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + get_login_token(),
        },
    )
    assert response.status_code == 200
    channels = response.json.get("available_outbound_channels")
    li = channels.get("LINKEDIN")
    assert li["name"] != None
    assert li["description"] != None
    assert li["statuses_available"] != None
    ss = channels.get("SELLSCALE")
    assert ss["name"] != None
    assert ss["description"] != None
    assert ss["statuses_available"] != None

    # Email as well
    client_sdr.weekly_email_outbound_target = 0
    response = app.test_client().get(
        "client/sdr/get_available_outbound_channels",
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + get_login_token(),
        },
    )
    assert response.status_code == 200
    channels = response.json.get("available_outbound_channels")
    email = channels.get("EMAIL")
    assert email["name"] != None
    assert email["description"] != None
    assert email["statuses_available"] != None


@use_app_context
def test_post_toggle_client_sdr_autopilot_enabled():
    client = basic_client()
    client_sdr = basic_client_sdr(client)
    srmgc = StackRankedMessageGenerationConfiguration(
        configuration_type=ConfigurationType.DEFAULT,
        generated_message_type=GeneratedMessageType.LINKEDIN,
        instruction="some instruction",
        computed_prompt="some prompt",
        client_id=client.id,
    )
    db.session.add(srmgc)
    db.session.commit()

    assert client_sdr.autopilot_enabled == False

    response = app.test_client().post(
        "client/sdr/toggle_autopilot_enabled",
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + get_login_token(),
        },
        data=json.dumps({"client_sdr_id": client_sdr.id}),
    )
    assert response.status_code == 200

    client_sdr = ClientSDR.query.filter_by(id=client_sdr.id).first()
    assert client_sdr.autopilot_enabled == True

    response = app.test_client().post(
        "client/sdr/toggle_autopilot_enabled",
        headers={
            "Content-Type": "application/json",
        },
        data=json.dumps({"client_sdr_id": client_sdr.id}),
    )
    assert response.status_code == 200

    client_sdr = ClientSDR.query.filter_by(id=client_sdr.id).first()
    assert client_sdr.autopilot_enabled == False


@use_app_context
def test_create_delete_client_pod_and_add_remove_sdr_from_pod():
    client = basic_client()
    client_sdr = basic_client_sdr(client)

    # create client pod
    response = app.test_client().post(
        "client/pod",
        headers={
            "Content-Type": "application/json",
        },
        data=json.dumps({"client_id": client.id, "name": "test_pod"}),
    )
    assert response.status_code == 200

    client_pod = ClientPod.query.filter_by(client_id=client.id).first()
    assert client_pod != None
    assert client_pod.name == "test_pod"

    # add sdr to pod
    response = app.test_client().post(
        "client/sdr/add_to_pod",
        headers={
            "Content-Type": "application/json",
        },
        data=json.dumps(
            {"client_sdr_id": client_sdr.id, "client_pod_id": client_pod.id}
        ),
    )
    assert response.status_code == 200

    client_sdr = ClientSDR.query.filter_by(id=client_sdr.id).first()
    assert client_sdr.client_pod_id == client_pod.id

    # get list of pods
    response = app.test_client().get(
        "client/pod/get_pods?client_id={}".format(client.id),
        headers={
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 200

    pods = response.json
    assert len(pods) == 1
    assert pods[0]["id"] == client_pod.id
    assert pods[0]["name"] == "test_pod"
    assert len(pods[0]["client_sdrs"]) == 1

    # remove sdr from pod
    response = app.test_client().post(
        "client/sdr/add_to_pod",
        headers={
            "Content-Type": "application/json",
        },
        data=json.dumps({"client_sdr_id": client_sdr.id, "client_pod_id": None}),
    )
    assert response.status_code == 200

    client_sdr = ClientSDR.query.filter_by(id=client_sdr.id).first()
    assert client_sdr.client_pod_id == None

    # remove pod
    response = app.test_client().delete(
        "client/pod",
        headers={
            "Content-Type": "application/json",
        },
        data=json.dumps({"client_pod_id": client_pod.id}),
    )
    assert response.status_code == 200

    client_pod = ClientPod.query.filter_by(id=client_pod.id).first()
    assert client_pod == None


@use_app_context
def test_post_update_description_and_fit():
    client = basic_client()
    client_sdr = basic_client_sdr(client)
    client_archetype = basic_archetype(client, client_sdr)
    client_sdr_id = client_sdr.id
    client_archetype_id = client_archetype.id

    # check old description
    assert client_archetype.persona_fit_reason == None

    # update description
    response = app.test_client().post(
        "client/archetype/{client_archetype_id}/update_description_and_fit".format(
            client_archetype_id=client_archetype_id
        ),
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + get_login_token(),
        },
        data=json.dumps(
            {
                "updated_persona_fit_reason": "test fit reason",
            }
        ),
    )
    assert response.status_code == 200

    # check new description
    client_archetype = ClientArchetype.query.filter_by(id=client_archetype_id).first()
    assert client_archetype.persona_fit_reason == "test fit reason"
