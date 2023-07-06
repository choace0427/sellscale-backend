exec(
    """
from model_import import ClientSDR 
from src.client.services import *

sdrs = ClientSDR.query.all()

for sdr in sdrs:
    print(sdr.id)
    reset_client_sdr_sight_auth_token(sdr.id)
"""
)
