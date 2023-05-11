EMAIL_PROVIDERS_BOUNCED_ADDRESSES = {
    'mailer-daemon@googlemail.com',
    'postmaster@yahoo.com',
    'postmaster@hotmail.com',
    'postmaster@outlook.com',
    'postmaster@aol.com',
    'abuse@mailchimp.com',
}

def is_email_bounced(sender: str, body: str) -> bool:
    """ Detect if a email was bounced by running the email sender and email body through a heuristic.

    Args:
        sender (str): The email address of the sender.
        body (str): The body of the email.

    Returns:
        bool: True if the email was bounced, False otherwise.
    """
    if sender in EMAIL_PROVIDERS_BOUNCED_ADDRESSES:
        return True

    if 'The email account that you tried to reach does not exist.' in body:
        return True

    heuristic_counter = 0

    # Chain of heuristics
    if '550 5.1.1' in body:
        heuristic_counter += 1
    if 'email address' or 'email account' in body:
        heuristic_counter += 1
    if 'does not exist' in body:
        heuristic_counter += 1

    if heuristic_counter >= 3:
        return True

