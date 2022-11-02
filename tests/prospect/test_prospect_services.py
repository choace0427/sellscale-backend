from app import db
from test_utils import test_app, basic_client, basic_archetype
from src.prospecting.services import (
    add_prospect,
    get_linkedin_slug_from_url,
    get_navigator_slug_from_url,
    add_prospects_from_json_payload,
)
from model_import import Prospect
from decorators import use_app_context


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
def test_add_prospects_from_json_payload():
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

    success, couldnt_add = add_prospects_from_json_payload(
        client.id, archetype.id, payload
    )
    assert success == True
    assert couldnt_add == []

    prospects = Prospect.query.all()
    assert len(prospects) == 4

    assert prospects[0].full_name == "Aakash Adesara"
    assert prospects[1].full_name == "Ishan Sharma"
    assert prospects[2].full_name == "Ishan No Linkedin"
    assert prospects[3].full_name == "Ishan No Email"


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
