import json

import mock
from tests.test_utils.decorators import use_app_context
from tests.test_utils.test_utils import (
    basic_archetype,
    basic_client,
    basic_generated_message,
    basic_prospect,
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

    prospect = basic_prospect(client=client_1, archetype=archetype_1)
    prospect_id = prospect.id

    default_stack_ranked_email_configuration_client_1 = (
        StackRankedMessageGenerationConfiguration(
            configuration_type=ConfigurationType.DEFAULT,
            generated_message_type=GeneratedMessageType.EMAIL,
            research_point_types=[],
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
            configuration_type=ConfigurationType.STRICT,
            generated_message_type=GeneratedMessageType.LINKEDIN,
            research_point_types=[],
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
            research_point_types=["CURRENT_EXPERIENCE_DESCRIPTION"],
            instruction="",
            computed_prompt="",
        )
    )
    db.session.add(default_stack_ranked_configuration_no_client)
    db.session.commit()
    CONFIG_D_ID = default_stack_ranked_configuration_no_client.id

    default_stack_ranked_linkedin_configuration_archetype_1_client_1 = (
        StackRankedMessageGenerationConfiguration(
            configuration_type=ConfigurationType.STRICT,
            generated_message_type=GeneratedMessageType.EMAIL,
            research_point_types=[
                "CURRENT_EXPERIENCE_DESCRIPTION",
                "CURRENT_JOB_DESCRIPTION",
            ],
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
    assert response.status_code == 200
    assert json.loads(response.data) == []

    # get just the default Email config: no client id; no archetype id
    #   should return: [CONFIG_D_ID]
    response = app.test_client().get(
        "message_generation/stack_ranked_configuration_priority?generated_message_type={generated_message_type}".format(
            generated_message_type="EMAIL"
        ),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 200
    assert [x[0]["id"] for x in json.loads(response.data)] == [CONFIG_D_ID]

    # get just the default config: client id = client #1, no archetype id
    #   response should match [CONFIG_A_ID, CONFIG_D_ID]
    response = app.test_client().get(
        "message_generation/stack_ranked_configuration_priority?client_id={}&generated_message_type={}".format(
            client_1_id, GeneratedMessageType.EMAIL.value
        ),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 200

    assert [x[0]["id"] for x in json.loads(response.data)][0] in [
        CONFIG_A_ID,
        CONFIG_D_ID,
    ]

    # get the email config for client id #1 and archetype #1
    # response should be [CONFIG_E_ID, CONFIG_A_ID, CONFIG_D_ID]
    response = app.test_client().get(
        "message_generation/stack_ranked_configuration_priority?client_id={}&archetype_id={}&generated_message_type={}".format(
            client_1_id, archetype_1_id, GeneratedMessageType.EMAIL.value
        ),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 200
    assert [x[0]["id"] for x in json.loads(response.data)][0] in [
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
    assert [x[0]["id"] for x in json.loads(response.data)] == [CONFIG_C_ID]

    # get the linkedin config for client id #1 and archetype #2
    # response should be [CONFIG_F_ID]
    response = app.test_client().get(
        "message_generation/stack_ranked_configuration_priority?client_id={}&archetype_id={}&generated_message_type={}".format(
            client_1_id, archetype_2_id, GeneratedMessageType.LINKEDIN.value
        ),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 200
    assert [x[0]["id"] for x in json.loads(response.data)][0] in [
        CONFIG_F_ID,
        CONFIG_C_ID,
    ]

    # get the available configs for prospect 1
    # response should be [] since no research points exist
    response = app.test_client().get(
        "message_generation/stack_ranked_configuration_priority?client_id={}&archetype_id={}&prospect_id={}&generated_message_type={}".format(
            client_1_id,
            archetype_1_id,
            prospect_id,
            GeneratedMessageType.EMAIL.value,
        ),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 200

    research_payload = basic_research_payload(prospect=prospect)
    research_point = basic_research_point(research_payload=research_payload)
    research_point.research_point_type = "CURRENT_EXPERIENCE_DESCRIPTION"
    db.session.add(research_point)
    db.session.commit()

    # get the available configs for prospect 1
    # response should be [CONFIG_D_ID]
    response = app.test_client().get(
        "message_generation/stack_ranked_configuration_priority?client_id={}&archetype_id={}&prospect_id={}&generated_message_type={}".format(
            client_1_id,
            archetype_1_id,
            prospect_id,
            GeneratedMessageType.EMAIL.value,
        ),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 200
    assert [x[0]["id"] for x in json.loads(response.data)] == [CONFIG_D_ID]

    research_point = basic_research_point(research_payload=research_payload)
    research_point.research_point_type = "CURRENT_JOB_DESCRIPTION"
    db.session.add(research_point)
    db.session.commit()

    # get the available configs for prospect 1
    # response should be [CONFIG_E_ID, CONFIG_D_ID]
    response = app.test_client().get(
        "message_generation/stack_ranked_configuration_priority?client_id={}&archetype_id={}&prospect_id={}&generated_message_type={}".format(
            client_1_id,
            archetype_1_id,
            prospect_id,
            GeneratedMessageType.EMAIL.value,
        ),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 200
    assert [x[0]["id"] for x in json.loads(response.data)][0] in [
        CONFIG_E_ID,
        CONFIG_D_ID,
    ]


@use_app_context
def test_get_stack_ranked_configuration_tool_prompts():
    client = basic_client()
    client_id = client.id
    archetype = basic_archetype(client)
    archetype_id = archetype.id
    prospect = basic_prospect(client, archetype)
    prospect_id = prospect.id

    configuration = StackRankedMessageGenerationConfiguration(
        configuration_type=ConfigurationType.DEFAULT,
        generated_message_type=GeneratedMessageType.LINKEDIN,
        research_point_types=["CURRENT_JOB_DESCRIPTION"],
        instruction="",
        computed_prompt="this is a prompt: {prompt}",
        client_id=client_id,
        archetype_id=archetype_id,
    )
    db.session.add(configuration)
    db.session.commit()
    configuration_id = configuration.id

    response = app.test_client().post(
        "message_generation/stack_ranked_configuration_tool/get_prompts",
        data=json.dumps(
            {
                "configuration_id": configuration_id,
                "prospect_id": prospect_id,
                "list_of_research_points": ["This is a research point"],
            }
        ),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 200
    assert json.loads(response.data) == {
        "full_prompt": "this is a prompt: name: Testing Testasara<>industry: None<>company: <>title: Testing Director<>notes: This is a research point<>response:",
        "prospect_prompt": "name: Testing Testasara<>industry: None<>company: <>title: Testing Director<>notes: This is a research point<>response:",
    }


@use_app_context
def test_post_toggle_stack_ranked_configuration_tool_active():
    client = basic_client()
    client_id = client.id
    archetype = basic_archetype(client)
    archetype_id = archetype.id
    prospect = basic_prospect(client, archetype)
    prospect_id = prospect.id

    configuration = StackRankedMessageGenerationConfiguration(
        configuration_type=ConfigurationType.DEFAULT,
        generated_message_type=GeneratedMessageType.LINKEDIN,
        research_point_types=["CURRENT_JOB_DESCRIPTION"],
        instruction="",
        computed_prompt="this is a prompt: {prompt}",
        client_id=client_id,
        archetype_id=archetype_id,
    )
    db.session.add(configuration)
    db.session.commit()
    configuration_id = configuration.id

    assert configuration.active is True

    response = app.test_client().post(
        "message_generation/stack_ranked_configuration_tool/toggle_active",
        data=json.dumps(
            {
                "configuration_id": configuration_id,
            }
        ),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 200

    configuration = StackRankedMessageGenerationConfiguration.query.get(
        configuration_id
    )
    assert configuration.active is False

    response = app.test_client().post(
        "message_generation/stack_ranked_configuration_tool/toggle_active",
        data=json.dumps(
            {
                "configuration_id": configuration_id,
            }
        ),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 200

    configuration: StackRankedMessageGenerationConfiguration = (
        StackRankedMessageGenerationConfiguration.query.get(configuration_id)
    )
    assert configuration.active is True

    configuration.always_enable = True
    db.session.add(configuration)
    db.session.commit()

    response = app.test_client().post(
        "message_generation/stack_ranked_configuration_tool/toggle_active",
        data=json.dumps(
            {
                "configuration_id": configuration_id,
            }
        ),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 400
    assert (
        response.data.decode("utf-8")
        == "This message configuration is meant to always be on."
    )


@mock.patch("src.ml.fine_tuned_models.wrapped_chat_gpt_completion", return_value="A")
def test_post_stack_ranked_configuration_tool_generate_sample(
    wrapped_create_completion_mock,
):
    response = app.test_client().post(
        "message_generation/stack_ranked_configuration_tool/generate_sample",
        data=json.dumps(
            {
                "computed_prompt": "this is a prompt: {prompt}",
                "prompt": "PROMPT_DATA",
            }
        ),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 200

    result = json.loads(response.data)
    assert result.get("full_prompt") == "this is a prompt: PROMPT_DATA"
