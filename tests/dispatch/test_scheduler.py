import unittest
from typing import Any, Callable

from dispatch.coroutine import call, gather
from dispatch.experimental.durable import durable
from dispatch.proto import Call, Error, Input, Output
from dispatch.proto import _any_unpickle as any_unpickle
from dispatch.scheduler import OneShotScheduler
from dispatch.sdk.v1 import call_pb2 as call_pb
from dispatch.sdk.v1 import exit_pb2 as exit_pb
from dispatch.sdk.v1 import poll_pb2 as poll_pb


@durable
async def call_one(function):
    return await call(Call(function=function))


@durable
async def call_many(*functions):
    return await gather(*[call_one(function) for function in functions])


import logging

logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


class TestOneShotScheduler(unittest.TestCase):
    def test_main_return(self):
        @durable
        async def main():
            return 1

        output = self.schedule(main)
        self.assert_exit_result_value(output, 1)

    def test_main_raise(self):
        @durable
        async def main():
            raise RuntimeError("oops")

        output = self.schedule(main)
        self.assert_exit_result_error(output, RuntimeError, "oops")

    def test_main_args(self):
        @durable
        async def main(a, b=1):
            return a + b

        output = self.schedule(main, 2, b=10)
        self.assert_exit_result_value(output, 12)

    def test_call_one(self):
        output = self.schedule(call_one, "foo")

        self.assert_poll_calls(output, [Call(function="foo", correlation_id=1)])

    def test_call_many(self):
        output = self.schedule(call_many, "foo", "bar", "baz")

        self.assert_poll_calls(
            output,
            [
                Call(function="foo", correlation_id=1),
                Call(function="bar", correlation_id=2),
                Call(function="baz", correlation_id=3),
            ],
        )

    def test_call_one_indirect(self):
        @durable
        async def main():
            return await call_one("foo")

        output = self.schedule(main)

        self.assert_poll_calls(output, [Call(function="foo", correlation_id=1)])

    def test_call_many_indirect(self):
        @durable
        async def main(*functions):
            return await call_many(*functions)

        output = self.schedule(main, "foo", "bar", "baz")

        self.assert_poll_calls(
            output,
            [
                Call(function="foo", correlation_id=1),
                Call(function="bar", correlation_id=2),
                Call(function="baz", correlation_id=3),
            ],
        )

    def test_depth_first_run(self):
        self.skipTest("not the case currently")

        @durable
        async def main():
            return await gather(
                call_many("a", "b", "c"),
                call_one("d"),
                call_many("e", "f", "g"),
                call_one("h"),
            )

        output = self.schedule(main)

        self.assert_poll_calls(
            output,
            [
                Call(function="a", correlation_id=1),
                Call(function="b", correlation_id=2),
                Call(function="c", correlation_id=3),
                Call(function="d", correlation_id=4),
                Call(function="e", correlation_id=5),
                Call(function="f", correlation_id=6),
                Call(function="g", correlation_id=7),
                Call(function="h", correlation_id=8),
            ],
        )

    def schedule(self, main: Callable, *args: Any, **kwargs: Any) -> Output:
        input = Input.from_input_arguments(main.__qualname__, *args, **kwargs)
        return OneShotScheduler(main).run(input)

    def assert_exit(self, output: Output) -> exit_pb.Exit:
        response = output._message
        self.assertTrue(response.HasField("exit"))
        self.assertFalse(response.HasField("poll"))
        return response.exit

    def assert_exit_result(self, output: Output) -> call_pb.CallResult:
        exit = self.assert_exit(output)
        self.assertTrue(exit.HasField("result"))
        self.assertFalse(exit.HasField("tail_call"))
        return exit.result

    def assert_exit_result_value(self, output: Output, expect: Any):
        result = self.assert_exit_result(output)
        self.assertTrue(result.HasField("output"))
        self.assertFalse(result.HasField("error"))
        self.assertEqual(expect, any_unpickle(result.output))

    def assert_exit_result_error(
        self, output: Output, expect: type[Exception], message: str | None = None
    ):
        result = self.assert_exit_result(output)
        self.assertFalse(result.HasField("output"))
        self.assertTrue(result.HasField("error"))

        error = Error._from_proto(result.error).to_exception()

        self.assertEqual(error.__class__, expect)
        if message is not None:
            self.assertEqual(str(error), message)

    def assert_poll(self, output: Output) -> poll_pb.Poll:
        response = output._message
        self.assertFalse(response.HasField("exit"))
        self.assertTrue(response.HasField("poll"))
        return response.poll

    def assert_poll_calls(self, output: Output, expect: list[Call]):
        poll = self.assert_poll(output)

        # We're not testing endpoint/input here. Just extract
        # function name and correlation ID.
        actual = [
            Call(function=c.function, correlation_id=c.correlation_id)
            for c in poll.calls
        ]
        self.assertListEqual(actual, expect)
