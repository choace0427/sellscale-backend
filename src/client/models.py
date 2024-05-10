import enum
from typing import Optional
from app import db
from src.client.sdr.email.models import SDREmailBank
from src.merge_crm.models import ClientSyncCRM
from src.prospecting.models import ProspectStatus, Prospect
import sqlalchemy as sa
import json
from src.subscriptions.models import Subscription
from sqlalchemy.dialects.postgresql import ARRAY


from src.utils.hasher import generate_uuid


class Client(db.Model):
    __tablename__ = "client"

    id = db.Column(db.Integer, primary_key=True)

    company_id = db.Column(db.Integer, db.ForeignKey("company.id"), nullable=True)
    company = db.Column(db.String)
    domain = db.Column(db.String, nullable=True)
    contact_name = db.Column(db.String)
    contact_email = db.Column(db.String)

    active = db.Column(db.Boolean, nullable=True)

    pipeline_notifications_webhook_url = db.Column(db.String, nullable=True)
    last_slack_msg_date = db.Column(db.DateTime, nullable=True)

    notification_allowlist = db.Column(
        db.ARRAY(sa.Enum(ProspectStatus, create_constraint=False)),
        nullable=True,
    )

    linkedin_outbound_enabled = db.Column(db.Boolean, nullable=True)
    email_outbound_enabled = db.Column(db.Boolean, nullable=True)

    super_sight_link = db.Column(db.String, nullable=True)
    monthly_revenue = db.Column(db.Integer, nullable=True)
    seat_expansion_opportunity = db.Column(db.Integer, nullable=True)

    tagline = db.Column(db.String, nullable=True)
    description = db.Column(db.String, nullable=True)

    do_not_contact_keywords_in_company_names = db.Column(
        db.ARRAY(db.String), nullable=True
    )
    do_not_contact_company_names = db.Column(db.ARRAY(db.String), nullable=True)
    do_not_contact_industries = db.Column(db.ARRAY(db.String), nullable=True)
    do_not_contact_location_keywords = db.Column(db.ARRAY(db.String), nullable=True)
    do_not_contact_titles = db.Column(db.ARRAY(db.String), nullable=True)
    do_not_contact_prospect_location_keywords = db.Column(
        db.ARRAY(db.String), nullable=True
    )
    do_not_contact_people_names = db.Column(db.ARRAY(db.String), nullable=True)
    do_not_contact_emails = db.Column(db.ARRAY(db.String), nullable=True)

    value_prop_key_points = db.Column(db.String, nullable=True)
    tone_attributes = db.Column(db.ARRAY(db.String), nullable=True)

    uuid = db.Column(db.String, nullable=True, unique=True, index=True)

    mission = db.Column(db.String, nullable=True)
    case_study = db.Column(db.String, nullable=True)

    analytics_activation_date = db.Column(db.DateTime, nullable=True)
    analytics_deactivation_date = db.Column(db.DateTime, nullable=True)

    contract_size = db.Column(db.Integer, nullable=True)

    pre_onboarding_survey = db.Column(db.JSON, nullable=True)
    is_pre_onboarding_survey_imported = db.Column(db.Boolean, nullable=True)

    # Survey questions
    example_outbound_copy = db.Column(db.String, nullable=True)
    existing_clients = db.Column(db.String, nullable=True)
    impressive_facts = db.Column(db.String, nullable=True)

    # Autogeneration
    auto_generate_li_messages = db.Column(db.Boolean, nullable=True, default=False)
    auto_generate_email_messages = db.Column(db.Boolean, nullable=True, default=False)

    merge_crm_account_token = db.Column(db.String, nullable=True)

    on_demo_set_webhook = db.Column(db.String, nullable=True)

    def regenerate_uuid(self) -> str:
        uuid_str = generate_uuid(base=str(self.id), salt=self.company)
        self.uuid = uuid_str
        db.session.commit()

        return uuid_str

    def to_dict(self) -> dict:
        from src.slack.auth.models import SlackAuthentication

        slack_authentication: SlackAuthentication = SlackAuthentication.query.filter_by(
            client_id=self.id
        ).first()
        slack_bot_connected: bool = slack_authentication is not None
        slack_bot_connecting_user_name = None
        if slack_bot_connected:
            connecting_sdr: ClientSDR = ClientSDR.query.filter_by(
                id=slack_authentication.client_sdr_id
            ).first()
            slack_bot_connecting_user_name = connecting_sdr.name

        return {
            "id": self.id,
            "company": self.company,
            "contact_name": self.contact_name,
            "contact_email": self.contact_email,
            "domain": self.domain,
            "active": self.active,
            "linkedin_outbound_enabled": self.linkedin_outbound_enabled,
            "email_outbound_enabled": self.email_outbound_enabled,
            "pipeline_notifications_webhook_url": self.pipeline_notifications_webhook_url,
            "tagline": self.tagline,
            "description": self.description,
            "value_prop_key_points": self.value_prop_key_points,
            "tone_attributes": self.tone_attributes,
            "mission": self.mission,
            "case_study": self.case_study,
            "contract_size": self.contract_size,
            "example_outbound_copy": self.example_outbound_copy,
            "existing_clients": self.existing_clients,
            "impressive_facts": self.impressive_facts,
            "auto_generate_li_messages": self.auto_generate_li_messages,
            "auto_generate_email_messages": self.auto_generate_email_messages,
            "slack_bot_connected": slack_bot_connected,
            "slack_bot_connecting_user_name": slack_bot_connecting_user_name,
        }
