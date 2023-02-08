import json

import mock
from decorators import use_app_context
from test_utils import (
    basic_archetype,
    basic_client,
    basic_email_schema,
    basic_generated_message,
    basic_generated_message_cta_with_text,
    basic_gnlp_model,
    basic_prospect,
    basic_prospect_email,
    basic_research_payload,
    basic_research_point,
    test_app,
)
from model_import import (
    StackRankedMessageGenerationConfiguration,
    ConfigurationType,
    GeneratedMessageType,
)
from app import app, db


@use_app_context
def test_get_stack_ranked_configuration_priority():
    client_1 = basic_client()
    client_1_id = client_1.id
    archetype_1 = basic_archetype(client=client_1)
    archetype_1_id = archetype_1.id
    archetype_2 = basic_archetype(client=client_1)
    archetype_2_id = archetype_2.id

    client_2 = basic_client()
    client_2_id = client_2.id

    default_stack_ranked_email_configuration_client_1 = (
        StackRankedMessageGenerationConfiguration(
            configuration_type=ConfigurationType.DEFAULT,
            generated_message_type=GeneratedMessageType.EMAIL,
            research_point_types=[],
            generated_message_ids=[],
            instruction="",
            computed_prompt="",
            client_id=client_1_id,
        )
    )
    db.session.add(default_stack_ranked_email_configuration_client_1)
    db.session.commit()
    CONFIG_A_ID = default_stack_ranked_email_configuration_client_1.id

    default_stack_ranked_email_configuration_client_2 = (
        StackRankedMessageGenerationConfiguration(
            configuration_type=ConfigurationType.DEFAULT,
            generated_message_type=GeneratedMessageType.EMAIL,
            research_point_types=[],
            generated_message_ids=[],
            instruction="",
            computed_prompt="",
            client_id=client_2_id,
        )
    )
    db.session.add(default_stack_ranked_email_configuration_client_2)
    db.session.commit()
    CONFIG_B_ID = default_stack_ranked_email_configuration_client_2.id

    default_stack_ranked_linkedin_configuration_client_1 = (
        StackRankedMessageGenerationConfiguration(
            configuration_type=ConfigurationType.DEFAULT,
            generated_message_type=GeneratedMessageType.LINKEDIN,
            research_point_types=[],
            generated_message_ids=[],
            instruction="",
            computed_prompt="",
            client_id=client_1_id,
        )
    )
    db.session.add(default_stack_ranked_linkedin_configuration_client_1)
    db.session.commit()
    CONFIG_C_ID = default_stack_ranked_linkedin_configuration_client_1.id

    default_stack_ranked_configuration_no_client = (
        StackRankedMessageGenerationConfiguration(
            configuration_type=ConfigurationType.DEFAULT,
            generated_message_type=GeneratedMessageType.EMAIL,
            research_point_types=[],
            generated_message_ids=[],
            instruction="",
            computed_prompt="",
        )
    )
    db.session.add(default_stack_ranked_configuration_no_client)
    db.session.commit()
    CONFIG_D_ID = default_stack_ranked_configuration_no_client.id

    default_stack_ranked_linkedin_configuration_archetype_1_client_1 = (
        StackRankedMessageGenerationConfiguration(
            configuration_type=ConfigurationType.DEFAULT,
            generated_message_type=GeneratedMessageType.EMAIL,
            research_point_types=[],
            generated_message_ids=[],
            instruction="",
            computed_prompt="",
            client_id=client_1_id,
            archetype_id=archetype_1_id,
        )
    )
    db.session.add(default_stack_ranked_linkedin_configuration_archetype_1_client_1)
    db.session.commit()
    CONFIG_E_ID = default_stack_ranked_linkedin_configuration_archetype_1_client_1.id

    default_stack_ranked_linkedin_configuration_archetype_2_client_1 = (
        StackRankedMessageGenerationConfiguration(
            configuration_type=ConfigurationType.DEFAULT,
            generated_message_type=GeneratedMessageType.LINKEDIN,
            research_point_types=[],
            generated_message_ids=[],
            instruction="",
            computed_prompt="",
            client_id=client_1_id,
            archetype_id=archetype_2_id,
        )
    )
    db.session.add(default_stack_ranked_linkedin_configuration_archetype_2_client_1)
    db.session.commit()
    CONFIG_F_ID = default_stack_ranked_linkedin_configuration_archetype_2_client_1.id

    all_stack_ranked_configs = StackRankedMessageGenerationConfiguration.query.all()
    assert len(all_stack_ranked_configs) == 6

    # get just the default Linkedin config: no client id; no archetype id
    #   this should error since no Linkedin config exists
    response = app.test_client().get(
        "message_generation/stack_ranked_configuration_priority?generated_message_type={generated_message_type}".format(
            generated_message_type="LINKEDIN"
        ),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 400

    # get just the default Email config: no client id; no archetype id
    #   should return: [CONFIG_D_ID]
    response = app.test_client().get(
        "message_generation/stack_ranked_configuration_priority?generated_message_type={generated_message_type}".format(
            generated_message_type="EMAIL"
        ),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 200
    assert [x["id"] for x in json.loads(response.data)] == [CONFIG_D_ID]

    # get just the default config: client id = client #1, no archetype id
    #   response should match [CONFIG_A_ID, CONFIG_D_ID]
    response = app.test_client().get(
        "message_generation/stack_ranked_configuration_priority?client_id={}&generated_message_type={}".format(
            client_1_id, GeneratedMessageType.EMAIL.value
        ),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 200

    assert [x["id"] for x in json.loads(response.data)] == [CONFIG_A_ID, CONFIG_D_ID]

    # get the email config for client id #1 and archetype #1
    # response should be [CONFIG_E_ID, CONFIG_A_ID, CONFIG_D_ID]
    response = app.test_client().get(
        "message_generation/stack_ranked_configuration_priority?client_id={}&archetype_id={}&generated_message_type={}".format(
            client_1_id, archetype_1_id, GeneratedMessageType.EMAIL.value
        ),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 200
    assert [x["id"] for x in json.loads(response.data)] == [
        CONFIG_E_ID,
        CONFIG_A_ID,
        CONFIG_D_ID,
    ]

    # get the linkedin config for client id #1 and archetype #1
    # response should be [CONFIG_C_ID]
    response = app.test_client().get(
        "message_generation/stack_ranked_configuration_priority?client_id={}&archetype_id={}&generated_message_type={}".format(
            client_1_id, archetype_1_id, GeneratedMessageType.LINKEDIN.value
        ),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 200
    assert [x["id"] for x in json.loads(response.data)] == [CONFIG_C_ID]

    # get the linkedin config for client id #1 and archetype #2
    # response should be [CONFIG_F_ID]
    response = app.test_client().get(
        "message_generation/stack_ranked_configuration_priority?client_id={}&archetype_id={}&generated_message_type={}".format(
            client_1_id, archetype_2_id, GeneratedMessageType.LINKEDIN.value
        ),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 200
    assert [x["id"] for x in json.loads(response.data)] == [CONFIG_F_ID, CONFIG_C_ID]
