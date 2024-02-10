import httpx

from dispatch.integrations.http import http_response_code_status
from dispatch.status import Status, register_error_type, register_output_type


def httpx_error_status(error: Exception) -> Status:
    # See https://www.python-httpx.org/exceptions/
    match error:
        case httpx.HTTPStatusError():
            return httpx_response_status(error.response)
        case httpx.InvalidURL():
            return Status.INVALID_ARGUMENT
        case httpx.UnsupportedProtocol():
            return Status.INVALID_ARGUMENT
        case httpx.TimeoutException():
            return Status.TIMEOUT

    return Status.TEMPORARY_ERROR


def httpx_response_status(response: httpx.Response) -> Status:
    return http_response_code_status(response.status_code)


# Register types of things that a function might return.
register_output_type(httpx.Response, httpx_response_status)


# Register base exceptions.
register_error_type(httpx.HTTPError, httpx_error_status)
register_error_type(httpx.StreamError, httpx_error_status)
register_error_type(httpx.InvalidURL, httpx_error_status)
register_error_type(httpx.CookieConflict, httpx_error_status)
