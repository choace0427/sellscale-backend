from email.policy import default
from typing import Optional

from sqlalchemy.dialects.postgresql import JSONB

from src.client.models import ClientArchetype, ClientSDR
from app import db
import sqlalchemy as sa
import enum
import requests
import datetime
import json
import os
import math

from src.client.sdr.services_client_sdr import (
    LINKEDIN_WARM_THRESHOLD,
    get_sla_schedules_for_sdr,
)
from src.utils.datetime.dateutils import get_current_monday_friday

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


class PhantomBusterSalesNavigatorConfig(db.Model):
    __tablename__ = "phantom_buster_sales_navigator_config"

    id = db.Column(db.Integer, primary_key=True)

    client_id = db.Column(db.Integer, db.ForeignKey("client.id"), nullable=True)
    client_sdr_id = db.Column(db.Integer, db.ForeignKey("client_sdr.id"), nullable=True)
    common_pool = db.Column(db.Boolean, default=False)

    phantom_name = db.Column(db.String)
    phantom_uuid = db.Column(db.String)
    linkedin_session_cookie = db.Column(db.String)

    daily_trigger_count = db.Column(db.Integer, default=0)  # 4 triggers per day
    daily_prospect_count = db.Column(db.Integer, default=0)  # 600 prospects per day
    in_use = db.Column(db.Boolean, default=False)

    last_run_date = db.Column(db.DateTime, nullable=True)
    error_message = db.Column(db.String, nullable=True)


class SalesNavigatorLaunchStatus(enum.Enum):
    NEEDS_AGENT = "NEEDS_AGENT"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class PhantomBusterSalesNavigatorLaunch(db.Model):
    __tablename__ = "phantom_buster_sales_navigator_launch"

    id = db.Column(db.Integer, primary_key=True)
    sales_navigator_config_id = db.Column(
        db.Integer,
        db.ForeignKey("phantom_buster_sales_navigator_config.id"),
        nullable=True,
    )
    client_sdr_id = db.Column(db.Integer, db.ForeignKey("client_sdr.id"))
    sales_navigator_url = db.Column(db.String)
    scrape_count = db.Column(db.Integer, default=0)

    status = db.Column(
        db.Enum(SalesNavigatorLaunchStatus), default=SalesNavigatorLaunchStatus.QUEUED
    )
    pb_container_id = db.Column(db.String, nullable=True)
    result_raw = db.Column(db.JSON, nullable=True)
    result_processed = db.Column(db.JSON, nullable=True)

    launch_date = db.Column(db.DateTime, nullable=True)
    error_message = db.Column(db.String, nullable=True)

    process_type = db.Column(db.String, nullable=True)

    name = db.Column(db.String, nullable=True)

    client_archetype_id = db.Column(db.Integer, db.ForeignKey("client_archetype.id"))

    account_filters_url = db.Column(db.String, nullable=True)

    def to_dict(self) -> dict:
        # Result is too large and should not be returned in the frontend unless during download
        # instead we will return a boolean to determine if the result is available to download

        return {
            "id": self.id,
            "sales_navigator_config_id": self.sales_navigator_config_id,
            "client_sdr_id": self.client_sdr_id,
            "sales_navigator_url": self.sales_navigator_url,
            "scrape_count": self.scrape_count,
            "status": self.status.value,
            "pb_container_id": self.pb_container_id,
            "result_available": (
                True if self.result_raw and self.result_processed else False
            ),
            "launch_date": self.launch_date,
            "name": self.name,
            "client_archetype_id": self.client_archetype_id,
            "account_filters_url": self.account_filters_url,
            "archetype": (
                ClientArchetype.query.get(self.client_archetype_id).archetype
                if self.client_archetype_id
                else None
            ),
            "process_type": self.process_type,
        }


class PhantomBusterPayload(db.Model):
    __tablename__ = "phantom_buster_payload"

    id = db.Column(db.Integer, primary_key=True)

    client_sdr_id = db.Column(db.Integer, db.ForeignKey("client_sdr.id"))
    pb_payload = db.Column(db.JSON, nullable=True)
    pb_type = db.Column(db.Enum(PhantomBusterType), nullable=True)
    status = db.Column(db.String, nullable=True)
    error_message = db.Column(db.String, nullable=True)


