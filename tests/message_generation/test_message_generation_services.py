import json

import mock
from decorators import use_app_context
from test_utils import (
    basic_archetype,
    basic_client,
    basic_client_sdr,
    basic_generated_message,
    basic_generated_message_cta_with_text,
    basic_gnlp_model,
    basic_prospect,
    basic_prospect_email,
    basic_research_payload,
    basic_research_point,
    basic_outbound_campaign,
    test_app,
)

from app import app, db
from model_import import (
    Client,
    GeneratedMessage,
    GeneratedMessageCTA,
    GeneratedMessageEditRecord,
    GeneratedMessageStatus,
    GeneratedMessageJobQueue,
    GeneratedMessageJobStatus,
    ProspectStatus,
)
from src.client.services import create_client
from src.message_generation.services import (
    GeneratedMessageType,
    Prospect,
    ProspectEmail,
    ProspectEmailStatus,
    ResearchPayload,
    ResearchPoints,
    batch_generate_prospect_emails,
    create_and_start_email_generation_jobs,
    clear_prospect_approved_email,
    create_cta,
    delete_cta,
    delete_message_generation_by_prospect_id,
    generate_linkedin_outreaches,
    generate_prospect_email,
    get_named_entities,
    get_named_entities_for_generated_message,
    mark_prospect_email_approved,
    mark_prospect_email_sent,
    research_and_generate_outreaches_for_prospect,
    run_check_message_has_bad_entities,
    toggle_cta_active,
    wipe_prospect_email_and_generations_and_research,
)
from src.research.models import ResearchPointType, ResearchType


@use_app_context
def test_create_cta():
    client = basic_client()
    archetype = basic_archetype(client)
    # cta = create_cta(text_value="test", archetype_id=archetype.id)
    response = app.test_client().post(
        "message_generation/create_cta",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "archetype_id": archetype.id,
                "text_value": "test",
            }
        ),
    )
    assert response.status_code == 200
    cta_id = response.json["cta_id"]
    cta = GeneratedMessageCTA.query.get(cta_id)
    assert cta.text_value == "test"
    assert cta.archetype_id == archetype.id
    assert cta.active


@use_app_context
def test_delete_cta():
    client = basic_client()
    archetype = basic_archetype(client)
    cta = create_cta(text_value="test", archetype_id=archetype.id)
    all_ctas: list = GeneratedMessageCTA.query.all()
    assert len(all_ctas) == 1

    response = app.test_client().delete(
        "message_generation/delete_cta",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "cta_id": cta.id,
            }
        ),
    )
    assert response.status_code == 200

    all_ctas = GeneratedMessageCTA.query.all()
    assert len(all_ctas) == 0


@use_app_context
def test_toggle_cta():
    client = basic_client()
    archetype = basic_archetype(client)
    cta = create_cta(text_value="test", archetype_id=archetype.id)
    cta_id = cta.id

    assert cta.active == True
    toggle_cta_active(cta_id=cta.id)
    assert cta.active == False
    response = app.test_client().post(
        "message_generation/toggle_cta_active",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "cta_id": cta_id,
            }
        ),
    )

    cta = GeneratedMessageCTA.query.get(cta_id)
    assert response.status_code == 200
    assert cta.active == True


@use_app_context
def test_delete_cta_with_generated_message():
    client = basic_client()
    archetype = basic_archetype(client)
    prospect = basic_prospect(client, archetype)
    gnlp_model = basic_gnlp_model(archetype)
    cta = create_cta(text_value="test", archetype_id=archetype.id)
    all_ctas: list = GeneratedMessageCTA.query.all()
    assert len(all_ctas) == 1

    message: GeneratedMessage = basic_generated_message(
        prospect=prospect, gnlp_model=gnlp_model
    )
    message.message_cta = cta.id
    db.session.add(message)
    db.session.commit()

    success = delete_cta(cta_id=cta.id)
    assert success is False
    all_ctas = GeneratedMessageCTA.query.all()
    assert len(all_ctas) == 1


