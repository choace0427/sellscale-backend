from app import db

from flask import Blueprint, jsonify, request

QUESTION_ENRICHMENT_BLUEPRINT = Blueprint("prospect", __name__)

@QUESTION_ENRICHMENT_BLUEPRINT.route("/echo", methods=["GET"])
def echo():
    return jsonify({"message": "echo"})