from flask import Blueprint, request, jsonify
from src.company.services import (
  company_backfill,
)
from src.authentication.decorators import require_user
from src.utils.request_helpers import get_request_parameter
from src.utils.slack import send_slack_message, URL_MAP
from app import db
import os

COMPANY_BLUEPRINT = Blueprint("company", __name__)

@COMPANY_BLUEPRINT.route("/backfill", methods=["POST"])
@require_user
def post_company_backfill(client_sdr_id: int):
  
  c_min = get_request_parameter(
    "min", request, json=True, required=True, parameter_type=int
  )
  c_max = get_request_parameter(
    "max", request, json=True, required=True, parameter_type=int
  )

  processed_count = company_backfill(c_min, c_max)

  return jsonify({
    'status': 'success',
    'data': {
      'processed_count': processed_count,
    },
  }), 200


    
  
