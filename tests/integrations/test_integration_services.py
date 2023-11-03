from app import app, db
from tests.test_utils.decorators import use_app_context
from model_import import Client, ClientArchetype, ClientSDR, GNLPModel, ProspectOverallStatus
from tests.test_utils.test_utils import (
    test_app,
    basic_client,
    get_login_token,
    basic_client_sdr,
    basic_prospect,
    basic_archetype,
    basic_gnlp_model,
    basic_generated_message_cta_with_text,
    basic_generated_message,
    basic_generated_message_cta
)
from src.client.services import (
    create_client,
    get_client,
    create_client_archetype,
    get_ctas,
    get_client_archetypes,
    get_client_archetype_performance,
    get_cta_stats,
    get_cta_by_archetype_id,
    get_client_sdr,
    get_sdr_available_outbound_channels,
)
import json
import mock

