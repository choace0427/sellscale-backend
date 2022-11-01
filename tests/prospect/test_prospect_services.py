from app import db
from test_utils import test_app, basic_client, basic_archetype
from src.prospecting.services import add_prospect
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
