import unittest
from typing import Any, Callable, List, Optional, Set, Type

import pytest

from dispatch.any import unmarshal_any
from dispatch.coroutine import AnyException, any, call, gather, race
from dispatch.experimental.durable import durable
from dispatch.proto import Arguments, Call, CallResult, Error, Input, Output, TailCall
from dispatch.scheduler import (
    AllFuture,
    AnyFuture,
    CoroutineResult,
    OneShotScheduler,
    RaceFuture,
)
from dispatch.sdk.v1 import call_pb2 as call_pb
from dispatch.sdk.v1 import exit_pb2 as exit_pb
from dispatch.sdk.v1 import poll_pb2 as poll_pb


@durable
async def call_one(function):
    return await call(Call(function=function))


@durable
async def call_any(*functions):
    return await any(*[call_one(function) for function in functions])


@durable
async def call_race(*functions):
    return await race(*[call_one(function) for function in functions])


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


@pytest.mark.asyncio
async def test_main_return():
    @durable
    async def main():
        return 1

    output = await start(main)
    assert_exit_result_value(output, 1)


@pytest.mark.asyncio
async def test_main_raise():
    @durable
    async def main():
        raise ValueError("oops")

    output = await start(main)
    assert_exit_result_error(output, ValueError, "oops")


@pytest.mark.asyncio
async def test_main_args():
    @durable
    async def main(a, b=1):
        return a + b

    output = await start(main, 2, b=10)
    assert_exit_result_value(output, 12)


@pytest.mark.asyncio
async def test_call_one():
    output = await start(call_one, "foo")

    assert_poll_call_functions(output, ["foo"])


@pytest.mark.asyncio
async def test_call_concurrently():
    output = await start(call_concurrently, "foo", "bar", "baz")

    assert_poll_call_functions(output, ["foo", "bar", "baz"])


@pytest.mark.asyncio
async def test_call_one_indirect():
    @durable
    async def main():
        return await call_one("foo")

    output = await start(main)

    assert_poll_call_functions(output, ["foo"])


@pytest.mark.asyncio
async def test_call_concurrently_indirect():
    @durable
    async def main(*functions):
        return await call_concurrently(*functions)

    output = await start(main, "foo", "bar", "baz")

    assert_poll_call_functions(output, ["foo", "bar", "baz"])


@pytest.mark.asyncio
async def test_depth_run():
    @durable
    async def main():
        return await gather(
            call_concurrently("a", "b", "c"),
            call_one("d"),
            call_concurrently("e", "f", "g"),
            call_one("h"),
        )

    output = await start(main)
    # In this test, the output is deterministic, but it does not follow the
    # order in which the coroutines are declared due to interleaving of the
    # asyncio event loop.
    #
    # Note that the order could change between Python versions, so we might
    # choose to remove this test, or adapt it in the future.
    assert_poll_call_functions(
        output,
        ["d", "h", "e", "f", "g", "a", "b", "c"],
        min_results=1,
        max_results=8,
    )


@pytest.mark.asyncio
async def test_resume_after_call():
    @durable
    async def main():
        result1 = await call_one("foo")
        result2 = await call_one("bar")
        return result1 + result2

    output = await start(main)
    calls = assert_poll_call_functions(output, ["foo"])
    output = await resume(
        main,
        output,
        [CallResult.from_value(1, correlation_id=calls[0].correlation_id)],
    )
    calls = assert_poll_call_functions(output, ["bar"])
    output = await resume(
        main,
        output,
        [CallResult.from_value(2, correlation_id=calls[0].correlation_id)],
    )
    assert_exit_result_value(output, 3)


@pytest.mark.asyncio
async def test_resume_after_gather_all_at_once():
    @durable
    async def main():
        return sum(await call_concurrently("a", "b", "c", "d"))

    output = await start(main)
    calls = assert_poll_call_functions(output, ["a", "b", "c", "d"])
    results = [
        CallResult.from_value(i, correlation_id=call.correlation_id)
        for i, call in enumerate(calls)
    ]
    output = await resume(main, output, results)
    assert_exit_result_value(output, 0 + 1 + 2 + 3)


