from src.email_outbound.models import EmailCustomizedFieldTypes
from model_import import EmailSchema, ProspectEmail
from tests.test_utils.test_utils import (
    basic_client,
    basic_archetype,
    basic_prospect,
    basic_generated_message,
)
from tests.test_utils.decorators import use_app_context
from tests.test_utils.test_utils import test_app
from app import db


@use_app_context
def test_prospect_email():
    client = basic_client()
    archetype = basic_archetype(client)
    prospect = basic_prospect(client, archetype)
    generated_message = basic_generated_message(prospect)

    prospect_email: ProspectEmail = ProspectEmail(
        prospect_id=prospect.id,
        personalized_first_line=generated_message.id,
    )
    db.session.add(prospect_email)
    db.session.commit()
    prospects = ProspectEmail.query.all()
    assert len(prospects) == 1
