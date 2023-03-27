from app import db, app
import pytest
from decorators import use_app_context
import datetime
import json

from test_utils import (
    test_app,
    get_login_token,
    basic_client,
    basic_archetype,
    basic_client_sdr,
    basic_prospect,
    basic_editor,
    basic_prospect_email,
    basic_generated_message_cta,
    basic_outbound_campaign,
)
from src.campaigns.services import create_outbound_campaign
from model_import import (
    OutboundCampaign,
    GeneratedMessageType,
    ProspectEmailStatus,
    ProspectEmailOutreachStatus,
)
import mock


@use_app_context
def test_get_campaign_details():
    client = basic_client()
    archetype = basic_archetype(client)
    client_sdr = basic_client_sdr(client)
    prospect = basic_prospect(client, archetype, client_sdr)
    campaign = basic_outbound_campaign([prospect.id], GeneratedMessageType.LINKEDIN, archetype, client_sdr)
    campaign_id = campaign.id

    response = app.test_client().get(
        f"campaigns/{campaign.id}",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {get_login_token()}",
        }
    )
    assert response.status_code == 200
    assert response.json.get("campaign_details").get("campaign_raw").get("id") == campaign.id
    assert response.json.get("campaign_details").get("prospects")[0].get("id") == prospect.id

    client_sdr_2 = basic_client_sdr(client)
    client_sdr_2.auth_token = "1234"
    db.session.add(client_sdr_2)
    db.session.commit()

    denied_response = app.test_client().get(
        f"campaigns/{campaign_id}",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer 1234",
        }
    )
    assert denied_response.status_code == 403

    no_record_response = app.test_client().get(
        f"campaigns/{campaign_id + 1}",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {get_login_token()}",
        }
    )
    assert no_record_response.status_code == 404



@use_app_context
def test_get_campaign_details_by_uuid():
    client = basic_client()
    archetype = basic_archetype(client)
    client_sdr = basic_client_sdr(client)
    prospect = basic_prospect(client, archetype, client_sdr)
    campaign = basic_outbound_campaign([prospect.id], GeneratedMessageType.LINKEDIN, archetype, client_sdr)
    campaign.uuid = 'test_uuid'
    campaign_id = campaign.id

    response = app.test_client().get(
        f"campaigns/uuid/{campaign.uuid}",
        headers={
            "Content-Type": "application/json",
        }
    )
    assert response.status_code == 200
    assert response.json.get("campaign_details").get("campaign_raw").get("id") == campaign.id


@use_app_context
def test_get_all_campaigns():
    client = basic_client()
    archetype = basic_archetype(client)
    client_sdr = basic_client_sdr(client)
    prospect = basic_prospect(client, archetype, client_sdr)
    campaign = basic_outbound_campaign(
        [prospect.id], GeneratedMessageType.EMAIL, archetype, client_sdr, name="Aa"
    )
    campaign_2 = basic_outbound_campaign(
        [prospect.id], GeneratedMessageType.EMAIL, archetype, client_sdr, name="Ab"
    )
    campaign_3 = basic_outbound_campaign(
        [prospect.id], GeneratedMessageType.LINKEDIN, archetype, client_sdr, name="B"
    )

    response = app.test_client().post(
        "campaigns/all_campaigns",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {get_login_token()}",
        },
        data=json.dumps({}),
    )
    assert response.status_code == 200
    assert response.json.get("total_count") == 3


@use_app_context
def test_create_generate_message_campaign():
    client = basic_client()
    archetype = basic_archetype(client)
    client_sdr = basic_client_sdr(client)

    prospect1 = basic_prospect(client, archetype)
    prospect2 = basic_prospect(client, archetype)
    prospect3 = basic_prospect(client, archetype)
    prospect_ids = [prospect1.id, prospect2.id, prospect3.id]

    response = app.test_client().post(
        "campaigns/",
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + get_login_token(),
        },
        data=json.dumps(
            {
                "prospect_ids": prospect_ids,
                "num_prospects": 3,
                "campaign_type": "LINKEDIN",
                "ctas": [5, 6],
                "client_archetype_id": archetype.id,
                "client_sdr_id": client_sdr.id,
                "campaign_start_date": "2021-01-01",
                "campaign_end_date": "2021-01-01",
            }
        ),
    )
    assert response.status_code == 200
    campaign_id = json.loads(response.data.decode("utf-8"))["campaign_id"]
    assert campaign_id > 0

    campaign: OutboundCampaign = OutboundCampaign.query.get(campaign_id)
    campaign_id = campaign.id
    assert campaign.id == campaign_id
    assert campaign.client_archetype_id == archetype.id
    assert campaign.client_sdr_id == client_sdr.id
    assert campaign.campaign_type.value == "LINKEDIN"
    assert campaign.prospect_ids == prospect_ids
    assert campaign.ctas == [5, 6]
    assert campaign.status.value == "PENDING"
    assert len(campaign.uuid) > 10

    response = app.test_client().post(
        f"campaigns/{campaign_id}/generate",
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + get_login_token(),
        },
    )
    assert response.status_code == 200


