from model_import import (
    EmailInteractionState,
    EmailSequenceState,
)

class SSData():
    """SSData is a class which holds data relevant to SellScale's custom email analytics data.

    Attributes:
        email (str): The email address of the prospect.
        email_interaction_state (EmailInteractionState): The interaction state of the prospect.
        email_sequence_state (EmailSequenceState): The sequence state of the prospect.

    Methods:
        from_dict: Creates an SSData object from a dictionary.
        to_str_dict: Returns a string dictionary representation of the SSData object.
        to_enum_dict: Returns an enum dictionary representation of the SSData object.
        get_email: Returns the email address of the prospect.
        get_email_interaction_state: Returns the interaction state of the prospect.
        get_email_sequence_state: Returns the sequence state of the prospect.
    """

    def __init__(
        self,
        email: str,
        email_interaction_state: EmailInteractionState,
        email_sequence_state: EmailSequenceState
    ):
        self.email = email
        self.email_interaction_state = email_interaction_state
        self.email_sequence_state = email_sequence_state

    @classmethod
    def from_dict(cls, raw_dict: dict):
        """Creates an SSData object from a dictionary.

        Returns:
            SSData: An SSData object.
        """
        return cls(
            raw_dict['email'],
            EmailInteractionState(raw_dict['email_interaction_state']),
            EmailSequenceState(raw_dict['email_sequence_state'])
        )

    def to_str_dict(self) -> dict:
        """Returns a string dictionary representation of the SSData object.

        Returns:
            dict: A string dictionary representation of the SSData object.
        """
        return {
            'email': self.email,
            'email_interaction_state': self.email_interaction_state.value,
            'email_sequence_state': self.email_sequence_state.value
        }

    def to_enum_dict(self) -> dict:
        """Returns an enum dictionary representation of the SSData object.

        Returns:
            dict: An enum dictionary representation of the SSData object.
        """
        return {
            'email': self.email,
            'email_interaction_state': self.email_interaction_state,
            'email_sequence_state': self.email_sequence_state
        }

    def get_email(self) -> str:
        """Returns the email address of the prospect.

        Returns:
            str: The email address of the prospect.
        """
        return self.email

    def get_email_interaction_state(self) -> EmailInteractionState:
        """Returns the interaction state of the prospect.

        Returns:
            EmailInteractionState: The interaction state of the prospect.
        """
        return self.email_interaction_state

    def get_email_sequence_state(self) -> EmailSequenceState:
        """Returns the sequence state of the prospect.

        Returns:
            EmailSequenceState: The sequence state of the prospect.
        """
        return self.email_sequence_state
