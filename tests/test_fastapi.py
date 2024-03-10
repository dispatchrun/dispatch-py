import base64
import os
import pickle
import unittest
from typing import Any
from unittest import mock

import fastapi
import google.protobuf.any_pb2
import google.protobuf.wrappers_pb2
import httpx
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from fastapi.testclient import TestClient

from dispatch.experimental.durable.registry import clear_functions
from dispatch.fastapi import Dispatch, parse_verification_key
from dispatch.function import Arguments, Error, Function, Input, Output
from dispatch.proto import _any_unpickle as any_unpickle
from dispatch.sdk.v1 import call_pb2 as call_pb
from dispatch.sdk.v1 import function_pb2 as function_pb
from dispatch.signature import public_key_from_pem
from dispatch.status import Status
from dispatch.test import EndpointClient

public_key_pem = "-----BEGIN PUBLIC KEY-----\nMCowBQYDK2VwAyEAJrQLj5P/89iXES9+vFgrIy29clF9CC/oPPsw3c5D0bs=\n-----END PUBLIC KEY-----"
public_key_pem2 = "-----BEGIN PUBLIC KEY-----\\nMCowBQYDK2VwAyEAJrQLj5P/89iXES9+vFgrIy29clF9CC/oPPsw3c5D0bs=\\n-----END PUBLIC KEY-----"
public_key = public_key_from_pem(public_key_pem)
public_key_bytes = public_key.public_bytes_raw()
public_key_b64 = base64.b64encode(public_key_bytes)


def create_dispatch_instance(app, endpoint):
    return Dispatch(
        app,
        endpoint=endpoint,
        api_key="0000000000000000",
        api_url="http://127.0.0.1:10000",
    )


