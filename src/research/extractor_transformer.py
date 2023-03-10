from abc import ABC, abstractmethod


class ExtractorAndTransformer(ABC):
    """This is the base class for all ExtractorAndTransformer classes.

    This class is responsible for creating a payload, then creating points from that payload.
    """

    def __init__(self, prospect_id):
        self.prospect_id = prospect_id
        self.payload_id = None
        self.research_point_ids = None

    def run(self):
        """This method is the entry point for all ExtractorAndTransformer classes.

        This ExtractorAndTransformer will create a payload, then create points from that payload.
        """
        if self.payload:
            print(
                "Payload already exists for this prospect. Skipping... please reset payload if you'd like to re-run."
            )
            return

        payload_id = self.create_payload()
        self.from_payload_create_points(payload_id)

    @abstractmethod
    def create_payload(self):
        """This method should create a research payload for the prospect.

        This should return the payload_id.
        """
        print("Not implemented")

    @abstractmethod
    def from_payload_create_points(self):
        """This method should create points from the payload.

        Any and every ResearchPoint should be created here.
        """
        print("Not implemented")
