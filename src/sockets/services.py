from typing import Optional

import requests


def send_socket_message(event: str, payload: dict, room_id: Optional[str] = None):
    # print("send_socket_message", event, payload, room_id)

    response = requests.post(
        "https://socket-service-t6ln.onrender.com/send-message",
        json={
            "sdr_id": -1,
            "event": event,
            "room_id": room_id,
            "payload": payload,
        },
        headers={"Content-Type": "application/json"},
    )

    return (True,)