@use_app_context
@mock.patch(
    "src.message_generation.services.research_and_generate_outreaches_for_prospect.delay"
)
def test_create_generate_email_campaign(message_gen_call_patch):
    client = basic_client()
    archetype = basic_archetype(client)
    client_sdr = basic_client_sdr(client)

    response = app.test_client().post(
        "campaigns/",
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + get_login_token(),
        },
        data=json.dumps(
            {
                "prospect_ids": [1, 2, 3, 4],
                "num_prospects": 4,
                "campaign_type": "EMAIL",
                "client_archetype_id": archetype.id,
                "client_sdr_id": client_sdr.id,
                "campaign_start_date": "2021-01-01",
                "campaign_end_date": "2021-01-01",
            }
        ),
    )
    assert response.status_code == 200
    campaign_id = json.loads(response.data.decode("utf-8"))["campaign_id"]
    assert campaign_id > 0

    campaign: OutboundCampaign = OutboundCampaign.query.get(campaign_id)
    campaign_id = campaign.id
    assert campaign.id == campaign_id
    assert campaign.client_archetype_id == archetype.id
    assert campaign.client_sdr_id == client_sdr.id
    assert campaign.campaign_type.value == "EMAIL"
    assert campaign.prospect_ids == [1, 2, 3, 4]
    assert campaign.ctas == None
    assert campaign.status.value == "PENDING"

    response = app.test_client().post(
        f"campaigns/{campaign_id}/generate",
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + get_login_token(),
        },
    )
    assert response.status_code == 200
    assert message_gen_call_patch.call_count == 0

    campaign = OutboundCampaign.query.get(campaign_id)
    assert campaign.editing_due_date > datetime.datetime.now()

    # test adjusting editing due date
    response = app.test_client().post(
        "campaigns/adjust_editing_due_date",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "campaign_id": campaign_id,
                "new_date": "2021-01-01",
            }
        ),
    )
    assert response.status_code == 200
    campaign = OutboundCampaign.query.get(campaign_id)
    assert campaign.editing_due_date == datetime.datetime(2021, 1, 1)


