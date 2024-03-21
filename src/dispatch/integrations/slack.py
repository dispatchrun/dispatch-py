import slack_sdk
import slack_sdk.errors
import slack_sdk.web

from dispatch.integrations.http import http_response_code_status
from dispatch.status import Status, register_error_type, register_output_type


def slack_error_status(error: Exception) -> Status:
    # See https://github.com/slackapi/python-slack-sdk/blob/main/slack/errors.py
    match error:
        case slack_sdk.errors.SlackApiError():
            if error.response is not None:
                return slack_response_status(error.response)

    return Status.TEMPORARY_ERROR


def slack_response_status(response: slack_sdk.web.SlackResponse) -> Status:
    return http_response_code_status(response.status_code)


# Register types of things that a function might return.
register_output_type(slack_sdk.web.SlackResponse, slack_response_status)

# Register base exception.
register_error_type(slack_sdk.errors.SlackClientError, slack_error_status)
