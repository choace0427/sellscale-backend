from app import db, app
from src.bump_framework.models import BumpLength
from src.email_sequencing.models import EmailSubjectLineTemplate
from src.email_sequencing.services import (
    create_email_sequence_step,
    get_email_sequence_step_for_sdr,
    get_sequence_step_count_for_sdr,
    modify_email_sequence_step,
    deactivate_sequence_step,
    activate_sequence_step,
    get_email_subject_line_template,
    create_email_subject_line_template,
    modify_email_subject_line_template,
    deactivate_email_subject_line_template,
    activate_email_subject_line_template,
)
from tests.test_utils.test_utils import (
    test_app,
    basic_client,
    basic_client_sdr,
    basic_archetype,
    basic_email_sequence_step,
    basic_email_subject_line_template,
)
from tests.test_utils.decorators import use_app_context

from model_import import ProspectOverallStatus, EmailSequenceStep


@use_app_context
def test_get_email_sequence_step_for_sdr():
    client = basic_client()
    client_sdr = basic_client_sdr(client)
    archetype = basic_archetype(client, client_sdr)
    email_sequence_step = basic_email_sequence_step(client_sdr, archetype)

    # Test with no parameters
    result = get_email_sequence_step_for_sdr(client_sdr.id)
    assert len(result) == 1
    assert result[0]["id"] == email_sequence_step.id


@use_app_context
def test_get_sequence_step_count_for_sdr():
    client = basic_client()
    client_sdr = basic_client_sdr(client)
    archetype = basic_archetype(client, client_sdr)
    email_sequence_step = basic_email_sequence_step(client_sdr, archetype)

    result = get_sequence_step_count_for_sdr(client_sdr.id)
    assert result["total"] == 1


@use_app_context
def test_create_email_sequence_step():
    client = basic_client()
    client_sdr = basic_client_sdr(client)
    archetype = basic_archetype(client, client_sdr)

    id = create_email_sequence_step(
        client_sdr_id=client_sdr.id,
        client_archetype_id=archetype.id,
        title="Test Title",
        template="Test Template",
        overall_status=ProspectOverallStatus.BUMPED,
        bumped_count=1,
        active=True,
        substatus="Test Substatus",
        default=False,
        sellscale_default_generated=False,
    )
    assert id is not None
    sequence_step: EmailSequenceStep = db.session.query(EmailSequenceStep).get(id)
    assert sequence_step is not None
    assert sequence_step.title == "Test Title"
    assert sequence_step.template == "Test Template"
    assert sequence_step.overall_status == ProspectOverallStatus.BUMPED
    assert sequence_step.bumped_count == 1
    assert sequence_step.active is True
    assert sequence_step.substatus == "Test Substatus"
    assert sequence_step.default is False
    assert sequence_step.sellscale_default_generated is False


@use_app_context
def test_modify_email_sequence_step():
    client = basic_client()
    client_sdr = basic_client_sdr(client)
    archetype = basic_archetype(client, client_sdr)
    email_sequence_step = basic_email_sequence_step(client_sdr, archetype, default=False)
    email_sequence_step_2 = basic_email_sequence_step(client_sdr, archetype, default=True)

    # Modify the email sequence step
    result = modify_email_sequence_step(
        client_sdr_id=client_sdr.id,
        client_archetype_id=archetype.id,
        sequence_step_id=email_sequence_step.id,
        title="Test Title",
        template="Test Template",
        bumped_count=1,
        default=True,
    )
    assert result is True
    sequence_step: EmailSequenceStep = db.session.query(EmailSequenceStep).get(
        email_sequence_step.id
    )
    assert sequence_step is not None
    assert sequence_step.title == "Test Title"
    assert sequence_step.template == "Test Template"
    assert sequence_step.bumped_count == 1
    assert sequence_step.default is True
    assert email_sequence_step_2.default is False


@use_app_context
def test_deactivate_sequence_step():
    client = basic_client()
    client_sdr = basic_client_sdr(client)
    archetype = basic_archetype(client, client_sdr)
    email_sequence_step = basic_email_sequence_step(client_sdr, archetype)

    # Deactivate the email sequence step
    result = deactivate_sequence_step(
        client_sdr_id=client_sdr.id,
        sequence_step_id=email_sequence_step.id,
    )
    assert result is True
    sequence_step: EmailSequenceStep = db.session.query(EmailSequenceStep).get(
        email_sequence_step.id
    )
    assert sequence_step is not None
    assert sequence_step.active is False


