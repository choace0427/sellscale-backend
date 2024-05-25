import datetime
from flask import Blueprint, request
from src.triggers.services import createTrigger, experiment_athelas_trigger, runTrigger
from src.authentication.decorators import require_user
from src.triggers.models import (
    Trigger,
    TriggerProspect,
    TriggerRun,
    convertBlocksToDict,
    get_blocks_from_output_dict,
)
from app import db
from src.utils.request_helpers import get_request_parameter

TRIGGERS_BLUEPRINT = Blueprint("triggers", __name__)


@TRIGGERS_BLUEPRINT.route("/")
def index():
    return "OK", 200


@TRIGGERS_BLUEPRINT.route("/all", methods=["GET"])
@require_user
def get_triggers(client_sdr_id: int):
    triggers: list[Trigger] = Trigger.query.filter_by(client_sdr_id=client_sdr_id).all()
    return {"triggers": [trigger.to_dict(True) for trigger in triggers]}, 200


@TRIGGERS_BLUEPRINT.route("/trigger/<int:trigger_id>", methods=["GET"])
@require_user
def get_trigger_data(client_sdr_id: int, trigger_id):
    trigger: Trigger = Trigger.query.filter_by(
        id=trigger_id, client_sdr_id=client_sdr_id
    ).first_or_404()
    return trigger.to_dict(), 200


@TRIGGERS_BLUEPRINT.route("/trigger/run/<int:trigger_id>", methods=["POST"])
@require_user
def create_trigger_run(client_sdr_id: int, trigger_id):
    # trigger = Trigger.query.filter_by(
    #     id=trigger_id, client_sdr_id=client_sdr_id
    # ).first_or_404()
    # new_run = TriggerRun(
    #     trigger_id=trigger.id, run_status="Running", run_at=datetime.datetime.utcnow()
    # )
    # db.session.add(new_run)
    # db.session.commit()

    success, run_id = runTrigger(trigger_id)

    return {"trigger_run_id": run_id}, 201


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
    trigger_run_id = trigger_run.id

    # mark trigger run as running
    trigger_run.run_status = "Uploading contacts"
    db.session.add(trigger_run)
    db.session.commit()

    trigger_run = TriggerRun.query.get(trigger_run_id)

    for prospect_data in prospects:
        # ensure that the prospect doesn't already exist by checking linkedin_url
        existing_prospect = (
            TriggerProspect.query.join(TriggerRun, Trigger)
            .filter(
                TriggerProspect.linkedin_url == prospect_data["linkedin_url"],
                Trigger.client_sdr_id == client_sdr_id,
            )
            .first()
        )
        if existing_prospect:
            continue

        prospect = TriggerProspect(trigger_run_id=trigger_run.id, **prospect_data)
        db.session.add(prospect)

    # mark trigger run as complete and set the completed_at timestamp
    trigger_run.run_status = "Completed"
    trigger_run.completed_at = datetime.datetime.utcnow()

    db.session.commit()
    return {"message": "Prospects added successfully"}, 201


@TRIGGERS_BLUEPRINT.route("/trigger/get_runs/<int:trigger_id>", methods=["GET"])
@require_user
def get_trigger_runs(client_sdr_id: int, trigger_id):
    trigger_runs = (
        TriggerRun.query.join(Trigger)
        .filter(
            TriggerRun.trigger_id == trigger_id, Trigger.client_sdr_id == client_sdr_id
        )
        .order_by(TriggerRun.id.desc())
        .limit(10)
        .all()
    )
    return {
        "trigger_runs": [trigger_run.to_dict() for trigger_run in trigger_runs]
    }, 200


@TRIGGERS_BLUEPRINT.route(
    "/trigger/get_prospects/<int:trigger_run_id>", methods=["GET"]
)
@require_user
def get_trigger_prospects(client_sdr_id: int, trigger_run_id):
    trigger_prospects = (
        TriggerProspect.query.join(TriggerRun, Trigger)
        .filter(TriggerRun.id == trigger_run_id, Trigger.client_sdr_id == client_sdr_id)
        .order_by(TriggerProspect.id.desc())
        .all()
    )
    return {
        "trigger_prospects": [
            trigger_prospect.to_dict() for trigger_prospect in trigger_prospects
        ]
    }, 200


@TRIGGERS_BLUEPRINT.route("/trigger", methods=["POST"])
@require_user
def post_create_trigger(client_sdr_id: int):
    archetype_id = get_request_parameter(
        "archetype_id", request, json=True, required=True, parameter_type=int
    )

    trigger_id = createTrigger(client_sdr_id, archetype_id)

    return {"trigger_id": trigger_id}, 201


@TRIGGERS_BLUEPRINT.route("/trigger/<int:trigger_id>", methods=["POST"])
@require_user
def post_update_trigger(client_sdr_id: int, trigger_id: int):
    emoji = get_request_parameter(
        "emoji", request, json=True, required=False, parameter_type=str
    )
    name = get_request_parameter(
        "name", request, json=True, required=False, parameter_type=str
    )
    description = get_request_parameter(
        "description", request, json=True, required=False, parameter_type=str
    )
    interval_in_minutes = get_request_parameter(
        "interval_in_minutes", request, json=True, required=False, parameter_type=int
    )
    active = get_request_parameter(
        "active", request, json=True, required=False, parameter_type=bool
    )
    blocks = get_request_parameter(
        "blocks", request, json=True, required=False, parameter_type=list
    )
    campaign_id = get_request_parameter(
        "campaign_id", request, json=True, required=False, parameter_type=int
    )

    trigger: Trigger = Trigger.query.filter_by(
        id=trigger_id, client_sdr_id=client_sdr_id
    ).first()
    if not trigger:
        return {"message": "Trigger not found"}, 404

    if campaign_id:
        trigger.client_archetype_id = campaign_id
    if emoji:
        trigger.emoji = emoji
    if name:
        trigger.name = name
    if description:
        trigger.description = description
    if interval_in_minutes:
        trigger.interval_in_minutes = interval_in_minutes
    if active is not None:
        trigger.active = active
    if blocks:
        trigger.blocks = convertBlocksToDict(get_blocks_from_output_dict(blocks))
    db.session.add(trigger)
    db.session.commit()

    return trigger.to_dict(), 200

@TRIGGERS_BLUEPRINT.route("/run_athelas_trigger", methods=["POST"])
def run_athelas_trigger():
    data = experiment_athelas_trigger()

    return data, 200