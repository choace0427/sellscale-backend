from app import db
from decorators import use_app_context
from test_utils import (
    test_app,
    basic_client,
    basic_client_sdr,
    basic_archetype,
    basic_prospect,
    basic_prospect_email,
    get_login_token,
)
from model_import import (
    Prospect,
    ProspectStatus,
    ProspectNote,
    ProspectEmail,
    ProspectEmailOutreachStatus,
    ProspectEmailStatusRecords,
    ProspectOverallStatus,
    Client,
    IScraperPayloadCache,
)
from src.prospecting.prospect_status_services import get_valid_next_prospect_statuses


@use_app_context
def test_get_valid_next_prospect_statuses():
    client = basic_client()
    client_sdr = basic_client_sdr(client)
    archetype = basic_archetype(client, client_sdr)
    prospect = basic_prospect(client, archetype, client_sdr)
    prospect_id = prospect.id

    # Test LinkedIn
    valid_next_statuses = get_valid_next_prospect_statuses(prospect.id, "LINKEDIN")
    assert len(valid_next_statuses["valid_next_statuses"]) == 3
    assert valid_next_statuses["valid_next_statuses"][ProspectStatus.QUEUED_FOR_OUTREACH.value] is not None
    assert valid_next_statuses["valid_next_statuses"][ProspectStatus.SENT_OUTREACH.value] is not None
    assert valid_next_statuses["valid_next_statuses"][ProspectStatus.NOT_QUALIFIED.value] is not None
    assert len(valid_next_statuses["all_statuses"]) == 13

    # Test LinkedIn again
    prospect.status = ProspectStatus.SENT_OUTREACH
    valid_next_statuses = get_valid_next_prospect_statuses(prospect.id, "LINKEDIN")
    assert len(valid_next_statuses["valid_next_statuses"]) == 4
    assert valid_next_statuses["valid_next_statuses"][ProspectStatus.ACCEPTED.value] is not None
    assert valid_next_statuses["valid_next_statuses"][ProspectStatus.RESPONDED.value] is not None
    assert valid_next_statuses["valid_next_statuses"][ProspectStatus.ACTIVE_CONVO.value] is not None
    assert valid_next_statuses["valid_next_statuses"][ProspectStatus.NOT_QUALIFIED.value] is not None
    assert len(valid_next_statuses["all_statuses"]) == 13

    # Test Email
    prospect_email = basic_prospect_email(prospect)
    prospect.approved_prospect_email_id = prospect_email.id
    valid_next_statuses = get_valid_next_prospect_statuses(prospect_id, "EMAIL")
    assert len(valid_next_statuses["valid_next_statuses"]) == 2
    assert valid_next_statuses["valid_next_statuses"][ProspectEmailOutreachStatus.SENT_OUTREACH.value] is not None
    assert valid_next_statuses["valid_next_statuses"][ProspectEmailOutreachStatus.NOT_SENT.value] is not None
    assert len(valid_next_statuses["all_statuses"]) == 11

    # Test Email again
    prospect_email.outreach_status = ProspectEmailOutreachStatus.SENT_OUTREACH
    valid_next_statuses = get_valid_next_prospect_statuses(prospect_id, "EMAIL")
    assert len(valid_next_statuses["valid_next_statuses"]) == 1
    assert valid_next_statuses["valid_next_statuses"][ProspectEmailOutreachStatus.EMAIL_OPENED.value] is not None
    assert len(valid_next_statuses["all_statuses"]) == 11
