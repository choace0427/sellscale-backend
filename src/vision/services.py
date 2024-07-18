from typing import Optional
import requests
import os


def attempt_chat_completion_with_vision(
    message: str,
    webpage_url: Optional[str] = None,
    image_url: Optional[str] = None,
    max_tokens: Optional[int] = 300,
    image_contents: Optional[str] = None,
):
    api_key = os.environ.get("OPENAI_KEY")

    if image_url:
        image_contents = image_url
    if webpage_url:
        # Convert webpage to image (as base64)
        response = requests.post(
            "https://production-sellscale-vision.onrender.com/screenshot",
            json={"url": webpage_url},
        )
        if response.status_code == 200:
            image_contents = f"data:image/png;base64,{response.text}"

    if image_contents is None:
        return False, "No image data found"

    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    payload = {
        "model": "gpt-4-vision-preview",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": message.strip()},
                    {
                        "type": "image_url",
                        "image_url": {"url": image_contents},
                    },
                ],
            }
        ],
        "max_tokens": max_tokens,
    }
    res = requests.post(
        "https://api.openai.com/v1/chat/completions", headers=headers, json=payload
    )
    response = res.json()
    if response is None or response["choices"] is None or len(response["choices"]) == 0:
        return False, "No response from OpenAI API"

    choices = response["choices"]
    top_choice = choices[0]
    result = top_choice["message"]["content"].strip()
    return True, result


def attempt_chat_completion_with_vision_base64(
        message: str,
        base_64_image: str,
):
    api_key = os.environ.get("OPENAI_KEY")

    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    payload = {
        "model": "gpt-4o",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": message.strip()},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base_64_image}"
                        },
                    },
                ],
            }
        ],
        "max_tokens": 2000,
    }
    res = requests.post(
        "https://api.openai.com/v1/chat/completions", headers=headers, json=payload
    )
    response = res.json()

    if response is None or response["choices"] is None or len(response["choices"]) == 0:
        return False, "No response from OpenAI API"

    choices = response["choices"]
    top_choice = choices[0]
    result = top_choice["message"]["content"].strip()
    return True, result