@use_app_context
@mock.patch(
    "src.message_generation.services.run_adversary",
    return_value=["test mistake", "test fix", 200],
)
@mock.patch(
    "src.message_generation.services.get_few_shot_baseline_prompt",
    return_value=[["completion 1", "completion 2"], 5],
)
@mock.patch(
    "src.message_generation.services.get_adversarial_ai_approval", return_value=True
)
@mock.patch("src.message_generation.services.run_message_rule_engine")
def test_generate_linkedin_outreaches(
    rule_engine_patch, ai_patch, completion_patch, adversary_patch
):
    payload = create_client(
        company="test",
        contact_name="test",
        contact_email="test",
        linkedin_outbound_enabled=True,
        email_outbound_enabled=True,
    )
    client: Client = Client.query.get(payload["client_id"])
    archetype = basic_archetype(client)
    prospect = basic_prospect(client, archetype)
    cta = create_cta(text_value="test", archetype_id=archetype.id)
    gnlp_model = basic_gnlp_model(archetype)
    gnlp_model.id = 5
    db.session.add(gnlp_model)
    db.session.commit()

    research_payload: ResearchPayload = ResearchPayload(
        prospect_id=prospect.id,
        research_type=ResearchType.LINKEDIN_ISCRAPER,
        payload={},
    )
    db.session.add(research_payload)
    db.session.commit()

    for i in ["research 1", "research 2"]:
        rp: ResearchPoints = ResearchPoints(
            research_payload_id=research_payload.id,
            research_point_type=ResearchPointType.YEARS_OF_EXPERIENCE_AT_CURRENT_JOB,
            value=i,
        )
        db.session.add(rp)
        db.session.commit()

    outreaches = generate_linkedin_outreaches(
        prospect_id=prospect.id,
        batch_id="123123123",
        cta_id=cta.id,
    )
    assert len(outreaches) == 8
    assert ai_patch.called is False

    generated_messages: list = GeneratedMessage.query.all()
    assert len(generated_messages) == 8
    for gm in generated_messages:
        assert gm.message_type == GeneratedMessageType.LINKEDIN
        assert gm.message_cta == cta.id
        assert gm.batch_id == "123123123"

        prospect = Prospect.query.get(gm.prospect_id)
        assert prospect.approved_outreach_message_id is not None

    prospect = Prospect.query.get(prospect.id)
    assert prospect.approved_outreach_message_id > 0

    assert rule_engine_patch.called is True


@use_app_context
@mock.patch("src.message_generation.services.run_message_rule_engine")
def test_update_message(rule_engine_mock):
    client = basic_client()
    archetype = basic_archetype(client)
    prospect = basic_prospect(client, archetype)
    gnlp_model = basic_gnlp_model(archetype)
    message: GeneratedMessage = basic_generated_message(
        prospect=prospect, gnlp_model=gnlp_model
    )
    db.session.add(message)
    db.session.commit()

    message: GeneratedMessage = GeneratedMessage.query.first()
    assert message.completion == "this is a test"
    assert not message.human_edited

    response = app.test_client().patch(
        "message_generation/",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "message_id": message.id,
                "update": "this is an update copy",
            }
        ),
    )
    assert response.status_code == 200

    messages: GeneratedMessage = GeneratedMessage.query.all()
    assert len(messages) == 1

    message = messages[0]
    assert message.completion == "this is an update copy"
    assert message.human_edited == True

    edit_records: list = GeneratedMessageEditRecord.query.all()
    assert len(edit_records) == 1


@mock.patch("src.message_generation.controllers.update_message")
def test_batch_update_messages(update_message_mock):
    response = app.test_client().patch(
        "/message_generation/batch_update",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "payload": [
                    {
                        "linkedin_url": "linkedin.com/in/jameszw",
                        "id": 102,
                        "full_name": "Test 2",
                        "title": "VP of Sales Ops & Strategy at Velocity Global",
                        "company": "Velocity Global",
                        "completion": "This is a test 1\n",
                        "message_id": 2,
                    },
                    {
                        "linkedin_url": "linkedin.com/in/jameszw",
                        "id": 2028,
                        "full_name": "Test 1",
                        "title": "VP of Sales Ops & Strategy at Velocity Global",
                        "company": "Velocity Global",
                        "completion": "This is a test 1\n",
                        "message_id": 3,
                    },
                ]
            }
        ),
    )
    assert response.status_code == 200
    assert update_message_mock.call_count == 2


