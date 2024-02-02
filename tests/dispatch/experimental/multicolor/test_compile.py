import time
import unittest
from enum import Enum
from types import FunctionType
from typing import Any

from dispatch.experimental.multicolor import (
    CustomYield,
    GeneratorYield,
    compile_function,
    yields,
)


class YieldTypes(Enum):
    SLEEP = 0
    ADD = 1
    MUL = 2
    STAR_ARGS_KWARGS = 3


@yields(type=YieldTypes.SLEEP)
def sleep(seconds):
    time.sleep(seconds)


@yields(type=YieldTypes.ADD)
def add(a: int, b: int) -> int:
    return a + b


@yields(type=YieldTypes.STAR_ARGS_KWARGS)
def star_args_kwargs(*args, **kwargs):
    pass


def adder(a: int, b: int) -> int:
    return add(a, b)


def empty():
    pass


def identity(x):
    return x


def identity_sleep(x):
    sleep(x)
    return x


def identity_sleep_yield(n):
    for i in range(n):
        sleep(i)
        yield i


class TestCompile(unittest.TestCase):
    def test_empty(self):
        self.assert_yields(empty, args=[], yields=[], returns=None)

    def test_identity(self):
        self.assert_yields(identity, args=[1], yields=[], returns=1)

    def test_identity_indirect(self):
        def identity_indirect(x):
            return identity(x)

        self.assert_yields(identity_indirect, args=[2], yields=[], returns=2)

    def test_identity_sleep(self):
        yields = [CustomYield(type=YieldTypes.SLEEP, args=[1])]
        self.assert_yields(identity_sleep, args=[1], yields=yields, returns=1)

    def test_identity_sleep_indirect(self):
        def identity_sleep_indirect(x):
            return identity_sleep(x)

        yields = [CustomYield(type=YieldTypes.SLEEP, args=[1])]
        self.assert_yields(identity_sleep_indirect, args=[1], yields=yields, returns=1)

    def test_adder(self):
        yields = [CustomYield(type=YieldTypes.ADD, args=[1, 2])]
        self.assert_yields(adder, args=[1, 2], sends=[3], yields=yields, returns=3)

    def test_adder_indirect(self):
        def adder_indirect(a, b):
            return adder(a, b)

        yields = [CustomYield(type=YieldTypes.ADD, args=[1, 2])]
        self.assert_yields(
            adder_indirect, args=[1, 2], sends=[3], yields=yields, returns=3
        )

    def test_star_args_kwargs_forward(self):
        def star_args_kwargs_forward(*args, **kwargs):
            star_args_kwargs(*args, **kwargs)

        yields = [
            CustomYield(
                type=YieldTypes.STAR_ARGS_KWARGS, args=[1, 2], kwargs={"foo": "bar"}
            )
        ]
        self.assert_yields(
            star_args_kwargs_forward, args=[1, 2], kwargs={"foo": "bar"}, yields=yields
        )

    def test_star_args_kwargs_explicit(self):
        def star_args_kwargs_explicit():
            star_args_kwargs(1, 2, foo="bar")

        yields = [
            CustomYield(
                type=YieldTypes.STAR_ARGS_KWARGS, args=[1, 2], kwargs={"foo": "bar"}
            )
        ]
        self.assert_yields(star_args_kwargs_explicit, yields=yields)

    def test_generator_yield(self):
        def generator():
            yield 1
            sleep(2)
            yield 3
            yield
            return 4

        yields = [
            GeneratorYield(value=1),
            CustomYield(type=YieldTypes.SLEEP, args=[2]),
            GeneratorYield(value=3),
            GeneratorYield(),
        ]
        self.assert_yields(generator, yields=yields, returns=4)

    def test_generator_yield_send(self):
        def generator():
            a = yield 1
            b = add(10, 20)
            c = yield 3
            return a, b, c

        yields = [
            GeneratorYield(value=1),
            CustomYield(type=YieldTypes.ADD, args=[10, 20]),
            GeneratorYield(value=3),
        ]
        self.assert_yields(
            generator, yields=yields, sends=[100, 30, 1000], returns=(100, 30, 1000)
        )

    def test_generator_range(self):
        def generator():
            for i in range(3):
                sleep(i)
                yield i

        yields = [
            CustomYield(type=YieldTypes.SLEEP, args=[0]),
            GeneratorYield(value=0),
            CustomYield(type=YieldTypes.SLEEP, args=[1]),
            GeneratorYield(value=1),
            CustomYield(type=YieldTypes.SLEEP, args=[2]),
            GeneratorYield(value=2),
        ]
        self.assert_yields(generator, yields=yields)

    def test_list_comprehensions(self):
        def fn():
            return sum([identity_sleep(i) for i in range(3)])

        yields = [
            CustomYield(type=YieldTypes.SLEEP, args=[0]),
            CustomYield(type=YieldTypes.SLEEP, args=[1]),
            CustomYield(type=YieldTypes.SLEEP, args=[2]),
        ]
        self.assert_yields(fn, yields=yields, returns=3)

    def test_list_comprehensions_2(self):
        def fn():
            return sum([x for x in identity_sleep_yield(3)])

        yields = [
            CustomYield(type=YieldTypes.SLEEP, args=[0]),
            CustomYield(type=YieldTypes.SLEEP, args=[1]),
            CustomYield(type=YieldTypes.SLEEP, args=[2]),
        ]
        self.assert_yields(fn, yields=yields, returns=3)

    def test_generator_comprehensions(self):
        def fn():
            return sum(identity_sleep(i) for i in range(3))

        yields = [
            CustomYield(type=YieldTypes.SLEEP, args=[0]),
            CustomYield(type=YieldTypes.SLEEP, args=[1]),
            CustomYield(type=YieldTypes.SLEEP, args=[2]),
        ]
        self.assert_yields(fn, yields=yields, returns=3)

    def test_class_method(self):
        class Foo:
            def sleep_then_fma(self, m, a, b):
                sleep(100)
                return self.mul(m, self.add_indirect(a, b))

            @yields(type=YieldTypes.MUL)
            def mul(self):
                raise RuntimeError("implementation is provided elsewhere")

            def add_indirect(self, a, b):
                return add(a, b)

        foo = Foo()
        self.assert_yields(
            foo.sleep_then_fma,
            args=[10, 1, 2],
            yields=[
                CustomYield(type=YieldTypes.SLEEP, args=[100]),
                CustomYield(type=YieldTypes.ADD, args=[1, 2]),
                CustomYield(type=YieldTypes.MUL, args=[10, 3]),
            ],
            sends=[None, 3, 30],
            returns=30,
        )

    def test_generator_evaluation(self):
        self.skipTest(
            "highlight how eager evaluation of generators can change the program"
        )

        def generator(n):
            for i in range(n):
                sleep(i)
                yield i

        def zipper(g, n):
            return list(zip(g(n), g(n)))

        # The generators are evaluated at their call site, which means
        # [0, 1, 2, 0, 1, 2] is observed rather than [0, 0, 1, 1, 2, 2].
        yields = [
            CustomYield(type=YieldTypes.SLEEP, args=[0]),
            CustomYield(type=YieldTypes.SLEEP, args=[1]),
            CustomYield(type=YieldTypes.SLEEP, args=[2]),
            CustomYield(type=YieldTypes.SLEEP, args=[0]),
            CustomYield(type=YieldTypes.SLEEP, args=[1]),
            CustomYield(type=YieldTypes.SLEEP, args=[2]),
        ]
        self.assert_yields(
            zipper, args=[generator, 3], yields=yields, returns=[(0, 0), (1, 1), (2, 2)]
        )

    def assert_yields(
        self,
        fn: FunctionType,
        yields: list[Any],
        args: list[Any] | None = None,
        kwargs: dict[str, Any] | None = None,
        returns: Any = None,
        sends: list[Any] | None = None,
    ):
        args = args if args is not None else []
        kwargs = kwargs if kwargs is not None else {}

        compiled_fn = compile_function(fn)
        gen = compiled_fn(*args, **kwargs)

        actual_yields = []
        actual_returns = None
        try:
            i = 0
            while True:
                if i == 0 or not sends:
                    value = gen.send(None)
                else:
                    value = gen.send(sends[i - 1])
                actual_yields.append(value)
                i += 1
        except StopIteration as e:
            actual_returns = e.value

        self.assertListEqual(actual_yields, yields)
        self.assertEqual(actual_returns, returns)