@use_app_context
@mock.patch(
    "src.campaigns.services.generate_outreaches_for_prospect_list_from_multiple_ctas.apply_async"
)
def test_change_campaign_status(generate_outreaches_for_prospect_list_from_multiple_ctas_patch):
    client = basic_client()
    archetype = basic_archetype(client)
    client_sdr = basic_client_sdr(client)

    response = app.test_client().post(
        "campaigns/",
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + get_login_token(),
        },
        data=json.dumps(
            {
                "prospect_ids": [1, 2, 3, 4],
                "num_prospects": 4,
                "campaign_type": "LINKEDIN",
                "ctas": [5, 6],
                "client_archetype_id": archetype.id,
                "client_sdr_id": client_sdr.id,
                "campaign_start_date": "2021-01-01",
                "campaign_end_date": "2021-01-01",
            }
        ),
    )
    assert response.status_code == 200
    campaign_id = json.loads(response.data.decode("utf-8"))["campaign_id"]
    assert campaign_id > 0
    campaign: OutboundCampaign = OutboundCampaign.query.get(campaign_id)
    assert campaign.status.value == "PENDING"

    response = app.test_client().patch(
        "campaigns/",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "campaign_id": campaign_id,
                "status": "IN_PROGRESS",
            }
        ),
    )

    assert response.status_code == 200
    campaign: OutboundCampaign = OutboundCampaign.query.get(campaign_id)
    assert campaign.status.value == "IN_PROGRESS"

    response = app.test_client().post(
        "campaigns/mark_ready_to_send",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "campaign_id": campaign_id,
            }
        ),
    )
    assert response.status_code == 200
    campaign: OutboundCampaign = OutboundCampaign.query.get(campaign_id)
    assert campaign.status.value == "READY_TO_SEND"

    campaign_id = campaign.id
    campaign_name = campaign.name
    assert campaign_name != "New Campaign Name"
    response = app.test_client().post(
        "campaigns/update_campaign_name",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "campaign_id": campaign_id,
                "name": "New Campaign Name",
            }
        ),
    )
    assert response.status_code == 200
    campaign: OutboundCampaign = OutboundCampaign.query.get(campaign_id)
    assert campaign.name == "New Campaign Name"

    campaign_start_date = campaign.campaign_start_date
    campaign_end_date = campaign.campaign_end_date

    new_start_date = datetime.datetime.now().isoformat()
    new_end_date = (datetime.datetime.now() + datetime.timedelta(days=1)).isoformat()

    assert campaign_start_date != new_start_date
    assert campaign_end_date != new_end_date

    response = app.test_client().post(
        "campaigns/update_campaign_dates",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "campaign_id": campaign_id,
                "start_date": new_start_date,
                "end_date": new_end_date,
            }
        ),
    )
    assert response.status_code == 200
    campaign: OutboundCampaign = OutboundCampaign.query.get(campaign_id)
    assert campaign.campaign_start_date.isoformat() == new_start_date
    assert campaign.campaign_end_date.isoformat() == new_end_date

    response = app.test_client().post(
        "campaigns/mark_initial_review_complete",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "campaign_id": campaign_id,
            }
        ),
    )
    assert response.status_code == 400

    response = app.test_client().post(
        f"campaigns/{campaign_id}/generate",
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + get_login_token(),
        },
    )
    assert response.status_code == 200
    campaign: OutboundCampaign = OutboundCampaign.query.get(campaign_id)
    assert campaign.status.value == "NEEDS_REVIEW"

    assert (
        generate_outreaches_for_prospect_list_from_multiple_ctas_patch.call_count == 1
    )


@use_app_context
def test_change_campaign_status_to_edit_complete():
    client = basic_client()
    archetype = basic_archetype(client)
    client_sdr = basic_client_sdr(client)

    response = app.test_client().post(
        "campaigns/",
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + get_login_token(),
        },
        data=json.dumps(
            {
                "prospect_ids": [1, 2, 3, 4],
                "num_prospects": 4,
                "campaign_type": "LINKEDIN",
                "ctas": [5, 6],
                "client_archetype_id": archetype.id,
                "client_sdr_id": client_sdr.id,
                "campaign_start_date": "2021-01-01",
                "campaign_end_date": "2021-01-01",
                "editor_id": None,
            }
        ),
    )
    assert response.status_code == 200
    campaign_id = json.loads(response.data.decode("utf-8"))["campaign_id"]
    assert campaign_id > 0
    campaign: OutboundCampaign = OutboundCampaign.query.get(campaign_id)
    assert campaign.status.value == "PENDING"

    response = app.test_client().patch(
        "campaigns/",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "campaign_id": campaign_id,
                "status": "IN_PROGRESS",
            }
        ),
    )

    assert response.status_code == 200
    campaign: OutboundCampaign = OutboundCampaign.query.get(campaign_id)
    assert campaign.status.value == "IN_PROGRESS"

    response = app.test_client().post(
        "campaigns/mark_initial_review_complete",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "campaign_id": campaign_id,
            }
        ),
    )
    assert response.status_code == 200
    campaign: OutboundCampaign = OutboundCampaign.query.get(campaign_id)
    assert campaign.status.value == "INITIAL_EDIT_COMPLETE"

    response = app.test_client().patch(
        "campaigns/batch",
        headers={"Content-Type": "application/json"},
        data=json.dumps({"payload": []}),
    )

    assert response.status_code == 200
    campaign = OutboundCampaign.query.get(campaign_id)
    assert campaign.status.value == "INITIAL_EDIT_COMPLETE"

    response = app.test_client().patch(
        "campaigns/batch",
        headers={"Content-Type": "application/json"},
        data=json.dumps({"payload": []}),
    )
    assert response.status_code == 200

    response = app.test_client().patch(
        "campaigns/batch",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "payload": [
                    {
                        "client": "Parker #14",
                        "campaign_id": campaign.id,
                        "archetype": "Online shop owners",
                        "name": "Martin Mrozowski",
                        "campaign_specs": "#148 LINKEDIN",
                        "campaign_start_date": "2022-12-14",
                        "campaign_end_date": "2023-01-14",
                        "status": "READY_TO_SEND",
                        "uuid": "4y8idpRlNXyvNth2Iy7Ei0Z4YOl5vjnT",
                        "campaign_name": "Pierce, Bash 1, Online shop owners, 75, 2022-12-26",
                        "auth_token": "PvVELxlEfi52pcKJ5ms8GJnVcFyQgKWg",
                        "num_prospects": "75",
                        "num_generated": "73",
                        "num_edited": "73",
                        "num_sent": "2",
                        "editor_id": None,
                        "editing_due_date": "2022-12-26",
                    }
                ]
            }
        ),
    )
    assert response.status_code == 200
    campaign = OutboundCampaign.query.get(campaign_id)
    assert campaign.status.value == "READY_TO_SEND"
    assert campaign.campaign_start_date.isoformat() == "2022-12-14T00:00:00"
    assert campaign.campaign_end_date.isoformat() == "2023-01-14T00:00:00"
    assert campaign.name == "Pierce, Bash 1, Online shop owners, 75, 2022-12-26"
    assert campaign.name == "Pierce, Bash 1, Online shop owners, 75, 2022-12-26"
    assert campaign.editing_due_date == datetime.datetime(2022, 12, 26)

    response = app.test_client().patch(
        "campaigns/batch_editing_attributes",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "payload": [
                    {
                        "campaign_id": campaign.id,
                        "reported_time_in_hours": 2,
                        "reviewed_feedback": True,
                        "sellscale_grade": "A",
                        "brief_feedback_summary": "this is feedback",
                        "detailed_feedback_link": "https://www.google.com",
                    }
                ]
            }
        ),
    )
    assert response.status_code == 200

    campaign = OutboundCampaign.query.get(campaign_id)
    assert campaign.reported_time_in_hours == 2
    assert campaign.reviewed_feedback
    assert campaign.sellscale_grade == "A"
    assert campaign.brief_feedback_summary == "this is feedback"
    assert campaign.detailed_feedback_link == "https://www.google.com"


