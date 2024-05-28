import json

import mock
from src.research.models import ResearchType
from tests.test_utils.decorators import use_app_context
from tests.test_utils.test_utils import (
    basic_archetype,
    basic_client,
    basic_client_sdr,
    basic_generated_message,
    basic_generated_message_cta,
    basic_generated_message_cta_with_text,
    basic_prospect,
    basic_prospect_email,
    basic_research_payload,
    basic_research_point,
    basic_outbound_campaign,
    basic_generated_message_job_queue,
    basic_stack_ranked_message_generation_config,
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
    create_and_start_email_generation_jobs,
    get_messages_queued_for_outreach,
    clear_prospect_approved_email,
    create_cta,
    delete_cta,
    delete_message_generation_by_prospect_id,
    generate_linkedin_outreaches,
    generate_prospect_email,
    mark_prospect_email_approved,
    mark_prospect_email_sent,
    research_and_generate_outreaches_for_prospect,
    toggle_cta_active,
    wipe_prospect_email_and_generations_and_research,
    get_generation_statuses,
    wipe_message_generation_job_queue,
    manually_mark_ai_approve,
    update_message,
)
from src.message_generation.services_few_shot_generations import (
    can_generate_with_patterns,
)


@use_app_context
def test_get_messages_queued_for_outreach():
    client = basic_client()
    sdr = basic_client_sdr(client)
    sdr_id = sdr.id
    archetype = basic_archetype(client, sdr)
    prospect = basic_prospect(client, archetype, sdr)
    prospect.company = "Test Company"
    prospect.status = "QUEUED_FOR_OUTREACH"
    prospect_id = prospect.id
    cta = basic_generated_message_cta(archetype)
    outbound_campaign = basic_outbound_campaign(
        [prospect_id], "LINKEDIN", archetype, sdr
    )
    generated_message = basic_generated_message(prospect, cta, outbound_campaign)
    generated_message_id = generated_message.id
    generated_message.message_status = "QUEUED_FOR_OUTREACH"
    prospect.approved_outreach_message_id = generated_message.id
    prospect.linkedin_url = "https://www.linkedin.com/in/davidmwei"

    messages, total_count = get_messages_queued_for_outreach(sdr_id)
    assert len(messages) == 1
    assert total_count == 1
    assert messages == [
        {
            "prospect_id": prospect_id,
            "full_name": "Testing Testasara",
            "title": "Testing Director",
            "company": "Test Company",
            "img_url": None,
            "message_id": generated_message_id,
            "completion": "this is a test",
            "icp_fit_score": prospect.icp_fit_score,
            "icp_fit_reason": prospect.icp_fit_reason,
            "archetype": archetype.archetype,
        }
    ]


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
    cta = create_cta(text_value="test", archetype_id=archetype.id, expiration_date=None)
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
    cta = create_cta(text_value="test", archetype_id=archetype.id, expiration_date=None)
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
    cta = create_cta(text_value="test", archetype_id=archetype.id, expiration_date=None)
    all_ctas: list = GeneratedMessageCTA.query.all()
    assert len(all_ctas) == 1

    message: GeneratedMessage = basic_generated_message(prospect=prospect)
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
    sdr = basic_client_sdr(client)
    prospect = basic_prospect(client, archetype, sdr)
    prospect_id = prospect.id
    campaign = basic_outbound_campaign(
        [prospect_id], GeneratedMessageType.LINKEDIN, archetype, sdr
    )
    cta = create_cta(text_value="test", archetype_id=archetype.id, expiration_date=None)

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
            research_point_type="YEARS_OF_EXPERIENCE_AT_CURRENT_JOB",
            value=i,
        )
        db.session.add(rp)
        db.session.commit()

    outreaches = generate_linkedin_outreaches(
        prospect_id=prospect.id,
        outbound_campaign_id=campaign.id,
        cta_id=cta.id,
    )
    assert len(outreaches) == 8
    assert ai_patch.called is False

    generated_messages: list[GeneratedMessage] = GeneratedMessage.query.all()
    assert len(generated_messages) == 8
    for gm in generated_messages:
        assert gm.message_type == GeneratedMessageType.LINKEDIN
        assert gm.message_cta == cta.id
        assert gm.outbound_campaign_id == campaign.id

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
    message: GeneratedMessage = basic_generated_message(prospect=prospect)
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


