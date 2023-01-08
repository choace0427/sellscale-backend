from app import db
import enum


class EditorTypes(enum.Enum):
    SELLSCALE_ADMIN = "SELLSCALE_ADMIN"  # a full time SellScale reviewer / employee
    SELLSCALE_EDITING_TEAM = (
        "SELLSCALE_EDITING_TEAM"  # a part time SellScale reviewer / employee / upworker
    )
    # CLIENT = "CLIENT" # a client of SellScale editing own content (not yet implemented)


class Editor(db.Model):
    __tablename__ = "editor"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), nullable=False)
    editor_type = db.Column(db.Enum(EditorTypes), nullable=False)

    def __repr__(self):
        return f"{self.name} ({self.email})"

    def __str__(self):
        return self.__repr__()
