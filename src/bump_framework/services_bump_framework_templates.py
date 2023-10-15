import re
from typing import Optional
from app import db
from model_import import BumpFrameworkTemplates
from src.prospecting.models import ProspectOverallStatus


def create_new_bump_framework_template(
    name: str, raw_prompt: str, human_readable_prompt: str, length: str
):
    # only alphabets with hyphens all lowercase
    tag = re.sub(r"[^a-z-]", "", name.replace(" ", "-").lower()).replace(" ", "-")
    bft: BumpFrameworkTemplates = BumpFrameworkTemplates(
        tag=tag,
        name=name,
        raw_prompt=raw_prompt,
        human_readable_prompt=human_readable_prompt,
        length=length,
        active=True,
    )
    db.session.add(bft)
    db.session.commit()


def toggle_bump_framework_template_active_status(bft_id: int):
    bft: BumpFrameworkTemplates = BumpFrameworkTemplates.query.get(bft_id)
    bft.active = not bft.active
    db.session.commit()


def update_bump_framework_template(
    bft_id: int, name: str, raw_prompt: str, human_readable_prompt: str, length: str
):
    bft: BumpFrameworkTemplates = BumpFrameworkTemplates.query.get(bft_id)
    bft.name = name
    bft.raw_prompt = raw_prompt
    bft.human_readable_prompt = human_readable_prompt
    bft.length = length
    db.session.commit()


def get_all_active_bump_framework_templates(
    bumped_count: Optional[int], overall_status: Optional[ProspectOverallStatus]
):
    frameworks_query = BumpFrameworkTemplates.query.filter_by(active=True)

    # if bumped_count is not None:
    #     frameworks_query = frameworks_query.filter_by(bumped_count=bumped_count)

    # if overall_status is not None:
    #     frameworks_query = frameworks_query.filter_by(overall_status=overall_status)

    frameworks = frameworks_query.all()

    return [bft.to_dict() for bft in frameworks]
