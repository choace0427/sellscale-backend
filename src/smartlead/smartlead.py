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

    def __init__(self):
        self.api_key = os.environ.get("SMARTLEAD_API_KEY")

    def get_lead_by_email_address(self, email_address):
        time.sleep(self.DELAY_SECONDS)
        url = f"{self.BASE_URL}/leads/?api_key={self.api_key}&email={email_address}"
        response = requests.get(url)
        if response.status_code == 429:
            return self.get_lead_by_email_address(email_address)
        return response.json()

    def get_message_history_using_lead_and_campaign_id(self, lead_id, campaign_id):
        time.sleep(self.DELAY_SECONDS)
        url = f"{self.BASE_URL}/campaigns/{campaign_id}/leads/{lead_id}/message-history?api_key={self.api_key}"
        response = requests.get(url)
        if response.status_code == 429:
            return self.get_message_history_using_lead_and_campaign_id(
                lead_id, campaign_id
            )
        return response.json()

    def get_campaign_sequence_by_id(self, campaign_id):
        time.sleep(self.DELAY_SECONDS)
        url = (
            f"{self.BASE_URL}/campaigns/{campaign_id}/sequences?api_key={self.api_key}"
        )
        response = requests.get(url)
        if response.status_code == 429:
            return self.get_campaign_sequence_by_id(campaign_id)
        return response.json()

    def get_campaign_statistics_by_id(self, campaign_id):
        time.sleep(self.DELAY_SECONDS)
        url = f"https://server.smartlead.ai/api/v1/campaigns/{campaign_id}/statistics?api_key={self.api_key}"
        response = requests.get(url)
        if response.status_code == 429:
            return self.get_campaign_statistics_by_id(campaign_id)

        return response.json()

    def get_emails(self, offset=0, limit=100):
        time.sleep(self.DELAY_SECONDS)
        url = f"{self.BASE_URL}/email-accounts/?api_key={self.api_key}&offset={offset}&limit={limit}"
        response = requests.get(url)
        if response.status_code == 429:
            return self.get_emails(offset, limit)
        return response.json()

    def get_campaign_sequences(self, campaign_id):
        time.sleep(self.DELAY_SECONDS)
        url = (
            f"{self.BASE_URL}/campaigns/{campaign_id}/sequences?api_key={self.api_key}"
        )
        response = requests.get(url)
        if response.status_code == 429:
            return self.get_campaign_sequences(campaign_id)
        return response.json()

    def get_campaign(self, campaign_id):
        time.sleep(self.DELAY_SECONDS)
        url = f"{self.BASE_URL}/campaigns/{campaign_id}?api_key={self.api_key}"
        response = requests.get(url)
        if response.status_code == 429:
            return self.get_campaign(campaign_id)
        return response.json()

    def get_campaign_analytics(self, campaign_id):
        time.sleep(self.DELAY_SECONDS)
        url = (
            f"{self.BASE_URL}/campaigns/{campaign_id}/analytics?api_key={self.api_key}"
        )
        response = requests.get(url)
        if response.status_code == 429:
            return self.get_campaign_analytics(campaign_id)
        return response.json()

    def get_campaign_email_accounts(self, campaign_id):
        time.sleep(self.DELAY_SECONDS)
        url = f"{self.BASE_URL}/campaigns/{campaign_id}/email-accounts?api_key={self.api_key}"
        response = requests.get(url)
        if response.status_code == 429:
            return self.get_campaign_email_accounts(campaign_id)
        return response.json()

    def get_campaign_leads(self, campaign_id, offset=0, limit=10):
        time.sleep(self.DELAY_SECONDS)
        url = f"{self.BASE_URL}/campaigns/{campaign_id}/leads?api_key={self.api_key}&offset={offset}&limit={limit}"
        response = requests.get(url)
        if response.status_code == 429:
            return self.get_campaign_leads(campaign_id, offset, limit)
        return response.json()

    def add_campaign_leads(
        self, campaign_id, leads: list[Lead]
    ):  # max 100 leads at a time
        time.sleep(self.DELAY_SECONDS)
        url = f"{self.BASE_URL}/campaigns/{campaign_id}/leads"
        response = requests.post(
            url,
            headers={
                "Content-Type": "application/json",
            },
            json={
                "lead_list": [lead.to_dict() for lead in leads],
            },
        )
        if response.status_code == 429:
            return self.add_campaign_leads(campaign_id, leads)
        return response.json()

    def get_warmup_stats(self, email_account_id):
        time.sleep(self.DELAY_SECONDS)
        url = f"{self.BASE_URL}/email-accounts/{email_account_id}/warmup-stats?api_key={self.api_key}"
        response = requests.get(url)
        if response.status_code == 429:
            return self.get_warmup_stats(email_account_id)
        return response.json()

    def get_leads_export(self, campaign_id):
        time.sleep(self.DELAY_SECONDS)
        url = f"{self.BASE_URL}/campaigns/{campaign_id}/leads-export?api_key={self.api_key}"
        response = requests.get(url)
        if response.status_code == 429:
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
        time.sleep(self.DELAY_SECONDS)
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
            return self.post_campaign_leads(campaign_id, lead_list)
        return response.json()
