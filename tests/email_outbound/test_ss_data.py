from tests.test_utils.decorators import use_app_context
from tests.test_utils.test_utils import test_app
from app import db

from src.email_outbound.ss_data import SSData
from model_import import (
    EmailInteractionState,
    EmailSequenceState,
)

@use_app_context
def test_init():
    email = 'test@sellscale.com'
    email_interaction_state = EmailInteractionState.EMAIL_SENT
    email_sequence_state = EmailSequenceState.IN_PROGRESS

    ssdata = SSData(email, email_interaction_state, email_sequence_state)
    assert ssdata is not None
    assert ssdata.get_email() == email
    assert ssdata.get_email_interaction_state() == email_interaction_state
    assert ssdata.get_email_sequence_state() == email_sequence_state
    assert ssdata.to_str_dict() == {
        'email': email,
        'email_interaction_state': email_interaction_state.value,
        'email_sequence_state': email_sequence_state.value
    }
    assert ssdata.to_enum_dict() == {
        'email': email,
        'email_interaction_state': email_interaction_state,
        'email_sequence_state': email_sequence_state
    }

    ssdata = SSData.from_dict({
        'email': email,
        'email_interaction_state': email_interaction_state.value,
        'email_sequence_state': email_sequence_state.value
    })
    assert ssdata is not None
    assert ssdata.get_email() == email
    assert ssdata.get_email_interaction_state() == email_interaction_state
    assert ssdata.get_email_sequence_state() == email_sequence_state

