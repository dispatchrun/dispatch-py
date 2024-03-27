"""Integration of Dispatch programmable endpoints for FastAPI.

Example:

    from dispatch.experimental.lambda_handler import Dispatch

    dispatch = Dispatch(api_key="test-key")

    @dispatch.function
    def my_function():
        return "Hello World!"

    @dispatch.entrypoint
    def entrypoint():
        my_function()

    def handler(event, context):
        dispatch.handle(event, context)
    """

import base64
import logging
import json

from dispatch.function import Registry
from dispatch.proto import Input
from dispatch.sdk.v1 import function_pb2 as function_pb
from dispatch.status import Status

logger = logging.getLogger(__name__)


class Dispatch(Registry):
    def __init__(
        self,
        api_key: str | None = None,
        api_url: str | None = None,
    ):
        """Initializes a Dispatch Lambda handler.

        Args:
            api_key: Dispatch API key to use for authentication. Uses the value of
                the DISPATCH_API_KEY environment variable by default.

            api_url: The URL of the Dispatch API to use. Uses the value of the
                DISPATCH_API_URL environment variable if set, otherwise
                defaults to the public Dispatch API (DEFAULT_API_URL).

        """

        # The endpoint (AWS Lambda ARN) is set when handling the first request.
        super().__init__(endpoint=None, api_key=api_key, api_url=api_url)

    def handle(self, event, context):
        # Use the context to determine the ARN of the Lambda function.
        self.endpoint = context.invoked_function_arn

        logger.debug("Dispatch handler invoked for %s with event: %s", self.endpoint, event)

        if not event:
            raise ValueError("event is required")

        try:
            raw = base64.b64decode(event)
        except Exception as e:
            raise ValueError(f"event is not base64 encoded: {e}")

        req = function_pb.RunRequest.FromString(raw)
        print(req)
        if not req.function:
            req.function = "entrypoint"
            # FIXME raise ValueError("function is required")

        try:
            func = self.functions[req.function]
        except KeyError:
            raise ValueError(f"function {req.function} not found")

        input = Input(req)
        try:
            output = func._primitive_call(input)
        except Exception:
            logger.error("function '%s' fatal error", req.function, exc_info=True)
            raise  # FIXME
        else:
            response = output._message
            status = Status(response.status)

            if response.HasField("poll"):
                logger.debug(
                    "function '%s' polling with %d call(s)",
                    req.function,
                    len(response.poll.calls),
                )
            elif response.HasField("exit"):
                exit = response.exit
                if not exit.HasField("result"):
                    logger.debug("function '%s' exiting with no result", req.function)
                else:
                    result = exit.result
                    if result.HasField("output"):
                        logger.debug(
                            "function '%s' exiting with output value", req.function
                        )
                    elif result.HasField("error"):
                        err = result.error
                        logger.debug(
                            "function '%s' exiting with error: %s (%s)",
                            req.function,
                            err.message,
                            err.type,
                        )
                if exit.HasField("tail_call"):
                    logger.debug(
                        "function '%s' tail calling function '%s'",
                        exit.tail_call.function,
                    )

            logger.debug("finished handling run request with status %s", status.name)
            resp = response.SerializeToString()
            resp = base64.b64encode(resp).decode("utf-8")
            return bytes(json.dumps(resp), "utf-8")
