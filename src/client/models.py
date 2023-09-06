import enum
from app import db
from src.prospecting.models import ProspectStatus, Prospect
from src.research.models import ResearchPointType
import sqlalchemy as sa
import json

from src.utils.hasher import generate_uuid


class Client(db.Model):
    __tablename__ = "client"

    id = db.Column(db.Integer, primary_key=True)

    company_id = db.Column(
        db.Integer, db.ForeignKey("company.id"), nullable=True)
    company = db.Column(db.String)
    contact_name = db.Column(db.String)
    contact_email = db.Column(db.String)

    active = db.Column(db.Boolean, nullable=True)

    pipeline_notifications_webhook_url = db.Column(db.String, nullable=True)

    notification_allowlist = db.Column(
        db.ARRAY(sa.Enum(ProspectStatus, create_constraint=False)),
        nullable=True,
    )

    linkedin_outbound_enabled = db.Column(db.Boolean, nullable=True)
    email_outbound_enabled = db.Column(db.Boolean, nullable=True)

    super_sight_link = db.Column(db.String, nullable=True)
    monthly_revenue = db.Column(db.Integer, nullable=True)
    seat_expansion_opportunity = db.Column(db.Integer, nullable=True)

    vessel_access_token = db.Column(
        db.String, nullable=True
    )  # access token for sales engagement
    vessel_sales_engagement_connection_id = db.Column(
        db.String, nullable=True
    )  # connection id for sales engagement connection

    vessel_crm_access_token = db.Column(db.String, nullable=True)
    vessel_personalization_field_name = db.Column(db.String, nullable=True)

    tagline = db.Column(db.String, nullable=True)
    description = db.Column(db.String, nullable=True)

    do_not_contact_keywords_in_company_names = db.Column(
        db.ARRAY(db.String), nullable=True
    )
    do_not_contact_company_names = db.Column(
        db.ARRAY(db.String), nullable=True)

    value_prop_key_points = db.Column(db.String, nullable=True)
    tone_attributes = db.Column(db.ARRAY(db.String), nullable=True)

    uuid = db.Column(db.String, nullable=True, unique=True, index=True)

    mission = db.Column(db.String, nullable=True)
    case_study = db.Column(db.String, nullable=True)

    analytics_activation_date = db.Column(db.DateTime, nullable=True)
    analytics_deactivation_date = db.Column(db.DateTime, nullable=True)

    contract_size = db.Column(
        db.Integer, server_default="10000", nullable=False)

    def regenerate_uuid(self) -> str:
        uuid_str = generate_uuid(base=str(self.id), salt=self.company)
        self.uuid = uuid_str
        db.session.commit()

        return uuid_str

    def to_dict(self) -> dict:
        return {
            "company": self.company,
            "contact_name": self.contact_name,
            "contact_email": self.contact_email,
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
        }


