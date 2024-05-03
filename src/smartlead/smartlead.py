import csv
from typing import Optional
import requests
from io import StringIO
import json
import os
import time


class EmailWarming:
    def __init__(
        self,
        id: int,
        name: str,
        email: str,
        status: str,
        total_sent: int,
        total_spam: int,
        warmup_reputation: str,
        sent_count: int,
        spam_count: int,
        inbox_count: int,
        warmup_email_received_count: int,
        stats_by_date: list,
    ):
        self.id = id
        self.name = name
        self.email = email
        self.status = status
        self.total_sent = total_sent
        self.total_spam = total_spam
        self.warmup_reputation = warmup_reputation
        self.sent_count = sent_count
        self.spam_count = spam_count
        self.inbox_count = inbox_count
        self.warmup_email_received_count = warmup_email_received_count
        self.stats_by_date = stats_by_date

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "status": self.status,
            "total_sent": self.total_sent,
            "total_spam": self.total_spam,
            "warmup_reputation": self.warmup_reputation,
            "sent_count": self.sent_count,
            "spam_count": self.spam_count,
            "inbox_count": self.inbox_count,
            "warmup_email_received_count": self.warmup_email_received_count,
            "stats_by_date": self.stats_by_date,
        }


class Lead:
    def __init__(
        self,
        first_name: str,
        last_name: str,
        email: str,
        phone_number: int,
        company_name: str,
        website: str,
        location: str,
        custom_fields: dict,
        linkedin_profile: str,
        company_url: str,
    ):
        self.first_name = first_name
        self.last_name = last_name
        self.email = email
        self.phone_number = phone_number
        self.company_name = company_name
        self.website = website
        self.location = location
        self.custom_fields = custom_fields
        self.linkedin_profile = linkedin_profile
        self.company_url = company_url

    def to_dict(self):
        return {
            "first_name": self.first_name,
            "last_name": self.last_name,
            "email": self.email,
            "phone_number": self.phone_number,
            "company_name": self.company_name,
            "website": self.website,
            "location": self.location,
            "custom_fields": self.custom_fields,
            "linkedin_profile": self.linkedin_profile,
            "company_url": self.company_url,
        }


class SmartleadCampaignStatisticEntry:
    """This class represents a data entry from the Smartlead Campaign Statistics API."""

    def __init__(
        self,
        lead_name: Optional[str] = None,
        lead_email: Optional[str] = None,
        lead_category: Optional[str] = None,
        sequence_number: Optional[int] = None,
        stats_id: Optional[int] = None,
        email_campaign_seq_id: Optional[int] = None,
        seq_variant_id: Optional[int] = None,
        email_subject: Optional[str] = None,
        email_message: Optional[str] = None,
        sent_time: Optional[str] = None,
        open_time: Optional[str] = None,
        click_time: Optional[str] = None,
        reply_time: Optional[str] = None,
        open_count: Optional[int] = None,
        click_count: Optional[int] = None,
        is_unsubscribed: Optional[bool] = None,
        is_bounced: Optional[bool] = None,
    ):
        self.lead_name = lead_name
        self.lead_email = lead_email
        self.lead_category = lead_category
        self.sequence_number = sequence_number
        self.stats_id = stats_id
        self.email_campaign_seq_id = email_campaign_seq_id
        self.seq_variant_id = seq_variant_id
        self.email_subject = email_subject
        self.email_message = email_message
        self.sent_time = sent_time
        self.open_time = open_time
        self.click_time = click_time
        self.reply_time = reply_time
        self.open_count = open_count
        self.click_count = click_count
        self.is_unsubscribed = is_unsubscribed
        self.is_bounced = is_bounced

    def to_dict(self):
        return {
            "lead_name": self.lead_name,
            "lead_email": self.lead_email,
            "lead_category": self.lead_category,
            "sequence_number": self.sequence_number,
            "stats_id": self.stats_id,
            "email_campaign_seq_id": self.email_campaign_seq_id,
            "seq_variant_id": self.seq_variant_id,
            "email_subject": self.email_subject,
            "email_message": self.email_message,
            "sent_time": self.sent_time,
            "open_time": self.open_time,
            "click_time": self.click_time,
            "reply_time": self.reply_time,
            "open_count": self.open_count,
            "click_count": self.click_count,
            "is_unsubscribed": self.is_unsubscribed,
            "is_bounced": self.is_bounced,
        }


