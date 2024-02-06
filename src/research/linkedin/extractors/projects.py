from datetime import datetime

from ....utils.abstract.attr_utils import deep_get
from ....ml.fine_tuned_models import get_completion
import math
import random

PATENT_SENTENCE_FRAMES = [
    "Noticed that you've patented '{}', that's so interesting!",
    "I couldn't help but see that you are the inventor of '{}', what inspired you to invent this?",
    "Love how you've patented '{}', must've been quite a journey",
    "I'm impressed by the patent you hold around '{}'",
    "Kudos on being the patent owner of '{}' - quite impressive!",
    "What inspired you to patent {}?",
    "Looks like you're quite a builder! I saw the patent you own around {}",
]


def get_recent_patent(prospect_id: int, data: dict):
    # noticed that you patented ______

    patent_title = deep_get(data, "personal.patents.0.title", "")

    if not patent_title:
        return {}

    raw_data = {"patent_title": patent_title}

    response = PATENT_SENTENCE_FRAMES[
        math.floor(len(PATENT_SENTENCE_FRAMES) * random.random())
    ].format(patent_title.lower())

    return {"raw_data": raw_data, "prompt": "", "response": response}
