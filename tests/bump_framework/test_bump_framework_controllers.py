from app import app
import json
from src.bump_framework.models import BumpLength
from src.bump_framework.services import create_bump_framework
from src.prospecting.models import ProspectOverallStatus
from test_utils import (
    test_app,
    basic_client,
    basic_client_sdr,
    basic_archetype,
    basic_bump_framework,
    get_login_token
)
from decorators import use_app_context

LOGIN_TOKEN = get_login_token()


@use_app_context
def test_get_bump_frameworks():
    client = basic_client()
    client_sdr = basic_client_sdr(client)
    client_archetype = basic_archetype(client, client_sdr)
    client_sdr_id = client_sdr.id
    bump_id = create_bump_framework(
        client_sdr_id=client_sdr.id,
        client_archetype_id=client_archetype.id,
        title="title",
        description="description",
        overall_status=ProspectOverallStatus.ACTIVE_CONVO,
        length=BumpLength.LONG,
        active=True,
        default=True
    )

    response = app.test_client().get(
        f"/bump_framework/bump?overall_statuses=ACCEPTED,ACTIVE_CONVO&archetype_ids={client_archetype.id}",
        headers={
            "Authorization": "Bearer {token}".format(token=LOGIN_TOKEN)
        },
    )
    assert response.status_code == 200
    response_json = json.loads(response.data)
    assert len(response_json.get('bump_frameworks')) == 1