@mock.patch(
    "src.message_generation.controllers.update_linkedin_message_for_prospect_id"
)
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
                        "prospect_id": 2,
                    },
                    {
                        "linkedin_url": "linkedin.com/in/jameszw",
                        "id": 2028,
                        "full_name": "Test 1",
                        "title": "VP of Sales Ops & Strategy at Velocity Global",
                        "company": "Velocity Global",
                        "completion": "This is a test 1\n",
                        "prospect_id": 3,
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

    message: GeneratedMessage = basic_generated_message(prospect=prospect)
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

    for i in range(10):
        basic_generated_message(prospect=prospect)

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
@mock.patch("src.ml.services.wrapped_chat_gpt_completion", return_value="completion")
def test_generate_prospect_email(
    wrapped_chat_gpt_completion_mock,
    rule_engine_mock,
    get_custom_completion_for_client_mock,
):
    client = basic_client()
    client_sdr = basic_client_sdr(client)
    archetype = basic_archetype(client)
    prospect = basic_prospect(client, archetype, client_sdr)
    prospect_id = prospect.id

    campaign = basic_outbound_campaign(
        [prospect_id], GeneratedMessageType.EMAIL, archetype, client_sdr
    )
    gen_message_job = basic_generated_message_job_queue(
        prospect, campaign, GeneratedMessageJobStatus.PENDING
    )

    db.session.commit()

    payload = basic_research_payload(prospect=prospect)
    point = basic_research_point(research_payload=payload)

    generate_prospect_email(prospect.id, campaign.id, gen_message_job.id)

    assert rule_engine_mock.called is True

    messages: list[GeneratedMessage] = GeneratedMessage.query.all()
    assert len(messages) == 2
    for message in messages:
        assert message.message_type == GeneratedMessageType.EMAIL
        # assert message.completion == "completion"

    prospect_emails: list[ProspectEmail] = ProspectEmail.query.all()
    prospect_email_ids = [pe.id for pe in prospect_emails]
    assert len(prospect_emails) == 1
    for prospect_email in prospect_emails:
        assert prospect_email.prospect_id == prospect_id
        assert prospect_email.personalized_subject_line in [x.id for x in messages]
        assert prospect_email.personalized_body in [x.id for x in messages]

    prospect: Prospect = Prospect.query.get(prospect_id)
    assert prospect.approved_prospect_email_id != None

    # response = app.test_client().post(
    #     "message_generation/pick_new_approved_email",
    #     headers={"Content-Type": "application/json"},
    #     data=json.dumps(
    #         {
    #             "prospect_id": prospect_id,
    #         }
    #     ),
    # )
    # assert response.status_code == 200

    prospect: Prospect = Prospect.query.get(prospect_id)


@use_app_context
@mock.patch(
    "src.message_generation.services.get_personalized_first_line_for_client",
    return_value=("completion", 5),
)
@mock.patch("src.research.linkedin.services.get_research_and_bullet_points_new")
@mock.patch("src.message_generation.services.run_message_rule_engine")
@mock.patch("src.ml.services.wrapped_chat_gpt_completion", return_value="completion")
def test_research_and_generate_emails_for_prospect_and_wipe(
    wrapped_chat_gpt_completion_mock,
    rule_engine_mock,
    linkedin_research_patch,
    get_custom_completion_for_client_mock,
):
    client = basic_client()
    archetype = basic_archetype(client)
    sdr = basic_client_sdr(client)
    prospect = basic_prospect(client, archetype, sdr)
    prospect_id = prospect.id

    db.session.commit()
    payload = basic_research_payload(prospect=prospect)
    point = basic_research_point(research_payload=payload)
    campaign = basic_outbound_campaign(
        [prospect_id], GeneratedMessageType.EMAIL, archetype, sdr
    )
    message_gen_job = basic_generated_message_job_queue(
        prospect, campaign, GeneratedMessageJobStatus.IN_PROGRESS
    )

    rp: ResearchPayload = ResearchPayload(
        prospect_id=prospect_id,
        research_type=ResearchType.LINKEDIN_ISCRAPER,
        payload={},
    )
    db.session.add(rp)
    db.session.commit()

    generate_prospect_email(
        prospect_id=prospect.id, campaign_id=campaign.id, gm_job_id=message_gen_job.id
    )
    assert rule_engine_mock.called is True

    messages: list[GeneratedMessage] = GeneratedMessage.query.all()
    assert len(messages) == 2
    for message in messages:
        assert message.message_type == GeneratedMessageType.EMAIL
        # assert message.completion == "completion"

    prospect_emails: list[ProspectEmail] = ProspectEmail.query.all()
    assert len(prospect_emails) == 1
    for prospect_email in prospect_emails:
        assert prospect_email.prospect_id == prospect_id
        print(prospect_email.to_dict())
        assert prospect_email.personalized_subject_line in [x.id for x in messages]
        assert prospect_email.personalized_body in [x.id for x in messages]

    another_client = basic_client()
    another_sdr = basic_client_sdr(another_client)
    another_archetype = basic_archetype(another_client)
    another_prospect = basic_prospect(another_client, another_archetype, another_sdr)
    another_prospect_id = another_prospect.id
    another_campaign = basic_outbound_campaign(
        [another_prospect_id],
        GeneratedMessageType.EMAIL,
        another_archetype,
        another_sdr,
    )
    another_message_gen_job = basic_generated_message_job_queue(
        another_prospect, another_campaign, GeneratedMessageJobStatus.IN_PROGRESS
    )

    rp: ResearchPayload = ResearchPayload(
        prospect_id=another_prospect_id,
        research_type=ResearchType.LINKEDIN_ISCRAPER,
        payload={},
    )
    db.session.add(rp)
    db.session.commit()

    generate_prospect_email(
        prospect_id=another_prospect_id,
        campaign_id=another_campaign.id,
        gm_job_id=another_message_gen_job.id,
    )
    messages: list = GeneratedMessage.query.all()
    prospect_emails = ProspectEmail.query.all()
    assert len(messages) == 2
    assert len(prospect_emails) == 1

    prospect: Prospect = Prospect.query.get(prospect_id)
    prospect.status = ProspectStatus.PROSPECTED
    db.session.add(prospect)
    db.session.commit()

    # wipe_prospect_email_and_generations_and_research(prospect_id=prospect_id)
    # messages: list = GeneratedMessage.query.all()
    # assert len(messages) == 0
    # prospect_emails = ProspectEmail.query.all()
    # assert len(prospect_emails) == 0
    # for email in prospect_emails:
    #     assert email.prospect_id == another_prospect_id


@use_app_context
@mock.patch("src.research.linkedin.services.get_research_and_bullet_points_new")
@mock.patch("src.message_generation.services.generate_linkedin_outreaches")
def test_research_and_generate_outreaches_for_prospect_individual(
    generate_linkedin_outreaches_patch,
    linkedin_research_patch,
):
    client = basic_client()
    client_sdr = basic_client_sdr(client)
    archetype = basic_archetype(client)
    prospect = basic_prospect(client, archetype, client_sdr)
    campaign = basic_outbound_campaign(
        [prospect.id], GeneratedMessageType.LINKEDIN, archetype, client_sdr
    )

    research_and_generate_outreaches_for_prospect(
        prospect_id=prospect.id, outbound_campaign_id=campaign.id
    )
    # assert generate_linkedin_outreaches_patch.call_count == 1
    assert linkedin_research_patch.call_count == 1


@use_app_context
@mock.patch("src.message_generation.services.run_message_rule_engine")
def test_change_prospect_email_status_sent(rule_engine_mock):
    client = basic_client()
    archetype = basic_archetype(client)
    prospect = basic_prospect(client, archetype)

    generated_message = basic_generated_message(prospect)
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

    prospect_email: ProspectEmail = ProspectEmail.query.get(prospect_email.id)
    prospect_email.id
    generated_message: GeneratedMessage = GeneratedMessage.query.get(
        generated_message_id
    )
    assert prospect_email.email_status == ProspectEmailStatus.DRAFT
    assert generated_message.message_status == GeneratedMessageStatus.DRAFT

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

    generated_message = basic_generated_message(prospect)
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

    prospect_email: ProspectEmail = ProspectEmail.query.get(prospect_email.id)
    prospect_email_id = prospect_email.id
    generated_message: GeneratedMessage = GeneratedMessage.query.get(
        generated_message_id
    )
    assert prospect_email.email_status == ProspectEmailStatus.DRAFT
    assert generated_message.message_status == GeneratedMessageStatus.DRAFT

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

    assert len(gm_status) == 6
    assert len(pe_status) == 4


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

        message: GeneratedMessage = basic_generated_message(prospect=prospect)
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
    generated_message = basic_generated_message(prospect)
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

    generated_message = basic_generated_message(prospect)
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

    generated_message = basic_generated_message(prospect)
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

    generated_message = basic_generated_message(prospect)
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

    generated_message = basic_generated_message(prospect)
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

    generated_message = basic_generated_message(prospect)
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

    generated_message = basic_generated_message(prospect)
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
    # assert openai_mock.call_count == 1
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
        client_sdr=client_sdr,
    )
    create_and_start_email_generation_jobs(email_campaign.id)
    gm_jobs: list[GeneratedMessageJobQueue] = GeneratedMessageJobQueue.query.all()
    for gm_job in gm_jobs:
        assert gm_job.status == GeneratedMessageJobStatus.PENDING
    assert len(gm_jobs) == 3
    assert generate_prospect_email_mock.call_count == 3