@use_app_context
def test_merge_then_split_multiple_linkedin_campaigns_succeed():
    client = basic_client()
    archetype = basic_archetype(client)
    archetype_id = archetype.id
    client_sdr = basic_client_sdr(client)
    client_sdr_id = client_sdr.id

    # test merging campaigns
    campaign1 = create_outbound_campaign(
        prospect_ids=[1, 2],
        num_prospects=2,
        campaign_type="LINKEDIN",
        client_archetype_id=archetype_id,
        client_sdr_id=client_sdr_id,
        campaign_start_date="2021-01-01",
        campaign_end_date="2021-01-01",
        ctas=[1, 2, 3],
    )
    campaign2 = create_outbound_campaign(
        prospect_ids=[2, 3, 4],
        num_prospects=3,
        campaign_type="LINKEDIN",
        client_archetype_id=archetype_id,
        client_sdr_id=client_sdr_id,
        campaign_start_date="2021-01-02",
        campaign_end_date="2021-01-05",
        ctas=[2, 3, 4],
    )

    response = app.test_client().post(
        "campaigns/merge",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "campaign_ids": [campaign1.id, campaign2.id],
            }
        ),
    )
    assert response.status_code == 200
    campaign_id = json.loads(response.data.decode("utf-8"))["new_campaign_id"]
    assert campaign_id > 0
    campaign: OutboundCampaign = OutboundCampaign.query.get(campaign_id)
    assert campaign.status.value == "PENDING"
    assert campaign.prospect_ids == [1, 2, 3, 4]
    assert campaign.campaign_end_date == datetime.datetime(2021, 1, 5)
    assert campaign.campaign_start_date == datetime.datetime(2021, 1, 1)
    assert campaign.campaign_type.value == "LINKEDIN"
    assert campaign.client_archetype_id == archetype_id
    assert campaign.client_sdr_id == client_sdr_id
    assert campaign.ctas == [1, 2, 3, 4]

    # test splitting campaigns
    split_campaign_id = campaign_id
    response = app.test_client().post(
        "campaigns/split",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "campaign_id": split_campaign_id,
                "num_campaigns": 3,
            }
        ),
    )
    assert response.status_code == 200
    campaign_ids = json.loads(response.data.decode("utf-8"))["campaign_ids"]
    assert len(campaign_ids) == 3
    assert campaign_ids[0] > 0
    assert campaign_ids[1] > 0
    assert campaign_ids[2] > 0
    campaign1: OutboundCampaign = OutboundCampaign.query.get(campaign_ids[0])
    campaign2: OutboundCampaign = OutboundCampaign.query.get(campaign_ids[1])
    campaign3: OutboundCampaign = OutboundCampaign.query.get(campaign_ids[2])

    assert len(campaign1.prospect_ids) in [1, 2]
    assert len(campaign2.prospect_ids) in [1, 2]
    assert len(campaign3.prospect_ids) in [1, 2]

    # test sum of length of all campaigns adds up to 4
    assert (
        len(campaign1.prospect_ids)
        + len(campaign2.prospect_ids)
        + len(campaign3.prospect_ids)
        == 4
    )
    # assert set of sum of length all campaigns is 4
    assert set(
        campaign1.prospect_ids + campaign2.prospect_ids + campaign3.prospect_ids
    ) == set([1, 2, 3, 4])

    # in a for loop, assert all campaigns are pending, have same start and end date, have same campaign type value, and have same archetype and client sdr id
    for c in [campaign1, campaign2, campaign3]:
        assert c.status.value == "PENDING"
        assert c.campaign_end_date == datetime.datetime(2021, 1, 5)
        assert c.campaign_start_date == datetime.datetime(2021, 1, 1)
        assert c.campaign_type.value == "LINKEDIN"
        assert c.client_archetype_id == archetype_id
        assert c.client_sdr_id == client_sdr_id
        assert c.ctas == [1, 2, 3, 4]

    # assrt original campaign is cancelled
    campaign = OutboundCampaign.query.get(split_campaign_id)
    assert campaign.status.value == "CANCELLED"

    # test the intersection of the prospect ids in a double for loop
    for c1 in [campaign1, campaign2, campaign3]:
        for c2 in [campaign1, campaign2, campaign3]:
            if c1.id != c2.id:
                assert set(c1.prospect_ids).isdisjoint(set(c2.prospect_ids))