@use_app_context
@mock.patch("src.message_generation.services.run_message_rule_engine")
def test_approve_message(rule_engine_mock):
    client = basic_client()
    archetype = basic_archetype(client)
    prospect = basic_prospect(client, archetype)
    gnlp_model = basic_gnlp_model(archetype)
    message: GeneratedMessage = basic_generated_message(
        prospect=prospect, gnlp_model=gnlp_model
    )
    db.session.add(message)
    db.session.commit()

    message: GeneratedMessage = GeneratedMessage.query.first()
    assert message.message_status == GeneratedMessageStatus.DRAFT

    response = app.test_client().post(
        "message_generation/approve",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "message_id": message.id,
            }
        ),
    )
    assert response.status_code == 200

    message: GeneratedMessage = GeneratedMessage.query.first()
    assert message.message_status == GeneratedMessageStatus.APPROVED


@use_app_context
def test_delete_message_generation_by_prospect_id():
    client = basic_client()
    archetype = basic_archetype(client)
    prospect = basic_prospect(client, archetype)
    gnlp_model = basic_gnlp_model(archetype)
    for i in range(10):
        basic_generated_message(prospect=prospect, gnlp_model=gnlp_model)

    messages: list = GeneratedMessage.query.all()
    assert len(messages) == 10

    delete_message_generation_by_prospect_id(prospect_id=prospect.id)

    messages: list = GeneratedMessage.query.all()
    assert len(messages) == 0


@use_app_context
@mock.patch(
    "src.message_generation.services.get_personalized_first_line_for_client",
    return_value=("completion", 5),
)
@mock.patch("src.message_generation.services.run_message_rule_engine")
def test_generate_prospect_email(
    rule_engine_mock, get_custom_completion_for_client_mock
):
    client = basic_client()
    archetype = basic_archetype(client)
    prospect = basic_prospect(client, archetype)
    prospect_id = prospect.id
    gnlp_model = basic_gnlp_model(archetype)
    gnlp_model.id = 5
    db.session.add(gnlp_model)
    db.session.commit()

    payload = basic_research_payload(prospect=prospect)
    point = basic_research_point(research_payload=payload)

    generate_prospect_email(prospect_id=prospect.id, batch_id="123123")

    assert rule_engine_mock.called is True
    assert get_custom_completion_for_client_mock.called is True

    messages: list = GeneratedMessage.query.all()
    assert len(messages) == 1
    for message in messages:
        assert message.message_type == GeneratedMessageType.EMAIL
        assert message.gnlp_model_id == None
        assert message.completion == "completion"
        assert message.batch_id == "123123"

    prospect_emails: list = ProspectEmail.query.all()
    prospect_email_ids = [pe.id for pe in prospect_emails]
    assert len(prospect_emails) == 1
    for prospect_email in prospect_emails:
        assert prospect_email.prospect_id == prospect_id
        assert prospect_email.personalized_first_line in [x.id for x in messages]
        assert prospect_email.batch_id == "123123"

    prospect: Prospect = Prospect.query.get(prospect_id)
    assert prospect.approved_prospect_email_id != None

    response = app.test_client().post(
        "message_generation/pick_new_approved_email",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "prospect_id": prospect_id,
            }
        ),
    )
    assert response.status_code == 200

    prospect: Prospect = Prospect.query.get(prospect_id)
    assert prospect.approved_prospect_email_id in prospect_email_ids