@pytest.mark.asyncio
async def test_resume_after_gather_one_at_a_time():
    @durable
    async def main():
        return sum(await call_concurrently("a", "b", "c", "d"))

    output = await start(main)
    calls = assert_poll_call_functions(output, ["a", "b", "c", "d"])
    for i, call in enumerate(calls):
        output = await resume(
            main,
            output,
            [CallResult.from_value(i, correlation_id=call.correlation_id)],
        )
        if i < len(calls) - 1:
            assert_empty_poll(output)

    assert_exit_result_value(output, 0 + 1 + 2 + 3)


@pytest.mark.asyncio
async def test_resume_after_any_result():
    @durable
    async def main():
        return await call_any("a", "b", "c", "d")

    output = await start(main)
    calls = assert_poll_call_functions(output, ["a", "b", "c", "d"])

    output = await resume(
        main,
        output,
        [CallResult.from_value(23, correlation_id=calls[1].correlation_id)],
    )
    assert_exit_result_value(output, 23)


@pytest.mark.asyncio
async def test_resume_after_all_errors():
    @durable
    async def main():
        return await call_any("a", "b", "c", "d")

    output = await start(main)
    calls = assert_poll_call_functions(output, ["a", "b", "c", "d"])
    results = [
        CallResult.from_error(
            Error.from_exception(RuntimeError(f"oops{i}")),
            correlation_id=call.correlation_id,
        )
        for i, call in enumerate(calls)
    ]
    output = await resume(main, output, results)
    assert_exit_result_error(
        output, AnyException, "4 coroutine(s) failed with an exception"
    )


@pytest.mark.asyncio
async def test_resume_after_race_result():
    @durable
    async def main():
        return await call_race("a", "b", "c", "d")

    output = await start(main)
    calls = assert_poll_call_functions(output, ["a", "b", "c", "d"])

    output = await resume(
        main,
        output,
        [CallResult.from_value(23, correlation_id=calls[1].correlation_id)],
    )
    assert_exit_result_value(output, 23)


@pytest.mark.asyncio
async def test_resume_after_race_error():
    @durable
    async def main():
        return await call_race("a", "b", "c", "d")

    output = await start(main)
    calls = assert_poll_call_functions(output, ["a", "b", "c", "d"])

    error = Error.from_exception(RuntimeError("oops"))
    output = await resume(
        main,
        output,
        [CallResult.from_error(error, correlation_id=calls[2].correlation_id)],
    )
    assert_exit_result_error(output, RuntimeError, "oops")


@pytest.mark.asyncio
async def test_dag():
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

    correlation_ids: Set[int] = set()

    output = await start(main)
    # a, b, c, d are called first. e is not because it depends on a.
    calls = assert_poll_call_functions(
        output, ["a", "b", "c", "d"], min_results=1, max_results=4
    )
    correlation_ids.update(call.correlation_id for call in calls)
    results = [
        CallResult.from_value(i, correlation_id=call.correlation_id)
        for i, call in enumerate(calls)
    ]
    output = await resume(main, output, results)
    # e is called next
    calls = assert_poll_call_functions(output, ["e"], min_results=1, max_results=1)
    correlation_ids.update(call.correlation_id for call in calls)
    output = await resume(
        main,
        output,
        [CallResult.from_value(4, correlation_id=calls[0].correlation_id)],
    )
    # f is called next
    calls = assert_poll_call_functions(output, ["f"], min_results=1, max_results=1)
    correlation_ids.update(call.correlation_id for call in calls)
    output = await resume(
        main,
        output,
        [CallResult.from_value(5, correlation_id=calls[0].correlation_id)],
    )
    # g, h are called next
    calls = assert_poll_call_functions(output, ["g", "h"], min_results=1, max_results=2)
    correlation_ids.update(call.correlation_id for call in calls)
    output = await resume(
        main,
        output,
        [
            CallResult.from_value(6, correlation_id=calls[0].correlation_id),
            CallResult.from_value(7, correlation_id=calls[1].correlation_id),
        ],
    )
    assert_exit_result_value(
        output,
        [
            [[0, 4], 1, [2, 3]],  # result1 = (a, e), b, (c, d)
            5,  # result2 = f
            [6, 7],  # result3 = (g, h)
        ],
    )

    assert len(correlation_ids) == 8


