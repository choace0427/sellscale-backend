from typing import Optional

import requests


import threading

# Create a lock for thread safety
lock = threading.Lock()

def send_socket_message(event: str, payload: dict, room_id: Optional[str] = None):
    with lock:
        try:
            response = requests.post(
                "https://socket-service-t6ln.onrender.com",
                json={
                    "sdr_id": -1,
                    "event": event,
                    "room_id": room_id,
                    "payload": payload,
                },
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
        except requests.RequestException as e:
            print(f"Socket request failed: {e}")
            return (False,)

    return (True,)