@use_app_context
@mock.patch(
    "src.message_generation.services.get_personalized_first_line_for_client",
    return_value=("completion", 5),
)
@mock.patch("src.research.linkedin.services.get_research_and_bullet_points_new")
@mock.patch("src.message_generation.services.run_message_rule_engine")
def test_research_and_generate_emails_for_prospect_and_wipe(
    rule_engine_mock, linkedin_research_patch, get_custom_completion_for_client_mock
):
    client = basic_client()
    archetype = basic_archetype(client)
    prospect = basic_prospect(client, archetype)
    prospect_id = prospect.id
    gnlp_model = basic_gnlp_model(archetype)
    gnlp_model.id = 5
    db.session.add(gnlp_model)
    db.session.commit()

    payload = basic_research_payload(prospect=prospect)
    point = basic_research_point(research_payload=payload)

    rp: ResearchPayload = ResearchPayload(
        prospect_id=prospect_id,
        research_type=ResearchType.LINKEDIN_ISCRAPER,
        payload={},
    )
    db.session.add(rp)
    db.session.commit()

    generate_prospect_email(prospect_id=prospect.id, batch_id="123123")
    assert rule_engine_mock.called is True

    assert get_custom_completion_for_client_mock.called is True

    messages: list = GeneratedMessage.query.all()
    messages[0].batch_id
    assert len(messages) == 1
    for message in messages:
        assert message.message_type == GeneratedMessageType.EMAIL
        assert message.gnlp_model_id == None
        assert message.completion == "completion"
        assert message.batch_id == "123123"

    prospect_emails: list = ProspectEmail.query.all()
    assert len(prospect_emails) == 1
    for prospect_email in prospect_emails:
        assert prospect_email.prospect_id == prospect_id
        assert prospect_email.personalized_first_line in [x.id for x in messages]
        assert prospect_email.batch_id == "123123"

    another_client = basic_client()
    another_archetype = basic_archetype(another_client)
    another_prospect = basic_prospect(another_client, another_archetype)
    another_prospect_id = another_prospect.id

    rp: ResearchPayload = ResearchPayload(
        prospect_id=another_prospect_id,
        research_type=ResearchType.LINKEDIN_ISCRAPER,
        payload={},
    )
    db.session.add(rp)
    db.session.commit()

    generate_prospect_email(
        prospect_id=another_prospect_id,
        batch_id="123123",
    )

    messages: list = GeneratedMessage.query.all()
    prospect_emails = ProspectEmail.query.all()
    assert len(messages) == 1
    assert len(prospect_emails) == 1

    prospect: Prospect = Prospect.query.get(prospect_id)
    prospect.status = ProspectStatus.PROSPECTED
    db.session.add(prospect)
    db.session.commit()

    wipe_prospect_email_and_generations_and_research(prospect_id=prospect_id)
    messages: list = GeneratedMessage.query.all()
    assert len(messages) == 0
    prospect_emails = ProspectEmail.query.all()
    assert len(prospect_emails) == 0
    for email in prospect_emails:
        assert email.prospect_id == another_prospect_id


@use_app_context
@mock.patch(
    "src.message_generation.services.get_few_shot_baseline_prompt",
    return_value=("completion", 5),
)
@mock.patch("src.research.linkedin.services.get_research_and_bullet_points_new")
@mock.patch("src.message_generation.services.generate_prospect_email.delay")
def test_batch_generate_emails_for_prospect(
    generate_email_mock, linkedin_research_patch, get_custom_completion_for_client_mock
):
    client = basic_client()
    archetype = basic_archetype(client)
    prospect1 = basic_prospect(client, archetype)
    prospect2 = basic_prospect(client, archetype)
    prospect3 = basic_prospect(client, archetype)

    batch_generate_prospect_emails(
        prospect_ids=[prospect1.id, prospect2.id, prospect3.id],
    )
    assert generate_email_mock.call_count == 3


@use_app_context
@mock.patch(
    "src.message_generation.services.research_and_generate_outreaches_for_prospect.delay"
)
def test_research_and_generate_outreaches_for_prospect_list(
    generate_outreach_mock,
):
    client = basic_client()
    archetype = basic_archetype(client)
    prospect = basic_prospect(client, archetype)

    response = app.test_client().post(
        "message_generation/batch",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "prospect_ids": [prospect.id],
            }
        ),
    )
    assert response.status_code == 200
    assert generate_outreach_mock.call_count == 1


@use_app_context
@mock.patch("src.research.linkedin.services.get_research_and_bullet_points_new")
@mock.patch("src.message_generation.services.generate_linkedin_outreaches")
def test_research_and_generate_outreaches_for_prospect_individual(
    generate_linkedin_outreaches_patch,
    linkedin_research_patch,
):
    client = basic_client()
    archetype = basic_archetype(client)
    prospect = basic_prospect(client, archetype)

    research_and_generate_outreaches_for_prospect(
        prospect_id=prospect.id,
        batch_id="123123",
    )
    assert generate_linkedin_outreaches_patch.call_count == 1
    assert linkedin_research_patch.call_count == 1


