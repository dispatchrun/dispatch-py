import pickle
import unittest
from typing import Any

import httpx
import fastapi
from fastapi.testclient import TestClient
import google.protobuf.wrappers_pb2

import dispatch.fastapi
import dispatch.coroutine
from dispatch.coroutine import Input, Output, Error, Status
from ring.coroutine.v1 import coroutine_pb2
from . import executor_service


class TestFastAPI(unittest.TestCase):
    def test_configure(self):
        app = fastapi.FastAPI()

        dispatch.fastapi.configure(
            app, api_key="test-key", public_url="https://127.0.0.1:9999"
        )

        @app.get("/")
        def read_root():
            return {"Hello": "World"}

        client = TestClient(app)

        # Ensure existing routes are still working.
        resp = client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"Hello": "World"})

        # Ensure Dispatch root is available.
        resp = client.post("/ring.coroutine.v1.ExecutorService/Execute")
        self.assertEqual(resp.status_code, 400)

    def test_configure_no_app(self):
        with self.assertRaises(ValueError):
            dispatch.fastapi.configure(
                None, api_key="test-key", public_url="http://127.0.0.1:9999"
            )

    def test_configure_no_api_key(self):
        app = fastapi.FastAPI()
        with self.assertRaises(ValueError):
            dispatch.fastapi.configure(
                app, api_key=None, public_url="http://127.0.0.1:9999"
            )

    def test_configure_no_public_url(self):
        app = fastapi.FastAPI()
        with self.assertRaises(ValueError):
            dispatch.fastapi.configure(app, api_key="test", public_url="")

    def test_configure_public_url_no_scheme(self):
        app = fastapi.FastAPI()
        with self.assertRaises(ValueError):
            dispatch.fastapi.configure(app, api_key="test", public_url="127.0.0.1:9999")

    def test_fastapi_simple_request(self):
        app = fastapi.FastAPI()
        dispatch.fastapi.configure(
            app, api_key="test-key", public_url="http://127.0.0.1:9999/"
        )

        @app.dispatch_coroutine()
        def my_cool_coroutine(input: Input) -> Output:
            return Output.value(
                f"You told me: '{input.input}' ({len(input.input)} characters)"
            )

        http_client = TestClient(app)

        client = executor_service.client(http_client)

        pickled = pickle.dumps("Hello World!")
        input_any = google.protobuf.any_pb2.Any()
        input_any.Pack(google.protobuf.wrappers_pb2.BytesValue(value=pickled))

        req = coroutine_pb2.ExecuteRequest(
            coroutine_uri=my_cool_coroutine.uri,
            coroutine_version="1",
            input=input_any,
        )

        resp = client.Execute(req)

        self.assertIsInstance(resp, coroutine_pb2.ExecuteResponse)
        self.assertEqual(resp.coroutine_uri, req.coroutine_uri)
        self.assertEqual(resp.coroutine_version, req.coroutine_version)

        resp.exit.result.output.Unpack(
            output_bytes := google.protobuf.wrappers_pb2.BytesValue()
        )
        output = pickle.loads(output_bytes.value)

        self.assertEqual(output, "You told me: 'Hello World!' (12 characters)")


def response_output(resp: coroutine_pb2.ExecuteResponse) -> Any:
    return dispatch.coroutine._any_unpickle(resp.exit.result.output)