@pytest.mark.asyncio
async def test_poll_error():
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
            call_one("a"),
            call_one("b"),
            c_then_d(),
        )

    output = await start(main, c_then_d)
    calls = assert_poll_call_functions(
        output, ["a", "b", "c"], min_results=1, max_results=3
    )

    call_a, call_b, call_c = calls
    a_result, b_result, c_result = 10, 20, 30
    output = await resume(
        main,
        output,
        [CallResult.from_value(c_result, correlation_id=call_c.correlation_id)],
    )
    assert_poll_call_functions(output, ["d"], min_results=1, max_results=3)

    output = await resume(main, output, [], poll_error=RuntimeError("too many calls"))
    assert_poll_call_functions(output, [])
    output = await resume(
        main,
        output,
        [
            CallResult.from_value(a_result, correlation_id=call_a.correlation_id),
            CallResult.from_value(b_result, correlation_id=call_b.correlation_id),
        ],
    )

    assert_exit_result_value(output, [a_result, b_result, c_result + 100])


@pytest.mark.asyncio
async def test_raise_indirect():
    @durable
    async def main():
        return await gather(call_one("a"), raises_error())

    output = await start(main)
    assert_exit_result_error(output, ValueError, "oops")


@pytest.mark.asyncio
async def test_raise_reset():
    @durable
    async def main(x: int, y: int):
        raise TailCall(
            call=Call(function="main", input=Arguments((), {"x": x + 1, "y": y + 2}))
        )

    output = await start(main, x=1, y=2)
    assert_exit_tail_call(
        output,
        tail_call=Call(function="main", input=Arguments((), {"x": 2, "y": 4})),
    )


@pytest.mark.asyncio
async def test_min_max_results_clamping():
    @durable
    async def main():
        return await call_concurrently("a", "b", "c")

    output = await start(main, poll_min_results=1, poll_max_results=10)
    assert_poll_call_functions(output, ["a", "b", "c"], min_results=1, max_results=3)

    output = await start(main, poll_min_results=1, poll_max_results=2)
    assert_poll_call_functions(output, ["a", "b", "c"], min_results=1, max_results=2)

    output = await start(main, poll_min_results=10, poll_max_results=10)
    assert_poll_call_functions(output, ["a", "b", "c"], min_results=3, max_results=3)


async def start(
    main: Callable,
    *args: Any,
    poll_min_results=1,
    poll_max_results=10,
    poll_max_wait_seconds=None,
    **kwargs: Any,
) -> Output:
    input = Input.from_input_arguments(main.__qualname__, *args, **kwargs)
    return await OneShotScheduler(
        main,
        poll_min_results=poll_min_results,
        poll_max_results=poll_max_results,
        poll_max_wait_seconds=poll_max_wait_seconds,
    ).run(input)


async def resume(
    main: Callable,
    prev_output: Output,
    call_results: List[CallResult],
    poll_error: Optional[Exception] = None,
):
    poll = assert_poll(prev_output)
    input = Input.from_poll_results(
        main.__qualname__,
        unmarshal_any(poll.typed_coroutine_state),
        call_results,
        Error.from_exception(poll_error) if poll_error else None,
    )
    return await OneShotScheduler(main).run(input)


def assert_exit(output: Output) -> exit_pb.Exit:
    response = output._message
    assert response.HasField("exit")
    assert not response.HasField("poll")
    return response.exit


def assert_exit_result(output: Output) -> call_pb.CallResult:
    exit = assert_exit(output)
    assert exit.HasField("result")
    assert not exit.HasField("tail_call")
    return exit.result


def assert_exit_result_value(output: Output, expect: Any):
    result = assert_exit_result(output)
    assert result.HasField("output")
    assert not result.HasField("error")
    assert expect == unmarshal_any(result.output)


def assert_exit_result_error(
    output: Output, expect: Type[Exception], message: Optional[str] = None
):
    result = assert_exit_result(output)
    assert not result.HasField("output")
    assert result.HasField("error")

    error = Error._from_proto(result.error).to_exception()
    assert error.__class__ == expect

    if message is not None:
        assert str(error) == message
    return error


