
import requests
import json
import os

class Smartlead:
    BASE_URL = 'https://server.smartlead.ai/api/v1'

    def __init__(self):
        self.api_key = os.environ.get("SMARTLEAD_API_KEY")
        
    def get_emails(self, offset=0, limit=100):
      url = f"{self.BASE_URL}/email-accounts/?api_key={self.api_key}&offset={offset}&limit={limit}"
      response = requests.get(url)
      return response.json()

    def get_campaign_sequences(self, campaign_id):
        url = f"{self.BASE_URL}/campaigns/{campaign_id}/sequences?api_key={self.api_key}"
        response = requests.get(url)
        return response.json()

    def get_campaign(self, campaign_id):
        url = f"{self.BASE_URL}/campaigns/{campaign_id}?api_key={self.api_key}"
        response = requests.get(url)
        return response.json()

    def get_campaign_email_accounts(self, campaign_id):
        url = f"{self.BASE_URL}/campaigns/{campaign_id}/email-accounts?api_key={self.api_key}"
        response = requests.get(url)
        return response.json()

    def get_campaign_leads(self, campaign_id, offset=0, limit=10):
        url = f"{self.BASE_URL}/campaigns/{campaign_id}/leads?api_key={self.api_key}&offset={offset}&limit={limit}"
        response = requests.get(url)
        return response.json()
      
    def get_warmup_stats(self, email_account_id):
        url = f"{self.BASE_URL}/email-accounts/{email_account_id}/warmup-stats?api_key={self.api_key}"
        response = requests.get(url)
        return response.json()
    
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
            "ignore_duplicate_leads_in_other_campaign": False
        }
        if not isinstance(lead_list, list) or not isinstance(settings, dict):
            raise ValueError("lead_list must be a list and settings must be a dictionary.")

        if len(lead_list) > 100:
            raise ValueError("You can only send a maximum of 100 leads at a time.")

        url = f"{self.BASE_URL}/campaigns/{campaign_id}/leads?api_key={self.api_key}"
        data = {
            "lead_list": lead_list,
            "settings": settings
        }
        headers = {'Content-Type': 'application/json'}
        response = requests.post(url, headers=headers, data=json.dumps(data))
        return response.json()


class EmailWarming:
    def __init__(self, id: int, name: str, email: str, status: str, total_sent: int, total_spam: int, warmup_reputation: str, sent_count: int, spam_count: int, inbox_count: int, warmup_email_received_count: int, stats_by_date: list, percent_complete: int):
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
        self.percent_complete = percent_complete
        
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
            "percent_complete": self.percent_complete
        }


