from datetime import datetime
from typing import Optional
from app import db
from src.prospecting.models import Prospect


class LinkedinConversationScrapeQueue(db.Model):
    __tablename__ = "linkedin_conversation_scrape_queue"

    id = db.Column(db.Integer, primary_key=True)

    conversation_urn_id = db.Column(db.String, unique=True, index=True, nullable=False)
    client_sdr_id = db.Column(db.Integer, db.ForeignKey("client_sdr.id"), nullable=False)
    prospect_id = db.Column(db.Integer, db.ForeignKey("prospect.id"), nullable=False)
    scrape_time = db.Column(db.DateTime, nullable=False)


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
    img_expire = db.Column(db.Numeric(20, 0), server_default="0", nullable=False)
    connection_degree = db.Column(db.String, nullable=True)
    li_url = db.Column(db.String, nullable=True)
    message = db.Column(db.String, nullable=True)
    entry_processed = db.Column(db.Boolean, default=False)
    entry_processed_manually = db.Column(db.Boolean, default=False)
    thread_urn_id = db.Column(db.String, nullable=True, index=True)
    urn_id = db.Column(db.String, nullable=True, index=True, unique=True)

    ai_generated = db.Column(db.Boolean, nullable=True) # is at least partially AI generated
    bump_framework_id = db.Column(db.Integer, db.ForeignKey("bump_framework.id"))
    bump_framework_title = db.Column(db.String, nullable=True)
    bump_framework_description = db.Column(db.String, nullable=True)
    bump_framework_length = db.Column(db.String, nullable=True)
    account_research_points = db.Column(db.ARRAY(db.String), nullable=True)

    bump_analytics_processed = db.Column(db.Boolean, default=False)

    def li_conversation_thread_by_prospect_id(prospect_id: int) -> list:
        p: Prospect = Prospect.query.filter_by(id=prospect_id).first()
        li_conversation_thread_id = p.li_conversation_thread_id

        if not li_conversation_thread_id:
            return []

        return (
            # contains instead of equals
            LinkedinConversationEntry.query.filter(
                LinkedinConversationEntry.conversation_url.ilike(
                    "%" + li_conversation_thread_id + "%"
                )
            )
            .order_by(LinkedinConversationEntry.date.desc())
            .all()
        )

    def to_dict(self):
        return {
            "id": self.id,
            "conversation_url": self.conversation_url,
            "author": self.author,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "date": self.date,
            "profile_url": self.profile_url,
            "headline": self.headline,
            "img_url": self.img_url,
            "img_expire": self.img_expire,
            "connection_degree": self.connection_degree,
            "li_url": self.li_url,
            "entry_processed": self.entry_processed,
            "entry_processed_manually": self.entry_processed_manually,
            "thread_urn_id": self.thread_urn_id,
            "urn_id": self.urn_id,
            "message": self.message,
            "ai_generated": self.ai_generated,
            "bump_framework_id": self.bump_framework_id,
            "bump_framework_title": self.bump_framework_title,
            "bump_framework_description": self.bump_framework_description,
            "bump_framework_length": self.bump_framework_length,
            "account_research_points": self.account_research_points,
            "bump_analytics_processed": self.bump_analytics_processed,
        }


class LinkedInConvoMessage():

    def __init__(self, author: str, message: str, connection_degree: str, li_id: Optional[int] = None, meta_data: Optional[dict] = None, date: Optional[datetime] = None):
        self.author = author
        self.message = message
        self.connection_degree = connection_degree
        self.li_id = li_id
        self.meta_data = meta_data
        self.date = date

    def to_dict(self):
        return {
            "author": self.author,
            "message": self.message,
            "connection_degree": self.connection_degree,
            "li_id": self.li_id,
            "meta_data": self.meta_data,
            "date": self.date,
        }