class TestFastAPI(unittest.TestCase):

    def test_Dispatch(self):
        app = fastapi.FastAPI()
        create_dispatch_instance(app, "https://127.0.0.1:9999")

        @app.get("/")
        def read_root():
            return {"Hello": "World"}

        client = TestClient(app)

        # Ensure existing routes are still working.
        resp = client.get("/")
        self.assertEqual(resp.status_code, 200)

        self.assertEqual(resp.json(), {"Hello": "World"})

        # Ensure Dispatch root is available.
        resp = client.post("/dispatch.sdk.v1.FunctionService/Run")
        self.assertEqual(resp.status_code, 400)

    def test_Dispatch_no_app(self):
        with self.assertRaises(ValueError):
            create_dispatch_instance(None, endpoint="http://127.0.0.1:9999")

    @mock.patch.dict(os.environ, {"DISPATCH_ENDPOINT_URL": ""})
    def test_Dispatch_no_endpoint(self):
        app = fastapi.FastAPI()
        with self.assertRaises(ValueError):
            create_dispatch_instance(app, endpoint="")

    def test_Dispatch_endpoint_no_scheme(self):
        app = fastapi.FastAPI()
        with self.assertRaises(ValueError):
            create_dispatch_instance(app, endpoint="127.0.0.1:9999")

    def test_fastapi_simple_request(self):
        app = fastapi.FastAPI()
        dispatch = create_dispatch_instance(app, endpoint="http://127.0.0.1:9999/")

        @dispatch.primitive_function
        def my_function(input: Input) -> Output:
            return Output.value(
                f"You told me: '{input.input}' ({len(input.input)} characters)"
            )

        client = EndpointClient.from_app(app)

        pickled = pickle.dumps("Hello World!")
        input_any = google.protobuf.any_pb2.Any()
        input_any.Pack(google.protobuf.wrappers_pb2.BytesValue(value=pickled))

        req = function_pb.RunRequest(
            function=my_function.name,
            input=input_any,
        )

        resp = client.run(req)

        self.assertIsInstance(resp, function_pb.RunResponse)

        resp.exit.result.output.Unpack(
            output_bytes := google.protobuf.wrappers_pb2.BytesValue()
        )
        output = pickle.loads(output_bytes.value)

        self.assertEqual(output, "You told me: 'Hello World!' (12 characters)")

    @mock.patch.dict(os.environ, {"DISPATCH_VERIFICATION_KEY": public_key_pem})
    def test_parse_verification_key_env_pem_str(self):
        verification_key = parse_verification_key(None)
        self.assertIsInstance(verification_key, Ed25519PublicKey)
        self.assertEqual(verification_key.public_bytes_raw(), public_key_bytes)

    @mock.patch.dict(os.environ, {"DISPATCH_VERIFICATION_KEY": public_key_pem2})
    def test_parse_verification_key_env_pem_escaped_newline_str(self):
        verification_key = parse_verification_key(None)
        self.assertIsInstance(verification_key, Ed25519PublicKey)
        self.assertEqual(verification_key.public_bytes_raw(), public_key_bytes)

    @mock.patch.dict(os.environ, {"DISPATCH_VERIFICATION_KEY": public_key_b64.decode()})
    def test_parse_verification_key_env_b64_str(self):
        verification_key = parse_verification_key(None)
        self.assertIsInstance(verification_key, Ed25519PublicKey)
        self.assertEqual(verification_key.public_bytes_raw(), public_key_bytes)

    def test_parse_verification_key_none(self):
        # The verification key is optional. Both Dispatch(verification_key=...) and
        # DISPATCH_VERIFICATION_KEY may be omitted/None.
        verification_key = parse_verification_key(None)
        self.assertIsNone(verification_key)

    def test_parse_verification_key_ed25519publickey(self):
        verification_key = parse_verification_key(public_key)
        self.assertIsInstance(verification_key, Ed25519PublicKey)
        self.assertEqual(verification_key.public_bytes_raw(), public_key_bytes)

    def test_parse_verification_key_pem_str(self):
        verification_key = parse_verification_key(public_key_pem)
        self.assertIsInstance(verification_key, Ed25519PublicKey)
        self.assertEqual(verification_key.public_bytes_raw(), public_key_bytes)

    def test_parse_verification_key_pem_escaped_newline_str(self):
        verification_key = parse_verification_key(public_key_pem2)
        self.assertIsInstance(verification_key, Ed25519PublicKey)
        self.assertEqual(verification_key.public_bytes_raw(), public_key_bytes)

    def test_parse_verification_key_pem_bytes(self):
        verification_key = parse_verification_key(public_key_pem.encode())
        self.assertIsInstance(verification_key, Ed25519PublicKey)
        self.assertEqual(verification_key.public_bytes_raw(), public_key_bytes)

    def test_parse_verification_key_b64_str(self):
        verification_key = parse_verification_key(public_key_b64.decode())
        self.assertIsInstance(verification_key, Ed25519PublicKey)
        self.assertEqual(verification_key.public_bytes_raw(), public_key_bytes)

    def test_parse_verification_key_b64_bytes(self):
        verification_key = parse_verification_key(public_key_b64)
        self.assertIsInstance(verification_key, Ed25519PublicKey)
        self.assertEqual(verification_key.public_bytes_raw(), public_key_bytes)

    def test_parse_verification_key_invalid(self):
        with self.assertRaisesRegex(ValueError, "invalid verification key 'foo'"):
            parse_verification_key("foo")

    @mock.patch.dict(os.environ, {"DISPATCH_VERIFICATION_KEY": "foo"})
    def test_parse_verification_key_invalid_env(self):
        with self.assertRaisesRegex(
            ValueError, "invalid DISPATCH_VERIFICATION_KEY 'foo'"
        ):
            parse_verification_key(None)


def response_output(resp: function_pb.RunResponse) -> Any:
    return any_unpickle(resp.exit.result.output)