@use_app_context
def test_get_generation_statuses():
    client = basic_client()
    archetype = basic_archetype(client)
    client_sdr = basic_client_sdr(client)
    prospect = basic_prospect(client, archetype, client_sdr)
    prospect_2 = basic_prospect(client, archetype, client_sdr)
    prospect_3 = basic_prospect(client, archetype, client_sdr)
    campaign = basic_outbound_campaign(
        prospect_ids=[prospect.id, prospect_2.id, prospect_3.id],
        campaign_type=GeneratedMessageType.LINKEDIN,
        client_archetype=archetype,
        client_sdr=client_sdr,
    )
    job1 = basic_generated_message_job_queue(
        prospect, campaign, GeneratedMessageJobStatus.PENDING
    )
    job2 = basic_generated_message_job_queue(
        prospect_2, campaign, GeneratedMessageJobStatus.COMPLETED
    )
    job3 = basic_generated_message_job_queue(
        prospect_3, campaign, GeneratedMessageJobStatus.FAILED
    )

    statuses = get_generation_statuses(campaign.id)
    assert statuses["total_job_count"] == 3
    assert statuses["statuses_count"].get(GeneratedMessageJobStatus.PENDING.value) == 1
    assert (
        statuses["statuses_count"].get(GeneratedMessageJobStatus.COMPLETED.value) == 1
    )
    assert statuses["statuses_count"].get(GeneratedMessageJobStatus.FAILED.value) == 1
    assert (
        statuses["statuses_count"].get(GeneratedMessageJobStatus.IN_PROGRESS.value) == 0
    )
    assert len(statuses["jobs_list"]) == 3