class EmailToLinkedInConnection(enum.Enum):
    RANDOM = "RANDOM"
    ALL_PROSPECTS = "ALL_PROSPECTS"
    OPENED_EMAIL_PROSPECTS_ONLY = "OPENED_EMAIL_PROSPECTS_ONLY"
    CLICKED_LINK_PROSPECTS_ONLY = "CLICKED_LINK_PROSPECTS_ONLY"
class ClientArchetype(db.Model):
    __tablename__ = "client_archetype"

    id = db.Column(db.Integer, primary_key=True)

    client_id = db.Column(db.Integer, db.ForeignKey("client.id"))
    archetype = db.Column(db.String)
    filters = db.Column(db.JSON, nullable=True)

    emoji = db.Column(db.String, nullable=True, default="👋")

    active = db.Column(db.Boolean, nullable=True, default=True)
    linkedin_active = db.Column(db.Boolean, nullable=True, default=False)
    email_active = db.Column(db.Boolean, nullable=True, default=False)

    email_to_linkedin_connection = db.Column(
        sa.Enum(EmailToLinkedInConnection, create_constraint=False), nullable=True
    )

    transformer_blocklist = db.Column(
        db.ARRAY(db.String),
        nullable=True,
    )  # use this list to blocklist transformer durings message generation
    transformer_blocklist_initial = db.Column(
        db.ARRAY(db.String),
        nullable=True,
    )  # use this list to blocklist transformers during initial message generation
    # child layer of transformer_blocklist

    disable_ai_after_prospect_engaged = db.Column(
        db.Boolean, nullable=True, default=False
    )

    client_sdr_id = db.Column(db.Integer, db.ForeignKey("client_sdr.id"), nullable=True)
    persona_fit_reason = db.Column(db.String, nullable=True)
    icp_matching_prompt = db.Column(db.String, nullable=True)
    icp_matching_option_filters = db.Column(db.JSON, nullable=True)
    persona_contact_objective = db.Column(db.String, nullable=True)
    persona_cta_framework_company = db.Column(db.String, nullable=True)
    persona_cta_framework_persona = db.Column(db.String, nullable=True)
    persona_cta_framework_action = db.Column(db.String, nullable=True)
    persona_use_cases = db.Column(db.String, nullable=True)
    persona_filters = db.Column(db.String, nullable=True)
    persona_lookalike_profile_1 = db.Column(db.String, nullable=True)
    persona_lookalike_profile_2 = db.Column(db.String, nullable=True)
    persona_lookalike_profile_3 = db.Column(db.String, nullable=True)
    persona_lookalike_profile_4 = db.Column(db.String, nullable=True)
    persona_lookalike_profile_5 = db.Column(db.String, nullable=True)

    is_unassigned_contact_archetype = db.Column(
        db.Boolean, nullable=True, default=False
    )  # if true, this archetype will be used for unassigned contacts

    prospect_filters = db.Column(db.JSON, nullable=True)
    email_blocks_configuration = db.Column(db.ARRAY(db.String), nullable=True)

    contract_size = db.Column(db.Integer, server_default="10000", nullable=False)
    first_message_delay_days = db.Column(db.Integer, nullable=True)
    li_bump_amount = db.Column(db.Integer, server_default="0", nullable=False)

    template_mode = db.Column(db.Boolean, nullable=True)

    sent_activation_notification = db.Column(db.Boolean, nullable=True, default=False)

    smartlead_campaign_id = db.Column(db.Integer, nullable=True)
    email_open_tracking_enabled = db.Column(db.Boolean, nullable=True, default=True)
    email_link_tracking_enabled = db.Column(db.Boolean, nullable=True, default=True)

    meta_data = db.Column(db.JSON, nullable=True)

    base_segment_id = db.Column(db.Integer, nullable=True)

    def to_dict(self) -> dict:
        from src.message_generation.models import GeneratedMessageCTA

        ctas: list[GeneratedMessageCTA] = (
            GeneratedMessageCTA.get_active_ctas_for_archetype(self.id)
        )

        return {
            "id": self.id,
            "client_id": self.client_id,
            "archetype": self.archetype,
            "filters": self.filters,
            "active": self.active,
            "linkedin_active": self.linkedin_active,
            "email_active": self.email_active,
            "email_to_linkedin_connection": self.email_to_linkedin_connection.value if self.email_to_linkedin_connection else None,
            "transformer_blocklist": (
                [t for t in self.transformer_blocklist]
                if self.transformer_blocklist
                else []
            ),
            "transformer_blocklist_initial": (
                [t for t in self.transformer_blocklist_initial]
                if self.transformer_blocklist_initial
                else []
            ),
            "disable_ai_after_prospect_engaged": self.disable_ai_after_prospect_engaged,
            "client_sdr_id": self.client_sdr_id,
            "persona_fit_reason": self.persona_fit_reason,
            "persona_contact_objective": self.persona_contact_objective,
            "icp_matching_prompt": self.icp_matching_prompt,
            "icp_matching_option_filters": self.icp_matching_option_filters,
            "is_unassigned_contact_archetype": self.is_unassigned_contact_archetype,
            "prospect_filters": self.prospect_filters,
            "ctas": [cta.to_dict() for cta in ctas],
            "email_blocks_configuration": self.email_blocks_configuration,
            "contract_size": self.contract_size,
            "first_message_delay_days": self.first_message_delay_days,
            "li_bump_amount": self.li_bump_amount,
            "emoji": self.emoji,
            "cta_framework_company": self.persona_cta_framework_company,
            "cta_framework_persona": self.persona_cta_framework_persona,
            "cta_framework_action": self.persona_cta_framework_action,
            "use_cases": self.persona_use_cases,
            "filters": self.persona_filters,
            "lookalike_profile_1": self.persona_lookalike_profile_1,
            "lookalike_profile_2": self.persona_lookalike_profile_2,
            "lookalike_profile_3": self.persona_lookalike_profile_3,
            "lookalike_profile_4": self.persona_lookalike_profile_4,
            "lookalike_profile_5": self.persona_lookalike_profile_5,
            "template_mode": self.template_mode,
            "smartlead_campaign_id": self.smartlead_campaign_id,
            "email_open_tracking_enabled": self.email_open_tracking_enabled,
            "email_link_tracking_enabled": self.email_link_tracking_enabled,
            "meta_data": self.meta_data,
            "base_segment_id": self.base_segment_id,
        }