class TestCoroutine(unittest.TestCase):
    def setUp(self):
        clear_functions()

        self.app = fastapi.FastAPI()

        @self.app.get("/")
        def root():
            return "OK"

        self.dispatch = create_dispatch_instance(
            self.app, endpoint="https://127.0.0.1:9999"
        )
        self.http_client = TestClient(self.app)
        self.client = EndpointClient.from_app(self.app)

    def execute(
        self, func: Function, input=None, state=None, calls=None
    ) -> function_pb.RunResponse:
        """Test helper to invoke coroutines on the local server."""
        req = function_pb.RunRequest(function=func.name)

        if input is not None:
            input_bytes = pickle.dumps(input)
            input_any = google.protobuf.any_pb2.Any()
            input_any.Pack(google.protobuf.wrappers_pb2.BytesValue(value=input_bytes))
            req.input.CopyFrom(input_any)
        if state is not None:
            req.poll_result.coroutine_state = state
        if calls is not None:
            for c in calls:
                req.poll_result.results.append(c)

        resp = self.client.run(req)
        self.assertIsInstance(resp, function_pb.RunResponse)
        return resp

    def call(self, func: Function, *args, **kwargs) -> function_pb.RunResponse:
        return self.execute(func, input=Arguments(args, kwargs))

    def proto_call(self, call: call_pb.Call) -> call_pb.CallResult:
        req = function_pb.RunRequest(
            function=call.function,
            input=call.input,
        )
        resp = self.client.run(req)
        self.assertIsInstance(resp, function_pb.RunResponse)

        # Assert the response is terminal. Good enough until the test client can
        # orchestrate coroutines.
        self.assertTrue(len(resp.poll.coroutine_state) == 0)

        resp.exit.result.correlation_id = call.correlation_id
        return resp.exit.result

    def test_no_input(self):
        @self.dispatch.primitive_function
        def my_function(input: Input) -> Output:
            return Output.value("Hello World!")

        resp = self.execute(my_function)

        out = response_output(resp)
        self.assertEqual(out, "Hello World!")

    def test_missing_coroutine(self):
        req = function_pb.RunRequest(
            function="does-not-exist",
        )

        with self.assertRaises(httpx.HTTPStatusError) as cm:
            self.client.run(req)
        self.assertEqual(cm.exception.response.status_code, 404)

    def test_string_input(self):
        @self.dispatch.primitive_function
        def my_function(input: Input) -> Output:
            return Output.value(f"You sent '{input.input}'")

        resp = self.execute(my_function, input="cool stuff")
        out = response_output(resp)
        self.assertEqual(out, "You sent 'cool stuff'")

    def test_error_on_access_state_in_first_call(self):
        @self.dispatch.primitive_function
        def my_function(input: Input) -> Output:
            try:
                print(input.coroutine_state)
            except ValueError:
                return Output.error(
                    Error.from_exception(
                        ValueError("This input is for a first function call")
                    )
                )
            return Output.value("not reached")

        resp = self.execute(my_function, input="cool stuff")
        self.assertEqual("ValueError", resp.exit.result.error.type)
        self.assertEqual(
            "This input is for a first function call", resp.exit.result.error.message
        )

    def test_error_on_access_input_in_second_call(self):
        @self.dispatch.primitive_function
        def my_function(input: Input) -> Output:
            if input.is_first_call:
                return Output.poll(state=42)
            try:
                print(input.input)
            except ValueError:
                return Output.error(
                    Error.from_exception(
                        ValueError("This input is for a resumed coroutine")
                    )
                )
            return Output.value("not reached")

        resp = self.execute(my_function, input="cool stuff")
        self.assertEqual(42, pickle.loads(resp.poll.coroutine_state))

        resp = self.execute(my_function, state=resp.poll.coroutine_state)
        self.assertEqual("ValueError", resp.exit.result.error.type)
        self.assertEqual(
            "This input is for a resumed coroutine", resp.exit.result.error.message
        )

    def test_duplicate_coro(self):
        @self.dispatch.primitive_function
        def my_function(input: Input) -> Output:
            return Output.value("Do one thing")

        with self.assertRaises(ValueError):

            @self.dispatch.primitive_function
            def my_function(input: Input) -> Output:
                return Output.value("Do something else")

    def test_two_simple_coroutines(self):
        @self.dispatch.primitive_function
        def echoroutine(input: Input) -> Output:
            return Output.value(f"Echo: '{input.input}'")

        @self.dispatch.primitive_function
        def len_coroutine(input: Input) -> Output:
            return Output.value(f"Length: {len(input.input)}")

        data = "cool stuff"
        resp = self.execute(echoroutine, input=data)
        out = response_output(resp)
        self.assertEqual(out, "Echo: 'cool stuff'")

        resp = self.execute(len_coroutine, input=data)
        out = response_output(resp)
        self.assertEqual(out, "Length: 10")

    def test_coroutine_with_state(self):
        @self.dispatch.primitive_function
        def coroutine3(input: Input) -> Output:
            if input.is_first_call:
                counter = input.input
            else:
                counter = input.coroutine_state
            counter -= 1
            if counter <= 0:
                return Output.value("done")
            return Output.poll(state=counter)

        # first call
        resp = self.execute(coroutine3, input=4)
        state = resp.poll.coroutine_state
        self.assertTrue(len(state) > 0)

        # resume, state = 3
        resp = self.execute(coroutine3, state=state)
        state = resp.poll.coroutine_state
        self.assertTrue(len(state) > 0)

        # resume, state = 2
        resp = self.execute(coroutine3, state=state)
        state = resp.poll.coroutine_state
        self.assertTrue(len(state) > 0)

        # resume, state = 1
        resp = self.execute(coroutine3, state=state)
        state = resp.poll.coroutine_state
        self.assertTrue(len(state) == 0)
        out = response_output(resp)
        self.assertEqual(out, "done")

    def test_coroutine_poll(self):
        @self.dispatch.primitive_function
        def coro_compute_len(input: Input) -> Output:
            return Output.value(len(input.input))

        @self.dispatch.primitive_function
        def coroutine_main(input: Input) -> Output:
            if input.is_first_call:
                text: str = input.input
                return Output.poll(
                    state=text, calls=[coro_compute_len._build_primitive_call(text)]
                )
            text = input.coroutine_state
            length = input.call_results[0].output
            return Output.value(f"length={length} text='{text}'")

        resp = self.execute(coroutine_main, input="cool stuff")

        # main saved some state
        state = resp.poll.coroutine_state
        self.assertTrue(len(state) > 0)
        # main asks for 1 call to compute_len
        self.assertEqual(len(resp.poll.calls), 1)
        call = resp.poll.calls[0]
        self.assertEqual(call.function, coro_compute_len.name)
        self.assertEqual(any_unpickle(call.input), "cool stuff")

        # make the requested compute_len
        resp2 = self.proto_call(call)
        # check the result is the terminal expected response
        len_resp = any_unpickle(resp2.output)
        self.assertEqual(10, len_resp)

        # resume main with the result
        resp = self.execute(coroutine_main, state=state, calls=[resp2])
        # validate the final result
        self.assertTrue(len(resp.poll.coroutine_state) == 0)
        out = response_output(resp)
        self.assertEqual("length=10 text='cool stuff'", out)

    def test_coroutine_poll_error(self):
        @self.dispatch.primitive_function
        def coro_compute_len(input: Input) -> Output:
            return Output.error(Error(Status.PERMANENT_ERROR, "type", "Dead"))

        @self.dispatch.primitive_function
        def coroutine_main(input: Input) -> Output:
            if input.is_first_call:
                text: str = input.input
                return Output.poll(
                    state=text, calls=[coro_compute_len._build_primitive_call(text)]
                )
            error = input.call_results[0].error
            if error is not None:
                return Output.value(f"msg={error.message} type='{error.type}'")
            else:
                raise RuntimeError(f"unexpected call results: {input.call_results}")

        resp = self.execute(coroutine_main, input="cool stuff")

        # main saved some state
        state = resp.poll.coroutine_state
        self.assertTrue(len(state) > 0)
        # main asks for 1 call to compute_len
        self.assertEqual(len(resp.poll.calls), 1)
        call = resp.poll.calls[0]
        self.assertEqual(call.function, coro_compute_len.name)
        self.assertEqual(any_unpickle(call.input), "cool stuff")

        # make the requested compute_len
        resp2 = self.proto_call(call)

        # resume main with the result
        resp = self.execute(coroutine_main, state=state, calls=[resp2])
        # validate the final result
        self.assertTrue(len(resp.poll.coroutine_state) == 0)
        out = response_output(resp)
        self.assertEqual(out, "msg=Dead type='type'")

    def test_coroutine_error(self):
        @self.dispatch.primitive_function
        def mycoro(input: Input) -> Output:
            return Output.error(Error(Status.PERMANENT_ERROR, "sometype", "dead"))

        resp = self.execute(mycoro)
        self.assertEqual("sometype", resp.exit.result.error.type)
        self.assertEqual("dead", resp.exit.result.error.message)

    def test_coroutine_expected_exception(self):
        @self.dispatch.primitive_function
        def mycoro(input: Input) -> Output:
            try:
                1 / 0
            except ZeroDivisionError as e:
                return Output.error(Error.from_exception(e))
            self.fail("should not reach here")

        resp = self.execute(mycoro)
        self.assertEqual("ZeroDivisionError", resp.exit.result.error.type)
        self.assertEqual("division by zero", resp.exit.result.error.message)
        self.assertEqual(Status.PERMANENT_ERROR, resp.status)

    def test_coroutine_unexpected_exception(self):
        @self.dispatch.function
        def mycoro():
            1 / 0
            self.fail("should not reach here")

        resp = self.call(mycoro)
        self.assertEqual("ZeroDivisionError", resp.exit.result.error.type)
        self.assertEqual("division by zero", resp.exit.result.error.message)
        self.assertEqual(Status.PERMANENT_ERROR, resp.status)

    def test_specific_status(self):
        @self.dispatch.primitive_function
        def mycoro(input: Input) -> Output:
            return Output.error(Error(Status.THROTTLED, "foo", "bar"))

        resp = self.execute(mycoro)
        self.assertEqual("foo", resp.exit.result.error.type)
        self.assertEqual("bar", resp.exit.result.error.message)
        self.assertEqual(Status.THROTTLED, resp.status)

    def test_tailcall(self):
        @self.dispatch.function
        def other_coroutine(value: Any) -> str:
            return f"Hello {value}"

        @self.dispatch.primitive_function
        def mycoro(input: Input) -> Output:
            return Output.tail_call(other_coroutine._build_primitive_call(42))

        resp = self.call(mycoro)
        self.assertEqual(other_coroutine.name, resp.exit.tail_call.function)
        self.assertEqual(42, any_unpickle(resp.exit.tail_call.input))

    def test_library_error_categorization(self):
        @self.dispatch.function
        def get(path: str) -> httpx.Response:
            http_response = self.http_client.get(path)
            http_response.raise_for_status()
            return http_response

        resp = self.call(get, "/")
        self.assertEqual(Status.OK, Status(resp.status))
        http_response = any_unpickle(resp.exit.result.output)
        self.assertEqual("application/json", http_response.headers["content-type"])
        self.assertEqual('"OK"', http_response.text)

        resp = self.call(get, "/missing")
        self.assertEqual(Status.NOT_FOUND, Status(resp.status))

    def test_library_output_categorization(self):
        @self.dispatch.function
        def get(path: str) -> httpx.Response:
            http_response = self.http_client.get(path)
            http_response.status_code = 429
            return http_response

        resp = self.call(get, "/")
        self.assertEqual(Status.THROTTLED, Status(resp.status))
        http_response = any_unpickle(resp.exit.result.output)
        self.assertEqual("application/json", http_response.headers["content-type"])
        self.assertEqual('"OK"', http_response.text)


class TestError(unittest.TestCase):
    def test_missing_type_and_message(self):
        with self.assertRaises(ValueError):
            Error(Status.TEMPORARY_ERROR, type=None, message=None)

    def test_error_with_ok_status(self):
        with self.assertRaises(ValueError):
            Error(Status.OK, type="type", message="yep")

    def test_from_exception_timeout(self):
        err = Error.from_exception(TimeoutError())
        self.assertEqual(Status.TIMEOUT, err.status)

    def test_from_exception_syntax_error(self):
        err = Error.from_exception(SyntaxError())
        self.assertEqual(Status.PERMANENT_ERROR, err.status)