class ClientArchetype(db.Model):
    __tablename__ = "client_archetype"

    id = db.Column(db.Integer, primary_key=True)

    client_id = db.Column(db.Integer, db.ForeignKey("client.id"))
    archetype = db.Column(db.String)
    filters = db.Column(db.JSON, nullable=True)

    emoji = db.Column(db.String, nullable=True, default="👋")

    active = db.Column(db.Boolean, nullable=True, default=True)

    transformer_blocklist = db.Column(
        db.ARRAY(sa.Enum(ResearchPointType, create_constraint=False)),
        nullable=True,
    )  # use this list to blocklist transformer durings message generation

    disable_ai_after_prospect_engaged = db.Column(
        db.Boolean, nullable=True, default=False
    )

    client_sdr_id = db.Column(
        db.Integer, db.ForeignKey("client_sdr.id"), nullable=True)
    persona_fit_reason = db.Column(db.String, nullable=True)
    icp_matching_prompt = db.Column(db.String, nullable=True)
    icp_matching_option_filters = db.Column(db.JSON, nullable=True)
    persona_contact_objective = db.Column(db.String, nullable=True)

    vessel_sequence_id = db.Column(db.String, nullable=True)

    is_unassigned_contact_archetype = db.Column(
        db.Boolean, nullable=True, default=False
    )  # if true, this archetype will be used for unassigned contacts

    prospect_filters = db.Column(db.JSON, nullable=True)
    email_blocks_configuration = db.Column(db.ARRAY(db.String), nullable=True)

    contract_size = db.Column(
        db.Integer, server_default="10000", nullable=False)

    def to_dict(self) -> dict:

        from src.message_generation.models import GeneratedMessageCTA

        ctas: list[
            GeneratedMessageCTA
        ] = GeneratedMessageCTA.get_active_ctas_for_archetype(self.id)

        return {
            "id": self.id,
            "client_id": self.client_id,
            "archetype": self.archetype,
            "filters": self.filters,
            "active": self.active,
            "transformer_blocklist": [t.value for t in self.transformer_blocklist]
            if self.transformer_blocklist
            else [],
            "disable_ai_after_prospect_engaged": self.disable_ai_after_prospect_engaged,
            "client_sdr_id": self.client_sdr_id,
            "persona_fit_reason": self.persona_fit_reason,
            "persona_contact_objective": self.persona_contact_objective,
            "icp_matching_prompt": self.icp_matching_prompt,
            "icp_matching_option_filters": self.icp_matching_option_filters,
            "vessel_sequence_id": self.vessel_sequence_id,
            "is_unassigned_contact_archetype": self.is_unassigned_contact_archetype,
            "prospect_filters": self.prospect_filters,
            "ctas": [cta.to_dict() for cta in ctas],
            "email_blocks_configuration": self.email_blocks_configuration,
            "contract_size": self.contract_size,
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
    name = db.Column(db.String)
    title = db.Column(db.String)
    email = db.Column(db.String)
    active = db.Column(db.Boolean, nullable=True, default=True)

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
    do_not_contact_company_names = db.Column(
        db.ARRAY(db.String), nullable=True)

    manual_warning_message = db.Column(db.String, nullable=True)

    li_at_token = db.Column(db.String)
    last_li_conversation_scrape_date = db.Column(db.DateTime, nullable=True)
    li_cookies = db.Column(db.String)

    vessel_mailbox = db.Column(db.String, nullable=True)

    autopilot_enabled = db.Column(db.Boolean, nullable=True, default=False)

    questionnaire = db.Column(SDRQuestionaireColumn, nullable=True)

    client_pod_id = db.Column(
        db.Integer, db.ForeignKey("client_pod.id"), nullable=True)

    nylas_auth_code = db.Column(db.String, nullable=True)
    nylas_account_id = db.Column(db.String, nullable=True)
    nylas_active = db.Column(db.Boolean, nullable=True, default=False)

    email_fetching_credits = db.Column(db.Integer, nullable=True, default=2000)
    ml_credits = db.Column(db.Integer, nullable=True, default=5000)

    img_url = db.Column(db.String, nullable=True)
    img_expire = db.Column(db.Numeric(
        20, 0), server_default="0", nullable=False)

    scrape_time = db.Column(db.Time, nullable=True)  # in UTC
    next_scrape = db.Column(db.DateTime, nullable=True)  # in UTC

    timezone = db.Column(
        db.String, server_default="America/Los_Angeles", nullable=False
    )

    uuid = db.Column(db.String, nullable=True, unique=True, index=True)
    onboarded = db.Column(db.Boolean, nullable=True, default=False)
    calendly_access_token = db.Column(db.String, nullable=True)
    calendly_refresh_token = db.Column(db.String, nullable=True)

    auto_generate_messages = db.Column(
        db.Boolean, nullable=True, default=False)
    auto_calendar_sync = db.Column(db.Boolean, nullable=True, default=False)
    auto_bump = db.Column(db.Boolean, nullable=True, default=False)

    message_generation_captivate_mode = db.Column(
        db.Boolean, nullable=True, default=False
    )

    analytics_activation_date = db.Column(db.DateTime, nullable=True)
    analytics_deactivation_date = db.Column(db.DateTime, nullable=True)

    disable_ai_on_prospect_respond = db.Column(
        db.Boolean, nullable=True, default=False)
    disable_ai_on_message_send = db.Column(
        db.Boolean, nullable=True, default=False)

    blacklisted_words = db.Column(db.ARRAY(db.String), nullable=True)

    conversion_percentages = db.Column(db.JSON, nullable=True)

    # Warmup
    warmup_linkedin_complete = db.Column(db.Boolean, nullable=True, default=False)

    def update_warmup_status(self) -> bool:
        """Updates the warmup status for the SDR using the warmup schedule and SLA value

        Returns:
            bool: The warmup status for the SDR
        """
        # Get the warmup schedule
        if self.warmup_linkedin_complete:
            return True

        warmup_schedule: WarmupScheduleLinkedIn = WarmupScheduleLinkedIn.query.filter_by(
            client_sdr_id=self.id
        ).first()

        # If no warmup schedule exists, create one
        if not warmup_schedule:
            warmup_schedule = WarmupScheduleLinkedIn()
            warmup_schedule.client_sdr_id = self.id
            warmup_schedule.set_conservative_schedule()

        # Check if the SDR is warm
        is_warm = warmup_schedule.is_warm(self.weekly_li_outbound_target)
        self.warmup_linkedin_complete = is_warm
        db.session.commit()

        return is_warm

    def regenerate_uuid(self) -> str:
        uuid_str = generate_uuid(base=str(self.id), salt=self.name)
        self.uuid = uuid_str
        db.session.commit()

        return uuid_str

    def to_dict(self) -> dict:
        client: Client = Client.query.get(self.client_id)

        # Get the warmup schedule
        warmup_schedule: WarmupScheduleLinkedIn = WarmupScheduleLinkedIn.query.filter_by(
            client_sdr_id=self.id
        ).first()

        return {
            "id": self.id,
            "client_name": client.company,
            "sdr_name": self.name,
            "sdr_title": self.title,
            "sdr_email": self.email,
            "active": self.active,
            "weekly_li_outbound_target": self.weekly_li_outbound_target,
            "weekly_email_outbound_target": self.weekly_email_outbound_target,
            "scheduling_link": self.scheduling_link,
            "pipeline_notifications_webhook_url": self.pipeline_notifications_webhook_url,
            "last_li_conversation_scrape_date": self.last_li_conversation_scrape_date,
            "li_connected": self.li_at_token is not None,
            "li_voyager_connected": self.li_cookies is not None
            and self.li_cookies != "INVALID",
            "nylas_connected": self.nylas_account_id is not None and self.nylas_active,
            "email_fetching_credits": self.email_fetching_credits,
            "ml_credits": self.ml_credits,
            "img_url": self.img_url,
            "img_expire": self.img_expire,
            "vessel_mailbox": self.vessel_mailbox,
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
            "do_not_contact_keywords": self.do_not_contact_keywords_in_company_names,
            "do_not_contact_company_names": self.do_not_contact_company_names,
            "linkedin_warmup_status": self.linkedin_warmup_status and self.linkedin_warmup_status.value,
            "warmup_schedule": warmup_schedule.to_dict() if warmup_schedule else None,
        }


class WarmupScheduleLinkedIn(db.Model):
    __tablename__ = "warmup_schedule_linkedin"

    id = db.Column(db.Integer, primary_key=True)

    client_sdr_id = db.Column(db.Integer, db.ForeignKey("client_sdr.id"))

    week_0_sla = db.Column(db.Integer, nullable=False, default=5)
    week_1_sla = db.Column(db.Integer, nullable=False, default=25)
    week_2_sla = db.Column(db.Integer, nullable=False, default=50)
    week_3_sla = db.Column(db.Integer, nullable=False, default=75)
    week_4_sla = db.Column(db.Integer, nullable=False, default=90)

    def is_warm(self, sla: int) -> bool:
        """Checks if the SDR is warm based on the SLA value. Needs to be greater than or equal to last warmup step.

        Args:
            sla (int): The SLA value to check against

        Returns:
            bool: True if the SDR is warm, False otherwise
        """
        if self.week_4_sla and sla >= self.week_4_sla:
            return True
        elif self.week_3_sla and sla >= self.week_3_sla:
            return True
        elif self.week_2_sla and sla >= self.week_2_sla:
            return True
        elif self.week_1_sla and sla >= self.week_1_sla:
            return True
        elif self.week_0_sla and sla >= self.week_0_sla:
            return True

        return False

    def set_conservative_schedule(self) -> bool:
        """Sets the conservative schedule for the SDR. This is the default schedule

        Returns:
            bool: True if successful, False otherwise
        """
        self.week_0_sla = 5
        self.week_1_sla = 25
        self.week_2_sla = 50
        self.week_3_sla = 75
        self.week_4_sla = 90
        db.session.commit()

        return True

    def set_custom_schedule(
        self,
        week_0_sla: int = None,
        week_1_sla: int = None,
        week_2_sla: int = None,
        week_3_sla: int = None,
        week_4_sla: int = None,
    ) -> bool:
        """Sets a custom schedule for the SDR. If a value is not provided, the
        existent value will be used. If no value exists, the conservative value will be used.

        Args:
            week_0_sla (int, optional): The SLA for week 0. Defaults to None.
            week_1_sla (int, optional): The SLA for week 1. Defaults to None.
            week_2_sla (int, optional): The SLA for week 2. Defaults to None.
            week_3_sla (int, optional): The SLA for week 3. Defaults to None.
            week_4_sla (int, optional): The SLA for week 4. Defaults to None.

        Returns:
            bool: True if successful, False otherwise
        """
        self.week_0_sla = week_0_sla or self.week_0_sla or 5
        self.week_1_sla = week_1_sla or self.week_1_sla or 25
        self.week_2_sla = week_2_sla or self.week_2_sla or 50
        self.week_3_sla = week_3_sla or self.week_3_sla or 75
        self.week_4_sla = week_4_sla or self.week_4_sla or 90
        db.session.commit()

        return True

    def get_next_sla(self, sla: int) -> int:
        """Gets the next SLA value for the SDR, or the current one.

        Args:
            sla (int): The current SLA value

        Returns:
            int: The next SLA value
        """
        if self.week_4_sla and sla >= self.week_4_sla:
            return sla
        elif self.week_3_sla and sla >= self.week_3_sla:
            return self.week_4_sla
        elif self.week_2_sla and sla >= self.week_2_sla:
            return self.week_3_sla
        elif self.week_1_sla and sla >= self.week_1_sla:
            return self.week_2_sla
        elif self.week_0_sla and sla >= self.week_0_sla:
            return self.week_1_sla

        return self.week_0_sla


    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "client_sdr_id": self.client_sdr_id,
            "week_0_sla": self.week_0_sla,
            "week_1_sla": self.week_1_sla,
            "week_2_sla": self.week_2_sla,
            "week_3_sla": self.week_3_sla,
            "week_4_sla": self.week_4_sla,
        }


class LinkedInSLAChange(db.Model):
    __tablename__ = "warmup_linkedin_sla_change"

    id = db.Column(db.Integer, primary_key=True)

    client_sdr_id = db.Column(db.Integer, db.ForeignKey("client_sdr.id"))

    # SLA values
    old_sla_value = db.Column(db.Integer, nullable=True)
    new_sla_value = db.Column(db.Integer, nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "client_sdr_id": self.client_sdr_id,
            "old_sla_value": self.old_sla_value,
            "new_sla_value": self.new_sla_value,
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
