from app import db
from src.response_ai.models import ResponseConfiguration
from typing import Optional


def create_response_configuration(
    archetype_id: int,
    li_first_follow_up: Optional[str] = None,
    li_second_follow_up: Optional[str] = None,
    li_third_follow_up: Optional[str] = None,
):
    response_configuration = ResponseConfiguration(
        archetype_id=archetype_id,
        li_first_follow_up=li_first_follow_up,
        li_second_follow_up=li_second_follow_up,
        li_third_follow_up=li_third_follow_up,
    )
    db.session.add(response_configuration)
    db.session.commit()
    return response_configuration