class ClientProduct(db.Model):
    __tablename__ = "client_product"

    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey("client.id"))

    name = db.Column(db.String)
    description = db.Column(db.String)
    how_it_works = db.Column(db.String, nullable=True)
    use_cases = db.Column(db.String, nullable=True)
    product_url = db.Column(db.String, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "client_id": self.client_id,
            "name": self.name,
            "description": self.description,
            "how_it_works": self.how_it_works,
            "use_cases": self.use_cases,
            "product_url": self.product_url,
        }


class ClientPod(db.Model):
    __tablename__ = "client_pod"

    id = db.Column(db.Integer, primary_key=True)

    client_id = db.Column(db.Integer, db.ForeignKey("client.id"))
    name = db.Column(db.String)
    active = db.Column(db.Boolean, nullable=True, default=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "client_id": self.client_id,
            "name": self.name,
            "active": self.active,
        }


class SDRQuestionaireColumn(sa.types.TypeDecorator):
    impl = sa.types.JSON

    COLUMN_SCHEMA = {  # Can be used in future for strong enforcement. For now just used for documentation.
        "education": [
            {
                "name": "University of California, Berkeley",
                "degree": "Bachelor's",
                "year_started": 0,
                "year_ended": 0,
            }
        ]
    }

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        self.validate_data(data=value)
        return json.dumps(value)

    def process_result_value(self, value, dialect) -> None:
        if value is None:
            return None

        return json.loads(value)

    def validate_data(self, data):
        """Validate that the data we are trying to insert follows the schema. Loose validation for now."""
        if not isinstance(data, dict):
            raise ValueError("Data must be a dictionary.")
        for key in data:
            if key not in self.COLUMN_SCHEMA:
                raise ValueError(f"Key {key} is not valid.")


