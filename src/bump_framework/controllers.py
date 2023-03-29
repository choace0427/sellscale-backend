from app import db

from flask import Blueprint, request, jsonify
from model_import import BumpFramework

BUMP_FRAMEWORK_BLUEPRINT = Blueprint("bump_framework", __name__)
