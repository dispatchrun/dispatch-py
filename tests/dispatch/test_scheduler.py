import unittest
from typing import Any, Callable

from dispatch.coroutine import call, gather
from dispatch.experimental.durable import durable
from dispatch.proto import Call, CallResult, Error, Input, Output
from dispatch.proto import _any_unpickle as any_unpickle
from dispatch.scheduler import OneShotScheduler
from dispatch.sdk.v1 import call_pb2 as call_pb
from dispatch.sdk.v1 import exit_pb2 as exit_pb
from dispatch.sdk.v1 import poll_pb2 as poll_pb


@durable
async def call_one(function):
    return await call(Call(function=function))


@durable
async def call_concurrently(*functions):
    return await gather(*[call_one(function) for function in functions])


@durable
async def call_sequentially(*functions):
    # Note: this fails on 3.11 but succeeds on 3.12.
    # return [await call_one(function) for function in functions]
    results = []
    for function in functions:
        results.append(await call_one(function))
    return results


@durable
async def raises_error():
    raise ValueError("oops")


class TestOneShotScheduler(unittest.TestCase):
    def test_main_return(self):
        @durable
        async def main():
            return 1

        output = self.start(main)
        self.assert_exit_result_value(output, 1)

    def test_main_raise(self):
        @durable
        async def main():
            raise ValueError("oops")

        output = self.start(main)
        self.assert_exit_result_error(output, ValueError, "oops")

    def test_main_args(self):
        @durable
        async def main(a, b=1):
            return a + b

        output = self.start(main, 2, b=10)
        self.assert_exit_result_value(output, 12)

    def test_call_one(self):
        output = self.start(call_one, "foo")

        self.assert_poll_call_functions(output, ["foo"])

    def test_call_concurrently(self):
        output = self.start(call_concurrently, "foo", "bar", "baz")

        self.assert_poll_call_functions(output, ["foo", "bar", "baz"])

    def test_call_one_indirect(self):
        @durable
        async def main():
            return await call_one("foo")

        output = self.start(main)

        self.assert_poll_call_functions(output, ["foo"])

    def test_call_concurrently_indirect(self):
        @durable
        async def main(*functions):
            return await call_concurrently(*functions)

        output = self.start(main, "foo", "bar", "baz")

        self.assert_poll_call_functions(output, ["foo", "bar", "baz"])

    def test_depth_first_run(self):
        @durable
        async def main():
            return await gather(
                call_concurrently("a", "b", "c"),
                call_one("d"),
                call_concurrently("e", "f", "g"),
                call_one("h"),
            )

        output = self.start(main)

        self.assert_poll_call_functions(
            output, ["a", "b", "c", "d", "e", "f", "g", "h"]
        )

    def test_resume_after_call(self):
        @durable
        async def main():
            result1 = await call_one("foo")
            result2 = await call_one("bar")
            return result1 + result2

        output = self.start(main)
        calls = self.assert_poll_call_functions(output, ["foo"])
        output = self.resume(
            main,
            output,
            [CallResult.from_value(1, correlation_id=calls[0].correlation_id)],
        )
        calls = self.assert_poll_call_functions(output, ["bar"])
        output = self.resume(
            main,
            output,
            [CallResult.from_value(2, correlation_id=calls[0].correlation_id)],
        )
        self.assert_exit_result_value(output, 3)

    def test_resume_after_gather_all_at_once(self):
        @durable
        async def main():
            return sum(await call_concurrently("a", "b", "c", "d"))

        output = self.start(main)
        calls = self.assert_poll_call_functions(output, ["a", "b", "c", "d"])
        results = [
            CallResult.from_value(i, correlation_id=call.correlation_id)
            for i, call in enumerate(calls)
        ]
        output = self.resume(main, output, results)
        self.assert_exit_result_value(output, 0 + 1 + 2 + 3)

    def test_resume_after_gather_one_at_a_time(self):
        @durable
        async def main():
            return sum(await call_concurrently("a", "b", "c", "d"))

        output = self.start(main)
        calls = self.assert_poll_call_functions(output, ["a", "b", "c", "d"])
        for i, call in enumerate(calls):
            output = self.resume(
                main,
                output,
                [CallResult.from_value(i, correlation_id=call.correlation_id)],
            )
            if i < len(calls) - 1:
                self.assert_empty_poll(output)

        self.assert_exit_result_value(output, 0 + 1 + 2 + 3)

    def test_dag(self):
        @durable
        async def main():
            result1 = await gather(
                call_sequentially("a", "e"),
                call_one("b"),
                call_concurrently("c", "d"),
            )
            result2 = await call_one("f")
            result3 = await call_concurrently("g", "h")
            return [result1, result2, result3]

        correlation_ids = set()

        output = self.start(main)
        # a, b, c, d are called first. e is not because it depends on a.
        calls = self.assert_poll_call_functions(output, ["a", "b", "c", "d"])
        correlation_ids.update(call.correlation_id for call in calls)
        results = [
            CallResult.from_value(i, correlation_id=call.correlation_id)
            for i, call in enumerate(calls)
        ]
        output = self.resume(main, output, results)
        # e is called next
        calls = self.assert_poll_call_functions(output, ["e"])
        correlation_ids.update(call.correlation_id for call in calls)
        output = self.resume(
            main,
            output,
            [CallResult.from_value(4, correlation_id=calls[0].correlation_id)],
        )
        # f is called next
        calls = self.assert_poll_call_functions(output, ["f"])
        correlation_ids.update(call.correlation_id for call in calls)
        output = self.resume(
            main,
            output,
            [CallResult.from_value(5, correlation_id=calls[0].correlation_id)],
        )
        # g, h are called next
        calls = self.assert_poll_call_functions(output, ["g", "h"])
        correlation_ids.update(call.correlation_id for call in calls)
        output = self.resume(
            main,
            output,
            [
                CallResult.from_value(6, correlation_id=calls[0].correlation_id),
                CallResult.from_value(7, correlation_id=calls[1].correlation_id),
            ],
        )
        self.assert_exit_result_value(
            output,
            [
                [[0, 4], 1, [2, 3]],  # result1 = (a, e), b, (c, d)
                5,  # result2 = f
                [6, 7],  # result3 = (g, h)
            ],
        )

        self.assertEqual(len(correlation_ids), 8)

    def test_poll_error(self):
        # The purpose of the test is to ensure that when a poll error occurs,
        # we only abort the calls that were made on the previous yield. Any
        # other in-flight calls from previous yields are not affected.

        @durable
        async def c_then_d():
            c_result = await call_one("c")
            try:
                # The poll error will affect this call only.
                d_result = await call_one("d")
            except RuntimeError as e:
                assert str(e) == "too many calls"
                d_result = 100
            return c_result + d_result

        @durable
        async def main(c_then_d):
            return await gather(
                call_concurrently("a", "b"),
                c_then_d(),
            )

        output = self.start(main, c_then_d)
        calls = self.assert_poll_call_functions(output, ["a", "b", "c"])

        call_a, call_b, call_c = calls
        a_result, b_result, c_result = 10, 20, 30
        output = self.resume(
            main,
            output,
            [CallResult.from_value(c_result, correlation_id=call_c.correlation_id)],
        )
        self.assert_poll_call_functions(output, ["d"])

        output = self.resume(
            main, output, [], poll_error=RuntimeError("too many calls")
        )
        self.assert_poll_call_functions(output, [])
        output = self.resume(
            main,
            output,
            [
                CallResult.from_value(a_result, correlation_id=call_a.correlation_id),
                CallResult.from_value(b_result, correlation_id=call_b.correlation_id),
            ],
        )

        self.assert_exit_result_value(output, [[a_result, b_result], c_result + 100])

    def test_raise_indirect(self):
        @durable
        async def main():
            return await gather(call_one("a"), raises_error())

        output = self.start(main)
        self.assert_exit_result_error(output, ValueError, "oops")

    def start(self, main: Callable, *args: Any, **kwargs: Any) -> Output:
        input = Input.from_input_arguments(main.__qualname__, *args, **kwargs)
        return OneShotScheduler(main).run(input)

    def resume(
        self,
        main: Callable,
        prev_output: Output,
        call_results: list[CallResult],
        poll_error: Exception | None = None,
    ):
        poll = self.assert_poll(prev_output)
        input = Input.from_poll_results(
            main.__qualname__,
            poll.coroutine_state,
            call_results,
            Error.from_exception(poll_error) if poll_error else None,
        )
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
        return error

    def assert_poll(self, output: Output) -> poll_pb.Poll:
        response = output._message
        if response.HasField("exit"):
            raise RuntimeError(
                f"coroutine unexpectedly returned {response.exit.result}"
            )
        self.assertTrue(response.HasField("poll"))
        return response.poll

    def assert_empty_poll(self, output: Output):
        poll = self.assert_poll(output)
        self.assertEqual(len(poll.calls), 0)

    def assert_poll_call_functions(self, output: Output, expect: list[str]):
        poll = self.assert_poll(output)
        # Note: we're not testing endpoint/input here.
        # Check function names match:
        self.assertListEqual([c.function for c in poll.calls], expect)
        # Check correlation IDs are unique.
        correlation_ids = [c.correlation_id for c in poll.calls]
        self.assertEqual(
            len(correlation_ids),
            len(set(correlation_ids)),
            "correlation IDs were not unique",
        )
        return poll.calls
