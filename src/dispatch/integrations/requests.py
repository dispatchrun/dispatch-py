import requests

from dispatch.integrations.http import http_response_code_status
from dispatch.status import Status, register_error_type, register_output_type


def requests_error_status(error: Exception) -> Status:
    # See https://requests.readthedocs.io/en/latest/api/#exceptions
    # and https://requests.readthedocs.io/en/latest/_modules/requests/exceptions/
    match error:
        case requests.HTTPError():
            if error.response is not None:
                return requests_response_status(error.response)
        case requests.Timeout():
            return Status.TIMEOUT
        case ValueError():  # base class of things like requests.InvalidURL, etc.
            return Status.INVALID_ARGUMENT

    return Status.TEMPORARY_ERROR


def requests_response_status(response: requests.Response) -> Status:
    return http_response_code_status(response.status_code)


# Register types of things that a function might return.
register_output_type(requests.Response, requests_response_status)

# Register base exception.
register_error_type(requests.RequestException, requests_error_status)