class ClientSDR(db.Model):
    __tablename__ = "client_sdr"

    id = db.Column(db.Integer, primary_key=True)

    client_id = db.Column(db.Integer, db.ForeignKey("client.id"))
    client = db.relationship("Client", backref="SDRs")
    name = db.Column(db.String)

    email = db.Column(db.String)
    weekly_report_cc_emails = db.Column(db.ARRAY(db.String), nullable=True)
    weekly_report_bcc_emails = db.Column(db.ARRAY(db.String), nullable=True)

    role = db.Column(db.String, nullable=True)

    active = db.Column(db.Boolean, nullable=True, default=True)
    is_onboarding = db.Column(db.Boolean, nullable=True, default=False)

    weekly_li_outbound_target = db.Column(db.Integer, nullable=True)
    weekly_email_outbound_target = db.Column(db.Integer, nullable=True)
    scheduling_link = db.Column(db.String, nullable=True)

    auth_token = db.Column(db.String, nullable=True)

    pipeline_notifications_webhook_url = db.Column(db.String, nullable=True)
    notification_allowlist = db.Column(
        db.ARRAY(sa.Enum(ProspectStatus, create_constraint=False)),
        nullable=True,
    )

    do_not_contact_keywords_in_company_names = db.Column(
        db.ARRAY(db.String), nullable=True
    )
    do_not_contact_company_names = db.Column(db.ARRAY(db.String), nullable=True)
    do_not_contact_industries = db.Column(db.ARRAY(db.String), nullable=True)
    do_not_contact_location_keywords = db.Column(db.ARRAY(db.String), nullable=True)
    do_not_contact_titles = db.Column(db.ARRAY(db.String), nullable=True)
    do_not_contact_prospect_location_keywords = db.Column(
        db.ARRAY(db.String), nullable=True
    )
    do_not_contact_people_names = db.Column(db.ARRAY(db.String), nullable=True)
    do_not_contact_emails = db.Column(db.ARRAY(db.String), nullable=True)

    manual_warning_message = db.Column(db.String, nullable=True)

    autopilot_enabled = db.Column(db.Boolean, nullable=True, default=False)

    questionnaire = db.Column(SDRQuestionaireColumn, nullable=True)

    client_pod_id = db.Column(db.Integer, db.ForeignKey("client_pod.id"), nullable=True)

    # Nylas (Email)
    nylas_auth_code = db.Column(db.String, nullable=True)
    nylas_account_id = db.Column(db.String, nullable=True)
    nylas_active = db.Column(db.Boolean, nullable=True, default=False)

    # Credits and limits
    email_fetching_credits = db.Column(db.Integer, nullable=True, default=2000)
    ml_credits = db.Column(db.Integer, nullable=True, default=5000)

    scrape_time = db.Column(db.Time, nullable=True)  # in UTC
    next_scrape = db.Column(db.DateTime, nullable=True)  # in UTC

    timezone = db.Column(
        db.String, server_default="America/Los_Angeles", nullable=False
    )
    automatically_added_timezone = db.Column(db.Boolean, nullable=True, default=False)

    uuid = db.Column(db.String, nullable=True, unique=True, index=True)
    onboarded = db.Column(db.Boolean, nullable=True, default=False)
    calendly_access_token = db.Column(db.String, nullable=True)
    calendly_refresh_token = db.Column(db.String, nullable=True)

    auto_generate_messages = db.Column(db.Boolean, nullable=True, default=False)
    auto_calendar_sync = db.Column(db.Boolean, nullable=True, default=False)
    auto_bump = db.Column(db.Boolean, nullable=True, default=False)

    message_generation_captivate_mode = db.Column(
        db.Boolean, nullable=True, default=False
    )

    analytics_activation_date = db.Column(db.DateTime, nullable=True)
    analytics_deactivation_date = db.Column(db.DateTime, nullable=True)

    disable_ai_on_prospect_respond = db.Column(db.Boolean, nullable=True, default=False)
    disable_ai_on_message_send = db.Column(db.Boolean, nullable=True, default=False)

    blacklisted_words = db.Column(db.ARRAY(db.String), nullable=True)

    meta_data = db.Column(db.JSON, nullable=True)

    conversion_percentages = db.Column(db.JSON, nullable=True)

    # Email
    email_open_tracking_enabled = db.Column(db.Boolean, nullable=True, default=True)
    email_link_tracking_enabled = db.Column(db.Boolean, nullable=True, default=True)

    # Slack Bot
    slack_user_id = db.Column(db.String, nullable=True)

    # Browser Extension
    browser_extension_ui_overlay = db.Column(db.Boolean, nullable=True, default=False)
    auto_archive_convos = db.Column(db.Boolean, nullable=True, default=True)

    # Warmup
    warmup_linkedin_complete = db.Column(db.Boolean, nullable=True, default=False)

    # LinkedIn Profile Information
    individual_id = db.Column(db.Integer, db.ForeignKey("individual.id"), nullable=True)
    linkedin_url = db.Column(db.String, nullable=True)
    title = db.Column(db.String)
    li_health = db.Column(db.Float, nullable=True)
    li_health_good_title = db.Column(db.Boolean, nullable=True)
    li_health_cover_image = db.Column(db.Boolean, nullable=True)
    li_health_profile_photo = db.Column(db.Boolean, nullable=True)
    li_health_premium = db.Column(db.Boolean, nullable=True)
    li_at_token = db.Column(db.String, nullable=True)
    last_li_conversation_scrape_date = db.Column(db.DateTime, nullable=True)
    li_cookies = db.Column(db.String, nullable=True)
    li_cover_img_url = db.Column(db.String, nullable=True)
    img_url = db.Column(db.String, nullable=True)
    img_expire = db.Column(db.Numeric(20, 0), server_default="0", nullable=False)
    user_agent = db.Column(db.String, nullable=True)
    last_linkedin_disconnection_notification_date = db.Column(
        db.DateTime, nullable=True
    )
    territory_name = db.Column(db.String, nullable=True)

    # Conversion goals
    conversion_sent_pct = db.Column(db.Float, nullable=True)
    conversion_open_pct = db.Column(db.Float, nullable=True)
    conversion_reply_pct = db.Column(db.Float, nullable=True)
    conversion_demo_pct = db.Column(db.Float, nullable=True)

    # Automatic Sending
    auto_send_linkedin_campaign = db.Column(db.Boolean, nullable=True, default=False)
    auto_send_email_campaign = db.Column(db.Boolean, nullable=True, default=False)

    # Messaging
    default_transformer_blocklist = db.Column(db.ARRAY(db.String), nullable=True)

    merge_user_id = db.Column(db.String, nullable=True)

    def regenerate_uuid(self) -> str:
        uuid_str = generate_uuid(base=str(self.id), salt=self.name)
        self.uuid = uuid_str
        db.session.commit()

        return uuid_str

    def is_subscribed_to_slack_notification(self, notification_type: enum.Enum) -> bool:
        """Check if the SDR is subscribed to a Slack notification type

        Args:
            notification_type (SlackNotificationType): The Slack notification type to check

        Returns:
            bool: Whether or not the SDR is subscribed to the Slack notification type
        """
        from src.slack.models import SlackNotification

        # Get the SlackNotification
        notification: SlackNotification = SlackNotification.query.filter_by(
            notification_type=notification_type
        ).first()
        if not notification:
            return False

        subscription: Subscription = Subscription.query.filter_by(
            client_sdr_id=self.id, slack_notification_id=notification.id
        ).first()

        return subscription is not None and subscription.active

    def to_dict(self, include_email_bank: Optional[bool] = True) -> dict:
        client: Client = Client.query.get(self.client_id)

        # Get the SLA schedules
        sla_schedules: list[SLASchedule] = SLASchedule.query.filter_by(
            client_sdr_id=self.id
        ).all()

        # Get the Emails
        if include_email_bank:
            email_bank: list[SDREmailBank] = SDREmailBank.query.filter_by(
                client_sdr_id=self.id
            ).all()

        # Get the CRM Sync
        client_sync_crm: ClientSyncCRM = ClientSyncCRM.query.filter_by(
            client_id=self.client_id
        ).first()

        unassigned_persona: ClientArchetype = ClientArchetype.query.filter_by(
            client_sdr_id=self.id, is_unassigned_contact_archetype=True
        ).first()

        return {
            "id": self.id,
            "client_name": client.company,
            "sdr_name": self.name,
            "sdr_title": self.title,
            "sdr_email": self.email,
            "role": self.role,
            "active": self.active,
            "auth_token": self.auth_token,
            "weekly_li_outbound_target": self.weekly_li_outbound_target,
            "weekly_email_outbound_target": self.weekly_email_outbound_target,
            "scheduling_link": self.scheduling_link,
            "pipeline_notifications_webhook_url": self.pipeline_notifications_webhook_url,
            "last_li_conversation_scrape_date": self.last_li_conversation_scrape_date,
            "li_connected": self.li_at_token is not None,
            "li_voyager_connected": self.li_at_token is not None
            and self.li_at_token != "INVALID",
            "nylas_connected": self.nylas_account_id is not None and self.nylas_active,
            "email_fetching_credits": self.email_fetching_credits,
            "ml_credits": self.ml_credits,
            "img_url": self.img_url,
            "img_expire": self.img_expire,
            "individual_id": self.individual_id,
            "timezone": self.timezone,
            "onboarded": self.onboarded,
            "calendly_connected": self.calendly_access_token is not None,
            "auto_generate_messages": self.auto_generate_messages,
            "auto_calendar_sync": self.auto_calendar_sync,
            "auto_bump": self.auto_bump,
            "message_generation_captivate_mode": self.message_generation_captivate_mode,
            "disable_ai_on_prospect_respond": self.disable_ai_on_prospect_respond,
            "disable_ai_on_message_send": self.disable_ai_on_message_send,
            "blacklisted_words": self.blacklisted_words,
            "conversion_percentages": self.conversion_percentages,
            "email_open_tracking_enabled": self.email_open_tracking_enabled,
            "email_link_tracking_enabled": self.email_link_tracking_enabled,
            "do_not_contact_keywords": self.do_not_contact_keywords_in_company_names,
            "do_not_contact_company_names": self.do_not_contact_company_names,
            "warmup_linkedin_complete": self.warmup_linkedin_complete,
            "sla_schedules": (
                [sla_schedule.to_dict() for sla_schedule in sla_schedules]
                if sla_schedules
                else None
            ),
            "browser_extension_ui_overlay": self.browser_extension_ui_overlay,
            "auto_archive_convos": self.auto_archive_convos,
            "slack_user_id": self.slack_user_id,
            "linkedin_url": self.linkedin_url,
            "li_health": self.li_health,
            "li_health_good_title": self.li_health_good_title,
            "li_health_cover_image": self.li_health_cover_image,
            "li_health_profile_photo": self.li_health_profile_photo,
            "li_health_premium": self.li_health_premium,
            "li_cover_img_url": self.li_cover_img_url,
            "conversion_sent_pct": self.conversion_sent_pct,
            "conversion_open_pct": self.conversion_open_pct,
            "conversion_reply_pct": self.conversion_reply_pct,
            "conversion_demo_pct": self.conversion_demo_pct,
            "meta_data": self.meta_data,
            "auto_send_linkedin_campaign": self.auto_send_linkedin_campaign,
            "auto_send_email_campaign": self.auto_send_email_campaign,
            "avg_contract_size": (
                client.contract_size if client and client.contract_size else 10000
            ),
            "unassigned_persona_id": (
                unassigned_persona.id if unassigned_persona else None
            ),
            "default_transformer_blocklist": (
                [t for t in self.default_transformer_blocklist]
                if self.default_transformer_blocklist
                else []
            ),
            "merge_user_id": self.merge_user_id,
            "client_sync_crm": client_sync_crm.to_dict() if client_sync_crm else None,
        }