class PhantomBusterAgent:
    FETCH_AGENT_URL = url = (
        "https://api.phantombuster.com/api/v2/agents/fetch?id={phantom_uuid}"
    )
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

    def get_status(self):
        url = self.FETCH_AGENT_OUTPUT.format(phantom_uuid=self.id)
        payload = {}
        headers = {
            "X-Phantombuster-Key": self.api_key,
            "accept": "application/json",
        }

        response = requests.request("GET", url, headers=headers, data=payload)
        data = response.json()

        output = data.get("output")
        status = data.get("status")

        if output and "Session cookie not valid" in output:
            return "error_invalid_cookie"
        elif output and "Process finished with an error" in output:
            return "error_unknown"

        return status

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

    def get_phantom_buster_payload(self, s3Folder, orgS3Folder):
        url = "https://cache1.phantombooster.com/{orgS3Folder}/{s3Folder}/result.json".format(
            orgS3Folder=orgS3Folder, s3Folder=s3Folder
        )

        headers = {"X-Phantombuster-Key": self.api_key}
        response = requests.request("GET", url, headers=headers, data={})

        return response.json()

    def get_output_by_container_id(self, container_id: str) -> dict:
        url = "https://api.phantombuster.com/api/v2/containers/fetch-result-object?id={container_id}".format(
            container_id=container_id
        )

        headers = {"X-Phantombuster-Key": self.api_key}
        response = requests.request("GET", url, headers=headers)
        response = response.json()
        result_object = response.get("resultObject", None)
        if result_object:
            result = json.loads(result_object)
            return result
        return None

    def update_launch_schedule(self, custom_volume: Optional[int] = None):
        config: PhantomBusterConfig = PhantomBusterConfig.query.filter(
            PhantomBusterConfig.phantom_uuid == self.id
        ).first()
        client_sdr: ClientSDR = ClientSDR.query.get(config.client_sdr_id)

        # Get SLA schedule
        monday, friday = get_current_monday_friday(datetime.datetime.now())
        schedules: list[dict] = get_sla_schedules_for_sdr(
            client_sdr_id=client_sdr.id, start_date=monday, end_date=friday
        )
        schedule = schedules[0] if len(schedules) > 0 else {}
        volume = schedule.get("linkedin_volume", client_sdr.weekly_li_outbound_target)

        # If custom volume is provided, use that instead
        if custom_volume != None:
            volume = custom_volume

        ADDS_PER_LAUNCH = 2
        target = math.ceil(volume / ADDS_PER_LAUNCH)

        # Check if the schedule qualifies the SDR to be "fully warm"
        if volume >= client_sdr.weekly_li_outbound_target:
            client_sdr.warmup_linkedin_complete = True
        else:
            client_sdr.warmup_linkedin_complete = False
        db.session.commit()

        dows = ["mon", "tue", "wed", "thu", "fri"]

        if target > 0:
            # max slots that we can have (add more elements to support higher total target SLAs)
            minute_slots = [7, 14, 24, 38, 41, 48, 54]
            hour_slots = [9, 10, 11, 12, 13, 14, 15, 16, 17]

            if target > 45:
                hours = hour_slots
                # Only include the number of minutes that we need to reach our target
                minutes = minute_slots[: math.ceil(target / (len(hours) * len(dows)))]
            else:
                # Only include the number of hours that we need to reach our target
                hours = hour_slots[: math.ceil(target / len(dows))]
                minutes = [41]
        else:
            hours = []
            minutes = []

        url = "https://api.phantombuster.com/api/v2/agents/save"

        payload = {
            "repeatedLaunchTimes": {
                "minute": minutes,
                "hour": hours,
                "day": [
                    1,
                    2,
                    3,
                    4,
                    5,
                    6,
                    7,
                    8,
                    9,
                    10,
                    11,
                    12,
                    13,
                    14,
                    15,
                    16,
                    17,
                    18,
                    19,
                    20,
                    21,
                    22,
                    23,
                    24,
                    25,
                    26,
                    27,
                    28,
                    29,
                    30,
                    31,
                ],
                "dow": dows,
                "month": [
                    "jan",
                    "feb",
                    "mar",
                    "apr",
                    "may",
                    "jun",
                    "jul",
                    "aug",
                    "sep",
                    "oct",
                    "nov",
                    "dec",
                ],
                "timezone": client_sdr.timezone,
            },
            "id": self.id,
        }
        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "X-Phantombuster-Key": self.api_key,
        }

        response = requests.post(url, json=payload, headers=headers)

        # print(response.text)

        return {
            "desired_target": client_sdr.weekly_li_outbound_target,
            "actual_target": len(hours) * len(minutes) * len(dows) * ADDS_PER_LAUNCH,
        }


