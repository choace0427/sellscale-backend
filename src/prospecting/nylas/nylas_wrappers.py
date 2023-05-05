import requests


def wrapped_nylas_get_threads(nylas_auth_code: str, email: str, limit: int) -> list[dict]:
    """ Wrapper for Nylas get threads function.

    Args:
        nylas_auth_code (str): Auth code for Nylas API
        email (str): Email to search for thread
        limit (int): Number of threads to return

    Returns:
        list[dict]: List of threads
    """
    # Get threads from Nylas
    res = requests.get(
        f"https://api.nylas.com/threads?limit={limit}&any_email={email}",
        headers={"Authorization": f"Bearer {nylas_auth_code}"},
    )
    if res.status_code != 200:
        return []

    result: list[dict] = res.json()

    return result


def wrapped_nylas_get_single_thread(nylas_auth_code: str, thread_id: str) -> dict:
    """ Wrapper for Nylas get single thread function.

    Args:
        nylas_auth_code (str): Auth code for Nylas API
        thread_id (str): ID of thread to get

    Returns:
        dict: Thread
    """
    # Get thread from Nylas
    res = requests.get(
        f"https://api.nylas.com/threads/{thread_id}",
        headers={"Authorization": f"Bearer {nylas_auth_code}"},
    )
    if res.status_code != 200:
        return {}

    result: dict = res.json()

    return result
