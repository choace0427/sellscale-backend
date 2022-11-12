from app import db
from test_utils import test_app, basic_client, basic_archetype
from src.prospecting.services import (
    add_prospect,
    get_linkedin_slug_from_url,
    get_navigator_slug_from_url,
    add_prospects_from_json_payload,
)
from model_import import Prospect, ProspectStatusRecords, Prospect, ProspectUploadBatch
from decorators import use_app_context
import mock
from app import app
import json


@use_app_context
def test_add_prospect():
    client = basic_client()
    archetype = basic_archetype(client)
    add_prospect(
        client_id=client.id,
        archetype_id=archetype.id,
        company="testing",
        company_url="testing.com",
        employee_count="10-100",
        full_name="testing",
        industry="saas",
        batch="123",
        linkedin_url=None,
        linkedin_bio=None,
        title="testing",
        twitter_url="testing",
    )

    prospects = Prospect.query.all()
    assert len(prospects) == 1
    assert prospects[0].client_id == client.id
    assert prospects[0].archetype_id == archetype.id
    assert prospects[0].batch == "123"

    archetype2 = basic_archetype(client)
    add_prospect(client_id=client.id, archetype_id=archetype2.id, batch="456")

    prospects = Prospect.query.all()
    assert len(prospects) == 2
    assert prospects[1].batch == "456"
    assert prospects[1].archetype_id == archetype2.id

    assert archetype.id != archetype2.id

    add_prospect(
        client_id=client.id,
        archetype_id=archetype.id,
        company="testing",
        company_url="testing.com",
        employee_count="10-100",
        full_name="testing",
        industry="saas",
        batch="123",
        linkedin_url=None,
        linkedin_bio=None,
        title="testing",
        twitter_url="testing",
    )
    prospects = Prospect.query.all()
    assert len(prospects) == 2

    add_prospect(
        client_id=client.id,
        archetype_id=archetype.id,
        company="testing",
        company_url="testing.com",
        employee_count="10-100",
        full_name="testing",
        industry="saas",
        batch="123",
        linkedin_url="12381",
        linkedin_bio=None,
        title="testing",
        twitter_url="testing",
    )
    prospects = Prospect.query.all()
    assert len(prospects) == 2

    add_prospect(
        client_id=client.id,
        archetype_id=archetype.id,
        company="testing",
        company_url="testing.com",
        employee_count="10-100",
        full_name="testing sara",  # new name here
        industry="saas",
        batch="123",
        linkedin_url="12381",
        linkedin_bio=None,
        title="testing",
        twitter_url="testing",
    )
    prospects = Prospect.query.all()
    assert len(prospects) == 3


@use_app_context
def test_get_linkedin_slug_from_url():
    urls = [
        "https://www.linkedin.com/in/testingsara",
        "www.linkedin.com/in/testingsara",
        "linkedin.com/in/testingsara",
        "https://www.linkedin.com/in/testingsara/?testing=123",
        "www.linkedin.com/in/testingsara/?testing=123",
        "linkedin.com/in/testingsara/?testing=123",
        "linkedin.com/in/testingsara?testing=123",
    ]

    for url in urls:
        slug = get_linkedin_slug_from_url(url)
        assert slug == "testingsara"


@use_app_context
def test_get_sales_nav_slug_from_url():
    urls = [
        "https://www.linkedin.com/sales/lead/testingsara",
        "www.linkedin.com/sales/lead/testingsara",
        "linkedin.com/sales/lead/testingsara",
    ]

    for url in urls:
        slug = get_navigator_slug_from_url(url)
        assert slug == "testingsara"