@use_app_context
def test_activate_sequence_step():
    client = basic_client()
    client_sdr = basic_client_sdr(client)
    archetype = basic_archetype(client, client_sdr)
    email_sequence_step = basic_email_sequence_step(client_sdr, archetype, active=False)

    # Activate the email sequence step
    result = activate_sequence_step(
        client_sdr_id=client_sdr.id,
        sequence_step_id=email_sequence_step.id,
    )
    assert result is True
    sequence_step: EmailSequenceStep = db.session.query(EmailSequenceStep).get(
        email_sequence_step.id
    )
    assert sequence_step is not None
    assert sequence_step.active is True


@use_app_context
def test_get_email_subject_line_template():
    client = basic_client()
    client_sdr = basic_client_sdr(client)
    archetype = basic_archetype(client, client_sdr)
    email_subject_line_template = basic_email_subject_line_template(client_sdr, archetype)

    # Test with no parameters
    result = get_email_subject_line_template(client_sdr.id, archetype.id)
    assert len(result) == 1
    assert result[0]["id"] == email_subject_line_template.id


@use_app_context
def test_create_email_subject_line_template():
    client = basic_client()
    client_sdr = basic_client_sdr(client)
    archetype = basic_archetype(client, client_sdr)

    id = create_email_subject_line_template(
        client_sdr_id=client_sdr.id,
        client_archetype_id=archetype.id,
        subject_line="Test Subject Line",
        active=True,
        sellscale_generated=False,
        is_magic_subject_line=False,
    )
    assert id is not None
    email_subject_line_template: EmailSubjectLineTemplate = db.session.query(
        EmailSubjectLineTemplate
    ).get(id)
    assert email_subject_line_template is not None
    assert email_subject_line_template.subject_line == "Test Subject Line"
    assert email_subject_line_template.active is True
    assert email_subject_line_template.sellscale_generated is False


@use_app_context
def test_modify_email_subject_line_template():
    client = basic_client()
    client_sdr = basic_client_sdr(client)
    archetype = basic_archetype(client, client_sdr)
    email_subject_line_template = basic_email_subject_line_template(client_sdr, archetype)

    # Modify the email subject line template
    result = modify_email_subject_line_template(
        client_sdr_id=client_sdr.id,
        client_archetype_id=archetype.id,
        email_subject_line_template_id=email_subject_line_template.id,
        subject_line="Test Subject Line",
    )
    assert result is True
    email_subject_line_template: EmailSubjectLineTemplate = db.session.query(
        EmailSubjectLineTemplate
    ).get(email_subject_line_template.id)
    assert email_subject_line_template is not None
    assert email_subject_line_template.subject_line == "Test Subject Line"


@use_app_context
def test_deactivate_email_subject_line_template():
    client = basic_client()
    client_sdr = basic_client_sdr(client)
    archetype = basic_archetype(client, client_sdr)
    email_subject_line_template = basic_email_subject_line_template(client_sdr, archetype)

    # Deactivate the email subject line template
    result = deactivate_email_subject_line_template(
        client_sdr_id=client_sdr.id,
        email_subject_line_template_id=email_subject_line_template.id,
    )
    assert result is True
    email_subject_line_template: EmailSubjectLineTemplate = db.session.query(
        EmailSubjectLineTemplate
    ).get(email_subject_line_template.id)
    assert email_subject_line_template is not None
    assert email_subject_line_template.active is False


@use_app_context
def test_activate_email_subject_line_template():
    client = basic_client()
    client_sdr = basic_client_sdr(client)
    archetype = basic_archetype(client, client_sdr)
    email_subject_line_template = basic_email_subject_line_template(client_sdr, archetype, active=False)

    # Activate the email subject line template
    result = activate_email_subject_line_template(
        client_sdr_id=client_sdr.id,
        email_subject_line_template_id=email_subject_line_template.id,
    )
    assert result is True
    email_subject_line_template: EmailSubjectLineTemplate = db.session.query(
        EmailSubjectLineTemplate
    ).get(email_subject_line_template.id)
    assert email_subject_line_template is not None
    assert email_subject_line_template.active is True
