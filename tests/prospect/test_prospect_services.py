from app import db
from tests.test_utils.test_utils import (
    test_app,
    basic_client,
    basic_client_sdr,
    basic_archetype,
    basic_prospect,
    basic_prospect_email,
    get_login_token,
    basic_generated_message,
    basic_generated_message_cta,
    basic_outbound_campaign,
)
from .constants import SAMPLE_LINKEDIN_RESEARCH_PAYLOAD
from src.prospecting.services import (
    search_prospects,
    get_prospects,
    add_prospect,
    get_prospect_generated_message,
    get_linkedin_slug_from_url,
    get_navigator_slug_from_url,
    add_prospects_from_json_payload,
    validate_prospect_json_payload,
    update_prospect_status_linkedin,
    update_prospect_status_email,
    create_prospect_from_linkedin_link,
    create_prospect_note,
    mark_prospects_as_queued_for_outreach,
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
    GeneratedMessage,
    OutboundCampaign,
    OutboundCampaignStatus,
    GeneratedMessageType,
)
from tests.test_utils.decorators import use_app_context
import mock
import src.utils.slack
from app import app
import json


@use_app_context
def test_search_prospects():
    c = basic_client()
    a = basic_archetype(c)
    c_sdr = basic_client_sdr(c)
    prospect = basic_prospect(c, a, c_sdr)  # Testing Testasara

    prospects = search_prospects(
        query="test", client_id=c.id, client_sdr_id=c_sdr.id, limit=10
    )
    assert len(prospects) == 1

    prospects = search_prospects(
        query="NO MATCH", client_id=c.id, client_sdr_id=c_sdr.id, limit=10
    )
    assert len(prospects) == 0


@use_app_context
def test_get_prospects():
    c = basic_client()
    a = basic_archetype(c)
    c_sdr = basic_client_sdr(c)
    prospect = basic_prospect(c, a, c_sdr, full_name="david", company="SellScale")
    prospect_2 = basic_prospect(c, a, c_sdr, full_name="adam", company="SellScale")
    prospect_3 = basic_prospect(c, a, c_sdr, full_name="ben", company="SellScale")

    order_1 = [{"field": "full_name", "direction": 1}]  # 1 = ascending, -1 = descending
    returned = get_prospects(c_sdr.id, limit=10, offset=0, ordering=order_1)
    assert returned.get("total_count") == 3
    prospects = returned.get("prospects")
    assert prospects[0].full_name == "adam"
    assert prospects[1].full_name == "ben"
    assert prospects[2].full_name == "david"

    prospect_4 = basic_prospect(c, a, c_sdr, full_name="adam", company="Apple")
    prospect_5 = basic_prospect(c, a, c_sdr, full_name="ben", company="Apple")
    order_2 = [
        {"field": "full_name", "direction": 1},  # 1 = ascending, -1 = descending
        {"field": "company", "direction": 1},  # 1 = ascending, -1 = descending
    ]
    returned = get_prospects(c_sdr.id, limit=10, offset=0, ordering=order_2)
    assert returned.get("total_count") == 5
    prospects = returned.get("prospects")
    assert prospects[0].full_name == "adam"
    assert prospects[0].company == "Apple"
    assert prospects[1].full_name == "adam"
    assert prospects[1].company == "SellScale"
    assert prospects[2].full_name == "ben"
    assert prospects[2].company == "Apple"
    assert prospects[3].full_name == "ben"
    assert prospects[3].company == "SellScale"
    assert prospects[4].full_name == "david"
    assert prospects[4].company == "SellScale"

    order_3 = [
        {"field": "company", "direction": 1},  # 1 = ascending, -1 = descending
        {"field": "full_name", "direction": 1},  # 1 = ascending, -1 = descending
    ]
    returned = get_prospects(c_sdr.id, limit=10, offset=0, ordering=order_3)
    assert returned.get("total_count") == 5
    prospects = returned.get("prospects")
    assert prospects[0].full_name == "adam"
    assert prospects[0].company == "Apple"
    assert prospects[1].full_name == "ben"
    assert prospects[1].company == "Apple"
    assert prospects[2].full_name == "adam"
    assert prospects[2].company == "SellScale"
    assert prospects[3].full_name == "ben"
    assert prospects[3].company == "SellScale"
    assert prospects[4].full_name == "david"
    assert prospects[4].company == "SellScale"

    prospect_6 = basic_prospect(
        c, a, c_sdr, full_name="jim", company="Apple", status=ProspectStatus.DEMO_SET
    )
    returned = get_prospects(
        c_sdr.id, status=["DEMO_SET"], limit=10, offset=0, ordering=order_3
    )
    assert returned.get("total_count") == 1
    prospects = returned.get("prospects")
    assert prospects[0].full_name == "jim"

    returned = get_prospects(c_sdr.id, limit=2, offset=0)
    assert returned.get("total_count") == 6

    # Test that statuses must match
    try:
        returned = get_prospects(c_sdr.id, status=["REMOVED"], limit=10, offset=0)
        assert False
    except ValueError:
        assert True

    # Test filtering by overall status
    prospect_7 = basic_prospect(
        c,
        a,
        c_sdr,
        full_name="jim",
        company="Datadog",
        overall_status=ProspectOverallStatus.DEMO,
    )
    returned = get_prospects(
        c_sdr.id, channel="LINKEDIN", status=["DEMO_SET"], limit=10, offset=0
    )
    assert returned.get("total_count") == 1
    prospects = returned.get("prospects")
    assert prospects[0].full_name == "jim"
    assert prospects[0].company == "Apple"

    # Test filtering by email
    prospect_8 = basic_prospect(c, a, c_sdr, full_name="dave", company="scalingsell")
    prospect_8_email = basic_prospect_email(
        prospect_8, outreach_status=ProspectEmailOutreachStatus.EMAIL_OPENED
    )
    returned = get_prospects(
        c_sdr.id, channel="EMAIL", status=["EMAIL_OPENED"], limit=10, offset=0
    )
    assert returned.get("total_count") == 1
    prospects = returned.get("prospects")
    assert prospects[0].full_name == "dave"
    assert prospects[0].company == "scalingsell"