@use_app_context
@mock.patch("src.message_generation.services.run_message_rule_engine")
def test_change_prospect_email_status_sent(rule_engine_mock):
    client = basic_client()
    archetype = basic_archetype(client)
    prospect = basic_prospect(client, archetype)
    gnlp_model = basic_gnlp_model(archetype)
    generated_message = basic_generated_message(prospect, gnlp_model)
    generated_message_id = generated_message.id
    prospect_email: ProspectEmail = basic_prospect_email(prospect)
    prospect_email.personalized_first_line = generated_message_id
    db.session.add(prospect_email)
    db.session.commit()

    prospect_email = ProspectEmail.query.get(prospect_email.id)
    assert prospect_email.email_status == ProspectEmailStatus.DRAFT
    assert prospect_email.personalized_first_line == generated_message_id
    assert generated_message.message_status == GeneratedMessageStatus.DRAFT

    prospect: Prospect = Prospect.query.get(prospect.id)
    assert prospect.approved_prospect_email_id == None

    response = app.test_client().post(
        "message_generation/post_batch_mark_prospect_email_approved",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "prospect_ids": [prospect.id],
            }
        ),
    )
    assert response.status_code == 200
    assert rule_engine_mock.call_count == 1

    prospect_email: ProspectEmail = ProspectEmail.query.get(prospect_email.id)
    prospect_email.id
    generated_message: GeneratedMessage = GeneratedMessage.query.get(
        generated_message_id
    )
    assert prospect_email.email_status == ProspectEmailStatus.APPROVED
    assert generated_message.message_status == GeneratedMessageStatus.APPROVED

    prospect: Prospect = Prospect.query.get(prospect.id)
    assert prospect.approved_prospect_email_id == prospect_email.id

    mark_prospect_email_sent(prospect_email.id)
    generated_message: GeneratedMessage = GeneratedMessage.query.get(
        generated_message_id
    )
    generated_message_id = generated_message.id
    assert prospect_email.email_status == ProspectEmailStatus.SENT
    assert generated_message.message_status == GeneratedMessageStatus.SENT


@use_app_context
@mock.patch("src.message_generation.services.run_message_rule_engine")
def test_clearing_approved_emails(run_message_rule_engine_mock):
    client = basic_client()
    archetype = basic_archetype(client)
    prospect = basic_prospect(client, archetype)
    gnlp_model = basic_gnlp_model(archetype)
    generated_message = basic_generated_message(prospect, gnlp_model)
    generated_message_id = generated_message.id
    prospect_email: ProspectEmail = basic_prospect_email(prospect)
    prospect_email.personalized_first_line = generated_message_id
    db.session.add(prospect_email)
    db.session.commit()

    prospect_email = ProspectEmail.query.get(prospect_email.id)
    assert prospect_email.email_status == ProspectEmailStatus.DRAFT
    assert prospect_email.personalized_first_line == generated_message_id
    assert generated_message.message_status == GeneratedMessageStatus.DRAFT

    prospect: Prospect = Prospect.query.get(prospect.id)
    assert prospect.approved_prospect_email_id == None

    response = app.test_client().post(
        "message_generation/post_batch_mark_prospect_email_approved",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "prospect_ids": [prospect.id],
            }
        ),
    )
    assert response.status_code == 200
    assert run_message_rule_engine_mock.call_count == 1

    prospect_email: ProspectEmail = ProspectEmail.query.get(prospect_email.id)
    prospect_email_id = prospect_email.id
    generated_message: GeneratedMessage = GeneratedMessage.query.get(
        generated_message_id
    )
    assert prospect_email.email_status == ProspectEmailStatus.APPROVED
    assert generated_message.message_status == GeneratedMessageStatus.APPROVED

    prospect: Prospect = Prospect.query.get(prospect.id)
    assert prospect.approved_prospect_email_id == prospect_email.id

    clear_prospect_approved_email(prospect.id)
    prospect: Prospect = Prospect.query.get(prospect.id)
    assert prospect.approved_prospect_email_id == None

    generated_message = GeneratedMessage.query.get(generated_message_id)
    assert generated_message.message_status == GeneratedMessageStatus.DRAFT

    prospect_email = ProspectEmail.query.get(prospect_email_id)
    assert prospect_email.email_status == ProspectEmailStatus.DRAFT


