"""Integration of Dispatch functions with http."""

import logging
import os
from datetime import timedelta
from http.server import BaseHTTPRequestHandler
from typing import Mapping, Optional, Union

from http_message_signatures import InvalidSignature

from dispatch.function import Registry
from dispatch.proto import Input
from dispatch.sdk.v1 import function_pb2 as function_pb
from dispatch.signature import (
    CaseInsensitiveDict,
    Ed25519PublicKey,
    Request,
    parse_verification_key,
    verify_request,
)
from dispatch.status import Status

logger = logging.getLogger(__name__)


class Dispatch:
    """A Dispatch instance to be serviced by a http server. The Dispatch class
    acts as a factory for DispatchHandler objects, by capturing the variables
    that would be shared between all DispatchHandler instances it created."""

    def __init__(
        self,
        registry: Registry,
        verification_key: Optional[Union[Ed25519PublicKey, str, bytes]] = None,
    ):
        """Initialize a Dispatch http handler.

        Args:
            registry: The registry of functions to be serviced.
        """
        self.registry = registry
        self.verification_key = parse_verification_key(verification_key)

    def __call__(self, request, client_address, server):
        return FunctionService(
            request,
            client_address,
            server,
            registry=self.registry,
            verification_key=self.verification_key,
        )


class FunctionServiceError(Exception):
    __slots__ = ("status", "code", "message")

    def __init__(self, status, code, message):
        self.status = status
        self.code = code
        self.message = message


class FunctionService(BaseHTTPRequestHandler):

    def __init__(
        self,
        request,
        client_address,
        server,
        registry: Registry,
        verification_key: Optional[Ed25519PublicKey] = None,
    ):
        self.registry = registry
        self.verification_key = verification_key
        self.error_content_type = "application/json"
        super().__init__(request, client_address, server)

    def send_error_response_invalid_argument(self, message: str):
        self.send_error_response(400, "invalid_argument", message)

    def send_error_response_not_found(self, message: str):
        self.send_error_response(404, "not_found", message)

    def send_error_response_unauthenticated(self, message: str):
        self.send_error_response(401, "unauthenticated", message)

    def send_error_response_permission_denied(self, message: str):
        self.send_error_response(403, "permission_denied", message)

    def send_error_response_internal(self, message: str):
        self.send_error_response(500, "internal", message)

    def send_error_response(self, status: int, code: str, message: str):
        body = f'{{"code":"{code}","message":"{message}"}}'.encode()
        self.send_response(status)
        self.send_header("Content-Type", self.error_content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path != "/dispatch.sdk.v1.FunctionService/Run":
            self.send_error_response_not_found("path not found")
            return

        content_length = int(self.headers.get("Content-Length", 0))
        if content_length == 0:
            self.send_error_response_invalid_argument("content length is required")
            return
        if content_length < 0:
            self.send_error_response_invalid_argument("content length is negative")
            return
        if content_length > 16_000_000:
            self.send_error_response_invalid_argument("content length is too large")
            return

        data: bytes = self.rfile.read(content_length)

        method = "POST"
        url = self.requestline  # TODO: need full URL

        try:
            content = function_service_run(
                url,
                method,
                dict(self.headers),
                data,
                self.registry,
                self.verification_key,
            )
        except FunctionServiceError as e:
            return self.send_error_response(e.status, e.code, e.message)

        self.send_response(200)
        self.send_header("Content-Type", "application/proto")
        self.end_headers()
        self.wfile.write(content)


def function_service_run(
    url: str,
    method: str,
    headers: Mapping[str, str],
    data: bytes,
    function_registry: Registry,
    verification_key: Optional[Ed25519PublicKey],
) -> bytes:
    logger.debug("handling run request with %d byte body", len(data))

    if verification_key is None:
        logger.debug("skipping request signature verification")
    else:
        signed_request = Request(
            method=method,
            url=url,
            headers=CaseInsensitiveDict(headers),
            body=data,
        )
        max_age = timedelta(minutes=5)
        try:
            verify_request(signed_request, verification_key, max_age)
        except ValueError as e:
            raise FunctionServiceError(401, "unauthenticated", str(e))
        except InvalidSignature as e:
            # The http_message_signatures package sometimes wraps does not
            # attach a message to the exception, so we set a default to
            # have some context about the reason for the error.
            message = str(e) or "invalid signature"
            raise FunctionServiceError(403, "permission_denied", message)

    req = function_pb.RunRequest.FromString(data)
    if not req.function:
        raise FunctionServiceError(400, "invalid_argument", "function is required")

    try:
        func = function_registry.functions[req.function]
    except KeyError:
        logger.debug("function '%s' not found", req.function)
        raise FunctionServiceError(
            404, "not_found", f"function '{req.function}' does not exist"
        )

    input = Input(req)
    logger.info("running function '%s'", req.function)

    try:
        output = func._primitive_call(input)
    except Exception:
        # This indicates that an exception was raised in a primitive
        # function. Primitive functions must catch exceptions, categorize
        # them in order to derive a Status, and then return a RunResponse
        # that carries the Status and the error details. A failure to do
        # so indicates a problem, and we return a 500 rather than attempt
        # to catch and categorize the error here.
        logger.error("function '%s' fatal error", req.function, exc_info=True)
        raise FunctionServiceError(
            500, "internal", f"function '{req.function}' fatal error"
        )

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
                logger.debug("function '%s' exiting with output value", req.function)
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
    return response.SerializeToString()