@use_app_context
def test_get_prospect_generated_message():
    client = basic_client()
    client_sdr = basic_client_sdr(client)
    archetype = basic_archetype(client, client_sdr)
    prospect = basic_prospect(client, archetype, client_sdr)
    cta = basic_generated_message_cta(archetype)
    li_message = basic_generated_message(prospect, cta)
    li_message_id = li_message.id
    li_message.message_type = "LINKEDIN"
    li_message.message_status = "APPROVED"
    email_message = basic_generated_message(prospect, cta)
    email_message_id = email_message.id
    email_message.message_type = "EMAIL"
    email_message.message_status = "APPROVED"
    db.session.add_all([li_message, email_message])
    db.session.commit()

    dict = get_prospect_generated_message(prospect.id, "LINKEDIN")
    assert dict["id"] == li_message_id
    assert dict["message_type"] == "LINKEDIN"

    dict = get_prospect_generated_message(prospect.id, "EMAIL")
    assert dict["id"] == email_message_id
    assert dict["message_type"] == "EMAIL"


@use_app_context
@mock.patch("src.prospecting.services.get_research_and_bullet_points_new.delay")
@mock.patch("src.prospecting.services.get_research_payload_new")
def test_update_prospect_status_with_note(
    get_research_payload_new_mock, get_research_and_bullet_points_new_delay
):
    client = basic_client()
    client_id = client.id
    archetype = basic_archetype(client)
    archetype_id = archetype.id
    client_sdr = basic_client_sdr(client)
    add_prospect(
        client_id=client_id,
        archetype_id=archetype_id,
        client_sdr_id=client_sdr.id,
        company="testing",
        company_url="testing.com",
        employee_count="10-100",
        full_name="testing",
        industry="saas",
        linkedin_url=None,
        linkedin_bio=None,
        title="testing",
        twitter_url="testing",
    )

    prospects = Prospect.query.all()
    assert len(prospects) == 1
    assert prospects[0].client_id == client_id
    assert prospects[0].archetype_id == archetype_id

    prospect0 = prospects[0]
    prospect_id = prospect0.id
    update_prospect_status_linkedin(
        prospect_id=prospect0.id,
        new_status=ProspectStatus.SENT_OUTREACH,
        note="testing",
    )

    prospect: Prospect = Prospect.query.get(prospect_id)
    assert prospect is not None
    assert prospect.status == ProspectStatus.SENT_OUTREACH

    notes: list = ProspectNote.query.all()
    assert len(notes) == 1
    assert notes[0].prospect_id == prospect_id
    assert notes[0].note == "testing"