def test_prospect_email_status_and_generated_message_status_parity():
    gm_status = [x.value for x in GeneratedMessageStatus]
    pe_status = [x.value for x in ProspectEmailStatus]

    assert len(gm_status) == len(pe_status)
    for status in gm_status:
        assert status in pe_status
    for status in pe_status:
        assert status in gm_status


@use_app_context
@mock.patch("src.message_generation.services.run_message_rule_engine", return_value=[])
@mock.patch(
    "src.research.linkedin.extractors.current_company.wrapped_create_completion",
    return_value="test",
)
def test_batch_approve_message_generations_by_heuristic(
    openai_wrapper_mock, rule_engine_mock
):
    prospect_ids = []

    client = basic_client()
    archetype = basic_archetype(client)
    for i in range(10):
        prospect = basic_prospect(client, archetype)
        prospect_ids.append(prospect.id)
        gnlp_model = basic_gnlp_model(archetype)
        message: GeneratedMessage = basic_generated_message(
            prospect=prospect, gnlp_model=gnlp_model
        )
        db.session.add(message)
        db.session.commit()

    messages: GeneratedMessage = GeneratedMessage.query.all()
    assert len(messages) == 10
    for message in messages:
        assert message.message_status == GeneratedMessageStatus.DRAFT
        prospect: Prospect = Prospect.query.get(message.prospect_id)
        assert prospect.approved_prospect_email_id == None
        assert prospect.status == ProspectStatus.PROSPECTED

    response = app.test_client().post(
        "/message_generation/batch_approve",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "prospect_ids": prospect_ids,
            }
        ),
    )
    assert response.status_code == 200

    messages: GeneratedMessage = GeneratedMessage.query.all()
    assert len(messages) == 10
    for message in messages:
        assert message.message_status == GeneratedMessageStatus.APPROVED
        prospect: Prospect = Prospect.query.get(message.prospect_id)
        assert prospect.status == ProspectStatus.PROSPECTED
        assert prospect.approved_outreach_message_id == message.id

    response = app.test_client().post(
        "message_generation/batch_disapprove",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "prospect_ids": prospect_ids,
            }
        ),
    )
    assert response.status_code == 200

    messages: GeneratedMessage = GeneratedMessage.query.all()
    assert len(messages) == 10
    for message in messages:
        assert message.message_status == GeneratedMessageStatus.DRAFT
        prospect: Prospect = Prospect.query.get(message.prospect_id)
        assert prospect.status == ProspectStatus.PROSPECTED
        assert prospect.approved_outreach_message_id == None


@use_app_context
@mock.patch(
    "src.message_generation.services.get_named_entities",
    return_value=["Marla", "Zuma", "Megan"],
)
def test_get_named_entities_for_generated_message(get_named_entities_patch):
    client = basic_client()
    archetype = basic_archetype(client)
    prospect = basic_prospect(client, archetype)
    gnlp_model = basic_gnlp_model(archetype)
    generated_message = basic_generated_message(prospect, gnlp_model)
    generated_message.completion = "Hey Marla! I read the recommendation Megan left for you (seriously, looks like you're a phenomenal teacher and an excellent marketer). Would love to chat about how Zuma can help turn leads into leases faster."
    db.session.add(generated_message)
    db.session.commit()

    entities = get_named_entities_for_generated_message(generated_message.id)
    assert len(entities) == 3


@use_app_context
@mock.patch(
    "src.message_generation.services.get_named_entities",
    return_value=["Marla", "Megan", "Zuma"],
)
def test_run_check_message_has_bad_entities(get_named_entities_patch):
    client = basic_client()
    archetype = basic_archetype(client)
    prospect = basic_prospect(client, archetype)
    gnlp_model = basic_gnlp_model(archetype)
    generated_message = basic_generated_message(prospect, gnlp_model)
    generated_message_id = generated_message.id
    generated_message.completion = "Hey Marla! I read the recommendation Megan left for you (seriously, looks like you're a phenomenal teacher and an excellent marketer). Would love to chat about how Zuma can help turn leads into leases faster."
    generated_message.prompt = "Oh no."
    db.session.add(generated_message)
    db.session.commit()

    assert generated_message.unknown_named_entities == None

    x, entities = run_check_message_has_bad_entities(generated_message.id)

    assert x == True
    assert len(entities) == 3

    gm: GeneratedMessage = GeneratedMessage.query.get(generated_message_id)
    assert gm.unknown_named_entities == ["Marla", "Megan", "Zuma"]


