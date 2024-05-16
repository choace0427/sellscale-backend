import os
from retell import Retell

def initiate_retell_call(phone_number):
    retell_api_key = os.environ.get("RETELL_API_KEY")
    client = Retell(api_key=retell_api_key)

    try:
        register_call_response = client.call.create(
            from_number='+15105887486', 
            to_number=phone_number
        )
        response_message = {
            "message": "Call initiated successfully",
            "call_details": register_call_response
        }
        status_code = 200
    except Exception as e:
        response_message = {
            "message": "Failed to initiate call",
            "error": str(e)
        }
        status_code = 500

    return response_message, status_code