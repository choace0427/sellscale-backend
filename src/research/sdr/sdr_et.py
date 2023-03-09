from src.research.extractor_transformer import ExtractorAndTransformer
from model_import import (ClientSDR, ResearchType)
from src.research.services import create_research_payload, create_research_point


class SDRExtractorTransformer(ExtractorAndTransformer):
    def __init__(self, prospect_id, client_sdr_id):
        super().__init__(prospect_id)
        self.client_sdr_id = client_sdr_id

    def create_payload(self):
        sdr: ClientSDR = ClientSDR.query.get(self.client_sdr_id)
        payload = sdr.questionnaire

        research_payload_id = create_research_payload(
            prospect_id=self.prospect_id,
            research_type=ResearchType.SDR_QUESTIONAIRE,
            payload=payload,
        )