class Smartlead:
    DELAY_SECONDS = 1.0
    BASE_URL = "https://server.smartlead.ai/api/v1"

    WEBHOOK_URLS = [
        {
            "name": "Email Sent",
            "url": "https://sellscale-api-prod.onrender.com/smartlead/webhooks/email_sent",
            "event_types": ["EMAIL_SENT"],
        },
        {
            "name": "Email Opened",
            "url": "https://sellscale-api-prod.onrender.com/smartlead/webhooks/email_opened",
            "event_types": ["EMAIL_OPEN"],
        },
        {
            "name": "Email Bounced",
            "url": "https://sellscale-api-prod.onrender.com/smartlead/webhooks/email_bounced",
            "event_types": ["EMAIL_BOUNCE"],
        },
        {
            "name": "Email Replied",
            "url": "https://sellscale-api-prod.onrender.com/smartlead/webhooks/email_replied",
            "event_types": ["EMAIL_REPLY"],
        },
        {
            "name": "Email Link Clicked",
            "url": "https://sellscale-api-prod.onrender.com/smartlead/webhooks/email_link_clicked",
            "event_types": ["EMAIL_LINK_CLICK"],
        },
    ]

    LEAD_CATEGORIES = {
        "Interested": 1,
        "Meeting Request": 2,
        "Not Interested": 3,
        "Do Not Contact": 4,
        "Information Request": 5,
        "Out of Office": 6,
        "Wrong Person": 7,
    }

    def __init__(self):
        self.api_key = os.environ.get("SMARTLEAD_API_KEY")

    def create_campaign(self, campaign_name: str):
        url = f"{self.BASE_URL}/campaigns/create?api_key={self.api_key}"
        data = {"name": campaign_name}
        headers = {"Content-Type": "application/json"}
        response = requests.post(url, headers=headers, data=json.dumps(data))
        if response.status_code == 429:
            time.sleep(self.DELAY_SECONDS)
            return self.create_campaign(campaign_name)
        return response.json()

    def update_campaign_general_settings(self, campaign_id: int, settings: dict):
        """Settings can look like this:

        ```
        settings = {
            "track_settings": ["DONT_TRACK_EMAIL_OPEN"], // allowed values are -> DONT_TRACK_EMAIL_OPEN | DONT_TRACK_LINK_CLICK | DONT_TRACK_REPLY_TO_AN_EMAIL
            "stop_lead_settings": "REPLY_TO_AN_EMAIL", // allowed values are -> CLICK_ON_A_LINK | OPEN_AN_EMAIL
            "unsubscribe_text": "",
            "send_as_plain_text": false,
            "follow_up_percentage": 100, // max allowed 100 min allowed 0
            "client_id": 33 // leave as null if not needed,
            "enable_ai_esp_matching": true // by default is false
        }
        ```
        """
        url = f"{self.BASE_URL}/campaigns/{campaign_id}/settings?api_key={self.api_key}"
        data = settings
        headers = {"Content-Type": "application/json"}
        response = requests.post(url, headers=headers, data=json.dumps(data))
        if response.status_code == 429:
            time.sleep(self.DELAY_SECONDS)
            return self.update_campaign_settings(campaign_id, settings)
        return response.json()

    def fetch_campaign_sequence(self, campaign_id: int):
        url = (
            f"{self.BASE_URL}/campaigns/{campaign_id}/sequences?api_key={self.api_key}"
        )
        response = requests.get(url)
        if response.status_code == 429:
            time.sleep(self.DELAY_SECONDS)
            return self.fetch_campaign_sequence(campaign_id)
        return response.json()

    def save_campaign_sequence(self, campaign_id: int, sequences: list):
        """Sequences should look like this:

        ```
        sequences = [
            {
                "seq_delay_details": {"delay_in_days": 20},
                "seq_number": 1,
                "subject": "{{Subject_Line}}",
                "email_body": "{{Body_1}}",
            },
            {
                "seq_delay_details": {"delay_in_days": 20},
                "seq_number": 2,
                "subject": "",
                "email_body": "{{Body_2}}",
            },
        ]
        ```
        """
        url = (
            f"{self.BASE_URL}/campaigns/{campaign_id}/sequences?api_key={self.api_key}"
        )
        data = {"sequences": sequences}
        headers = {"Content-Type": "application/json"}
        response = requests.post(url, headers=headers, data=json.dumps(data))
        if response.status_code == 429:
            time.sleep(self.DELAY_SECONDS)
            return self.save_campaign_sequence(campaign_id, sequences)
        return response.json()

    def add_email_account_to_campaign(
        self, campaign_id: int, email_account_ids: list[int]
    ):
        url = f"{self.BASE_URL}/campaigns/{campaign_id}/email-accounts?api_key={self.api_key}"

        data = {"email_account_ids": email_account_ids}
        headers = {"Content-Type": "application/json"}
        response = requests.post(url, headers=headers, data=json.dumps(data))
        if response.status_code == 429:
            time.sleep(self.DELAY_SECONDS)
            return self.add_email_account_to_campaign(campaign_id, email_account_ids)
        return response.json()

    def update_email_account(self, email_account_id: int, max_email_per_day: int):
        url = (
            f"{self.BASE_URL}/email-accounts/{email_account_id}?api_key={self.api_key}"
        )
        data = {"max_email_per_day": max_email_per_day}
        headers = {"Content-Type": "application/json"}
        response = requests.post(url, headers=headers, data=json.dumps(data))
        if response.status_code == 429:
            time.sleep(self.DELAY_SECONDS)
            return self.update_email_account(email_account_id, max_email_per_day)
        return response.json()

    def add_all_campaign_webhooks(
        self, campaign_id: int, event_type: Optional[str] = None
    ):
        def add_campaign_webhook(
            campaign_id: int, name: str, webhook_url: str, event_types: list
        ):
            url = f"{self.BASE_URL}/campaigns/{campaign_id}/webhooks?api_key={self.api_key}"
            data = {
                "name": name,
                "webhook_url": webhook_url,
                "event_types": event_types,
            }
            headers = {"Content-Type": "application/json"}
            response = requests.post(url, headers=headers, data=json.dumps(data))
            if response.status_code == 429:
                time.sleep(self.DELAY_SECONDS)
                return add_campaign_webhook(campaign_id, name, url, event_types)
            return response.json()

        responses = []

        for url_package in self.WEBHOOK_URLS:
            if event_type and url_package["event_types"][0] != event_type:
                continue
            response = add_campaign_webhook(
                campaign_id=campaign_id,
                name=url_package["name"],
                webhook_url=url_package["url"],
                event_types=url_package["event_types"],
            )
            responses.append(response)

        return responses

    def update_campaign_schedule(self, campaign_id: int, schedule: dict):
        """Schedule should look like this:

        ```
        campaign_schedule = {
            "timezone": "America/Los_Angeles",
            "days_of_the_week": [1, 2, 3],  # [0,1,2,3,4,5,6] 0 is Sunday
            "start_hour": "09:00",  # "09:00"
            "end_hour": "18:00",  # "18:00"
            "min_time_btw_emails": 10,  # time in minutes between emails
            "max_new_leads_per_day": 20,  # max new leads per day
            "schedule_start_time": datetime.now().isoformat(),  # Standard ISO format accepted
        }
        ```
        """
        url = f"{self.BASE_URL}/campaigns/{campaign_id}/schedule?api_key={self.api_key}"
        data = schedule
        headers = {"Content-Type": "application/json"}
        response = requests.post(url, headers=headers, data=json.dumps(data))
        if response.status_code == 429:
            time.sleep(self.DELAY_SECONDS)
            return self.update_campaign_schedule(campaign_id, schedule)
        return response.json()

    def post_campaign_status(self, campaign_id: int, status: str):
        """Status can either be: "PAUSED" | "STOPPED" | "START" """
        url = f"{self.BASE_URL}/campaigns/{campaign_id}/status?api_key={self.api_key}"
        data = {"status": status}
        headers = {"Content-Type": "application/json"}
        response = requests.post(url, headers=headers, data=json.dumps(data))
        if response.status_code == 429:
            time.sleep(self.DELAY_SECONDS)
            return self.post_campaign_status(campaign_id, status)
        return response.json()

    def add_leads_to_campaign_by_id(self, campaign_id: int, lead_list: list):
        url = f"{self.BASE_URL}/campaigns/{campaign_id}/leads?api_key={self.api_key}"
        data = {"lead_list": lead_list}
        headers = {"Content-Type": "application/json"}
        response = requests.post(url, headers=headers, data=json.dumps(data))
        if response.status_code == 429:
            time.sleep(self.DELAY_SECONDS)
            return self.add_leads_to_campaign_by_id(campaign_id, lead_list)
        return response.json()

    def reply_to_lead(
        self,
        campaign_id: int,
        email_stats_id: str,
        email_body: str,
        reply_message_id: str,
        reply_email_time: str,
        reply_email_body: str,
        cc: Optional[list],
    ):
        url = f"{self.BASE_URL}/campaigns/{campaign_id}/reply-email-thread?api_key={self.api_key}"
        data = {
            "email_stats_id": email_stats_id,
            "email_body": email_body,
            "reply_message_id": reply_message_id,
            "reply_email_time": reply_email_time,
            "reply_email_body": reply_email_body,
            "cc": ",".join(cc) if cc else None,
        }
        headers = {"Content-Type": "application/json"}
        response = requests.post(url, headers=headers, data=json.dumps(data))
        if response.status_code == 429:
            time.sleep(self.DELAY_SECONDS)
            return self.reply_to_lead(
                campaign_id,
                email_stats_id,
                email_body,
                reply_message_id,
                reply_email_time,
                reply_email_body,
                cc,
            )
        if response.status_code == 200:
            return True

    def get_lead_categories(self):
        url = f"{self.BASE_URL}/leads/fetch-categories?api_key={self.api_key}"
        response = requests.get(url)
        if response.status_code == 429:
            time.sleep(self.DELAY_SECONDS)
            return self.get_lead_categories()
        return response.json()

    def get_lead_by_email_address(self, email_address):
        url = f"{self.BASE_URL}/leads/?api_key={self.api_key}&email={email_address}"
        response = requests.get(url)
        if response.status_code == 429:
            time.sleep(self.DELAY_SECONDS)
            return self.get_lead_by_email_address(email_address)
        return response.json()

    def post_update_lead_category(
        self,
        campaign_id: int,
        lead_id: int,
        category_id: int,
        pause_lead: Optional[bool] = True,
    ):
        url = f"{self.BASE_URL}/campaigns/{campaign_id}/leads/{lead_id}/category?api_key={self.api_key}"
        data = {"category_id": category_id, "pause_lead": pause_lead}
        headers = {"Content-Type": "application/json"}
        response = requests.post(url, headers=headers, data=json.dumps(data))
        if response.status_code == 429:
            time.sleep(self.DELAY_SECONDS)
            return self.post_update_lead_category(
                campaign_id, lead_id, category_id, pause_lead
            )
        return response.json()

    def pause_lead_by_campaign_id(
        self,
        campaign_id: int,
        lead_id: int,
    ):
        url = f"{self.BASE_URL}/campaigns/{campaign_id}/leads/{lead_id}/pause?api_key={self.api_key}"
        response = requests.post(url)
        if response.status_code == 429:
            time.sleep(self.DELAY_SECONDS)
            return self.pause_lead_by_campaign_id(campaign_id, lead_id)
        return response.json()

    def resume_lead_by_campaign_id(
        self,
        campaign_id: int,
        lead_id: int,
    ):
        url = f"{self.BASE_URL}/campaigns/{campaign_id}/leads/{lead_id}/resume?api_key={self.api_key}"
        response = requests.post(url)
        if response.status_code == 429:
            time.sleep(self.DELAY_SECONDS)
            return self.resume_lead_by_campaign_id(campaign_id, lead_id)
        return response.json()

    def get_message_history_using_lead_and_campaign_id(self, lead_id, campaign_id):
        url = f"{self.BASE_URL}/campaigns/{campaign_id}/leads/{lead_id}/message-history?api_key={self.api_key}"
        response = requests.get(url)
        if response.status_code == 429:
            time.sleep(self.DELAY_SECONDS)
            return self.get_message_history_using_lead_and_campaign_id(
                lead_id, campaign_id
            )
        return response.json()

    def get_campaign_sequence_by_id(self, campaign_id):
        url = (
            f"{self.BASE_URL}/campaigns/{campaign_id}/sequences?api_key={self.api_key}"
        )
        response = requests.get(url)
        if response.status_code == 429:
            time.sleep(self.DELAY_SECONDS)
            return self.get_campaign_sequence_by_id(campaign_id)
        return response.json()

    def get_campaign_statistics_by_id(self, campaign_id):
        url = f"https://server.smartlead.ai/api/v1/campaigns/{campaign_id}/statistics?api_key={self.api_key}"
        response = requests.get(url)
        if response.status_code == 429:
            time.sleep(self.DELAY_SECONDS)
            return self.get_campaign_statistics_by_id(campaign_id)
        return response.json()

    def get_emails(self, offset=0, limit=100, username: str = None):
        url = f"{self.BASE_URL}/email-accounts/?api_key={self.api_key}&offset={offset}&limit={limit}"
        if username:
            url += f"&username={username}"
        response = requests.get(url)
        if response.status_code == 429:
            time.sleep(self.DELAY_SECONDS)
            return self.get_emails(offset, limit)
        return response.json()

    def get_campaign_sequences(self, campaign_id):
        url = (
            f"{self.BASE_URL}/campaigns/{campaign_id}/sequences?api_key={self.api_key}"
        )
        response = requests.get(url)
        if response.status_code == 429:
            time.sleep(self.DELAY_SECONDS)
            return self.get_campaign_sequences(campaign_id)
        return response.json()

    def get_campaign(self, campaign_id):
        url = f"{self.BASE_URL}/campaigns/{campaign_id}?api_key={self.api_key}"
        response = requests.get(url)
        if response.status_code == 429:
            time.sleep(self.DELAY_SECONDS)
            return self.get_campaign(campaign_id)
        return response.json()

    def get_campaign_analytics(self, campaign_id):
        url = (
            f"{self.BASE_URL}/campaigns/{campaign_id}/analytics?api_key={self.api_key}"
        )
        response = requests.get(url)
        if response.status_code == 429:
            time.sleep(self.DELAY_SECONDS)
            return self.get_campaign_analytics(campaign_id)
        return response.json()

    def get_campaign_email_accounts(self, campaign_id):
        url = f"{self.BASE_URL}/campaigns/{campaign_id}/email-accounts?api_key={self.api_key}"
        response = requests.get(url)
        if response.status_code == 429:
            time.sleep(self.DELAY_SECONDS)
            return self.get_campaign_email_accounts(campaign_id)
        return response.json()

    def get_campaign_leads(self, campaign_id, offset=0, limit=10):
        url = f"{self.BASE_URL}/campaigns/{campaign_id}/leads?api_key={self.api_key}&offset={offset}&limit={limit}"
        response = requests.get(url)
        if response.status_code == 429:
            time.sleep(self.DELAY_SECONDS)
            return self.get_campaign_leads(campaign_id, offset, limit)
        return response.json()

    def add_campaign_leads(self, campaign_id, leads: list):  # max 100 leads at a time
        url = f"{self.BASE_URL}/campaigns/{campaign_id}/leads?api_key={self.api_key}"
        response = requests.post(
            url,
            headers={
                "Content-Type": "application/json",
            },
            json={
                "lead_list": leads,
            },
        )
        if response.status_code == 429:
            time.sleep(self.DELAY_SECONDS)
            return self.add_campaign_leads(campaign_id, leads)
        return response.json()

    def add_or_update_warmup(self, email_account_id: int, warmup_data: dict) -> dict:
        """`warmup_data` format is

        warmup_data = {
            "warmup_enabled": true, // set false to disable warmup
            "total_warmup_per_day": 35,
            "daily_rampup": 2, // set this value to have daily ramup increase in warmup emails
            "reply_rate_percentage": 38,
            "warmup_key_id": "apple-juice" //string value if passed will update the custom warmup-key identifier
        }
        """
        url = f"{self.BASE_URL}/email-accounts/{email_account_id}/warmup?api_key={self.api_key}"
        response = requests.post(
            url,
            headers={
                "Content-Type": "application/json",
            },
            data=json.dumps(warmup_data),
        )
        if response.status_code == 429:
            time.sleep(self.DELAY_SECONDS)
            return self.add_or_update_warmup(email_account_id, warmup_data)
        return response.json()

    def get_warmup_stats(self, email_account_id):
        url = f"{self.BASE_URL}/email-accounts/{email_account_id}/warmup-stats?api_key={self.api_key}"
        response = requests.get(url)
        if response.status_code == 429:
            time.sleep(self.DELAY_SECONDS)
            return self.get_warmup_stats(email_account_id)
        return response.json()

    def get_leads_export(self, campaign_id):
        url = f"{self.BASE_URL}/campaigns/{campaign_id}/leads-export?api_key={self.api_key}"
        response = requests.get(url)
        if response.status_code == 429:
            time.sleep(self.DELAY_SECONDS)
            return self.get_leads_export(campaign_id)

        if response.status_code != 200:
            return []

        # Read the CSV file
        csv_data = StringIO(response.text)
        reader = csv.DictReader(csv_data)

        result = []
        for row in reader:
            record = {}

            last_email_sent = int(row["last_email_sequence_sent"])
            opened = int(row["open_count"])
            replied = int(row["reply_count"])
            clicked = int(row["click_count"])

            record["email"] = row["email"]
            record["is_unsubscribed"] = row["is_unsubscribed"] == "true"
            record["is_interested"] = row["is_interested"] == "true"
            record["is_clicked"] = clicked > 0

            if last_email_sent > 0:
                record["is_sent"] = True
                if opened > 0:
                    record["is_opened"] = True
                    if replied > 0:
                        record["is_replied"] = True

            result.append(record)

        return result

    def post_campaign_leads(self, campaign_id, lead_list):
        """`lead_list` format is

        lead_list = [
            {
                "first_name": "Cristiano",
                "last_name": "Ronaldo",
                "email": "cristiano@mufc.com",
                "phone_number": "0239392029",
                "company_name": "Manchester United",
                "website": "mufc.com",
                "location": "London",
                "custom_fields": {
                    "Title": "Regional Manager",
                    "First_Line": "Loved your recent post about remote work on Linkedin"
                },
                "linkedin_profile": "http://www.linkedin.com/in/cristianoronaldo",
                "company_url": "mufc.com"
            }
            # ... (add up to 100 leads)
        ]
        """
        settings = {
            "ignore_global_block_list": True,
            "ignore_unsubscribe_list": True,
            "ignore_duplicate_leads_in_other_campaign": False,
        }
        if not isinstance(lead_list, list) or not isinstance(settings, dict):
            raise ValueError(
                "lead_list must be a list and settings must be a dictionary."
            )

        if len(lead_list) > 100:
            raise ValueError("You can only send a maximum of 100 leads at a time.")

        url = f"{self.BASE_URL}/campaigns/{campaign_id}/leads?api_key={self.api_key}"
        data = {"lead_list": lead_list, "settings": settings}
        headers = {"Content-Type": "application/json"}
        response = requests.post(url, headers=headers, data=json.dumps(data))
        if response.status_code == 429:
            time.sleep(self.DELAY_SECONDS)
            return self.post_campaign_leads(campaign_id, lead_list)
        return response.json()

    def create_email_account(self, json_data):
        url = f"{self.BASE_URL}/email-accounts/save?api_key={self.api_key}"
        response = requests.post(
            url,
            headers={
                "Content-Type": "application/json",
            },
            json=json_data,
        )
        if response.status_code == 429:
            time.sleep(self.DELAY_SECONDS)
            return self.create_email_account(json_data)
        return response.json()

    def deactivate_email_account(self, email_account_id: str):
        url = (
            f"{self.BASE_URL}/email-accounts/{email_account_id}?api_key={self.api_key}"
        )
        response = requests.post(
            url,
            headers={
                "Content-Type": "application/json",
            },
            json={"max_email_per_day": 0},
        )
        if response.status_code == 429:
            time.sleep(self.DELAY_SECONDS)
            return self.deactivate_email_account(email_account_id)
        return response.json()

    def remove_email_account_from_campaign(
        self, campaign_id: int, email_account_ids: list[str]
    ):
        url = f"{self.BASE_URL}/campaigns/{campaign_id}/email-accounts?api_key={self.api_key}"
        response = requests.delete(
            url,
            headers={
                "Content-Type": "application/json",
            },
            json={"email_account_ids": email_account_ids},
        )
        if response.status_code == 429:
            time.sleep(self.DELAY_SECONDS)
            return self.remove_email_account_from_campaign(
                campaign_id, email_account_ids
            )
        return response.json()
