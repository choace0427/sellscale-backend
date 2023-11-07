from http.client import ACCEPTED
import re
from typing import Optional
from app import db
from model_import import LinkedinInitialMessageTemplateLibrary
from src.prospecting.models import ProspectOverallStatus


def create_new_linkedin_initial_message_template(
    name: str,
    raw_prompt: str,
    human_readable_prompt: str,
    length: str,
    transformer_blocklist: list,
    tone: str,
    labels: list,
):
    # only alphabets with hyphens all lowercase
    tag = re.sub(r"[^a-z-]", "", name.replace(" ", "-").lower()).replace(" ", "-")
    li_template: LinkedinInitialMessageTemplateLibrary = LinkedinInitialMessageTemplateLibrary(
        tag=tag,
        name=name,
        raw_prompt=raw_prompt,
        human_readable_prompt=human_readable_prompt,
        length=length,
        active=True,
        transformer_blocklist=transformer_blocklist,
        tone=tone,
        labels=labels,
    )
    db.session.add(li_template)
    db.session.commit()


def toggle_linkedin_initial_message_template_active_status(li_template_id: int):
    li_template: LinkedinInitialMessageTemplateLibrary = LinkedinInitialMessageTemplateLibrary.query.get(li_template_id)
    li_template.active = not li_template.active
    db.session.commit()


def update_linkedin_initial_message_template(
    li_template_id: int,
    name: str,
    raw_prompt: str,
    human_readable_prompt: str,
    length: str,
    transformer_blocklist: list,
    tone: str,
    labels: list,
):
    li_template: LinkedinInitialMessageTemplateLibrary = LinkedinInitialMessageTemplateLibrary.query.get(li_template_id)
    li_template.name = name
    li_template.raw_prompt = raw_prompt
    li_template.human_readable_prompt = human_readable_prompt
    li_template.length = length
    li_template.transformer_blocklist = transformer_blocklist
    li_template.tone = tone
    li_template.labels = labels
    db.session.commit()


def get_all_linkedin_initial_message_templates():
    frameworks = LinkedinInitialMessageTemplateLibrary.query.filter_by(active=True).all()

    return [bft.to_dict() for bft in frameworks]