@use_app_context
@mock.patch("src.prospecting.services.get_research_and_bullet_points_new.delay")
@mock.patch("src.prospecting.services.get_research_payload_new")
def test_update_prospect_status_active_convo_disable_ai(
    get_research_payload_new_mock, get_research_and_bullet_points_new_delay
):
    client = basic_client()
    archetype = basic_archetype(client)
    client_sdr = basic_client_sdr(client)
    add_prospect(
        client_id=client.id,
        archetype_id=archetype.id,
        client_sdr_id=client_sdr.id,
        company="testing",
        company_url="testing.com",
        employee_count="10-100",
        full_name="testing",
        industry="saas",
        linkedin_url=None,
        linkedin_bio=None,
        title="testing",
        twitter_url="testing",
    )
    prospects = Prospect.query.all()
    prospect0 = prospects[0]
    prospect0.status = ProspectStatus.RESPONDED
    db.session.add(prospect0)
    db.session.commit()
    prospect0_id = prospect0.id

    update_prospect_status_linkedin(
        prospect_id=prospect0_id,
        new_status=ProspectStatus.ACTIVE_CONVO,
        note="testing",
    )
    prospect = Prospect.query.get(prospect0_id)
    assert prospect is not None
    assert prospect.deactivate_ai_engagement == None

    client2 = basic_client()
    archetype2 = basic_archetype(client2)
    archetype2.disable_ai_after_prospect_engaged = True
    client_sdr2 = basic_client_sdr(client2)
    add_prospect(
        client_id=client2.id,
        archetype_id=archetype2.id,
        client_sdr_id=client_sdr2.id,
        company="testing",
        company_url="testing.com",
        employee_count="10-100",
        full_name="testing",
        industry="saas",
        linkedin_url=None,
        linkedin_bio=None,
        title="testing",
        twitter_url="testing",
    )
    prospects = Prospect.query.all()
    assert len(prospects) == 2
    prospect1 = prospects[1]
    prospect1.status = ProspectStatus.RESPONDED
    db.session.add(prospect1)
    db.session.commit()
    prospect1_id = prospect1.id

    update_prospect_status_linkedin(
        prospect_id=prospect1_id,
        new_status=ProspectStatus.ACTIVE_CONVO,
        note="testing",
    )
    prospect = Prospect.query.get(prospect1_id)
    assert prospect is not None
    # assert prospect.deactivate_ai_engagement == True