@use_app_context
def test_make_fake_campaign_with_10_prospect_ids_then_split_into_5_parts():
    client = basic_client()
    archetype = basic_archetype(client)
    archetype_id = archetype.id
    client_sdr = basic_client_sdr(client)
    client_sdr_id = client_sdr.id

    campaign1 = create_outbound_campaign(
        prospect_ids=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        num_prospects=10,
        campaign_type="LINKEDIN",
        client_archetype_id=archetype_id,
        client_sdr_id=client_sdr_id,
        campaign_start_date="2021-01-01",
        campaign_end_date="2021-01-01",
        ctas=[1, 2, 3],
    )

    original_campaign_id = campaign1.id
    response = app.test_client().post(
        "campaigns/split",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "campaign_id": campaign1.id,
                "num_campaigns": 5,
            }
        ),
    )
    assert response.status_code == 200
    campaign_ids = json.loads(response.data.decode("utf-8"))["campaign_ids"]

    # assert original campaign is cancelled
    campaign = OutboundCampaign.query.get(original_campaign_id)
    assert campaign.status.value == "CANCELLED"

    assert len(campaign_ids) == 5
    assert campaign_ids[0] > 0
    assert campaign_ids[1] > 0
    assert campaign_ids[2] > 0
    assert campaign_ids[3] > 0
    assert campaign_ids[4] > 0
    campaign1: OutboundCampaign = OutboundCampaign.query.get(campaign_ids[0])
    campaign2: OutboundCampaign = OutboundCampaign.query.get(campaign_ids[1])
    campaign3: OutboundCampaign = OutboundCampaign.query.get(campaign_ids[2])
    campaign4: OutboundCampaign = OutboundCampaign.query.get(campaign_ids[3])
    campaign5: OutboundCampaign = OutboundCampaign.query.get(campaign_ids[4])

    assert len(campaign1.prospect_ids) == 2
    assert len(campaign2.prospect_ids) == 2
    assert len(campaign3.prospect_ids) == 2
    assert len(campaign4.prospect_ids) == 2
    assert len(campaign5.prospect_ids) == 2

    # test sum of length of all campaigns adds up to 10
    assert (
        len(campaign1.prospect_ids)
        + len(campaign2.prospect_ids)
        + len(campaign3.prospect_ids)
        + len(campaign4.prospect_ids)
        + len(campaign5.prospect_ids)
        == 10
    )
    # assert set of sum of length all campaigns is 10
    assert set(
        campaign1.prospect_ids
        + campaign2.prospect_ids
        + campaign3.prospect_ids
        + campaign4.prospect_ids
        + campaign5.prospect_ids
    ) == set([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])

    # in a for loop, assert all campaigns are pending, have same start and end date, have same campaign type value, and have same archetype and client sdr id
    for c in [campaign1, campaign2, campaign3, campaign4, campaign5]:
        assert c.status.value == "PENDING"
        assert c.campaign_end_date == datetime.datetime(2021, 1, 1)
        assert c.campaign_start_date == datetime.datetime(2021, 1, 1)
        assert c.campaign_type.value == "LINKEDIN"
        assert c.client_archetype_id == archetype_id
        assert c.client_sdr_id == client_sdr_id
        assert c.ctas == [1, 2, 3]

    # test the intersection of the sets of each campaign to ensure no overlap in a double for-loop
    for c1 in [campaign1, campaign2, campaign3, campaign4, campaign5]:
        for c2 in [campaign1, campaign2, campaign3, campaign4, campaign5]:
            if c1.id != c2.id:
                assert len(set(c1.prospect_ids).intersection(set(c2.prospect_ids))) == 0


