import datetime
from flask import Blueprint, request
from src.authentication.decorators import require_user
from src.triggers.models import Trigger, TriggerProspect, TriggerRun
from app import db
from src.utils.request_helpers import get_request_parameter

TRIGGERS_BLUEPRINT = Blueprint("triggers", __name__)


@TRIGGERS_BLUEPRINT.route("/")
def index():
    return "OK", 200


@TRIGGERS_BLUEPRINT.route("/all", methods=["GET"])
@require_user
def get_triggers(client_sdr_id: int):
    triggers: list = Trigger.query.filter_by(client_sdr_id=client_sdr_id).all()
    return {"triggers": [trigger.to_dict() for trigger in triggers]}, 200


@TRIGGERS_BLUEPRINT.route("/trigger/<int:trigger_id>", methods=["GET"])
@require_user
def get_trigger_data(client_sdr_id: int, trigger_id):
    trigger = Trigger.query.filter_by(
        id=trigger_id, client_sdr_id=client_sdr_id
    ).first_or_404()
    return trigger.to_dict(), 200


@TRIGGERS_BLUEPRINT.route("/trigger/run/<int:trigger_id>", methods=["POST"])
@require_user
def create_trigger_run(client_sdr_id: int, trigger_id):
    trigger = Trigger.query.filter_by(
        id=trigger_id, client_sdr_id=client_sdr_id
    ).first_or_404()
    new_run = TriggerRun(
        trigger_id=trigger.id, run_status="Queued", run_at=datetime.datetime.utcnow()
    )
    db.session.add(new_run)
    db.session.commit()
    return {"trigger_run_id": new_run.id}, 201


@TRIGGERS_BLUEPRINT.route(
    "/trigger/run/prospects/<int:trigger_run_id>", methods=["POST"]
)
@require_user
def add_trigger_run_prospects(client_sdr_id: int, trigger_run_id):
    prospects = get_request_parameter(
        "prospects",
        request,
        json=True,
        required=True,
    )

    trigger_run = (
        TriggerRun.query.join(Trigger)
        .filter(TriggerRun.id == trigger_run_id, Trigger.client_sdr_id == client_sdr_id)
        .first_or_404()
    )

    for prospect_data in prospects:
        prospect = TriggerProspect(trigger_run_id=trigger_run.id, **prospect_data)
        db.session.add(prospect)

    db.session.commit()
    return {"message": "Prospects added successfully"}, 201
