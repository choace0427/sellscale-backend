# Description: Helper methods for testing the ml_adversary module.

from app import db, app
from tests.test_utils.test_utils import (
    test_app,
    basic_client,
    basic_client_sdr,
    basic_archetype,
    basic_prospect,
    basic_generated_message,
)

fake_openai_response = {"choices": [{"text": "test completion    "}]}

fake_openai_response_fail = {"choices": []}

fake_adversary_response = {
    "choices": [{"text": ' """test mistake."""\n---\nfix: """test fix."""\n---\n.'}]
}


def setup_generated_message():
    """Helper method to setup a generated message for testing. Removes redundant code.

    Returns:
        GeneratedMessage: A generated message object
    """
    c = basic_client()
    archetype = basic_archetype(client=c)
    prospect = basic_prospect(client=c, archetype=archetype)
    generated_message = basic_generated_message(prospect=prospect)
    return generated_message
