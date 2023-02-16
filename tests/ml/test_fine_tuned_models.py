from app import db, app
from test_utils import (
    basic_client,
    basic_archetype,
)
from decorators import use_app_context
from src.message_generation.services import *
from model_import import GeneratedMessageCTA, GeneratedMessage, GeneratedMessageStatus
from src.research.models import ResearchPointType, ResearchType
from src.client.services import create_client
from model_import import Client, ProspectStatus
from test_utils import test_app
from app import db
import mock
import json
from src.ml.fine_tuned_models import *


@use_app_context
@mock.patch(
    "src.ml.fine_tuned_models.get_open_ai_completion", return_value="this is a test"
)
def test_get_latest_custom_model(get_open_ai_completion_patch):
    client = basic_client()
    archetype = basic_archetype(client)
    archetype_id = archetype.id

    for i in range(10):
        data = get_custom_completion_for_client(
            archetype_id=archetype_id,
            model_type=GNLPModelType.OUTREACH,
            prompt="test",
            max_tokens=40,
            n=1,
        )
        assert data[0] == "this is a test"
        assert data[1] > 0

        models = GNLPModel.query.all()
        assert len(models) == 1

    for i in range(10):
        data = get_custom_completion_for_client(
            archetype_id=archetype_id,
            model_type=GNLPModelType.EMAIL_FIRST_LINE,
            prompt="test",
            max_tokens=40,
            n=1,
        )
        assert data[0] == "this is a test"
        assert data[1] > 0

        models = GNLPModel.query.all()
        assert len(models) == 2

    assert get_open_ai_completion_patch.call_count == 20
