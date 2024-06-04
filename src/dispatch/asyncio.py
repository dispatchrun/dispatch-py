import asyncio
import functools
import inspect
import signal
import threading


class Runner:
    """Runner is a class similar to asyncio.Runner but that we use for backward
    compatibility with Python 3.10 and earlier.
    """

    def __init__(self):
        self._loop = asyncio.new_event_loop()
        self._interrupt_count = 0

    def __enter__(self):
        return self

    def __exit__(self, *args, **kwargs):
        self.close()

    def close(self):
        try:
            loop = self._loop
            _cancel_all_tasks(loop)
            loop.run_until_complete(loop.shutdown_asyncgens())
            if hasattr(loop, "shutdown_default_executor"):  # Python 3.9+
                loop.run_until_complete(loop.shutdown_default_executor())
        finally:
            loop.close()

    def get_loop(self):
        return self._loop

    def run(self, coro):
        if not inspect.iscoroutine(coro):
            raise ValueError("a coroutine was expected, got {!r}".format(coro))

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            pass
        else:
            raise RuntimeError(
                "Runner.run() cannot be called from a running event loop"
            )

        task = self._loop.create_task(coro)
        sigint_handler = None

        if (
            threading.current_thread() is threading.main_thread()
            and signal.getsignal(signal.SIGINT) is signal.default_int_handler
        ):
            sigint_handler = functools.partial(self._on_sigint, main_task=task)
            try:
                signal.signal(signal.SIGINT, sigint_handler)
            except ValueError:
                # `signal.signal` may throw if `threading.main_thread` does
                # not support signals (e.g. embedded interpreter with signals
                # not registered - see gh-91880)
                sigint_handler = None

        self._interrupt_count = 0
        try:
            asyncio.set_event_loop(self._loop)
            return self._loop.run_until_complete(task)
        except asyncio.CancelledError:
            if self._interrupt_count > 0:
                uncancel = getattr(task, "uncancel", None)
                if uncancel is not None and uncancel() == 0:
                    raise KeyboardInterrupt()
            raise  # CancelledError
        finally:
            asyncio.set_event_loop(None)
            if (
                sigint_handler is not None
                and signal.getsignal(signal.SIGINT) is sigint_handler
            ):
                signal.signal(signal.SIGINT, signal.default_int_handler)

    def _on_sigint(self, signum, frame, main_task):
        self._interrupt_count += 1
        if self._interrupt_count == 1 and not main_task.done():
            main_task.cancel()
            # wakeup loop if it is blocked by select() with long timeout
            self._loop.call_soon_threadsafe(lambda: None)
            return
        raise KeyboardInterrupt()


def _cancel_all_tasks(loop):
    to_cancel = asyncio.all_tasks(loop)
    if not to_cancel:
        return

    for task in to_cancel:
        task.cancel()

    loop.run_until_complete(asyncio.gather(*to_cancel, return_exceptions=True))

    for task in to_cancel:
        if task.cancelled():
            continue
        if task.exception() is not None:
            loop.call_exception_handler(
                {
                    "message": "unhandled exception during asyncio.run() shutdown",
                    "exception": task.exception(),
                    "task": task,
                }
            )
