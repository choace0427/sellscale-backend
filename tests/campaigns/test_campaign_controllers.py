from app import db, app
from test_utils import test_app
import pytest
from decorators import use_app_context
import datetime
import json

from test_utils import (
    basic_client,
    basic_archetype,
    basic_client_sdr,
    basic_email_schema,
    basic_prospect,
)
from src.campaigns.services import create_outbound_campaign
from model_import import OutboundCampaign
import mock


@use_app_context
@mock.patch(
    "src.message_generation.services.research_and_generate_outreaches_for_prospect.delay"
)
def test_create_generate_message_campaign(message_gen_call_patch):
    client = basic_client()
    archetype = basic_archetype(client)
    client_sdr = basic_client_sdr(client)

    prospect1 = basic_prospect(client, archetype)
    prospect2 = basic_prospect(client, archetype)
    prospect3 = basic_prospect(client, archetype)
    prospect_ids = [prospect1.id, prospect2.id, prospect3.id]

    response = app.test_client().post(
        "campaigns/",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "prospect_ids": prospect_ids,
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
        "campaigns/generate",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "campaign_id": campaign_id,
            }
        ),
    )
    assert response.status_code == 200
    assert message_gen_call_patch.call_count == 3


@use_app_context
@mock.patch(
    "src.message_generation.services.research_and_generate_outreaches_for_prospect.delay"
)
@mock.patch("src.campaigns.services.batch_generate_prospect_emails")
def test_create_generate_email_campaign(gen_email_patch, message_gen_call_patch):
    client = basic_client()
    archetype = basic_archetype(client)
    client_sdr = basic_client_sdr(client)
    email_schema = basic_email_schema(archetype=archetype)
    email_schema_id = email_schema.id

    response = app.test_client().post(
        "campaigns/",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "prospect_ids": [1, 2, 3, 4],
                "campaign_type": "EMAIL",
                "email_schema_id": email_schema_id,
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
    assert campaign.email_schema_id == email_schema_id
    assert campaign.status.value == "PENDING"

    response = app.test_client().post(
        "campaigns/generate",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "campaign_id": campaign_id,
            }
        ),
    )
    assert response.status_code == 200
    assert message_gen_call_patch.call_count == 0
    assert gen_email_patch.call_count == 1


@use_app_context
def test_change_campaign_status():
    client = basic_client()
    archetype = basic_archetype(client)
    client_sdr = basic_client_sdr(client)

    response = app.test_client().post(
        "campaigns/",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "prospect_ids": [1, 2, 3, 4],
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


@use_app_context
def test_change_campaign_status_to_edit_complete():
    client = basic_client()
    archetype = basic_archetype(client)
    client_sdr = basic_client_sdr(client)

    response = app.test_client().post(
        "campaigns/",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "prospect_ids": [1, 2, 3, 4],
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


@use_app_context
def test_merge_multiple_linkedin_campaigns_succeed():
    client = basic_client()
    archetype = basic_archetype(client)
    archetype_id = archetype.id
    client_sdr = basic_client_sdr(client)
    client_sdr_id = client_sdr.id

    campaign1 = create_outbound_campaign(
        prospect_ids=[1, 2],
        campaign_type="LINKEDIN",
        client_archetype_id=archetype_id,
        client_sdr_id=client_sdr_id,
        campaign_start_date="2021-01-01",
        campaign_end_date="2021-01-01",
        ctas=[1, 2, 3],
    )
    campaign2 = create_outbound_campaign(
        prospect_ids=[2, 3, 4],
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


@use_app_context
def test_merge_multiple_email_campaigns_succeed():
    client = basic_client()
    archetype = basic_archetype(client)
    archetype_id = archetype.id
    client_sdr = basic_client_sdr(client)
    client_sdr_id = client_sdr.id
    email_schema = basic_email_schema(archetype=archetype)
    email_schema_id = email_schema.id

    campaign1 = create_outbound_campaign(
        prospect_ids=[1, 2],
        campaign_type="EMAIL",
        client_archetype_id=archetype_id,
        client_sdr_id=client_sdr_id,
        campaign_start_date="2021-01-01",
        campaign_end_date="2021-01-01",
        email_schema_id=email_schema_id,
    )
    campaign1_id = campaign1.id
    campaign2 = create_outbound_campaign(
        prospect_ids=[2, 3, 4],
        campaign_type="EMAIL",
        client_archetype_id=archetype_id,
        client_sdr_id=client_sdr_id,
        campaign_start_date="2021-01-02",
        campaign_end_date="2021-01-05",
        email_schema_id=email_schema_id,
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
    assert campaign.email_schema_id == email_schema_id

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
    email_schema = basic_email_schema(archetype=archetype)
    email_schema_id = email_schema.id

    campaign1 = create_outbound_campaign(
        prospect_ids=[1, 2],
        campaign_type="EMAIL",
        client_archetype_id=archetype_id,
        client_sdr_id=client_sdr_id,
        campaign_start_date="2021-01-01",
        campaign_end_date="2021-01-01",
        email_schema_id=email_schema_id,
    )
    campaign1_id = campaign1.id
    campaign2 = create_outbound_campaign(
        prospect_ids=[2, 3, 4],
        campaign_type="LINKEDIN",
        client_archetype_id=archetype_id,
        client_sdr_id=client_sdr_id,
        campaign_start_date="2021-01-02",
        campaign_end_date="2021-01-05",
        email_schema_id=email_schema_id,
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
    email_schema = basic_email_schema(archetype=archetype)
    email_schema_id = email_schema.id

    archetype_2 = basic_archetype(client)
    archetype_2_id = archetype_2.id

    campaign1 = create_outbound_campaign(
        prospect_ids=[1, 2],
        campaign_type="EMAIL",
        client_archetype_id=archetype_id,
        client_sdr_id=client_sdr_id,
        campaign_start_date="2021-01-01",
        campaign_end_date="2021-01-01",
        email_schema_id=email_schema_id,
    )
    campaign1_id = campaign1.id
    campaign2 = create_outbound_campaign(
        prospect_ids=[2, 3, 4],
        campaign_type="EMAIL",
        client_archetype_id=archetype_2_id,
        client_sdr_id=client_sdr_id,
        campaign_start_date="2021-01-02",
        campaign_end_date="2021-01-05",
        email_schema_id=email_schema_id,
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