class TestCoroutine(unittest.TestCase):
    def setUp(self):
        self.app = fastapi.FastAPI()
        dispatch.fastapi.configure(
            self.app, api_key="test-key", public_url="https://127.0.0.1:9999"
        )
        http_client = TestClient(self.app)
        self.client = executor_service.client(http_client)

    def execute(
        self, coroutine, input=None, state=None, calls=None
    ) -> coroutine_pb2.ExecuteResponse:
        """Test helper to invoke coroutines on the local server."""
        req = coroutine_pb2.ExecuteRequest(
            coroutine_uri=coroutine.uri,
            coroutine_version="1",
        )

        if input is not None:
            input_bytes = pickle.dumps(input)
            input_any = google.protobuf.any_pb2.Any()
            input_any.Pack(google.protobuf.wrappers_pb2.BytesValue(value=input_bytes))
            req.input.CopyFrom(input_any)
        if state is not None:
            req.poll_response.state = state
        if calls is not None:
            for c in calls:
                req.poll_response.results.append(c)

        resp = self.client.Execute(req)
        self.assertIsInstance(resp, coroutine_pb2.ExecuteResponse)
        return resp

    def call(self, call: coroutine_pb2.Call) -> coroutine_pb2.CallResult:
        req = coroutine_pb2.ExecuteRequest(
            coroutine_uri=call.coroutine_uri,
            coroutine_version=call.coroutine_version,
            input=call.input,
        )
        resp = self.client.Execute(req)
        self.assertIsInstance(resp, coroutine_pb2.ExecuteResponse)

        # Assert the response is terminal. Good enough until the test client can
        # orchestrate coroutines.
        self.assertTrue(len(resp.poll.state) == 0)

        return coroutine_pb2.CallResult(
            coroutine_uri=resp.coroutine_uri,
            coroutine_version=resp.coroutine_version,
            correlation_id=call.correlation_id,
            result=resp.exit.result,
        )

    def test_no_input(self):
        @self.app.dispatch_coroutine()
        def my_cool_coroutine(input: Input) -> Output:
            return Output.value("Hello World!")

        resp = self.execute(my_cool_coroutine)

        out = response_output(resp)
        self.assertEqual(out, "Hello World!")

    def test_missing_coroutine(self):
        req = coroutine_pb2.ExecuteRequest(
            coroutine_uri="does-not-exist",
            coroutine_version="1",
        )

        with self.assertRaises(httpx.HTTPStatusError) as cm:
            self.client.Execute(req)
        self.assertEqual(cm.exception.response.status_code, 404)

    def test_string_input(self):
        @self.app.dispatch_coroutine()
        def my_cool_coroutine(input: Input) -> Output:
            return Output.value(f"You sent '{input.input}'")

        resp = self.execute(my_cool_coroutine, input="cool stuff")
        out = response_output(resp)
        self.assertEqual(out, "You sent 'cool stuff'")

    def test_error_on_access_state_in_first_call(self):
        @self.app.dispatch_coroutine()
        def my_cool_coroutine(input: Input) -> Output:
            print(input.state)
            return Output.value("not reached")

        resp = self.execute(my_cool_coroutine, input="cool stuff")
        self.assertEqual("ValueError", resp.exit.result.error.type)
        self.assertEqual(
            "This input is for a first coroutine call", resp.exit.result.error.message
        )

    def test_error_on_access_input_in_second_call(self):
        @self.app.dispatch_coroutine()
        def my_cool_coroutine(input: Input) -> Output:
            if input.is_first_call:
                return Output.callback(state=42)
            print(input.input)
            return Output.value("not reached")

        resp = self.execute(my_cool_coroutine, input="cool stuff")
        resp = self.execute(my_cool_coroutine, state=resp.poll.state)

        self.assertEqual("ValueError", resp.exit.result.error.type)
        self.assertEqual(
            "This input is for a resumed coroutine", resp.exit.result.error.message
        )

    def test_duplicate_coro(self):
        @self.app.dispatch_coroutine()
        def my_cool_coroutine(input: Input) -> Output:
            return Output.value("Do one thing")

        with self.assertRaises(ValueError):

            @self.app.dispatch_coroutine()
            def my_cool_coroutine(input: Input) -> Output:
                return Output.value("Do something else")

    def test_two_simple_coroutines(self):
        @self.app.dispatch_coroutine()
        def echoroutine(input: Input) -> Output:
            return Output.value(f"Echo: '{input.input}'")

        @self.app.dispatch_coroutine()
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
        @self.app.dispatch_coroutine()
        def coroutine3(input: Input) -> Output:
            if input.is_first_call:
                counter = input.input
            else:
                counter = input.state
            counter -= 1
            if counter <= 0:
                return Output.value("done")
            return Output.callback(state=counter)

        # first call
        resp = self.execute(coroutine3, input=4)
        state = resp.poll.state
        self.assertTrue(len(state) > 0)

        # resume, state = 3
        resp = self.execute(coroutine3, state=state)
        state = resp.poll.state
        self.assertTrue(len(state) > 0)

        # resume, state = 2
        resp = self.execute(coroutine3, state=state)
        state = resp.poll.state
        self.assertTrue(len(state) > 0)

        # resume, state = 1
        resp = self.execute(coroutine3, state=state)
        state = resp.poll.state
        self.assertTrue(len(state) == 0)
        out = response_output(resp)
        self.assertEqual(out, "done")

    def test_coroutine_poll(self):
        @self.app.dispatch_coroutine()
        def coro_compute_len(input: Input) -> Output:
            return Output.value(len(input.input))

        @self.app.dispatch_coroutine()
        def coroutine_main(input: Input) -> Output:
            if input.is_first_call:
                text: str = input.input
                return Output.callback(
                    state=text, calls=[coro_compute_len.call_with(text)]
                )
            text = input.state
            length = input.calls[0].result
            return Output.value(f"length={length} text='{text}'")

        resp = self.execute(coroutine_main, input="cool stuff")

        # main saved some state
        state = resp.poll.state
        self.assertTrue(len(state) > 0)
        # main asks for 1 call to compute_len
        self.assertEqual(len(resp.poll.calls), 1)
        call = resp.poll.calls[0]
        self.assertEqual(call.coroutine_uri, coro_compute_len.uri)
        self.assertEqual(dispatch.coroutine._any_unpickle(call.input), "cool stuff")

        # make the requested compute_len
        resp2 = self.call(call)
        # check the result is the terminal expected response
        len_resp = dispatch.coroutine._any_unpickle(resp2.result.output)
        self.assertEqual(10, len_resp)

        # resume main with the result
        resp = self.execute(coroutine_main, state=state, calls=[resp2])
        # validate the final result
        self.assertTrue(len(resp.poll.state) == 0)
        out = response_output(resp)
        self.assertEqual("length=10 text='cool stuff'", out)

    def test_coroutine_error(self):
        @self.app.dispatch_coroutine()
        def mycoro(input: Input) -> Output:
            return Output.error(Error(Status.PERMANENT_ERROR, "sometype", "dead"))

        resp = self.execute(mycoro)
        self.assertEqual("sometype", resp.exit.result.error.type)
        self.assertEqual("dead", resp.exit.result.error.message)

    def test_coroutine_expected_exception(self):
        @self.app.dispatch_coroutine()
        def mycoro(input: Input) -> Output:
            try:
                1 / 0
            except ZeroDivisionError as e:
                return Output.error(Error.from_exception(e))
            self.fail("should not reach here")

        resp = self.execute(mycoro)
        self.assertEqual("ZeroDivisionError", resp.exit.result.error.type)
        self.assertEqual("division by zero", resp.exit.result.error.message)
        self.assertEqual(Status.TEMPORARY_ERROR, resp.status)

    def test_coroutine_unexpected_exception(self):
        @self.app.dispatch_coroutine()
        def mycoro(input: Input) -> Output:
            uhoh = 1 / 0
            self.fail("should not reach here")

        resp = self.execute(mycoro)
        self.assertEqual("ZeroDivisionError", resp.exit.result.error.type)
        self.assertEqual("division by zero", resp.exit.result.error.message)
        self.assertEqual(Status.TEMPORARY_ERROR, resp.status)

    def test_specific_status(self):
        @self.app.dispatch_coroutine()
        def mycoro(input: Input) -> Output:
            return Output.error(Error(Status.THROTTLED, "foo", "bar"))

        resp = self.execute(mycoro)
        self.assertEqual("foo", resp.exit.result.error.type)
        self.assertEqual("bar", resp.exit.result.error.message)
        self.assertEqual(Status.THROTTLED, resp.status)

    def test_tailcall(self):
        @self.app.dispatch_coroutine()
        def other_coroutine(input: Input) -> Output:
            return Output.value(f"Hello {input.input}")

        @self.app.dispatch_coroutine()
        def mycoro(input: Input) -> Output:
            return Output.tailcall(other_coroutine.call_with(42))

        resp = self.execute(mycoro)
        self.assertEqual(other_coroutine.uri, resp.exit.tail_call.coroutine_uri)
        self.assertEqual(
            42, dispatch.coroutine._any_unpickle(resp.exit.tail_call.input)
        )
