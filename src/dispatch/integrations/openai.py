import openai  # type: ignore

from dispatch.integrations.http import http_response_code_status
from dispatch.status import Status, register_error_type


def openai_error_status(error: Exception) -> Status:
    # See https://github.com/openai/openai-python/blob/main/src/openai/_exceptions.py
    if isinstance(error, openai.APITimeoutError):
        return Status.TIMEOUT
    elif isinstance(error, openai.APIStatusError):
        return http_response_code_status(error.status_code)

    return Status.TEMPORARY_ERROR


# Register base exception.
register_error_type(openai.OpenAIError, openai_error_status)
