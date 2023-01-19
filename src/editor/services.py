from app import db
from model_import import Editor, EditorTypes


def create_editor(
    name: str,
    email: str,
    editor_type: EditorTypes,
):
    editor = Editor(
        name=name,
        email=email,
        editor_type=editor_type,
    )
    db.session.add(editor)
    db.session.commit()
    return editor


def update_editor(
    name: str,
    email: str,
    editor_type: EditorTypes,
):
    editor = Editor.query.filter_by(email=email).first()
    if not editor:
        raise Exception(f"Editor not found for email {email}")
    editor.name = name
    editor.editor_type = editor_type
    db.session.commit()
    return editor


def toggle_editor_active(editor_id: int):
    editor = Editor.query.filter(Editor.id == editor_id).first()
    if not editor:
        raise Exception(f"Editor not found for id {editor_id}")
    editor.active = not editor.active
    db.session.add(editor)
    db.session.commit()
    return editor