@use_app_context
@mock.patch("src.prospecting.services.get_research_and_bullet_points_new.delay")
@mock.patch("src.prospecting.services.get_research_payload_new")
def test_add_prospect(
    get_research_payload_new_mock, get_research_and_bullet_points_new_delay
):
    client = basic_client()
    client_id = client.id
    archetype = basic_archetype(client)
    archetype_id = archetype.id
    client_sdr = basic_client_sdr(client)
    client_sdr_id = client_sdr.id
    add_prospect(
        client_id=client_id,
        archetype_id=archetype_id,
        client_sdr_id=client_sdr_id,
        company="testing",
        company_url="testing.com",
        employee_count="10-100",
        full_name="testing testoro",
        industry="saas",
        linkedin_url=None,
        linkedin_bio=None,
        title="testing",
        twitter_url="testing",
    )

    prospects = Prospect.query.all()
    assert len(prospects) == 1
    assert prospects[0].client_id == client_id
    assert prospects[0].archetype_id == archetype_id
    assert prospects[0].first_name == "Testing"
    assert prospects[0].last_name == "Testoro"

    client = Client.query.get(client_id)
    archetype2 = basic_archetype(client)
    archetype_id2 = archetype2.id
    client_sdr2 = basic_client_sdr(client)
    add_prospect(
        client_id=client_id, archetype_id=archetype_id2, client_sdr_id=client_sdr2.id
    )

    prospects = Prospect.query.order_by(Prospect.id.asc()).all()
    assert len(prospects) == 2
    assert prospects[1].archetype_id == archetype_id2

    assert archetype_id != archetype_id2

    add_prospect(
        client_id=client_id,
        archetype_id=archetype_id,
        client_sdr_id=client_sdr_id,
        company="testing testasara",
        company_url="testing.com",
        employee_count="10-100",
        full_name="testing testoro",
        industry="saas",
        linkedin_url=None,
        linkedin_bio=None,
        title="testing",
        twitter_url="testing",
    )
    prospects = Prospect.query.all()
    assert len(prospects) == 2

    add_prospect(
        client_id=client_id,
        archetype_id=archetype_id,
        client_sdr_id=client_sdr_id,
        company="testing",
        company_url="testing.com",
        employee_count="10-100",
        full_name="testing testoro",
        industry="saas",
        linkedin_url="12381",
        linkedin_bio=None,
        title="testing",
        twitter_url="testing",
    )
    prospects = Prospect.query.all()
    assert len(prospects) == 2

    add_prospect(
        client_id=client_id,
        archetype_id=archetype_id,
        client_sdr_id=client_sdr_id,
        company="testing",
        company_url="testing.com",
        employee_count="10-100",
        full_name="testing sara",  # new name here
        industry="saas",
        linkedin_url="12381",
        linkedin_bio=None,
        title="testing",
        twitter_url="testing",
    )
    prospects = Prospect.query.all()
    assert len(prospects) == 3

    add_prospect(
        client_id=client_id,
        archetype_id=archetype_id,
        client_sdr_id=client_sdr_id,
        company="testing 2",
        company_url="testing.com",
        employee_count="10-100",
        full_name="testing david",
        industry="saas",
        linkedin_url="12381",
        linkedin_bio="something",
        title="testing",
        twitter_url="testing",
        linkedin_num_followers=100,
    )
    prospects = Prospect.query.filter(Prospect.li_num_followers > 0).all()
    assert len(prospects) == 1


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
@mock.patch("src.prospecting.services.create_prospect_from_linkedin_link.apply_async")
@mock.patch(
    "src.prospecting.controllers.collect_and_run_celery_jobs_for_upload.apply_async"
)
def test_add_prospects_from_json_payload(
    collect_and_run_celery_jobs_for_upload_mock, mock_create_from_linkedin
):
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
            "email": "aakash.adesara@gmail.com",
            "full_name": "Aakash Adesara",
            "linkedin_url": "https://www.linkedin.com/in/aaadesara/",  # duplicate
            "title": "Growth Engineer",
        },
        {
            "company": "Athelas",
            "company_url": "https://athelas.com/",
            "email": "aakash.adesara@gmail.com",
            "full_name": "Ishan Sharma",
            "linkedin_url": "https://www.linkedin.com/in/aaadesara/",  # duplicate
            "title": "Growth Engineer",
        },
        {
            "company": "Athelas",
            "company_url": "https://athelas.com/",
            "email": "aakash.adesara@gmail.com",
            "full_name": "Ishan No Linkedin",
            "linkedin_url": "some_linkedin",
            "title": "Growth Engineer",
        },
        {
            "company": "Athelas",
            "company_url": "https://athelas.com/",
            "email": "",  # no  email
            "full_name": "Ishan No Email",
            "linkedin_url": "another_linkedin",
            "title": "Growth Engineer",
        },
        {
            "company": "Athelas",
            "company_url": "https://athelas.com/",
            "email": "",  # no  email
            "full_name": "",
            "linkedin_url": "final_linkedin",
            "title": "Growth Engineer",
        },
    ]
    client = basic_client()
    sdr = basic_client_sdr(client)
    archetype = basic_archetype(client, sdr)
    archetype_id = archetype.id
    response = app.test_client().post(
        "prospect/add_prospect_from_csv_payload",
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + get_login_token(),
        },
        data=json.dumps(
            {
                "archetype_id": archetype_id,
                "csv_payload": payload,
                "email_enabled": False,
            }
        ),
    )
    assert response.status_code == 200

    # Too many prospects, service denied.
    payload = [x for x in range(3000)]
    response = app.test_client().post(
        "prospect/add_prospect_from_csv_payload",
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + get_login_token(),
        },
        data=json.dumps(
            {
                "archetype_id": archetype_id,
                "csv_payload": payload,
                "email_enabled": False,
            }
        ),
    )
    assert response.status_code == 400


