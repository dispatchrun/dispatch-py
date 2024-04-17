"""Integration of Dispatch functions with gRPC."""

import logging
import os
from typing import Optional, Union

from dispatch.function import Registry
from dispatch.proto import Input
from dispatch.sdk.v1.function_pb2_grpc import FunctionServiceServicer

logger = logging.getLogger(__name__)


class FunctionService(FunctionServiceServicer):
    """A Dispatch instance to be serviced by a gRPC server."""

    def __init__(        self,            registry: Registry    ):
        """Initialize a Dispatch gRPC service.

        Args:
            registry: The registry of functions to be serviced.
        """
        self.registry = registry

    def Run(self, request, context):
        if not request.function:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details("function is required")
            return

        try:
            func = self.registry.functions[request.function]
        except KeyError:
            logger.debug("function '%s' not found", request.function)
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details(f"function '{request.function}' does not exist")
            return

        logger.info("running function '%s'", request.function)
        try:
            output = func._primitive_call(Input(request))
        except Exception as e:
            logger.error("function '%s' fatal error", request.function, exc_info=True)
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"function '{request.function}' fatal error")
            return

        return output._message

# TODO: interceptor for verification key
