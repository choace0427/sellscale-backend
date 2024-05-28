from flask import jsonify
from tests.test_utils.decorators import use_app_context
from app import db
from model_import import ResearchType
from tests.test_utils.test_utils import (
    test_app,
    basic_client,
    basic_archetype,
    basic_prospect,
    basic_generated_message,
    basic_research_payload,
    basic_research_point,
    basic_generated_message_cta,
)
from app import app, db
import json
import mock


@use_app_context
@mock.patch("src.editing_tools.services.openai.Completion.create")
def test_editing_tools_endpoint(openai_mock):
    response = app.test_client().post(
        "editing_tools/edit_message",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "message_copy": "Some message copy",
                "instruction": "some instructions",
            }
        ),
    )

    assert response.status_code == 200
    assert openai_mock.call_count == 1


@use_app_context
def test_get_editing_details():
    client = basic_client()
    archetype = basic_archetype(client)
    prospect = basic_prospect(client, archetype)
    cta = basic_generated_message_cta(archetype)
    cta_id = cta.id

    li_payload = basic_research_payload(prospect)
    li_payload.research_type = ResearchType.LINKEDIN_ISCRAPER
    db.session.add(li_payload)
    db.session.commit()
    li_point = basic_research_point(li_payload)
    li_point_id = li_point.id

    serp_payload = basic_research_payload(prospect)
    serp_payload.research_type = ResearchType.SERP_PAYLOAD
    db.session.add(serp_payload)
    db.session.commit()
    serp_point = basic_research_point(serp_payload)
    serp_point_id = serp_point.id

    generated_message = basic_generated_message(prospect)
    generated_message.message_cta = cta_id
    generated_message.research_points = [li_point_id, serp_point_id]
    db.session.add(generated_message)
    db.session.commit()

    response = app.test_client().get(
        "editing_tools/editing_details/{}".format(generated_message.id)
    )
    assert response.status_code == 200
    assert response.json["cta"] == cta.to_dict()
    assert response.json["linkedin_payload"] == li_payload.payload
    assert response.json["serp_payload"] == serp_payload.payload
    assert response.json["research_points"] == [
        li_point.to_dict(),
        serp_point.to_dict(),
    ]