@use_app_context
@mock.patch("src.prospecting.services.create_prospect_from_linkedin_link.apply_async")
@mock.patch(
    "src.prospecting.controllers.collect_and_run_celery_jobs_for_upload.apply_async"
)
@mock.patch("src.prospecting.services.add_prospect")
def test_add_2_prospects_from_csv(
    mock_add_prospect,
    mock_collect_and_run_celery_jobs_for_upload,
    mock_create_from_linkedin,
):
    payload = [
        {
            "First Name": "Suzanne",
            "Last Name": "Cooner",
            "State": "Iowa",
            "full_name": "Suzanne Cooner",
            "company": "Audubon County Memorial Hospital",
            "title": "Chief Executive Officer",
            "linkedin_url": "https://www.linkedin.com/in/suzanne-cooner-31849321",
        },
        {
            "First Name": "Michelle",
            "Last Name": "Rebelsky",
            "State": "Iowa",
            "full_name": "Michelle Rebelsky",
            "company": "Audubon County Memorial Hospital",
            "title": "Chief Medical Officer",
            "linkedin_url": "https://www.linkedin.com/in/michelle-rebelsky-md-mba-609702143",
        },
    ]

    client = basic_client()
    client_sdr = basic_client_sdr(client)
    archetype = basic_archetype(client, client_sdr)
    archetype_id = archetype.id
    response = app.test_client().post(
        "prospect/add_prospect_from_csv_payload",
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + get_login_token(),
        },
        data=json.dumps(
            {
                "archetype_id": archetype_id,
                "csv_payload": payload,
            }
        ),
    )
    assert response.status_code == 200

    prospects = Prospect.query.all()
    assert len(prospects) == 0
    assert mock_add_prospect.call_count == 0

    for i in prospects:
        assert i.company_url == "https://athelas.com/"


@use_app_context
def test_validate_prospect_json_payload_invalid():
    """
    Tests that a bad payload is rejected
    """
    bad_li_payload = [
        {
            "company": "Athelas",
            "company_url": "https://athelas.com/",
            "email": "",
            "full_name": "Aakash Adesara",
            "linkedin_urlBAD": "",
            "title": "Growth Engineer",
        },
    ]
    validated, _ = validate_prospect_json_payload(payload=bad_li_payload)
    assert validated == False

    bad_email_payload = [
        {
            "company": "Athelas",
            "company_url": "https://athelas.com/",
            "emailBAD": "",
            "full_name": "Aakash Adesara",
            "linkedin_url": "",
            "title": "Growth Engineer",
        },
    ]
    validated, _ = validate_prospect_json_payload(payload=bad_email_payload)
    assert validated == False

    correct_payload = [
        {
            "company": "Athelas",
            "company_url": "https://athelas.com/",
            "email": "some_email",
            "full_name": "Aakash Adesara",
            "linkedin_url": "some_url",
            "title": "Growth Engineer",
        },
    ]
    validated, _ = validate_prospect_json_payload(payload=correct_payload)
    assert validated == True


