from model_import import Client, ClientArchetype, ClientSDR, GNLPModel
from decorators import use_app_context
from test_utils import test_app
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
