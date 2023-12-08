class WeeklyReportWarmupPayload:
    linkedin_outbound_per_week: int
    email_outbound_per_week: int
    linkedin_outbound_per_week_next_week: int
    email_outbound_per_week_next_week: int
    active_emails_str: int

    def __init__(
        self,
        linkedin_outbound_per_week: int,
        email_outbound_per_week: int,
        linkedin_outbound_per_week_next_week: int,
        email_outbound_per_week_next_week: int,
        active_emails_str: int,
    ):
        self.linkedin_outbound_per_week = linkedin_outbound_per_week
        self.email_outbound_per_week = email_outbound_per_week
        self.email_outbound_per_week_next_week = email_outbound_per_week_next_week
        self.linkedin_outbound_per_week_next_week = linkedin_outbound_per_week_next_week
        self.active_emails_str = active_emails_str

    def to_dict(self):
        return {
            "linkedin_outbound_per_week": self.linkedin_outbound_per_week,
            "email_outbound_per_week": self.email_outbound_per_week,
            "linkedin_outbound_per_week_next_week": self.linkedin_outbound_per_week_next_week,
            "email_outbound_per_week_next_week": self.email_outbound_per_week_next_week,
            "active_emails_str": self.active_emails_str,
        }


class WeeklyReportPipelineData:
    num_sent: int
    num_opens: int
    num_replies: int
    num_positive_response: int
    num_demos: int

    def __init__(
        self,
        num_sent: int,
        num_opens: int,
        num_replies: int,
        num_positive_response: int,
        num_demos: int,
    ):
        self.num_sent = num_sent
        self.num_opens = num_opens
        self.num_replies = num_replies
        self.num_positive_response = num_positive_response
        self.num_demos = num_demos

    def to_dict(self):
        return {
            "num_sent": self.num_sent,
            "num_opens": self.num_opens,
            "num_replies": self.num_replies,
            "num_positive_response": self.num_positive_response,
            "num_demos": self.num_demos,
        }


class WeeklyReportActiveCampaign:
    campaign_emoji: str
    campaign_name: str
    campaign_id: int
    campaign_completion_percent: float
    campaign_channel: str

    num_sent: int
    num_opens: int
    num_replies: int
    num_positive_replies: int
    num_demos: int

    def __init__(
        self,
        campaign_emoji: str,
        campaign_name: str,
        campaign_id: int,
        campaign_completion_percent: float,
        campaign_channel: str,
        num_sent: int,
        num_opens: int,
        num_replies: int,
        num_positive_replies: int,
        num_demos: int,
    ):
        self.campaign_emoji = campaign_emoji
        self.campaign_name = campaign_name
        self.campaign_id = campaign_id
        self.campaign_completion_percent = campaign_completion_percent
        self.campaign_channel = campaign_channel
        self.num_sent = num_sent
        self.num_opens = num_opens
        self.num_replies = num_replies
        self.num_positive_replies = num_positive_replies
        self.num_demos = num_demos

    def to_dict(self):
        return {
            "campaign_emoji": self.campaign_emoji,
            "campaign_name": self.campaign_name,
            "campaign_id": self.campaign_id,
            "campaign_completion_percent": self.campaign_completion_percent,
            "campaign_channel": self.campaign_channel,
            "num_sent": self.num_sent,
            "num_opens": self.num_opens,
            "num_replies": self.num_replies,
            "num_positive_replies": self.num_positive_replies,
            "num_demos": self.num_demos,
        }


class ProspectResponse:
    prospect_name: str
    prospect_company: str
    user_name: str
    message: str

    def __init__(
        self, prospect_name: str, prospect_company: str, user_name: str, message: str
    ):
        self.prospect_name = prospect_name
        self.prospect_company = prospect_company
        self.user_name = user_name
        self.message = message

    def to_dict(self):
        return {
            "prospect_name": self.prospect_name,
            "prospect_company": self.prospect_company,
            "user_name": self.user_name,
            "message": self.message,
        }