def assert_exit_tail_call(output: Output, tail_call: Call):
    exit = assert_exit(output)
    assert not exit.HasField("result")
    assert exit.HasField("tail_call")
    assert tail_call._as_proto() == exit.tail_call


def assert_poll(output: Output) -> poll_pb.Poll:
    response = output._message
    if response.HasField("exit"):
        raise RuntimeError(f"coroutine unexpectedly returned {response.exit.result}")
    assert response.HasField("poll")
    return response.poll


def assert_empty_poll(output: Output):
    poll = assert_poll(output)
    assert len(poll.calls) == 0


def assert_poll_call_functions(
    output: Output, expect: List[str], min_results=None, max_results=None
):
    poll = assert_poll(output)
    # Note: we're not testing endpoint/input here.
    # Check function names match:
    assert [c.function for c in poll.calls] == expect
    # Check correlation IDs are unique.
    correlation_ids = [c.correlation_id for c in poll.calls]
    assert len(correlation_ids) == len(
        set(correlation_ids)
    ), "correlation IDs were not unique"
    if min_results is not None:
        assert min_results == poll.min_results
    if max_results is not None:
        assert max_results == poll.max_results
    return poll.calls


class TestAllFuture(unittest.TestCase):
    def test_empty(self):
        future = AllFuture()

        self.assertTrue(future.ready())
        self.assertListEqual(future.value(), [])
        self.assertIsNone(future.error())

    def test_one_result_value(self):
        future = AllFuture(order=[10], waiting={10})

        self.assertFalse(future.ready())
        future.add_result(CoroutineResult(coroutine_id=10, value="foobar"))

        self.assertTrue(future.ready())
        self.assertIsNone(future.error())
        self.assertListEqual(future.value(), ["foobar"])

    def test_one_result_error(self):
        future = AllFuture(order=[10], waiting={10})

        self.assertFalse(future.ready())
        error = RuntimeError("oops")
        future.add_result(CoroutineResult(coroutine_id=10, error=error))

        self.assertTrue(future.ready())
        self.assertIs(future.error(), error)

        with self.assertRaises(AssertionError):
            future.value()

    def test_one_generic_error(self):
        future = AllFuture(order=[10], waiting={10})

        self.assertFalse(future.ready())
        error = RuntimeError("oops")
        future.add_error(error)

        self.assertTrue(future.ready())
        self.assertIs(future.error(), error)

        with self.assertRaises(AssertionError):
            future.value()

    def test_two_result_values(self):
        future = AllFuture(order=[10, 20], waiting={10, 20})

        self.assertFalse(future.ready())
        future.add_result(CoroutineResult(coroutine_id=20, value="bar"))
        self.assertFalse(future.ready())
        future.add_result(CoroutineResult(coroutine_id=10, value="foo"))

        self.assertTrue(future.ready())
        self.assertIsNone(future.error())
        self.assertListEqual(future.value(), ["foo", "bar"])

    def test_two_result_errors(self):
        future = AllFuture(order=[10, 20], waiting={10, 20})

        self.assertFalse(future.ready())
        error1 = RuntimeError("oops1")
        error2 = RuntimeError("oops2")
        future.add_result(CoroutineResult(coroutine_id=20, error=error2))

        self.assertTrue(future.ready())
        self.assertIs(future.error(), error2)

        future.add_result(CoroutineResult(coroutine_id=10, error=error1))
        self.assertIs(future.error(), error2)

        future.add_error(error1)
        self.assertIs(future.error(), error2)

        with self.assertRaises(AssertionError):
            future.value()