class SLASchedule(db.Model):
    __tablename__ = "sla_schedule"

    id = db.Column(db.Integer, primary_key=True)
    client_sdr_id = db.Column(db.Integer, db.ForeignKey("client_sdr.id"))

    # Start and end date to create a range during which the SLA is valid
    start_date = db.Column(db.DateTime, nullable=False)
    end_date = db.Column(db.DateTime, nullable=False)

    # SLA values for LinkedIn
    linkedin_volume = db.Column(db.Integer, nullable=False)
    linkedin_special_notes = db.Column(db.String, nullable=True)
    linkedin_ai_adjusted = db.Column(db.Boolean, nullable=True, default=False)
    linkedin_past_volume = db.Column(db.Integer, nullable=True)

    # SLA values for email
    email_volume = db.Column(db.Integer, nullable=False)
    email_special_notes = db.Column(db.String, nullable=True)
    email_ai_adjusted = db.Column(db.Boolean, nullable=True, default=False)
    email_past_volume = db.Column(db.Integer, nullable=True)

    # Which week
    week = db.Column(db.Integer, nullable=True)

    def to_dict(self) -> dict:
        from datetime import datetime

        # If the current date is within the date range, return is_current_week True
        # Otherwise, return is_current_week False
        is_current_week = (
            (self.start_date <= datetime.utcnow() <= self.end_date)
            if self.start_date and self.end_date
            else False
        )

        return {
            "is_current_week": is_current_week,
            "id": self.id,
            "client_sdr_id": self.client_sdr_id,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "linkedin_volume": self.linkedin_volume,
            "linkedin_special_notes": self.linkedin_special_notes,
            "linkedin_ai_adjusted": self.linkedin_ai_adjusted,
            "liinkedin_past_volume": self.linkedin_past_volume,
            "email_volume": self.email_volume,
            "email_special_notes": self.email_special_notes,
            "email_ai_adjusted": self.email_ai_adjusted,
            "email_past_volume": self.email_past_volume,
            "week": self.week,
        }


