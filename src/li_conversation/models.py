from datetime import datetime
from typing import Optional

from src.client.models import ClientArchetype
from app import db
from src.prospecting.models import Prospect
from sqlalchemy.sql.expression import func


import sqlalchemy as sa


class LinkedinInitialMessageTemplateLibrary(db.Model):
    __tablename__ = "linkedin_initial_message_template_library"

    id = db.Column(db.Integer, primary_key=True)

    tag = db.Column(db.String, nullable=False)
    name = db.Column(db.String, nullable=False)
    raw_prompt = db.Column(db.String, nullable=False)
    human_readable_prompt = db.Column(db.String, nullable=False)
    length = db.Column(db.String, nullable=False)
    tag = db.Column(db.String, nullable=True)

    labels = db.Column(db.ARRAY(db.String), nullable=True)
    tone = db.Column(db.String, nullable=True)

    active = db.Column(db.Boolean, nullable=False, default=True)

    transformer_blocklist = db.Column(
        db.ARRAY(db.String),
        nullable=True,
    )

    def to_dict(self):
        return {
            "id": self.id,
            "tag": self.tag,
            "name": self.name,
            "raw_prompt": self.raw_prompt,
            "human_readable_prompt": self.human_readable_prompt,
            "length": self.length,
            "active": self.active,
            "labels": self.labels,
            "tone": self.tone,
            "transformer_blocklist": self.transformer_blocklist,
        }


class LinkedinInitialMessageTemplate(db.Model):
    __tablename__ = "linkedin_initial_message_template"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String, nullable=True)
    message = db.Column(db.String(600), nullable=False)
    client_sdr_id = db.Column(db.Integer, db.ForeignKey("client_sdr.id"), nullable=True)
    client_archetype_id = db.Column(
        db.Integer, db.ForeignKey("client_archetype.id"), nullable=True
    )

    active = db.Column(db.Boolean, nullable=False, default=True)
    times_used = db.Column(db.Integer, nullable=False, default=0)
    times_accepted = db.Column(db.Integer, nullable=False, default=0)

    sellscale_generated = db.Column(db.Boolean, nullable=True, default=False)

    additional_instructions = db.Column(db.String, nullable=True)
    research_points = db.Column(db.ARRAY(db.String), nullable=True)

    def get_random(client_archetype_id: int):
        return (
            LinkedinInitialMessageTemplate.query.filter_by(
                client_archetype_id=client_archetype_id, active=True
            )
            .order_by(func.random())
            .first()
        )

    def to_dict(self):
        archetype: ClientArchetype = ClientArchetype.query.get(self.client_archetype_id)

        return {
            "id": self.id,
            "message": self.message,
            "client_sdr_id": self.client_sdr_id,
            "client_archetype_id": self.client_archetype_id,
            "client_archetype_archetype": archetype.archetype if archetype else None,
            "active": self.active,
            "times_used": self.times_used,
            "times_accepted": self.times_accepted,
            "sellscale_generated": self.sellscale_generated,
            "additional_instructions": self.additional_instructions,
            "research_points": self.research_points,
            "title": self.title,
        }


class LinkedinConversationScrapeQueue(db.Model):
    __tablename__ = "linkedin_conversation_scrape_queue"

    id = db.Column(db.Integer, primary_key=True)

    conversation_urn_id = db.Column(db.String, unique=True, index=True, nullable=False)
    client_sdr_id = db.Column(
        db.Integer, db.ForeignKey("client_sdr.id"), nullable=False
    )
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

    ai_generated = db.Column(
        db.Boolean, nullable=True
    )  # is at least partially AI generated

    # Relevant for bumps
    bump_framework_id = db.Column(db.Integer, db.ForeignKey("bump_framework.id"))
    bump_framework_title = db.Column(db.String, nullable=True)
    bump_framework_description = db.Column(db.String, nullable=True)
    bump_framework_length = db.Column(db.String, nullable=True)
    account_research_points = db.Column(db.ARRAY(db.String), nullable=True)

    # Relevant for initial message
    initial_message_id = db.Column(db.Integer, db.ForeignKey("generated_message.id"))
    initial_message_cta_id = db.Column(
        db.Integer, db.ForeignKey("generated_message_cta.id")
    )
    initial_message_cta_text = db.Column(db.String, nullable=True)
    initial_message_research_points = db.Column(db.ARRAY(db.String), nullable=True)
    initial_message_stack_ranked_config_id = db.Column(
        db.Integer, db.ForeignKey("stack_ranked_message_generation_configuration.id")
    )
    initial_message_stack_ranked_config_name = db.Column(db.String, nullable=True)

    bump_analytics_processed = db.Column(db.Boolean, default=False)

    latest_reply_from_sdr_date = db.Column(db.DateTime, nullable=True)

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
            "initial_message_id": self.initial_message_id,
            "initial_message_cta_id": self.initial_message_cta_id,
            "initial_message_cta_text": self.initial_message_cta_text,
            "initial_message_research_points": self.initial_message_research_points,
            "initial_message_stack_ranked_config_id": self.initial_message_stack_ranked_config_id,
            "initial_message_stack_ranked_config_name": self.initial_message_stack_ranked_config_name,
        }


class LinkedInConvoMessage:
    def __init__(
        self,
        author: str,
        message: str,
        connection_degree: str,
        li_id: Optional[int] = None,
        meta_data: Optional[dict] = None,
        date: Optional[datetime] = None,
    ):
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