class SampleProspect:
    prospect_name: str
    prospect_icp_fit: str
    prospect_title: str
    prospect_company: str

    def __init__(
        self,
        prospect_name: str,
        prospect_icp_fit: str,
        prospect_title: str,
        prospect_company: str,
    ):
        self.prospect_name = prospect_name
        self.prospect_icp_fit = prospect_icp_fit
        self.prospect_title = prospect_title
        self.prospect_company = prospect_company

    def to_dict(self):
        return {
            "prospect_name": self.prospect_name,
            "prospect_icp_fit": self.prospect_icp_fit,
            "prospect_title": self.prospect_title,
            "prospect_company": self.prospect_company,
        }


class NextWeekSampleProspects:
    campaign_emoji: str
    campaign_name: str
    campaign_id: int
    prospects_left: int
    sample_prospects: list[SampleProspect]

    def __init__(
        self,
        campaign_emoji: str,
        campaign_name: str,
        campaign_id: int,
        prospects_left: int,
        sample_prospects: list[SampleProspect],
    ):
        self.campaign_emoji = campaign_emoji
        self.campaign_name = campaign_name
        self.campaign_id = campaign_id
        self.prospects_left = prospects_left
        self.sample_prospects = sample_prospects

    def to_dict(self):
        return {
            "campaign_emoji": self.campaign_emoji,
            "campaign_name": self.campaign_name,
            "campaign_id": self.campaign_id,
            "prospects_left": self.prospects_left,
            "sample_prospects": [
                sample_prospect.to_dict() for sample_prospect in self.sample_prospects
            ],
        }


class WeeklyReportData:
    warmup_payload: WeeklyReportWarmupPayload
    cumulative_client_pipeline: WeeklyReportPipelineData
    last_week_client_pipeline: WeeklyReportPipelineData
    active_campaigns: list[WeeklyReportActiveCampaign]
    demo_responses: list[ProspectResponse]
    prospect_responses: list[ProspectResponse]
    next_week_sample_prospects: list[NextWeekSampleProspects]
    num_prospects_added: int
    auth_token: str
    user_name: str
    date_start: str
    date_end: str
    company: str
    linkedin_token_valid: bool

    def __init__(
        self,
        warmup_payload: WeeklyReportWarmupPayload,
        cumulative_client_pipeline: WeeklyReportPipelineData,
        last_week_client_pipeline: WeeklyReportPipelineData,
        active_campaigns: list[WeeklyReportActiveCampaign],
        demo_responses: list[ProspectResponse],
        prospect_responses: list[ProspectResponse],
        next_week_sample_prospects: list[NextWeekSampleProspects],
        num_prospects_added: int,
        auth_token: str,
        user_name: str,
        date_start: str,
        date_end: str,
        company: str,
        linkedin_token_valid: bool,
    ):
        self.warmup_payload = warmup_payload
        self.cumulative_client_pipeline = cumulative_client_pipeline
        self.last_week_client_pipeline = last_week_client_pipeline
        self.active_campaigns = active_campaigns
        self.demo_responses = demo_responses
        self.prospect_responses = prospect_responses
        self.next_week_sample_prospects = next_week_sample_prospects
        self.num_prospects_added = num_prospects_added
        self.auth_token = auth_token
        self.user_name = user_name
        self.date_start = date_start
        self.date_end = date_end
        self.company = company
        self.linkedin_token_valid = linkedin_token_valid

    def to_dict(self):
        return {
            "warmup_payload": self.warmup_payload.to_dict(),
            "cumulative_client_pipeline": self.cumulative_client_pipeline.to_dict(),
            "last_week_client_pipeline": self.last_week_client_pipeline.to_dict(),
            "active_campaigns": [
                campaign.to_dict() for campaign in self.active_campaigns
            ],
            "demo_responses": [
                demo_response.to_dict() for demo_response in self.demo_responses
            ],
            "prospect_responses": [
                prospect_response.to_dict()
                for prospect_response in self.prospect_responses
            ],
            "next_week_sample_prospects": [
                next_week_sample_prospect.to_dict()
                for next_week_sample_prospect in self.next_week_sample_prospects
            ],
            "num_prospects_removed": self.num_prospects_added,
            "auth_token": self.auth_token,
            "user_name": self.user_name,
            "date_start": self.date_start,
            "date_end": self.date_end,
            "company": self.company,
            "linkedin_token_valid": self.linkedin_token_valid,
        }
