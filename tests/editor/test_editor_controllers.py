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


@use_app_context
def test_post_update_editor():
    editor = Editor(
        name="test",
        email="email",
        editor_type=EditorTypes.SELLSCALE_ADMIN,
    )
    db.session.add(editor)
    db.session.commit()

    response = app.test_client().post(
        "/editor/update",
        data=json.dumps(
            {
                "name": "test2",
                "email": "email",
                "editor_type": "SELLSCALE_EDITING_TEAM",
            }
        ),
        content_type="application/json",
    )
    assert response.status_code == 200

    editor = Editor.query.filter_by(email="email").first()
    assert editor.name == "test2"
    assert editor.editor_type == EditorTypes.SELLSCALE_EDITING_TEAM


@use_app_context
def test_post_toggle_editor_active():
    editor = Editor(
        name="test",
        email="email",
        editor_type=EditorTypes.SELLSCALE_ADMIN,
    )
    editor.active = True
    db.session.add(editor)
    db.session.commit()

    response = app.test_client().post(
        "/editor/toggle_active",
        data=json.dumps(
            {
                "editor_id": editor.id,
            }
        ),
        content_type="application/json",
    )
    assert response.status_code == 200

    editor = Editor.query.filter_by(email="email").first()
    assert not editor.active
