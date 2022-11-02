from app import db
from test_utils import test_app, basic_client, basic_archetype
from src.prospecting.services import (
    add_prospect,
    get_linkedin_slug_from_url,
    get_navigator_slug_from_url,
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
    assert len(prospects) == 1
    assert prospects[0].batch == "456"
    assert prospects[0].archetype_id == archetype2.id

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
    assert len(prospects) == 1

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
