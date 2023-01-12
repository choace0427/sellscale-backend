from email.policy import default
from app import db
import sqlalchemy as sa
import enum
import requests
import datetime
import json
import os

PHANTOMBUSTER_API_KEY = os.environ.get("PHANTOMBUSTER_API_KEY")

class PhantomBusterType(enum.Enum):
    INBOX_SCRAPER = "INBOX_SCRAPER"
    OUTBOUND_ENGINE = "OUTBOUND_ENGINE"


class PhantomBusterConfig(db.Model):
    __tablename__ = "phantom_buster_config"

    id = db.Column(db.Integer, primary_key=True)

    client_id = db.Column(db.Integer, db.ForeignKey("client.id"))
    client_sdr_id = db.Column(db.Integer, db.ForeignKey("client_sdr.id"))

    pb_type = db.Column(db.Enum(PhantomBusterType), nullable=True)

    google_sheets_uuid = db.Column(db.String, nullable=True)

    phantom_name = db.Column(db.String)
    phantom_uuid = db.Column(db.String)

    last_run_date = db.Column(db.DateTime, nullable=True)
    error_message = db.Column(db.String, nullable=True)


class PhantomBusterAgent:
    FETCH_AGENT_URL = (
        url
    ) = "https://api.phantombuster.com/api/v2/agents/fetch?id={phantom_uuid}"
    FETCH_AGENT_OUTPUT = (
        "https://api.phantombuster.com/api/v2/agents/fetch-output?id={phantom_uuid}"
    )

    def __init__(self, id: int):
        self.id = id
        self.api_key = PHANTOMBUSTER_API_KEY

    def get_last_run_date(self):
        url = self.FETCH_AGENT_URL.format(phantom_uuid=self.id)
        payload = {}
        headers = {
            "X-Phantombuster-Key": self.api_key,
            "accept": "application/json",
        }
        response = requests.request("GET", url, headers=headers, data=payload)
        data: dict = response.json()
        return datetime.datetime.fromtimestamp(data.get("updatedAt") / 1000.0)

    def get_error_message(self):
        url = self.FETCH_AGENT_OUTPUT.format(phantom_uuid=self.id)
        payload = {}
        headers = {
            "X-Phantombuster-Key": self.api_key,
            "accept": "application/json",
        }

        response = requests.request("GET", url, headers=headers, data=payload)
        data = response.json()
        output = data.get("output")

        if "Session cookie not valid" in output:
            return "Session cookie not valid anymore. Please update the cookie."
        return None

    def get_arguments(self):
        url = self.FETCH_AGENT_URL.format(phantom_uuid=self.id)
        payload = {}
        headers = {
            "X-Phantombuster-Key": self.api_key,
            "accept": "application/json",
        }
        response = requests.request("GET", url, headers=headers, data=payload)
        data: dict = response.json()

        arguments = json.loads(data.get("argument", ""))

        return arguments

    def update_argument(self, key: str, new_value: str):
        arguments = self.get_arguments()
        arguments[key] = new_value

        new_arguments = json.dumps(arguments)
        url = "https://api.phantombuster.com/api/v2/agents/save"

        payload = json.dumps(
            {
                "id": self.id,
                "argument": new_arguments,
            }
        )
        headers = {
            "X-Phantombuster-Key": self.api_key,
            "accept": "application/json",
            "Content-Type": "application/json",
        }

        requests.request("POST", url, headers=headers, data=payload)
        return True
