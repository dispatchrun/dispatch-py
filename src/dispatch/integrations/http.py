from dispatch.status import Status


def http_response_code_status(code: int) -> Status:
    """Returns a Status that's broadly equivalent to an HTTP response
    status code."""
    if code == 400:  # Bad Request
        return Status.INVALID_ARGUMENT
    elif code == 401:  # Unauthorized
        return Status.UNAUTHENTICATED
    elif code == 403:  # Forbidden
        return Status.PERMISSION_DENIED
    elif code == 404:  # Not Found
        return Status.NOT_FOUND
    elif code == 408:  # Request Timeout
        return Status.TIMEOUT
    elif code == 429:  # Too Many Requests
        return Status.THROTTLED
    elif code == 501:  # Not Implemented
        return Status.PERMANENT_ERROR

    category = code // 100
    if category == 1:  # 1xx informational
        return Status.PERMANENT_ERROR
    elif category == 2:  # 2xx success
        return Status.OK
    elif category == 3:  # 3xx redirection
        return Status.PERMANENT_ERROR
    elif category == 4:  # 4xx client error
        return Status.PERMANENT_ERROR
    elif category == 5:  # 5xx server error
        return Status.TEMPORARY_ERROR

    return Status.UNSPECIFIED
