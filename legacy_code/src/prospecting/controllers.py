from typing import List

from src.prospecting.models import ExistingContact
from src.prospecting.services import (
    get_prospect_li_history,
    patch_prospect,
    prospect_removal_check_from_csv_payload,
)
from src.prospecting.models import ProspectNote
from src.prospecting.services import send_to_purgatory
from src.prospecting.nylas.services import (
    nylas_send_email,
)
from app import db

from flask import Blueprint, jsonify, request, Response
from src.prospecting.models import (
    Prospect,
    ProspectStatus,
    ProspectChannels,
    ProspectHiddenReason,
)
from datetime import datetime
from src.email_outbound.models import ProspectEmail
from src.email_outbound.models import ProspectEmailOutreachStatus
from src.prospecting.services import (
    mark_prospect_as_removed,
    search_prospects,
    get_prospects,
    batch_mark_prospects_as_sent_outreach,
    mark_prospects_as_queued_for_outreach,
    create_prospect_from_linkedin_link,
    create_prospects_from_linkedin_link_list,
    batch_mark_as_lead,
    update_prospect_status_linkedin,
    update_prospect_status_email,
    validate_prospect_json_payload,
    get_valid_channel_type_choices,
    toggle_ai_engagement,
    send_slack_reminder_for_prospect,
    get_prospects_for_icp,
    create_prospect_note,
    get_prospect_details,
    batch_update_prospect_statuses,
    mark_prospect_reengagement,
    get_prospect_generated_message,
    send_li_referral_outreach_connection,
    add_prospect_referral,
    add_existing_contact,
    get_existing_contacts,
    add_existing_contacts_to_persona,
    get_prospects_for_income_pipeline,
    get_li_message_from_contents,
    add_prospect_message_feedback,
)
from src.prospecting.prospect_status_services import (
    get_valid_next_prospect_statuses,
    prospect_email_unsubscribe,
)
from src.prospecting.upload.services import (
    create_raw_csv_entry_from_json_payload,
    populate_prospect_uploads_from_json_payload,
    collect_and_run_celery_jobs_for_upload,
    run_and_assign_health_score,
)
from src.utils.request_helpers import get_request_parameter

from tqdm import tqdm
import time
from src.prospecting.services import delete_prospect_by_id

from src.utils.random_string import generate_random_alphanumeric
from src.authentication.decorators import require_user
from src.client.models import ClientArchetype, ClientSDR, Client
from src.utils.slack import send_slack_message, URL_MAP
from src.email_outbound.email_store.hunter import (
    find_hunter_emails_for_prospects_under_archetype,
)
from src.prospecting.services import update_prospect_demo_date
from src.message_generation.services import add_generated_msg_queue

PROSPECTING_BLUEPRINT = Blueprint("prospect", __name__)

@PROSPECTING_BLUEPRINT.route("<prospect_id>/email/<email_id>", methods=["GET"])
@require_user
def get_email(client_sdr_id: int, prospect_id: int, email_id: int):

    prospect: Prospect = Prospect.query.filter(Prospect.id == prospect_id).first()
    if not prospect:
        return jsonify({"message": "Prospect not found"}), 404
    elif prospect.client_sdr_id != client_sdr_id:
        return jsonify({"message": "Prospect does not belong to user"}), 403

    prospect_email: ProspectEmail = ProspectEmail.query.get(
        prospect.approved_prospect_email_id
    )
    if not prospect_email:
        return jsonify({"message": "No prospect email data found"}), 404

    try:
        sei = SalesEngagementIntegration(prospect.client_id)

        data = sei.get_email_by_id(email_id=email_id)
    except:
        data = {}

    return (
        jsonify(
            {"message": "Success", "data": data["email"] if data.get("email") else None}
        ),
        200,
    )