@use_app_context
@mock.patch("src.prospecting.services.create_prospect_from_linkedin_link.delay")
def test_add_prospects_from_json_payload_invalid(
    create_prospect_from_linkedin_link_patch,
):
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

    response = add_prospects_from_json_payload(client.id, archetype.id, payload)
    assert response == ("Success", 0)

    prospects = Prospect.query.all()
    assert len(prospects) == 0


@use_app_context
def test_toggle_ai_engagement_endpoint():
    client = basic_client()
    client_sdr = basic_client_sdr(client)
    archetype = basic_archetype(client)
    prospect = basic_prospect(client, archetype, client_sdr)
    prospect_id = prospect.id

    assert not prospect.deactivate_ai_engagement

    response = app.test_client().patch(
        f"prospect/{prospect_id}/ai_engagement",
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + get_login_token(),
        },
        data=json.dumps({}),
    )
    assert response.status_code == 200

    prospect = Prospect.query.get(prospect_id)
    assert prospect is not None
    # assert prospect.deactivate_ai_engagement == True


@use_app_context
def test_delete_prospect_by_id_endpoint():
    client = basic_client()
    archetype = basic_archetype(client)
    prospect = basic_prospect(client, archetype)
    prospect_id = prospect.id

    response = app.test_client().delete(
        "prospect/delete_prospect",
        headers={"Content-Type": "application/json"},
        data=json.dumps({"prospect_id": prospect_id}),
    )
    assert response.status_code == 200
    assert Prospect.query.get(prospect.id) is None


@use_app_context
def test_reengage_accepted_prospected():
    client = basic_client()
    archetype = basic_archetype(client)
    prospect = basic_prospect(client, archetype)
    prospect_id = prospect.id
    prospect.status = ProspectStatus.ACCEPTED

    response = app.test_client().post(
        "prospect/mark_reengagement",
        headers={"Content-Type": "application/json"},
        data=json.dumps({"prospect_id": prospect_id}),
    )
    assert response.status_code == 200
    assert Prospect.query.get(prospect_id) is not None
    prospect: Prospect = Prospect.query.get(prospect_id)
    assert prospect.status == ProspectStatus.RESPONDED
    assert prospect.last_reviewed is None
    assert prospect.times_bumped == 1

    response = app.test_client().post(
        "prospect/mark_reengagement",
        headers={"Content-Type": "application/json"},
        data=json.dumps({"prospect_id": prospect_id}),
    )
    assert response.status_code == 200
    assert Prospect.query.get(prospect_id) is not None
    prospect: Prospect = Prospect.query.get(prospect_id)
    assert prospect.times_bumped == 2


@use_app_context
def test_reengage_active_prospected():
    client = basic_client()
    archetype = basic_archetype(client)
    prospect = basic_prospect(client, archetype)
    prospect_id = prospect.id
    prospect.status = ProspectStatus.ACTIVE_CONVO

    response = app.test_client().post(
        "prospect/mark_reengagement",
        headers={"Content-Type": "application/json"},
        data=json.dumps({"prospect_id": prospect_id}),
    )
    assert response.status_code == 200
    assert Prospect.query.get(prospect.id) is not None
    prospect: Prospect = Prospect.query.get(prospect.id)
    assert prospect.status == ProspectStatus.ACTIVE_CONVO


@use_app_context
@mock.patch("src.prospecting.services.send_slack_message")
def test_send_slack_reminder(send_slack_message_patch):
    client = basic_client()
    client.id = 1
    client.pipeline_notifications_webhook_url = "some_c_webhook"
    client_sdr = basic_client_sdr(client)
    client_sdr.id = 1
    client_sdr.pipeline_notifications_webhook_url = "some_sdr_webhook"
    archetype = basic_archetype(client)
    archetype.id = 1
    prospect = basic_prospect(client, archetype)
    prospect.id = 1
    prospect.client_id = 1
    prospect.client_sdr_id = 1
    prospect.li_last_message_from_prospect = "Last Message Test"
    prospect.li_conversation_thread_id = "some_url"
    db.session.commit()

    response = app.test_client().post(
        "prospect/send_slack_reminder",
        headers={"Content-Type": "application/json"},
        data=json.dumps({"prospect_id": 1, "alert_reason": "test alert reason"}),
    )
    assert response.status_code == 200

    assert send_slack_message_patch is src.prospecting.services.send_slack_message
    assert send_slack_message_patch.call_count == 1

    prospect: Prospect = Prospect.query.get(1)
    # assert prospect.last_reviewed is not None
    # assert prospect.deactivate_ai_engagement == True


