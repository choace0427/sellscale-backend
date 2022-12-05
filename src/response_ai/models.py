from app import db


class ResponseConfiguration(db.Model):
    __tablename__ = "response_configuration"

    archetype_id = db.Column(
        db.Integer, db.ForeignKey("client_archetype.id"), primary_key=True
    )

    li_first_follow_up = db.Column(db.String, nullable=True)
    li_second_follow_up = db.Column(db.String, nullable=True)
    li_third_follow_up = db.Column(db.String, nullable=True)
