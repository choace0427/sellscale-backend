from requests.exceptions import HTTPError, ConnectionError, Timeout


class ReadTimeoutError(Exception):
    pass


class Server5xxError(Exception):
    pass


class LinkedInError(Exception):
    pass


class LinkedInBadRequestError(LinkedInError):
    pass


class LinkedInForbiddenError(LinkedInError):
    pass


class LinkedInNotFoundError(LinkedInError):
    pass


class LinkedInTooManyRequestsError(LinkedInError):
    pass


ERROR_CODE_EXCEPTION_MAPPING = {
    400: LinkedInBadRequestError,
    403: LinkedInForbiddenError,
    404: LinkedInNotFoundError,
    429: LinkedInTooManyRequestsError,
}


def get_exception_for_error_code(error_code):
    return ERROR_CODE_EXCEPTION_MAPPING.get(error_code, None)


def raise_for_error(response):
    # LOGGER.error(f'{response.status_code}: {response.text}, REASON: {response.reason}')

    try:
        response.raise_for_status()
    except (HTTPError, ConnectionError) as error:
        try:
            content_length = len(response.content)
            if content_length == 0:
                # There is nothing we can do here since LinkedIn has neither sent
                # us a 2xx response nor a response content.
                return
            response = response.json()
            error_code = response.get("status")
            if get_exception_for_error_code(error_code):
                message = "%s: %s" % (
                    response.get("error", str(error)),
                    response.get("message", "Unknown Error"),
                )
                ex = get_exception_for_error_code(error_code)
                raise ex(message)
            else:
                raise LinkedInError(error)
        except (ValueError, TypeError):
            raise LinkedInError(error)
