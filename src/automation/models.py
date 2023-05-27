from email.policy import default

from src.client.models import ClientSDR
from app import db
import sqlalchemy as sa
import enum
import requests
import datetime
import json
import os
import math

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


class PhantomBusterPayload(db.Model):
    __tablename__ = "phantom_buster_payload"

    id = db.Column(db.Integer, primary_key=True)

    client_sdr_id = db.Column(db.Integer, db.ForeignKey("client_sdr.id"))
    pb_payload = db.Column(db.JSON, nullable=True)
    pb_type = db.Column(db.Enum(PhantomBusterType), nullable=True)


class PhantomBusterAgent:
    FETCH_AGENT_URL = (
        url
    ) = "https://api.phantombuster.com/api/v2/agents/fetch?id={phantom_uuid}"
    FETCH_AGENT_OUTPUT = (
        "https://api.phantombuster.com/api/v2/agents/fetch-output?id={phantom_uuid}"
    )
    LAUNCH_AGENT = "https://api.phantombuster.com/api/v1/agent/{phantom_uuid}/launch"

    def __init__(self, id: str):
        self.id = id
        self.api_key = PHANTOMBUSTER_API_KEY

    def run_phantom(self):
        url = self.LAUNCH_AGENT.format(phantom_uuid=self.id)
        headers = {
            "accept": "application/json",
            "X-Phantombuster-Key": self.api_key,
        }
        response = requests.post(url, headers=headers)

        return response

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

        resp = requests.request("POST", url, headers=headers, data=payload)

        return True

    def get_output(self):
        data = self.get_agent_data()
        s3_folder = data.get("s3Folder")
        orgS3Folder = data.get("orgS3Folder")

        return self.get_phantom_buster_payload(s3_folder, orgS3Folder)

    #

    def get_phantom_buster_payload(self, s3Folder, orgS3Folder):

        url = "https://cache1.phantombooster.com/{orgS3Folder}/{s3Folder}/result.json".format(
            orgS3Folder=orgS3Folder, s3Folder=s3Folder
        )

        headers = {"X-Phantombuster-Key": "UapzERoGG1Q7qcY1jmoisJgR6MNJUmdL2w4UcLCtOJQ"}
        response = requests.request("GET", url, headers=headers, data={})

        return response.json()


    #

    def update_launch_schedule(self):

        config: PhantomBusterConfig = PhantomBusterConfig.query.filter(PhantomBusterConfig.phantom_uuid == self.id).first()
        client_sdr: ClientSDR = ClientSDR.query.get(config.client_sdr_id)

        ADDS_PER_LAUNCH = 2
        target = math.ceil(client_sdr.weekly_li_outbound_target / ADDS_PER_LAUNCH)

        dows = ["mon", "tue", "wed", "thu", "fri"]

        if target > 0:
            # max slots that we can have (add more elements to support higher total target SLAs)
            minute_slots = [7, 14, 24, 38, 41, 48, 54]
            hour_slots = [9, 10, 11, 12, 13, 14, 15, 16, 17]

            if target > 45:
                hours = hour_slots
                # Only include the number of minutes that we need to reach our target
                minutes = minute_slots[:math.ceil(target / (len(hours) * len(dows)))]
            else:
                # Only include the number of hours that we need to reach our target
                hours = hour_slots[:math.ceil(target / len(dows))]
                minutes = [41]
        else:
            hours = []
            minutes = []

        url = "https://api.phantombuster.com/api/v2/agents/save"

        payload = {
            "repeatedLaunchTimes": {
                "minute": minutes,
                "hour": hours,
                "day": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31],
                "dow": dows,
                "month": ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"],
                "timezone": client_sdr.timezone,
            },
            "id": self.id
        }
        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "X-Phantombuster-Key": self.api_key
        }

        response = requests.post(url, json=payload, headers=headers)

        #print(response.text)

        return {
            "desired_target": client_sdr.weekly_li_outbound_target,
            "actual_target": len(hours) * len(minutes) * len(dows) * ADDS_PER_LAUNCH,
        }