@use_app_context
def test_merge_multiple_email_campaigns_succeed():
    client = basic_client()
    archetype = basic_archetype(client)
    archetype_id = archetype.id
    client_sdr = basic_client_sdr(client)
    client_sdr_id = client_sdr.id
    editor = basic_editor()
    editor_2 = basic_editor()

    campaign1 = create_outbound_campaign(
        prospect_ids=[1, 2],
        num_prospects=2,
        campaign_type="EMAIL",
        client_archetype_id=archetype_id,
        client_sdr_id=client_sdr_id,
        campaign_start_date="2021-01-01",
        campaign_end_date="2021-01-01",
    )
    campaign1.editor_id = editor.id
    db.session.add(campaign1)
    db.session.commit()

    campaign1_id = campaign1.id
    campaign2 = create_outbound_campaign(
        prospect_ids=[2, 3, 4],
        num_prospects=3,
        campaign_type="EMAIL",
        client_archetype_id=archetype_id,
        client_sdr_id=client_sdr_id,
        campaign_start_date="2021-01-02",
        campaign_end_date="2021-01-05",
    )
    campaign2.editor_id = editor.id
    db.session.add(campaign2)
    db.session.commit()
    campaign2_id = campaign2.id

    response = app.test_client().post(
        "campaigns/merge",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "campaign_ids": [campaign1.id, campaign2.id],
            }
        ),
    )
    assert response.status_code == 200
    campaign_id = json.loads(response.data.decode("utf-8"))["new_campaign_id"]
    assert campaign_id > 0
    campaign: OutboundCampaign = OutboundCampaign.query.get(campaign_id)
    assert campaign.status.value == "PENDING"
    assert campaign.prospect_ids == [1, 2, 3, 4]
    assert campaign.campaign_end_date == datetime.datetime(2021, 1, 5)
    assert campaign.campaign_start_date == datetime.datetime(2021, 1, 1)
    assert campaign.campaign_type.value == "EMAIL"
    assert campaign.client_archetype_id == archetype_id
    assert campaign.client_sdr_id == client_sdr_id

    campaign1 = OutboundCampaign.query.get(campaign1_id)
    campaign2 = OutboundCampaign.query.get(campaign2_id)
    merged_campaign = OutboundCampaign.query.get(campaign_id)
    assert campaign1.status.value == "CANCELLED"
    assert campaign2.status.value == "CANCELLED"
    assert merged_campaign.status.value == "PENDING"