@use_app_context
@mock.patch("src.prospecting.services.create_prospect_from_linkedin_link.delay")
def test_add_prospects_from_json_payload(mock_create_from_linkedin):
    payload = [
        {
            "company": "Athelas",
            "company_url": "https://athelas.com/",
            "email": "aakash.adesara@gmail.com",
            "full_name": "Aakash Adesara",
            "linkedin_url": "https://www.linkedin.com/in/aaadesara/",
            "title": "Growth Engineer",
        },
        {
            "company": "Athelas",
            "company_url": "https://athelas.com/",
            "email": "aakash.adesara@gmail.com",  # duplicate shouldn't add
            "full_name": "Aakash Adesara",
            "linkedin_url": "https://www.linkedin.com/in/aaadesara/",
            "title": "Growth Engineer",
        },
        {
            "company": "Athelas",
            "company_url": "https://athelas.com/",
            "email": "aakash.adesara@gmail.com",
            "full_name": "Ishan Sharma",  # different name
            "linkedin_url": "https://www.linkedin.com/in/aaadesara/",
            "title": "Growth Engineer",
        },
        {
            "company": "Athelas",
            "company_url": "https://athelas.com/",
            "email": "aakash.adesara@gmail.com",
            "full_name": "Ishan No Linkedin",  # no linkeidn
            "linkedin_url": "",
            "title": "Growth Engineer",
        },
        {
            "company": "Athelas",
            "company_url": "https://athelas.com/",
            "email": "",  # no  email
            "full_name": "Ishan No Email",
            "linkedin_url": "https://www.linkedin.com/in/aaadesara/",
            "title": "Growth Engineer",
        },
    ]
    client = basic_client()
    archetype = basic_archetype(client)
    archetype_id = archetype.id
    response = app.test_client().post(
        "prospect/add_prospect_from_csv_payload",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "client_id": client.id,
                "archetype_id": archetype.id,
                "csv_payload": payload,
            }
        ),
    )
    assert response.status_code == 200

    batches: list = ProspectUploadBatch.query.all()
    assert len(batches) == 1

    batch_0: ProspectUploadBatch = batches[0]
    assert batch_0.archetype_id == archetype_id
    assert batch_0.num_prospects == 5

    prospects = Prospect.query.all()
    assert len(prospects) == 1
    assert mock_create_from_linkedin.call_count == 4

    assert prospects[0].full_name == "Ishan No Linkedin"

    for i in prospects:
        assert i.company_url == "https://athelas.com/"


@use_app_context
def test_add_prospects_from_json_payload_invalid():
    payload = [
        {
            "company": "Athelas",
            "company_url": "https://athelas.com/",
            "email": "",
            "full_name": "Aakash Adesara",
            "linkedin_url": "",
            "title": "Growth Engineer",
        },
    ]
    client = basic_client()
    archetype = basic_archetype(client)

    success, couldnt_add = add_prospects_from_json_payload(
        client.id, archetype.id, payload
    )
    assert success == False
    assert couldnt_add == ["Aakash Adesara"]

    prospects = Prospect.query.all()
    assert len(prospects) == 0


@use_app_context
@mock.patch(
    "src.prospecting.clay_run.clay_run_prospector.ClayRunProspector.prospect_sync",
    return_value=[
        {
            "Company": "Athelas",
            "Company URL": "https://athelas.com/",
            "Employee Count": "10-100",
            "Full Name": "Aakash Adesara",
            "Industry": "saas",
            "Linkedin": "https://www.linkedin.com/in/aaadesara/",
            "Linkedin Bio": "Growth Engineer",
            "Title": "Growth Engineer",
            "Twitter": "https://twitter.com/aaadesara",
        }
    ],
)
def test_prospecting_with_clay(prospect_sync_patch):
    client = basic_client()
    archetype = basic_archetype(client)

    archetype_id = archetype.id
    location = "San Francisco Bay Area"
    headline = "Software Engineer"
    industry = "Computer Software"
    experience = "1-3 years"

    response = app.test_client().post(
        "prospect/",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "archetype_id": archetype_id,
                "location": location,
                "headline": headline,
                "industry": industry,
                "experience": experience,
            }
        ),
    )
    assert response.status_code == 200
    assert prospect_sync_patch.call_count == 1

    prospects: list = Prospect.query.all()
    assert len(prospects) == 1
    assert prospects[0].full_name == "Aakash Adesara"
    assert prospects[0].company == "Athelas"
    assert prospects[0].company_url == "https://athelas.com/"
    prospect_id = prospects[0].id

    response = app.test_client().patch(
        "prospect/",
        headers={"Content-Type": "application/json"},
        data=json.dumps({"prospect_id": prospect_id, "new_status": "SENT_OUTREACH"}),
    )
    assert response.status_code == 200
    prospect = Prospect.query.get(prospect_id)
    assert prospect.status.value == "SENT_OUTREACH"

    records = ProspectStatusRecords.query.all()
    assert len(records) == 1
