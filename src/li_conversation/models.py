from app import db


class LinkedinConversationEntry(db.Model):
    __tablename__ = "linkedin_conversation_entry"

    id = db.Column(db.Integer, primary_key=True)

    conversation_url = db.Column(db.String, nullable=True)
    author = db.Column(db.String, nullable=True)
    first_name = db.Column(db.String, nullable=True)
    last_name = db.Column(db.String, nullable=True)
    date = db.Column(db.DateTime, nullable=True)
    profile_url = db.Column(db.String, nullable=True)
    headline = db.Column(db.String, nullable=True)
    img_url = db.Column(db.String, nullable=True)
    connection_degree = db.Column(db.String, nullable=True)
    li_url = db.Column(db.String, nullable=True)
    message = db.Column(db.String, nullable=True)
