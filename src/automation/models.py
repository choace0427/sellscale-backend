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

    def get_agent_data(self):
        url = self.FETCH_AGENT_URL.format(phantom_uuid=self.id)
        payload = {}
        headers = {
            "X-Phantombuster-Key": self.api_key,
            "accept": "application/json",
        }
        response = requests.request("GET", url, headers=headers, data=payload)
        data: dict = response.json()
        return data

    def get_last_run_date(self):
        data = self.get_agent_data()
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

    def get_output(self):
        data = self.get_agent_data()
        s3_folder = data.get("s3Folder")
        orgS3Folder = data.get("orgS3Folder")

        return self.get_phantom_buster_payload(s3_folder, orgS3Folder)

    def get_phantom_buster_payload(self, s3Folder, orgS3Folder):
        url = "https://phantombuster.s3.amazonaws.com/{orgS3Folder}/{s3Folder}/result.json".format(
            orgS3Folder=orgS3Folder, s3Folder=s3Folder
        )

        headers = {"X-Phantombuster-Key": "UapzERoGG1Q7qcY1jmoisJgR6MNJUmdL2w4UcLCtOJQ"}
        response = requests.request("GET", url, headers=headers, data={})

        return json.loads(response.text)
