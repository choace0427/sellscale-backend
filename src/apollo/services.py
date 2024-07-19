import requests
from app import db
from src.apollo.models import ApolloCookies


def save_apollo_cookies(cookies: str, csrf_token: str) -> bool:
    """Saves Apollo cookies.

    Args:
        cookies (str): cookies string
        csrf_token (str): CSRF token

    Returns:
        bool: True if cookies were saved successfully, False otherwise
    """
    try:
        # Clear old Apollo cookies
        ApolloCookies.query.delete()

        # Save new Apollo cookies
        apollo_cookies = ApolloCookies(cookies=cookies, csrf_token=csrf_token)
        db.session.add(apollo_cookies)
        db.session.commit()
        return True
    except Exception as e:
        print(f"Error saving Apollo cookies: {e}")
        return False


def get_apollo_cookies() -> dict:
    """Gets Apollo cookies.

    Returns:
        dict: Apollo cookies
    """
    try:
        apollo_cookies: ApolloCookies = ApolloCookies.query.first()
        return apollo_cookies.cookies, apollo_cookies.csrf_token
    except Exception as e:
        print(f"Error getting Apollo cookies: {e}")
        return {}

def get_fuzzy_company_list(q_tag_fuzzy_name):
    cookies, csrf_token = get_apollo_cookies()
    if not cookies:
        return (
           ({"status": "error", "message": "Error getting Apollo cookies."}),
            500,
        )
    headers = {
        "x-csrf-token": csrf_token,
        "cookie": cookies,
    }
    params = {
        "q_tag_fuzzy_name": q_tag_fuzzy_name,
        "kind": "technology",
        "display_mode": "fuzzy_select_mode",
        "cacheKey": 1705003292782,
    }
    response = requests.get(
        "https://app.apollo.io/api/v1/tags/search", headers=headers, params=params
    )

    return response