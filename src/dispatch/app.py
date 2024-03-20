import threading

from fastapi import FastAPI

from dispatch.fastapi import Dispatch as FastAPIDispatch
from dispatch.function import Function, Registry
from dispatch.proto import Input, Output


class Dispatch(FastAPIDispatch):
    def __init__(self):
        app = FastAPI()
        super().__init__(app)
        # TODO: logging

    def stop(self):
        self._should_stop = True

    def run(self, function: Function, *args):
        def primitive_root(input: Input) -> Output:
            if input.is_first_call:
                return Output.poll(state=None, calls=[input.input])
            self.stop()
            return Output.value(0)

        wrapped_root = self.primitive_function(primitive_root)

        thread = threading.Thread(target=super().run)
        thread.start()

        while True:  # TODO: timeout? condition variable?
            if self._ready:
                break

        call = function.build_call(*args)

        wrapped_root._primitive_dispatch(call)

        thread.join()
