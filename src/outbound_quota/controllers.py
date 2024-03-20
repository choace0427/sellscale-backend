from flask import Blueprint
from src.outbound_quota.services import capture_outbound_quota_snapshot


OUTBOUND_QUOTA_BLUEPRINT = Blueprint("/outbound_quota", __name__)


def filler_func():
    # capture_outbound_quota_snapshot
    pass