class ProcessQueueStatus(enum.Enum):
    QUEUED = "QUEUED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETE = "COMPLETE"  # This should, in theory, never be used
    RETRY = "RETRY"
    FAILED = "FAILED"


class ProcessQueue(db.Model):
    """A queue for processing various tasks

    Useful for any kind of scheduled processes and async process pipeline
    """

    __tablename__ = "process_queue"

    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String, nullable=False)
    meta_data = db.Column(JSONB, nullable=True)
    execution_date = db.Column(db.DateTime, nullable=False)
    executed_at = db.Column(db.DateTime, nullable=True)
    status = db.Column(
        db.Enum(ProcessQueueStatus), default=ProcessQueueStatus.QUEUED, nullable=True
    )
    fail_reason = db.Column(db.String, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type,
            "meta_data": self.meta_data,
            "execution_date": str(self.execution_date),
            "executed_at": str(self.executed_at),
            "created_at": str(self.created_at),
            "status": self.status.value if self.status else None,
            "fail_reason": self.fail_reason,
        }


class ProcessQueueFailedJob(db.Model):

    __tablename__ = "process_queue_failed_job"

    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String, nullable=False)
    meta_data = db.Column(JSONB, nullable=True)
    execution_date = db.Column(db.DateTime, nullable=False)
    executed_at = db.Column(db.DateTime, nullable=True)
    status = db.Column(
        db.Enum(ProcessQueueStatus), default=ProcessQueueStatus.QUEUED, nullable=True
    )
    fail_reason = db.Column(db.String, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type,
            "meta_data": self.meta_data,
            "execution_date": str(self.execution_date),
            "executed_at": str(self.executed_at),
            "created_at": str(self.created_at),
            "status": self.status.value if self.status else None,
            "fail_reason": self.fail_reason,
        }


class ApolloScraperJob(db.Model):

    __tablename__ = "apollo_scraper_job"

    id = db.Column(db.Integer, primary_key=True)
    client_sdr_id = db.Column(
        db.Integer, db.ForeignKey("client_sdr.id"), nullable=False
    )
    archetype_id = db.Column(
        db.Integer, db.ForeignKey("client_archetype.id"), nullable=True
    )
    segment_id = db.Column(db.Integer, db.ForeignKey("segment.id"), nullable=True)

    name = db.Column(db.String, nullable=False)
    page_num = db.Column(db.Integer, nullable=False)
    page_size = db.Column(db.Integer, nullable=False)
    max_pages = db.Column(db.Integer, nullable=True)

    filters = db.Column(JSONB, nullable=True)
    active = db.Column(db.Boolean, default=True)

    def to_dict(self) -> dict:

        from src.segment.models import Segment

        segment: Segment = Segment.query.get(self.segment_id)

        from src.client.models import ClientArchetype

        archetype: ClientArchetype = ClientArchetype.query.get(self.archetype_id)

        return {
            "id": self.id,
            "archetype_id": self.archetype_id,
            "archetype_name": archetype.archetype if archetype else None,
            "segment_id": self.segment_id,
            "segment_name": segment.segment_title if segment else None,
            "name": self.name,
            "page_num": self.page_num,
            "page_size": self.page_size,
            "max_pages": self.max_pages,
            "filters": self.filters,
            "active": self.active,
        }
