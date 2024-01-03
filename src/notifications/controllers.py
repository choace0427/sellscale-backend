from flask import Blueprint
from src.notifications.models import OperatorNotification

NOTIFICATION_BLUEPRINT = Blueprint("notification", __name__)


@NOTIFICATION_BLUEPRINT.route("/")
def index():
    return "OK", 200