@use_app_context
def test_merge_multiple_email_campaigns_failed_for_type():
    client = basic_client()
    archetype = basic_archetype(client)
    archetype_id = archetype.id
    client_sdr = basic_client_sdr(client)
    client_sdr_id = client_sdr.id

    campaign1 = create_outbound_campaign(
        prospect_ids=[1, 2],
        num_prospects=2,
        campaign_type="EMAIL",
        client_archetype_id=archetype_id,
        client_sdr_id=client_sdr_id,
        campaign_start_date="2021-01-01",
        campaign_end_date="2021-01-01",
    )
    campaign1_id = campaign1.id
    campaign2 = create_outbound_campaign(
        prospect_ids=[2, 3, 4],
        num_prospects=3,
        campaign_type="LINKEDIN",
        client_archetype_id=archetype_id,
        client_sdr_id=client_sdr_id,
        campaign_start_date="2021-01-02",
        campaign_end_date="2021-01-05",
    )
    campaign2_id = campaign2.id

    response = app.test_client().post(
        "campaigns/merge",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "campaign_ids": [campaign1.id, campaign2.id],
            }
        ),
    )
    assert response.status_code == 400
    assert response.text == "Campaigns must be of the same type"
    all_campaigns = OutboundCampaign.query.all()
    assert len(all_campaigns) == 2

    campaign1 = OutboundCampaign.query.get(campaign1_id)
    campaign2 = OutboundCampaign.query.get(campaign2_id)
    assert campaign1.status.value == "PENDING"
    assert campaign2.status.value == "PENDING"


@use_app_context
def test_merge_multiple_email_campaigns_failed_for_archetype():
    client = basic_client()
    archetype = basic_archetype(client)
    archetype_id = archetype.id
    client_sdr = basic_client_sdr(client)
    client_sdr_id = client_sdr.id

    archetype_2 = basic_archetype(client)
    archetype_2_id = archetype_2.id

    campaign1 = create_outbound_campaign(
        prospect_ids=[1, 2],
        num_prospects=2,
        campaign_type="EMAIL",
        client_archetype_id=archetype_id,
        client_sdr_id=client_sdr_id,
        campaign_start_date="2021-01-01",
        campaign_end_date="2021-01-01",
    )
    campaign1_id = campaign1.id
    campaign2 = create_outbound_campaign(
        prospect_ids=[2, 3, 4],
        num_prospects=3,
        campaign_type="EMAIL",
        client_archetype_id=archetype_2_id,
        client_sdr_id=client_sdr_id,
        campaign_start_date="2021-01-02",
        campaign_end_date="2021-01-05",
    )
    campaign2_id = campaign2.id

    response = app.test_client().post(
        "campaigns/merge",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "campaign_ids": [campaign1.id, campaign2.id],
            }
        ),
    )
    assert response.status_code == 400
    assert response.text == "Campaigns must be of the same client archetype"
    all_campaigns = OutboundCampaign.query.all()
    assert len(all_campaigns) == 2

    campaign1 = OutboundCampaign.query.get(campaign1_id)
    campaign2 = OutboundCampaign.query.get(campaign2_id)
    assert campaign1.status.value == "PENDING"
    assert campaign2.status.value == "PENDING"

    campaign1 = OutboundCampaign.query.get(campaign1_id)
    campaign2 = OutboundCampaign.query.get(campaign2_id)
    editor1 = basic_editor()
    editor2 = basic_editor()

    campaign1.editor_id = editor1.id
    campaign2.editor_id = editor2.id
    campaign2.client_archetype_id = campaign1.client_archetype_id
    db.session.add(campaign1)
    db.session.add(campaign2)
    db.session.commit()

    response = app.test_client().post(
        "campaigns/merge",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "campaign_ids": [campaign1.id, campaign2.id],
            }
        ),
    )
    assert response.status_code == 400
    assert (
        response.text
        == "Campaigns must have the same editor assigned to edit! Please consolidate the editors."
    )

    campaign2 = OutboundCampaign.query.get(campaign2_id)
    campaign2.editor_id = editor1.id
    db.session.add(campaign2)
    db.session.commit()

    response = app.test_client().post(
        "campaigns/merge",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "campaign_ids": [campaign1.id, campaign2.id],
            }
        ),
    )
    assert response.status_code == 200


@use_app_context
def test_assign_editor_to_campaign():
    client = basic_client()
    archetype = basic_archetype(client)
    archetype_id = archetype.id
    client_sdr = basic_client_sdr(client)
    client_sdr_id = client_sdr.id

    campaign = create_outbound_campaign(
        prospect_ids=[1, 2],
        num_prospects=2,
        campaign_type="EMAIL",
        client_archetype_id=archetype_id,
        client_sdr_id=client_sdr_id,
        campaign_start_date="2021-01-01",
        campaign_end_date="2021-01-01",
    )
    campaign_id = campaign.id

    editor = basic_editor()
    editor_id = editor.id

    response = app.test_client().post(
        f"campaigns/assign_editor",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "editor_id": editor_id,
                "campaign_id": campaign_id,
            }
        ),
    )
    assert response.status_code == 200
    campaign = OutboundCampaign.query.get(campaign_id)
    assert campaign.editor_id == editor_id