@use_app_context
@mock.patch(
    "src.message_generation.services.get_named_entities",
    return_value=["Dr. Drozd"],
)
def test_run_check_message_has_bad_entities_with_exceptions(get_named_entities_patch):
    client = basic_client()
    client.company = "Curative"
    client_id = client.id
    client = Client.query.get(client_id)
    archetype = basic_archetype(client)
    prospect = basic_prospect(client, archetype)
    gnlp_model = basic_gnlp_model(archetype)
    generated_message = basic_generated_message(prospect, gnlp_model)
    generated_message_id = generated_message.id
    generated_message.prompt = "Dan Drozd, MD"
    generated_message.completion = "Hi Dr. Drozd!"
    db.session.add(generated_message)
    db.session.commit()

    assert generated_message.unknown_named_entities == None

    x, entities = run_check_message_has_bad_entities(generated_message.id)

    assert x == False
    assert len(entities) == 0

    gm: GeneratedMessage = GeneratedMessage.query.get(generated_message_id)
    assert gm.unknown_named_entities == []

    generated_message.prompt = "dan drozd, MD"
    generated_message.completion = "Hi Dr. Drozd!"
    db.session.add(generated_message)
    db.session.commit()

    x, entities = run_check_message_has_bad_entities(generated_message.id)
    assert x == False
    assert len(entities) == 0


@use_app_context
@mock.patch(
    "src.message_generation.services.get_named_entities",
    return_value=["ad-hoc SQL"],
)
def test_run_check_message_has_bad_entities_with_sanitization(get_named_entities_patch):
    client = basic_client()
    client.company = "SellScale"
    client_id = client.id
    client = Client.query.get(client_id)
    archetype = basic_archetype(client)
    prospect = basic_prospect(client, archetype)
    gnlp_model = basic_gnlp_model(archetype)
    generated_message = basic_generated_message(prospect, gnlp_model)
    generated_message_id = generated_message.id
    generated_message.prompt = "Uses ad-hoc SQL sometimes."
    generated_message.completion = "I see you enjoy using ad-hoc SQL sometimes."
    db.session.add(generated_message)
    db.session.commit()

    assert generated_message.unknown_named_entities == None

    x, entities = run_check_message_has_bad_entities(generated_message.id)

    assert x == False
    assert len(entities) == 0

    gm: GeneratedMessage = GeneratedMessage.query.get(generated_message_id)
    assert gm.unknown_named_entities == []


@use_app_context
@mock.patch(
    "src.message_generation.services.get_named_entities",
    return_value=["Marla", "Megan", "Zuma"],
)
def test_run_check_message_has_bad_entities_with_no_ner_cta(get_named_entities_patch):
    client = basic_client()
    archetype = basic_archetype(client)
    prospect = basic_prospect(client, archetype)
    gnlp_model = basic_gnlp_model(archetype)
    generated_message = basic_generated_message(prospect, gnlp_model)
    generated_message_id = generated_message.id
    generated_message.completion = "Hey Marla! I read the recommendation Megan left for you (seriously, looks like you're a phenomenal teacher and an excellent marketer). Would love to chat about how Zuma can help turn leads into leases faster."
    generated_message.prompt = "Oh no."
    generated_message_cta = basic_generated_message_cta_with_text(
        archetype, "No entities here."
    )
    generated_message.message_cta = generated_message_cta.id
    db.session.add(generated_message)
    db.session.add(generated_message_cta)
    db.session.commit()

    assert generated_message.unknown_named_entities == None

    x, entities = run_check_message_has_bad_entities(generated_message.id)

    assert x == True
    assert len(entities) == 3

    gm: GeneratedMessage = GeneratedMessage.query.get(generated_message_id)
    assert gm.unknown_named_entities == ["Marla", "Megan", "Zuma"]


