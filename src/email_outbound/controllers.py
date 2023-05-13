from src.client.models import ClientSDR, Client
from src.email_outbound.services import get_sequences, add_sequence
from src.authentication.decorators import require_user
from app import db
from src.utils.slack import send_slack_message
from src.utils.slack import URL_MAP

from flask import Blueprint, request, jsonify
from src.message_generation.services import (
    mark_prospect_email_approved,
)
from src.email_outbound.services import (
    batch_update_emails,
    batch_mark_prospect_email_sent,
    create_sales_engagement_interaction_raw,
    collect_and_update_status_from_ss_data,
)
from src.email_outbound.outreach_io.services import (
    validate_outreach_csv_payload,
    convert_outreach_payload_to_ss,
)
from src.utils.request_helpers import get_request_parameter
from tqdm import tqdm
from src.message_generation.services import (
    wipe_prospect_email_and_generations_and_research,
)

EMAIL_GENERATION_BLUEPRINT = Blueprint("email_generation", __name__)


@EMAIL_GENERATION_BLUEPRINT.route("/approve", methods=["POST"])
def approve():
    prospect_email_id = get_request_parameter(
        "prospect_email_id", request, json=True, required=True
    )

    success = mark_prospect_email_approved(prospect_email_id=prospect_email_id)
    if success:
        return "OK", 200
    return "Could not approve email.", 400


@EMAIL_GENERATION_BLUEPRINT.route("/batch/mark_sent", methods=["POST"])
def batch_mark_sent():
    prospect_ids = get_request_parameter(
        "prospect_ids", request, json=True, required=True
    )
    campaign_id = get_request_parameter(
        "campaign_id", request, json=True, required=True
    )

    prospect_ids = [int(prospect_id) for prospect_id in prospect_ids]
    campaign_id = int(campaign_id)

    # TODO: something with this message later
    broadcasted = batch_mark_prospect_email_sent(
        prospect_ids=prospect_ids, campaign_id=campaign_id
    )

    return "OK", 200


@EMAIL_GENERATION_BLUEPRINT.route("/wipe_prospect_email_and_research", methods=["POST"])
def wipe_prospect_email_and_research():
    prospect_id = get_request_parameter(
        "prospect_id", request, json=True, required=True
    )
    success = wipe_prospect_email_and_generations_and_research(prospect_id=prospect_id)
    if success:
        return "OK", 200
    return "Failed to wipe", 400


@EMAIL_GENERATION_BLUEPRINT.route("/batch_update_emails", methods=["POST"])
def post_batch_update_emails():
    payload: dict = get_request_parameter("payload", request, json=True, required=True)
    success, message = batch_update_emails(payload=payload)
    if success:
        return message, 200
    return message, 400


@EMAIL_GENERATION_BLUEPRINT.route("/update_status/csv", methods=["POST"])
def update_status_from_csv_payload():
    csv_payload: list = get_request_parameter(
        "csv_payload", request, json=True, required=True
    )
    client_id: int = get_request_parameter(
        "client_id", request, json=True, required=True
    )
    client_sdr_id: int = get_request_parameter(
        "client_sdr_id", request, json=True, required=True
    )
    payload_source: str = get_request_parameter(
        "payload_source", request, json=True, required=True
    )

    # Validate the payload
    if payload_source == "OUTREACH":
        validated, message = validate_outreach_csv_payload(csv_payload)
        if not validated:
            return message, 400

    # Create raw entry
    sei_raw_id = create_sales_engagement_interaction_raw(
        client_id,
        client_sdr_id,
        csv_payload,
        payload_source,
    )
    if sei_raw_id is None:
        return "Failed to ingest third-party CSV.", 400
    elif sei_raw_id == -1:
        return "This third-party CSV already exists, check for duplicate upload?", 400

    # Depending on csv type, convert raw entry into SS data (celery)
    # Then chain update status using SS data (celery)
    if payload_source == "OUTREACH":
        convert_outreach_payload_to_ss.apply_async(
            args=[client_id, client_sdr_id, sei_raw_id, csv_payload],
            link=collect_and_update_status_from_ss_data.s(),
        )

    return "Status update is in progress", 200


@EMAIL_GENERATION_BLUEPRINT.route("/add_sequence", methods=["POST"])
@require_user
def post_add_sequence(client_sdr_id: int):
    title = get_request_parameter(
        "title", request, json=True, required=True, parameter_type=str
    )
    archetype_id = get_request_parameter(
        "archetype_id", request, json=True, required=True, parameter_type=int
    )
    data = get_request_parameter(
        "data", request, json=True, required=True, parameter_type=list
    )

    result = add_sequence(title, client_sdr_id, archetype_id, data)

    client_sdr = ClientSDR.query.get(client_sdr_id)
    client_id = client_sdr.client_id
    client: Client = Client.query.get(client_id)

    steps_str = ""
    for i, step in enumerate(data):
        steps_str += "{num}. {subject} \n {body}\n\n".format(
            subject=step["subject"], body=step["body"], num=i + 1
        )

    send_slack_message(
        message="*Sequence for Outreach*\nFor {client_sdr_name} from {client_company} :tada:\n\n_Steps:_\n{steps_str}".format(
            client_sdr_name=client_sdr.name,
            client_company=client.company,
            steps_str=steps_str,
        ),
        webhook_urls=[URL_MAP["outreach-send-to"]],
    )

    return result


@EMAIL_GENERATION_BLUEPRINT.route("/all_sequences", methods=["GET"])
@require_user
def get_all_sequences(client_sdr_id: int):
    archetype_id = get_request_parameter(
        "archetype_id", request, json=False, required=True
    )

    return get_sequences(client_sdr_id, archetype_id)