@use_app_context
@mock.patch(
    "src.research.linkedin.services.research_personal_profile_details",
    return_value=SAMPLE_LINKEDIN_RESEARCH_PAYLOAD,
)
@mock.patch("src.prospecting.services.get_research_and_bullet_points_new.delay")
def test_create_prospect_from_linkedin_link(
    get_research_and_bullet_points_new_delay_mock,
    research_personal_profile_details_patch,
):
    client = basic_client()
    archetype = basic_archetype(client)
    client_id = client.id
    archetype_id = archetype.id
    linkedin_url = "https://www.linkedin.com/in/johnny/"

    create_prospect_from_linkedin_link(
        archetype_id=archetype.id,
        url=linkedin_url,
        batch="123",
        email="johnny@sellscale.com",
    )

    prospect = Prospect.query.first()
    assert prospect.client_id == client_id
    assert prospect.archetype_id == archetype_id
    assert prospect.email == "johnny@sellscale.com"
    assert prospect.employee_count == "1001-5000"
    assert prospect.industry == "Information Technology & Services"
    assert prospect.linkedin_url == "linkedin.com/in/matthewdbarlow"
    assert (
        prospect.title
        == "Senior Manager - Global Sales Compensation & Administration at Sungard Availability Services"
    )
    assert (
        prospect.company_url
        == "https://www.linkedin.com/company/sungard-availability-services/"
    )
    assert prospect.company == "Sungard Availability Services"
    assert (
        "Highly successful, dependable, with a strong work ethic and noted leadership skills. Strategic minded with an eye to the optimal future state.  Experience in managing processes and systems, with background in Lean Six Sigma and Scrum. Organized and detail-oriented. Focused on benefiting the team dynamic and quality of work through effective communication and a high level of integrity."
        in prospect.linkedin_bio
    )
    assert prospect.first_name == "Matthew"
    assert prospect.last_name == "Barlow"

    iscraper_cache: list[IScraperPayloadCache] = IScraperPayloadCache.query.all()
    assert len(iscraper_cache) == 2


@use_app_context
def test_create_prospect_note():
    client = basic_client()
    client_sdr = basic_client_sdr(client)
    archetype = basic_archetype(client)
    prospect = basic_prospect(client, archetype, client_sdr)

    prospect_note_id = create_prospect_note(prospect.id, "test note")
    notes: list[ProspectNote] = ProspectNote.query.all()
    assert len(notes) == 1
    assert notes[0].prospect_id == prospect.id
    assert notes[0].id == prospect_note_id