class DemoFeedback(db.Model):
    __tablename__ = "demo_feedback"

    id = db.Column(db.Integer, primary_key=True)

    client_id = db.Column(db.Integer, db.ForeignKey("client.id"))
    client_sdr_id = db.Column(db.Integer, db.ForeignKey("client_sdr.id"))
    prospect_id = db.Column(db.Integer, db.ForeignKey("prospect.id"))

    status = db.Column(db.String)
    rating = db.Column(db.String)
    feedback = db.Column(db.String)
    demo_date = db.Column(db.DateTime, nullable=True)
    next_demo_date = db.Column(db.DateTime, nullable=True)
    ai_adjustments = db.Column(db.String, nullable=True)

    def to_dict(self) -> dict:
        prospect: Prospect = Prospect.query.get(self.prospect_id)

        return {
            "id": self.id,
            "client_id": self.client_id,
            "client_sdr_id": self.client_sdr_id,
            "prospect_id": self.prospect_id,
            "prospect_name": prospect.full_name,
            "prospect_img_url": prospect.img_url,
            "demo_date": prospect.demo_date,
            "status": self.status,
            "rating": self.rating,
            "feedback": self.feedback,
            "ai_adjustments": self.ai_adjustments,
            "demo_date": self.demo_date,
            "next_demo_date": self.next_demo_date,
        }