@use_app_context
def test_wipe_message_generation_job_queue():
    client = basic_client()
    archetype = basic_archetype(client)
    client_sdr = basic_client_sdr(client)
    prospect = basic_prospect(client, archetype, client_sdr)
    prospect_2 = basic_prospect(client, archetype, client_sdr)
    prospect_3 = basic_prospect(client, archetype, client_sdr)
    campaign = basic_outbound_campaign(
        prospect_ids=[prospect.id, prospect_2.id, prospect_3.id],
        campaign_type=GeneratedMessageType.LINKEDIN,
        client_archetype=archetype,
        client_sdr=client_sdr,
    )
    job1 = basic_generated_message_job_queue(
        prospect, campaign, GeneratedMessageJobStatus.PENDING
    )
    job2 = basic_generated_message_job_queue(
        prospect_2, campaign, GeneratedMessageJobStatus.COMPLETED
    )
    job3 = basic_generated_message_job_queue(
        prospect_3, campaign, GeneratedMessageJobStatus.FAILED
    )

    assert len(GeneratedMessageJobQueue.query.all()) == 3
    wipe_message_generation_job_queue(campaign.id)
    assert len(GeneratedMessageJobQueue.query.all()) == 0


@use_app_context
def test_manually_mark_ai_approve():
    client = basic_client()
    sdr = basic_client_sdr(client)
    archetype = basic_archetype(client, sdr)
    prospect = basic_prospect(client, archetype, sdr)
    cta = basic_generated_message_cta(archetype)

    campaign = basic_outbound_campaign(
        [prospect.id],
        GeneratedMessageType.EMAIL,
        client_archetype=archetype,
        client_sdr=sdr,
    )
    gm = basic_generated_message(prospect, cta)

    assert gm.ai_approved is None
    manually_mark_ai_approve(gm.id, True)
    gm = GeneratedMessage.query.get(gm.id)
    assert gm.ai_approved is True


@use_app_context
@mock.patch("src.message_generation.services.run_message_rule_engine")
def test_update_message_service(rule_engine_mock):
    client = basic_client()
    archetype = basic_archetype(client)
    prospect = basic_prospect(client, archetype)

    message: GeneratedMessage = basic_generated_message(prospect=prospect)
    message_id = message.id

    # No change
    assert message.completion == "this is a test"
    update_message(message_id, message.completion)
    message = GeneratedMessage.query.get(message_id)
    assert message.completion == "this is a test"
    assert message.human_edited is None
    gm_record = GeneratedMessageEditRecord.query.all()
    assert len(gm_record) == 1

    # Change not within 2 character minimum
    assert message.completion == "this is a test"
    update_message(message_id, "this is a testt")
    message = GeneratedMessage.query.get(message_id)
    assert message.completion == "this is a testt"
    assert message.human_edited is None
    gm_record = GeneratedMessageEditRecord.query.all()
    assert len(gm_record) == 2

    # Change
    assert message.completion == "this is a testt"
    assert message.human_edited is None
    update_message(message_id, "this is a test 2")
    message = GeneratedMessage.query.get(message_id)
    assert message.completion == "this is a test 2"
    assert message.human_edited is True
    gm_record = GeneratedMessageEditRecord.query.all()
    assert len(gm_record) == 3


@use_app_context
def test_can_generate_with_patterns():
    client = basic_client()
    sdr = basic_client_sdr(client)
    client_id = client.id
    sdr_id = sdr.id

    assert can_generate_with_patterns(sdr_id) is False

    pattern = basic_stack_ranked_message_generation_config(client_id=client_id)
    assert can_generate_with_patterns(sdr_id) is True