@use_app_context
def test_post_remove_ungenerated_prospects():
    client = basic_client()
    archetype = basic_archetype(client)
    archetype_id = archetype.id
    client_sdr = basic_client_sdr(client)
    client_sdr_id = client_sdr.id

    cta = basic_generated_message_cta(archetype=archetype)
    cta.active = True
    db.session.add(cta)
    db.session.commit()

    prospect = basic_prospect(archetype=archetype, client=client)
    prospect2 = basic_prospect(archetype=archetype, client=client)
    prospect3 = basic_prospect(archetype=archetype, client=client)
    email = basic_prospect_email(prospect=prospect)
    prospect3.approved_prospect_email_id = email.id
    db.session.add(prospect3)
    db.session.commit()
    prospect_ids = [prospect.id, prospect2.id, prospect3.id]
    prospect_3_id = prospect3.id

    campaign = create_outbound_campaign(
        prospect_ids=prospect_ids,
        num_prospects=3,
        campaign_type="EMAIL",
        client_archetype_id=archetype_id,
        client_sdr_id=client_sdr_id,
        campaign_start_date="2021-01-01",
        campaign_end_date="2021-01-01",
    )
    campaign_id = campaign.id

    response = app.test_client().post(
        f"campaigns/remove_ungenerated_prospects",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "campaign_id": campaign_id,
            }
        ),
    )
    assert response.status_code == 200
    campaign = OutboundCampaign.query.get(campaign_id)
    assert campaign.prospect_ids == [prospect_3_id]

    # test creating a LI campaign from this email campaign
    response = app.test_client().post(
        "campaigns/create_li_campaign_from_email",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "campaign_id": campaign_id,
            }
        ),
    )
    assert response.status_code == 200
    campaign_id = response.json["campaign_id"]
    assert campaign_id > 0

    campaign = OutboundCampaign.query.get(campaign_id)
    assert campaign.campaign_type.value == "LINKEDIN"
    assert campaign.prospect_ids == [prospect_3_id]
    assert campaign.client_archetype_id == archetype_id
    assert campaign.ctas == [cta.id]
    assert campaign.client_sdr_id == client_sdr_id

    all_campaigns = OutboundCampaign.query.all()
    assert len(all_campaigns) == 2


@use_app_context
def test_get_campaign_analytics():
    client = basic_client()
    archetype = basic_archetype(client)
    client_sdr = basic_client_sdr(client)
    prospect = basic_prospect(archetype=archetype, client=client)
    prospect2 = basic_prospect(archetype=archetype, client=client)
    prospect3 = basic_prospect(archetype=archetype, client=client)
    email = basic_prospect_email(
        prospect=prospect,
        email_status=ProspectEmailStatus.SENT,
        outreach_status=ProspectEmailOutreachStatus.SENT_OUTREACH,
    )
    email2 = basic_prospect_email(
        prospect=prospect2,
        email_status=ProspectEmailStatus.SENT,
        outreach_status=ProspectEmailOutreachStatus.ACCEPTED,
    )
    email3 = basic_prospect_email(
        prospect=prospect3,
        email_status=ProspectEmailStatus.SENT,
        outreach_status=ProspectEmailOutreachStatus.ACTIVE_CONVO,
    )
    prospect_ids = [prospect.id, prospect2.id, prospect3.id]

    campaign = basic_outbound_campaign(
        prospect_ids, GeneratedMessageType.EMAIL, archetype, client_sdr
    )
    campaign_id = campaign.id

    response = app.test_client().get(
        "campaigns/get_campaign_analytics?campaign_id={}".format(campaign_id),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 200
    assert response.json["campaign_id"] == campaign_id
    assert response.json["campaign_type"] == "EMAIL"
    assert response.json["campaign_name"] == campaign.name
    assert response.json["not_sent"] == []
    assert response.json["email_sent"] == [prospect.id]
    assert response.json["email_accepted"] == [prospect2.id]
    assert response.json["email_replied"] == [prospect3.id]
