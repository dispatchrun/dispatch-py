from dispatch.function import  Function
from dispatch.fastapi import Dispatch as FastAPI

class Dispatch(Registry):
    def __init__(
        self
    ):
        self._app = FastAPI()
        self.registry = {}

    def run(self, function: Function, ):
        self._app.run(function, args)