@use_app_context
def test_update_prospect_status_email():
    client = basic_client()
    client_sdr = basic_client_sdr(client)
    archetype = basic_archetype(client)
    prospect = basic_prospect(client, archetype, client_sdr)
    prospect_id = prospect.id
    prospect_email = basic_prospect_email(prospect)
    prospect_email_id = prospect_email.id

    # No override success
    update_prospect_status_email(
        prospect_id, ProspectEmailOutreachStatus.SENT_OUTREACH, override_status=True
    )
    prospect_email: ProspectEmail = ProspectEmail.query.get(prospect_email_id)
    assert prospect_email.outreach_status == ProspectEmailOutreachStatus.SENT_OUTREACH
    prospect: Prospect = Prospect.query.get(prospect_id)
    assert prospect.overall_status == ProspectOverallStatus.SENT_OUTREACH
    prospect_email_status_record: ProspectEmailStatusRecords = (
        ProspectEmailStatusRecords.query.first()
    )
    assert prospect_email_status_record.prospect_email_id == prospect_email_id
    assert (
        prospect_email_status_record.from_status == ProspectEmailOutreachStatus.UNKNOWN
    )
    assert (
        prospect_email_status_record.to_status
        == ProspectEmailOutreachStatus.SENT_OUTREACH
    )

    # No override fail
    update_prospect_status_email(prospect_id, ProspectEmailOutreachStatus.DEMO_SET)
    prospect_email: ProspectEmail = ProspectEmail.query.get(prospect_email_id)
    assert prospect_email.outreach_status == ProspectEmailOutreachStatus.SENT_OUTREACH
    prospect: Prospect = Prospect.query.get(prospect_id)
    assert prospect.overall_status == ProspectOverallStatus.SENT_OUTREACH
    prospect_email_status_record: ProspectEmailStatusRecords = (
        ProspectEmailStatusRecords.query.filter_by(
            prospect_email_id=prospect_email_id
        ).all()
    )
    assert len(prospect_email_status_record) == 1

    # Override
    update_prospect_status_email(
        prospect_id, ProspectEmailOutreachStatus.DEMO_SET, override_status=True
    )
    prospect_email: ProspectEmail = ProspectEmail.query.get(prospect_email_id)
    assert prospect_email.outreach_status == ProspectEmailOutreachStatus.DEMO_SET
    prospect: Prospect = Prospect.query.get(prospect_id)
    assert prospect.overall_status == ProspectOverallStatus.DEMO
    prospect_email_status_record: ProspectEmailStatusRecords = (
        ProspectEmailStatusRecords.query.first()
    )
    assert prospect_email_status_record.prospect_email_id == prospect_email_id
    assert (
        prospect_email_status_record.from_status == ProspectEmailOutreachStatus.UNKNOWN
    )
    assert (
        prospect_email_status_record.to_status
        == ProspectEmailOutreachStatus.SENT_OUTREACH
    )
    prospect_email_status_record: ProspectEmailStatusRecords = (
        ProspectEmailStatusRecords.query.filter_by(
            prospect_email_id=prospect_email_id
        ).all()
    )
    assert len(prospect_email_status_record) == 2
    assert prospect_email_status_record[1].prospect_email_id == prospect_email_id
    assert (
        prospect_email_status_record[1].from_status
        == ProspectEmailOutreachStatus.SENT_OUTREACH
    )
    assert (
        prospect_email_status_record[1].to_status
        == ProspectEmailOutreachStatus.DEMO_SET
    )


@use_app_context
def test_mark_prospects_as_queued_for_outreach():
    client = basic_client()
    sdr = basic_client_sdr(client)
    archetype = basic_archetype(client, sdr)
    prospect = basic_prospect(client, archetype, sdr)
    prospect_id = prospect.id
    cta = basic_generated_message_cta(archetype)
    generated_message = basic_generated_message(prospect, cta)
    oc = basic_outbound_campaign(
        [prospect_id], GeneratedMessageType.LINKEDIN, archetype, sdr
    )
    oc_id = oc.id
    generated_message_id = generated_message.id
    generated_message.message_status = "APPROVED"
    generated_message.outbound_campaign_id = oc_id
    prospect.approved_outreach_message_id = generated_message.id
    prospect.linkedin_url = "https://www.linkedin.com/in/davidmwei"

    result = mark_prospects_as_queued_for_outreach([prospect.id], sdr.id)
    assert result == (True, None)
    prospect = Prospect.query.get(prospect_id)
    assert prospect.status == ProspectStatus.QUEUED_FOR_OUTREACH
    assert prospect.overall_status == ProspectOverallStatus.PROSPECTED
    generated_message = GeneratedMessage.query.get(generated_message_id)
    assert generated_message.message_status.value == "QUEUED_FOR_OUTREACH"
    oc: OutboundCampaign = OutboundCampaign.query.get(oc_id)
    assert oc.status == OutboundCampaignStatus.COMPLETE