class TestAnyFuture(unittest.TestCase):
    def test_empty(self):
        future = AnyFuture()

        self.assertTrue(future.ready())
        self.assertIsNone(future.value())
        self.assertIsNone(future.error())

    def test_one_result_value(self):
        future = AnyFuture(order=[10], waiting={10})

        self.assertFalse(future.ready())
        future.add_result(CoroutineResult(coroutine_id=10, value="foobar"))

        self.assertTrue(future.ready())
        self.assertIsNone(future.error())
        self.assertEqual(future.value(), "foobar")

    def test_one_result_error(self):
        future = AnyFuture(order=[10], waiting={10})

        self.assertFalse(future.ready())
        error = RuntimeError("oops")
        future.add_result(CoroutineResult(coroutine_id=10, error=error))

        self.assertTrue(future.ready())
        self.assertIs(future.error(), error)

        with self.assertRaises(AssertionError):
            future.value()

    def test_one_generic_error(self):
        future = AnyFuture(order=[10], waiting={10})

        self.assertFalse(future.ready())
        error = RuntimeError("oops")
        future.add_error(error)

        self.assertTrue(future.ready())
        self.assertIs(future.error(), error)

        with self.assertRaises(AssertionError):
            future.value()

    def test_two_result_values(self):
        future = AnyFuture(order=[10, 20], waiting={10, 20})

        self.assertFalse(future.ready())

        future.add_result(CoroutineResult(coroutine_id=20, value="bar"))
        self.assertTrue(future.ready())
        self.assertIsNone(future.error())
        self.assertEqual(future.value(), "bar")

        future.add_result(CoroutineResult(coroutine_id=10, value="foo"))
        self.assertTrue(future.ready())
        self.assertIsNone(future.error())
        self.assertEqual(future.value(), "bar")

    def test_two_result_errors(self):
        future = AnyFuture(order=[10, 20], waiting={10, 20})

        self.assertFalse(future.ready())
        error1 = RuntimeError("oops1")
        error2 = RuntimeError("oops2")
        future.add_result(CoroutineResult(coroutine_id=20, error=error2))

        self.assertFalse(future.ready())
        future.add_result(CoroutineResult(coroutine_id=10, error=error1))
        self.assertTrue(future.ready())
        self.assertEqual(repr(future.error()), repr(AnyException([error1, error2])))

        with self.assertRaises(AssertionError):
            future.value()


class TestRaceFuture(unittest.TestCase):
    def test_empty(self):
        future = RaceFuture()

        self.assertTrue(future.ready())
        self.assertIsNone(future.value())
        self.assertIsNone(future.error())

    def test_one_result_value(self):
        future = RaceFuture(waiting={10})

        self.assertFalse(future.ready())
        future.add_result(CoroutineResult(coroutine_id=10, value="foobar"))

        self.assertTrue(future.ready())
        self.assertIsNone(future.error())
        self.assertEqual(future.value(), "foobar")

    def test_one_result_error(self):
        future = RaceFuture(waiting={10})

        self.assertFalse(future.ready())
        error = RuntimeError("oops")
        future.add_result(CoroutineResult(coroutine_id=10, error=error))

        self.assertTrue(future.ready())
        self.assertIs(future.error(), error)

        with self.assertRaises(AssertionError):
            future.value()

    def test_one_generic_error(self):
        future = RaceFuture(waiting={10})

        self.assertFalse(future.ready())
        error = RuntimeError("oops")
        future.add_error(error)

        self.assertTrue(future.ready())
        self.assertIs(future.error(), error)

        with self.assertRaises(AssertionError):
            future.value()

    def test_two_result_values(self):
        future = RaceFuture(waiting={10, 20})

        self.assertFalse(future.ready())

        future.add_result(CoroutineResult(coroutine_id=20, value="bar"))
        self.assertTrue(future.ready())
        self.assertIsNone(future.error())
        self.assertEqual(future.value(), "bar")

        future.add_result(CoroutineResult(coroutine_id=10, value="foo"))
        self.assertTrue(future.ready())
        self.assertIsNone(future.error())
        self.assertEqual(future.value(), "bar")

    def test_two_result_errors(self):
        future = RaceFuture(waiting={10, 20})

        self.assertFalse(future.ready())
        error1 = RuntimeError("oops")
        future.add_result(CoroutineResult(coroutine_id=10, error=error1))

        self.assertTrue(future.ready())
        self.assertIs(future.error(), error1)

        error2 = RuntimeError("oops2")
        future.add_result(CoroutineResult(coroutine_id=20, error=error2))
        self.assertIs(future.error(), error1)

        future.add_error(error2)
        self.assertIs(future.error(), error1)

        with self.assertRaises(AssertionError):
            future.value()
