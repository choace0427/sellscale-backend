from app import db
from decorators import use_app_context
from test_utils import test_app
from model_import import EditorTypes, Editor

from app import app
import json
import mock


@use_app_context
def test_post_create_editor():
    response = app.test_client().post(
        "/editor/create",
        data=json.dumps(
            {
                "name": "test",
                "email": "email",
                "editor_type": "SELLSCALE_ADMIN",
            }
        ),
        content_type="application/json",
    )
    assert response.status_code == 200

    editor = Editor.query.filter_by(email="email").first()
    assert editor.name == "test"
    assert editor.editor_type == EditorTypes.SELLSCALE_ADMIN