@use_app_context
@mock.patch(
    "src.message_generation.services.get_named_entities",
    return_value=["Marla", "Megan", "Zuma"],
)
def test_run_check_message_has_bad_entities_with_ner_cta(get_named_entities_patch):
    client = basic_client()
    archetype = basic_archetype(client)
    prospect = basic_prospect(client, archetype)
    gnlp_model = basic_gnlp_model(archetype)
    generated_message = basic_generated_message(prospect, gnlp_model)
    generated_message_id = generated_message.id
    generated_message.completion = "Hey Marla! I read the recommendation Megan left for you (seriously, looks like you're a phenomenal teacher and an excellent marketer). Would love to chat about how Zuma can help turn leads into leases faster."
    generated_message.prompt = "Oh no."
    generated_message_cta = basic_generated_message_cta_with_text(
        archetype, "Marla is here."
    )
    generated_message.message_cta = generated_message_cta.id
    db.session.add(generated_message)
    db.session.add(generated_message_cta)
    db.session.commit()

    assert generated_message.unknown_named_entities == None

    x, entities = run_check_message_has_bad_entities(generated_message.id)

    assert x == True
    assert len(entities) == 2

    gm: GeneratedMessage = GeneratedMessage.query.get(generated_message_id)
    assert gm.unknown_named_entities == ["Megan", "Zuma"]


@use_app_context
@mock.patch(
    "src.message_generation.services.get_named_entities",
    return_value=["CEO"],
)
def test_run_check_message_has_bad_entities_with_ner_cta(get_named_entities_patch):
    client = basic_client()
    archetype = basic_archetype(client)
    prospect = basic_prospect(client, archetype)
    gnlp_model = basic_gnlp_model(archetype)
    generated_message = basic_generated_message(prospect, gnlp_model)
    generated_message_id = generated_message.id
    generated_message.completion = "Hey Jim, love what you're doing as CEO."
    generated_message.prompt = "Chief Executive Officer"
    generated_message_cta = basic_generated_message_cta_with_text(
        archetype, "Marla is here."
    )
    generated_message.message_cta = generated_message_cta.id
    db.session.add(generated_message)
    db.session.add(generated_message_cta)
    db.session.commit()

    assert generated_message.unknown_named_entities == None
    x, entities = run_check_message_has_bad_entities(generated_message.id)
    assert x == False
    assert len(entities) == 0

    gm: GeneratedMessage = GeneratedMessage.query.get(generated_message_id)
    assert gm.unknown_named_entities == []


@use_app_context
@mock.patch(
    "openai.Completion.create",
    return_value={"choices": [{"text": "\n\nSellscale // David"}]},
)
def test_get_named_entities(openai_mock):
    entities = get_named_entities("Sellscale tester - David")
    assert openai_mock.call_count == 1
    assert len(entities) == 2
    assert entities[0] == "Sellscale"
    assert entities[1] == "David"


@use_app_context
@mock.patch("openai.Completion.create", return_value=None)
def test_get_named_entities_fail(openai_mock):
    entities = get_named_entities("")
    assert len(entities) == 0

    entities = get_named_entities("Sellscale tester - David")
    assert openai_mock.call_count == 1
    assert len(entities) == 0


@use_app_context
@mock.patch(
    "openai.Completion.create",
    return_value={"choices": [{"text": "\n\nNONE"}]},
)
def test_get_named_entities_no_return(openai_mock):
    entities = get_named_entities("Sellscale tester - David")
    assert openai_mock.call_count == 1
    assert len(entities) == 0


@use_app_context
@mock.patch("src.message_generation.services.generate_prospect_email.apply_async")
def test_create_and_start_email_generation_jobs(generate_prospect_email_mock):
    client = basic_client()
    archetype = basic_archetype(client)
    client_sdr = basic_client_sdr(client)
    prospect = basic_prospect(client, archetype, client_sdr)
    prospect_2 = basic_prospect(client, archetype, client_sdr)
    prospect_3 = basic_prospect(client, archetype, client_sdr)

    email_campaign = basic_outbound_campaign(
        prospect_ids=[prospect.id, prospect_2.id, prospect_3.id],
        campaign_type=GeneratedMessageType.EMAIL,
        client_archetype=archetype,
        client_sdr=client_sdr
    )
    create_and_start_email_generation_jobs(email_campaign.id)
    gm_jobs: list[GeneratedMessageJobQueue] = GeneratedMessageJobQueue.query.all()
    for gm_job in gm_jobs:
        assert gm_job.status == GeneratedMessageJobStatus.PENDING
    assert len(gm_jobs) == 3
    assert generate_prospect_email_mock.call_count == 3