class PLGProductLeads(db.Model):
    __tablename__ = "plg_product_leads"

    id = db.Column(db.Integer, primary_key=True)

    email = db.Column(db.String)
    user_linkedin_url = db.Column(db.String)
    prospect_linkedin_url = db.Column(db.String)
    blocks = db.Column(db.JSON)

    is_test = db.Column(db.Boolean, nullable=True, default=False)


# asset type: PDF, TEXT, URL


class ClientAssetType(enum.Enum):
    PDF = "PDF"
    TEXT = "TEXT"
    URL = "URL"


class ClientAssets(db.Model):
    __tablename__ = "client_assets"

    id = db.Column(db.Integer, primary_key=True)

    client_id = db.Column(db.Integer, db.ForeignKey("client.id"), nullable=True)
    client_archetype_ids = db.Column(ARRAY(db.Integer), nullable=True)
    asset_key = db.Column(db.String)
    asset_value = db.Column(db.String)
    asset_raw_value = db.Column(db.String)

    asset_type = db.Column(
        sa.Enum(ClientAssetType, create_constraint=False), nullable=True
    )
    asset_tags = db.Column(db.ARRAY(db.String), nullable=True)

    num_sends = db.Column(db.Integer, nullable=True)
    num_opens = db.Column(db.Integer, nullable=True)
    num_replies = db.Column(db.Integer, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "client_id": self.client_id,
            "client_archetype_ids": self.client_archetype_ids,
            "asset_key": self.asset_key,
            "asset_value": self.asset_value,
            "asset_type": self.asset_type and self.asset_type.value,
            "asset_tags": self.asset_tags,
            "asset_raw_value": self.asset_raw_value,
            "num_sends": self.num_sends,
            "num_opens": self.num_opens,
            "num_replies": self.num_replies,
        }


class ClientAssetArchetypeReasonMapping(db.Model):
    __tablename__ = "client_asset_archetype_reason_mapping"

    id = db.Column(db.Integer, primary_key=True)

    client_asset_id = db.Column(
        db.Integer, db.ForeignKey("client_assets.id"), nullable=False
    )
    client_archetype_id = db.Column(
        db.Integer, db.ForeignKey("client_archetype.id"), nullable=False
    )
    reason = db.Column(db.String, nullable=False)
    step_number = db.Column(db.Integer, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "client_asset_id": self.client_asset_id,
            "client_archetype_id": self.client_archetype_id,
            "reason": self.reason,
            "step_number": self.step_number,
        }
