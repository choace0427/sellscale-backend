from src.email_outbound.models import EmailCustomizedFieldTypes
from src.ml.models import GNLPModelType


def test_email_field_types():
    email_customized_values = [e.value for e in EmailCustomizedFieldTypes]
    gnlp_values = [e.value for e in GNLPModelType]

    for e in email_customized_values:
        assert e in gnlp_values
