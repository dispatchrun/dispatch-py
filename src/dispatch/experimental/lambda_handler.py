"""Integration of Dispatch programmable endpoints for AWS Lambda.

Example:

    from dispatch.experimental.lambda_handler import Dispatch

    dispatch = Dispatch(api_key="test-key")

    @dispatch.function
    def my_function():
        return "Hello World!"

    @dispatch.function
    def entrypoint():
        my_function()

    def handler(event, context):
        dispatch.handle(event, context, entrypoint="entrypoint")
    """

import asyncio
import base64
import json
import logging
from typing import Optional

from awslambdaric.lambda_context import LambdaContext

from dispatch.function import Registry
from dispatch.http import BlockingFunctionService
from dispatch.proto import Input
from dispatch.sdk.v1 import function_pb2 as function_pb
from dispatch.status import Status

logger = logging.getLogger(__name__)


class Dispatch(BlockingFunctionService):
    def __init__(
        self,
        registry: Optional[Registry] = None,
    ):
        """Initializes a Dispatch Lambda handler."""
        # We use a fake endpoint to initialize the base class. The actual endpoint (the Lambda ARN)
        # is only known when the handler is invoked.
        super().__init__(registry)

    def handle(
        self, event: str, context: LambdaContext, entrypoint: Optional[str] = None
    ):
        # The ARN is not none until the first invocation of the Lambda function.
        # We override the endpoint of all registered functions before any execution.
        if context.invoked_function_arn:
            self.endpoint = context.invoked_function_arn
        # TODO: this might mutate the default registry, we should figure out a better way.
        self.registry.endpoint = self.endpoint

        if not event:
            raise ValueError("event is required")

        try:
            raw = base64.b64decode(event)
        except Exception as e:
            raise ValueError("event is not base64 encoded") from e

        req = function_pb.RunRequest.FromString(raw)

        function: Optional[str] = req.function if req.function else entrypoint
        if not function:
            raise ValueError("function is required")

        logger.debug(
            "Dispatch handler invoked for %s function %s with runRequest: %s",
            self.endpoint,
            function,
            req,
        )

        try:
            func = self.registry.functions[req.function]
        except KeyError:
            raise ValueError(f"function {req.function} not found")

        input = Input(req)
        try:
            output = asyncio.run(func._primitive_call(input))
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
            respBytes = response.SerializeToString()
            respStr = base64.b64encode(respBytes).decode("utf-8")
            return bytes(json.dumps(respStr), "utf-8")
