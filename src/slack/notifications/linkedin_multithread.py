import datetime
from typing import Optional
from src.client.models import Client, ClientArchetype, ClientSDR
from src.prospecting.models import Prospect
from src.prospecting.models import ProspectReferral
from src.email_outbound.models import ProspectEmail
from src.message_generation.models import GeneratedMessage
from src.slack.models import SlackNotificationType
from src.slack.slack_notification_center import slack_bot_send_message
from src.slack.slack_notification_class import SlackNotificationClass


class LinkedInMultiThreadNotification(SlackNotificationClass):
    """A Slack notification that is sent whenever the SDR gives feedback on a Demo

    `client_sdr_id` (MANDATORY): The ID of the ClientSDR that sent the notification
    `developer_mode` (MANDATORY): Whether or not the notification is being sent in developer mode. Defaults to False.
    `referral_id` (OPTIONAL): The ID of the referral to reference.

    This class inherits from SlackNotificationClass.
    """

    required_fields = {
        "sdr",
        "archetype_name",
        "referred_name",
        "referred_company",
        "referral_name",
        "referral_company",
        "referred_message",
        "referral_message",
        "direct_link",
    }

    def __init__(
        self,
        client_sdr_id: int,
        developer_mode: Optional[bool] = False,
        referred_prospect_id: Optional[int] = None,
        generated_message_id: Optional[int] = None,
    ):
        super().__init__(client_sdr_id, developer_mode)
        self.referred_prospect_id = referred_prospect_id
        self.generated_message_id = generated_message_id

        return

    def send_notification(self, preview_mode: bool) -> bool:
        """Sends a notification to Slack using the class's attributes and the Slack API. There should be no parameters to this function.

        Args:
            preview_mode (bool): Whether or not the notification is being sent in preview mode. Preview mode sends to a 'dummy' message to the channel.

        Returns:
            bool: Whether or not the message was successfully sent
        """

        def get_preview_fields() -> dict:
            """Gets the fields to be used in the preview message."""
            client_sdr: ClientSDR = ClientSDR.query.get(self.client_sdr_id)

            return {
                "sdr": client_sdr.name,
                "archetype_name": "CEOs of AI Companies",
                "referred_name": "Jane Doe",
                "referred_company": "AnotherCompany",
                "referral_name": "John Doe",
                "referral_company": "SomeCompany",
                "referred_message": "Hi Jane! Got your contact from John -- he mentioned you might be interested in our AI-powered sales platform. Would love to connect and chat!",
                "referral_message": "This sounds interesting, but I'm not sure if we're the right fit. I know someone that might benefit, reach out to Jane Doe at AnotherCompany.",
                "direct_link": "https://app.sellscale.com/authenticate?stytch_token_type=direct&token={auth_token}&redirect=contacts/".format(
                    auth_token=client_sdr.auth_token,
                ),
            }

        def get_fields() -> dict:
            """Gets the fields to be used in the message."""
            client_sdr: ClientSDR = ClientSDR.query.get(self.client_sdr_id)

            prospect_referred: Prospect = Prospect.query.get(self.referred_prospect_id)
            referral_record: ProspectReferral = ProspectReferral.query.filter_by(
                prospect_id=self.referred_prospect_id
            ).first()
            if not referral_record:
                raise Exception(
                    "No referral record found for prospect_id: {}".format(
                        self.prospect_id
                    )
                )

            prospect_referring: Prospect = Prospect.query.get(
                referral_record.referral_id
            )
            archetype: ClientArchetype = ClientArchetype.query.get(
                prospect_referred.archetype_id
            )
            gm: GeneratedMessage = GeneratedMessage.query.get(self.generated_message_id)

            return {
                "sdr": client_sdr.name,
                "archetype_name": archetype.archetype,
                "referred_name": prospect_referred.full_name,
                "referred_company": prospect_referred.company,
                "referral_name": prospect_referring.full_name,
                "referral_company": prospect_referring.company,
                "referral_message": prospect_referring.li_last_message_from_prospect,
                "referred_message": gm.completion if gm else "-",
                "direct_link": "https://app.sellscale.com/authenticate?stytch_token_type=direct&token={auth_token}&redirect=prospects/{prospect_id}".format(
                    auth_token=client_sdr.auth_token,
                    prospect_id=prospect_referred.id,
                ),
            }

        # Get the required objects / fields
        if preview_mode:
            fields = get_preview_fields()
        else:
            fields = get_fields()

        # Get the fields
        sdr = fields.get("sdr")
        archetype_name = fields.get("archetype_name")
        referred_name = fields.get("referred_name")
        referred_company = fields.get("referred_company")
        referral_name = fields.get("referral_name")
        referral_company = fields.get("referral_company")
        referred_message = fields.get("referred_message")
        referral_message = fields.get("referral_message")
        direct_link = fields.get("direct_link")
        
        #validate the required fields
        self.validate_required_fields(fields)

        client_sdr: ClientSDR = ClientSDR.query.get(self.client_sdr_id)
        client: Client = Client.query.get(client_sdr.client_id)

        # Send the message
        slack_bot_send_message(
            notification_type=SlackNotificationType.LINKEDIN_MULTI_THREAD,
            client_id=client.id,
            base_message=f"🧵 SellScale just multi-threaded",
            blocks=[
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "🧵 SellScale just multi-threaded",
                        "emoji": True,
                    },
                },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": "SellScale is reaching out to *{referred_name} ({referred_company})* through a referral from *{referral_name} ({referral_company})* on behalf of *{sdr_name}* for *{archetype_name}*".format(
                                referral_name=referred_name,
                                referral_company=referral_company,
                                referred_name=referred_name,
                                referred_company=referred_company,
                                sdr_name=client_sdr.name,
                                archetype_name=archetype_name,
                            ),
                        }
                    ],
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*😴 Original Contact*: {referral_name} ({referral_company})\n*Message from Contact*: _{referral_message}_".format(
                            referral_name=referral_name,
                            referral_company=referral_company,
                            referral_message=referral_message,
                        ),
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*🆕 New Contact*: {referred_name} ({referred_company})\n*Outreach to new contact*: _{referred_message}_".format(
                            referred_name=referred_name,
                            referred_company=referred_company,
                            referred_message=referred_message,
                        ),
                    },
                },
            ],
            client_sdr_id=client_sdr.id,
            override_preference=preview_mode,
            testing=self.developer_mode,
        )

        return True

    def send_notification_preview(self) -> bool:
        """Sends a test notification (using dummy data) to Slack using the class's attributes and the Slack API. There should be no parameters to this function.

        Returns:
            bool: Whether or not the message was successfully sent
        """
        return super().send_notification_preview()
