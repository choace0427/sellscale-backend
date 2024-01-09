from app import db

from flask import Blueprint, request, jsonify
from src.authentication.decorators import require_user
from src.utils.request_helpers import get_request_parameter
from src.warmup_snapshot.models import WarmupSnapshot
from src.warmup_snapshot.services import (
    pass_through_smartlead_warmup_request,
    set_warmup_snapshots_for_client,
)
from src.client.models import ClientSDR


WARMUP_SNAPSHOT = Blueprint("warmup", __name__)


@WARMUP_SNAPSHOT.route("/smartlead", methods=["GET"])
@require_user
def get_smartlead_warmup_passthrough_api(client_sdr_id: int):
    """Passes through the Smartlead warmup API."""

    results = pass_through_smartlead_warmup_request(client_sdr_id=client_sdr_id)

    return jsonify({"status": "success", "inboxes": results}), 200


@WARMUP_SNAPSHOT.route("/snapshots", methods=["GET"])
@require_user
def get_warmup_snapshots(client_sdr_id: int):
    """Fetches all channel warmups for SDRs at the same client as a given SDR."""

    client_sdr: ClientSDR = ClientSDR.query.filter_by(id=client_sdr_id).first()
    client_id = client_sdr.client_id

    client_sdrs: list[ClientSDR] = ClientSDR.query.filter_by(client_id=client_id).all()
    client_sdr_ids = [x.id for x in client_sdrs]

    results = WarmupSnapshot.query.filter(
        WarmupSnapshot.client_sdr_id.in_(client_sdr_ids)
    ).all()

    # make an array like this:
    # [{sdr_name: 'Hristina Bell', title: 'GTM Leader', profile_pic: 'URL', snapshots: [warmup.to_dict()]}]

    sdrs = []
    for client_sdr in client_sdrs:
        sdr = client_sdr.to_dict()
        sdr["snapshots"] = [
            x.to_dict() for x in results if x.client_sdr_id == client_sdr.id
        ]
        sdrs.append(sdr)

    return (
        jsonify({"status": "success", "sdrs": sdrs}),
        200,
    )


@WARMUP_SNAPSHOT.route("/snapshots", methods=["POST"])
@require_user
def post_capture_new_snapshots(client_sdr_id: int):
    """Captures a new snapshot for a given SDR."""
    client_id = get_request_parameter(
        "client_id", request, json=True, required=False, parameter_type=int
    )

    if not client_id:
        client_sdr: ClientSDR = ClientSDR.query.filter_by(id=client_sdr_id).first()
        client_id = client_sdr.client_id

    set_warmup_snapshots_for_client(client_id=client_id)

    return (
        jsonify({"status": "success", "message": "Captured new warmup snapshots"}),
        200,
    )
