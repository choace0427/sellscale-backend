from app import db
from src.prospecting.models import Prospect


class LinkedinConversationEntry(db.Model):
    __tablename__ = "linkedin_conversation_entry"

    id = db.Column(db.Integer, primary_key=True)

    conversation_url = db.Column(db.String, index=True, nullable=True)
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
    entry_processed = db.Column(db.Boolean, default=False)

    def li_conversation_thread_by_prospect_id(prospect_id: int):
        p: Prospect = Prospect.query.filter_by(id=prospect_id).first()
        li_conversation_thread_id = p.li_conversation_thread_id

        return (
            LinkedinConversationEntry.query.filter_by(
                conversation_url=li_conversation_thread_id
            )
            .order_by(LinkedinConversationEntry.date.desc())
            .all()
        )

    def to_dict(self):
        return {
            "conversation_url": self.conversation_url,
            "author": self.author,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "date": self.date,
            "profile_url": self.profile_url,
            "headline": self.headline,
            "img_url": self.img_url,
            "connection_degree": self.connection_degree,
            "li_url": self.li_url,
            "message": self.message,
        }
