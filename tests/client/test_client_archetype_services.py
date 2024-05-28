from app import app, db
from tests.test_utils.decorators import use_app_context
from model_import import (
    Client,
    ClientArchetype,
    ClientSDR,
    ProspectOverallStatus,
)
from src.client.archetype.services_client_archetype import (
    bulk_action_move_prospects_to_archetype,
)
from src.client.services_client_archetype import hard_deactivate_client_archetype
from src.email_outbound.models import ProspectEmail
from src.message_generation.models import GeneratedMessage, GeneratedMessageStatus
from src.prospecting.models import Prospect, ProspectStatus
from tests.test_utils.test_utils import (
    test_app,
    basic_client,
    get_login_token,
    basic_client_sdr,
    basic_prospect,
    basic_prospect_email,
    basic_archetype,
    basic_generated_message_cta_with_text,
    basic_generated_message,
    basic_generated_message_cta,
)
from src.client.services import (
    create_client,
    get_client,
    create_client_archetype,
    get_ctas,
    get_client_archetypes,
    get_client_archetype_performance,
    get_cta_stats,
    get_cta_by_archetype_id,
    get_client_sdr,
    get_sdr_available_outbound_channels,
)

import json
import mock


@use_app_context
def test_hard_deactivate_client_archetype():
    client = basic_client()
    sdr = basic_client_sdr(client)
    sdr_id = sdr.id
    archetype = basic_archetype(client, sdr)
    archetype_id = archetype.id
    prospect = basic_prospect(client, archetype, sdr)
    prospect_id = prospect.id
    prospect_email = basic_prospect_email(prospect)
    prospect_email_id = prospect_email.id
    li_message = basic_generated_message(prospect)
    li_message_id = li_message.id
    subject_line = basic_generated_message(prospect)
    subject_line_id = subject_line.id
    first_line = basic_generated_message(prospect)
    first_line_id = first_line.id
    body = basic_generated_message(prospect)
    body_id = body.id

    prospect.approved_outreach_message_id = li_message.id
    prospect_email.personalized_subject_line = subject_line.id
    prospect_email.personalized_first_line = first_line.id
    prospect_email.personalized_body = body.id
    db.session.commit()

    # This should work because the status is in PROSPECTED
    result = hard_deactivate_client_archetype(sdr_id, archetype_id)
    assert result == True
    archetype: ClientArchetype = ClientArchetype.query.get(archetype_id)
    prospect: Prospect = Prospect.query.get(prospect_id)
    prospect_email: ProspectEmail = ProspectEmail.query.get(prospect_email_id)
    li_message: GeneratedMessage = GeneratedMessage.query.get(li_message_id)
    subject_line: GeneratedMessage = GeneratedMessage.query.get(subject_line_id)
    first_line: GeneratedMessage = GeneratedMessage.query.get(first_line_id)
    body: GeneratedMessage = GeneratedMessage.query.get(body_id)
    assert archetype.active == False
    assert prospect.active == False
    assert prospect.approved_outreach_message_id == None
    assert prospect_email.personalized_subject_line == None
    assert prospect_email.personalized_first_line == None
    assert prospect_email.personalized_body == None
    assert li_message.message_status == GeneratedMessageStatus.BLOCKED
    assert subject_line.message_status == GeneratedMessageStatus.BLOCKED
    assert first_line.message_status == GeneratedMessageStatus.BLOCKED
    assert body.message_status == GeneratedMessageStatus.BLOCKED

    # This wont work because the status is in ACCEPTED
    prospect = basic_prospect(client, archetype, sdr)
    prospect_id = prospect.id
    prospect_email = basic_prospect_email(prospect)
    prospect_email_id = prospect_email.id
    li_message = basic_generated_message(prospect)
    li_message_id = li_message.id
    subject_line = basic_generated_message(prospect)
    subject_line_id = subject_line.id
    first_line = basic_generated_message(prospect)
    first_line_id = first_line.id
    body = basic_generated_message(prospect)
    body_id = body.id

    prospect.approved_outreach_message_id = li_message.id
    prospect.status = ProspectStatus.ACCEPTED
    prospect_email.personalized_subject_line = subject_line.id
    prospect_email.personalized_first_line = first_line.id
    prospect_email.personalized_body = body.id
    li_message.message_status = GeneratedMessageStatus.SENT
    subject_line.message_status = GeneratedMessageStatus.SENT
    first_line.message_status = GeneratedMessageStatus.SENT
    body.message_status = GeneratedMessageStatus.SENT
    db.session.commit()

    result = hard_deactivate_client_archetype(sdr_id, archetype_id)
    assert result == True
    archetype: ClientArchetype = ClientArchetype.query.get(archetype_id)
    prospect: Prospect = Prospect.query.get(prospect_id)
    li_message: GeneratedMessage = GeneratedMessage.query.get(li_message_id)
    subject_line: GeneratedMessage = GeneratedMessage.query.get(subject_line_id)
    first_line: GeneratedMessage = GeneratedMessage.query.get(first_line_id)
    body: GeneratedMessage = GeneratedMessage.query.get(body_id)
    assert archetype.active == False
    assert prospect.active == False
    assert prospect.approved_outreach_message_id == li_message.id
    assert prospect_email.personalized_subject_line == subject_line.id
    assert prospect_email.personalized_first_line == first_line.id
    assert prospect_email.personalized_body == body.id
    assert li_message.message_status == GeneratedMessageStatus.SENT
    assert subject_line.message_status == GeneratedMessageStatus.SENT
    assert first_line.message_status == GeneratedMessageStatus.SENT
    assert body.message_status == GeneratedMessageStatus.SENT


@use_app_context
@mock.patch(
    "src.client.services_client_archetype.mark_queued_and_classify.apply_async",
    return_value=True,
)
def test_bulk_action_move_prospects_to_archetype(mock_mark_queued_and_classify):
    client = basic_client()
    sdr = basic_client_sdr(client)
    archetype = basic_archetype(client, sdr)
    archetype_id = archetype.id
    archetype_2 = basic_archetype(client, sdr)
    archetype_2_id = archetype_2.id
    prospect = basic_prospect(client, archetype, sdr)
    prospect_id = prospect.id
    prospect_2 = basic_prospect(client, archetype, sdr)
    prospect_2_id = prospect_2.id

    # Move both prospects to archetype_2
    assert prospect.archetype_id == archetype_id
    assert prospect_2.archetype_id == archetype_id
    result = bulk_action_move_prospects_to_archetype(
        sdr.id, archetype_2_id, [prospect_id, prospect_2_id]
    )
    assert result == True
    prospect: Prospect = Prospect.query.get(prospect_id)
    prospect_2: Prospect = Prospect.query.get(prospect_2_id)
    assert prospect.archetype_id == archetype_2_id
    assert prospect_2.archetype_id == archetype_2_id
    assert mock_mark_queued_and_classify.call_count == 2

    # Move prospect to archetype
    result = bulk_action_move_prospects_to_archetype(
        sdr.id, archetype_id, [prospect_id]
    )
    assert result == True
    prospect: Prospect = Prospect.query.get(prospect_id)
    prospect_2: Prospect = Prospect.query.get(prospect_2_id)
    assert prospect.archetype_id == archetype_id
    assert prospect_2.archetype_id == archetype_2_id
    assert mock_mark_queued_and_classify.call_count == 3
