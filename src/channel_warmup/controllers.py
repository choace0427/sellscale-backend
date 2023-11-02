from app import db

from flask import Blueprint, request, jsonify
from src.authentication.decorators import require_user
from src.channel_warmup.models import ChannelWarmup
from src.channel_warmup.services import pass_through_smartlead_warmup_request
from src.channel_warmup.services import (
    set_channel_warmups_for_sdr,
    set_channel_warmups_for_all_active_sdrs,
)
from src.client.models import ClientSDR


CHANNEL_WARMUP = Blueprint("email/warmup", __name__)


@CHANNEL_WARMUP.route("/smartlead", methods=["GET"])
@require_user
def get_smartlead_warmup_passthrough_api(client_sdr_id: int):
    """Passes through the Smartlead warmup API."""

    results = pass_through_smartlead_warmup_request(client_sdr_id=client_sdr_id)

    return jsonify({"status": "success", "inboxes": results}), 200


@CHANNEL_WARMUP.route("/channel_warmups", methods=["GET"])
@require_user
def get_channel_warmups(client_sdr_id: int):
    """Fetches all channel warmups for SDRs at the same client as a given SDR."""

    client_sdr: ClientSDR = ClientSDR.query.filter_by(id=client_sdr_id).first()
    client_id = client_sdr.client_id

    client_sdrs: list[ClientSDR] = ClientSDR.query.filter_by(client_id=client_id).all()
    client_sdr_ids = [x.id for x in client_sdrs]

    results = ChannelWarmup.query.filter(
        ChannelWarmup.client_sdr_id.in_(client_sdr_ids)
    ).all()

    # make an array like this:
    # [{sdr_name: 'Hristina Bell', title: 'GTM Leader', profile_pic: 'URL', channels: [warmup.to_dict()]}]

    sdrs = []
    for client_sdr in client_sdrs:
        sdr = client_sdr.to_dict()
        sdr["channels"] = [
            x.to_dict() for x in results if x.client_sdr_id == client_sdr.id
        ]
        sdrs.append(sdr)

    return (
        jsonify({"status": "success", "sdrs": sdrs}),
        200,
    )
