import mock
from app import app, db

from model_import import Client, PersonaSplitRequestTask, PersonaSplitRequest
from decorators import use_app_context
from src.email_outbound.models import ProspectEmail
from src.message_generation.models import GeneratedMessage
from src.personas.services import get_unassignable_prospects_using_icp_heuristic, unassign_prospects
from src.prospecting.models import Prospect
from test_utils import (
    test_app,
    basic_client,
    basic_client_sdr,
    basic_archetype,
    basic_prospect,
    basic_prospect_email,
    basic_generated_message,
)


@use_app_context
def test_get_unassignable_prospects_using_icp_heuristic():
    client = basic_client()
    sdr = basic_client_sdr(client)
    sdr_id = sdr.id
    archetype = basic_archetype(client, sdr)
    archetype_id = archetype.id
    prospect = basic_prospect(client, archetype, sdr)
    prospect_id = prospect.id
    prospect.icp_fit_score = 0
    prospect.icp_fit_reason = "test"
    db.session.commit()
    prospect_2 = basic_prospect(client, archetype, sdr)
    prospect_2_id = prospect_2.id
    prospect_2.icp_fit_score = 3
    prospect_2.icp_fit_reason = "test"
    db.session.commit()

    ids, dicts = get_unassignable_prospects_using_icp_heuristic(client_sdr_id=sdr_id, client_archetype_id=archetype_id)
    assert len(ids) == 1
    assert prospect_id in ids
    assert prospect_2_id not in ids
    assert len(dicts) == 1
    assert dicts[0]["id"] == prospect_id
    assert dicts[0]["icp_fit_score"] == 0
    assert dicts[0]["icp_fit_reason"] == "test"


@use_app_context
def test_unassign_prospects():
    client = basic_client()
    sdr = basic_client_sdr(client)
    sdr_id = sdr.id
    archetype = basic_archetype(client, sdr)
    archetype_id = archetype.id
    unassigned_archetype = basic_archetype(client, sdr)
    unassigned_archetype.is_unassigned_contact_archetype = True
    db.session.commit()

    # Setup first prospect, which has both LI and Email messages
    prospect = basic_prospect(client, archetype, sdr)
    prospect_id = prospect.id
    prospect.icp_fit_score = 0
    prospect.icp_fit_reason = "test"
    prospect_email = basic_prospect_email(prospect)
    gm = basic_generated_message(prospect)
    gm_id = gm.id
    prospect.approved_outreach_message_id = gm_id
    gm2 = basic_generated_message(prospect)
    gm2_id = gm2.id
    prospect_email.personalized_first_line = gm2_id
    db.session.commit()

    # Setup second prospect, which has neither (not tested since high ICP)
    prospect_2 = basic_prospect(client, archetype, sdr)
    prospect_2_id = prospect_2.id
    prospect_2.icp_fit_score = 3
    prospect_2.icp_fit_reason = "test"
    db.session.commit()

    prospect_1: Prospect = Prospect.query.get(prospect_id)
    assert prospect_1.approved_outreach_message_id == gm_id
    assert prospect_1.archetype_id == archetype_id
    prospect_2: Prospect = Prospect.query.get(prospect_2_id)
    assert prospect_2.archetype_id == archetype_id
    success = unassign_prospects(
        client_sdr_id=sdr_id,
        client_archetype_id=archetype_id,
        use_icp_heuristic=True,
    )
    assert success
    assert GeneratedMessage.query.get(gm_id) is None
    assert GeneratedMessage.query.get(gm2_id) is None
    prospect_1: Prospect = Prospect.query.get(prospect_id)
    assert prospect_1.approved_outreach_message_id is None
    assert prospect_1.archetype_id == unassigned_archetype.id
    prospect_2: Prospect = Prospect.query.get(prospect_2_id)
    assert prospect_2.archetype_id == archetype_id
