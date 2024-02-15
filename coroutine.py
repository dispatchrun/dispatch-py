import logging

import fastapi
import requests

from dispatch import gather
from dispatch.fastapi import Dispatch

logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


app = fastapi.FastAPI()
dispatch = Dispatch(app)


@dispatch.function()
def get(url: str):
    r = requests.get(url)
    r.raise_for_status()
    return r


@dispatch.coroutine()
async def subroutine1():
    print("subroutine1")
    return await gather(
        get.call("https://httpstat.us/201"), get.call("https://httpstat.us/202")
    )


@dispatch.coroutine()
async def subroutine2():
    print("subroutine2")
    response1 = await get.call("https://httpstat.us/201")
    print("subroutine2 => 201")
    response2 = await get.call("https://httpstat.us/202")
    print("subroutine2 => 202")
    return (response1, response2)


@dispatch.coroutine()
async def indirect(url: str):
    print("indirect")
    return await get.call(url)


@dispatch.coroutine()
async def main():
    results = await gather(
        # FIXME: uncomment some/all of these to trigger the segfault
        subroutine1(),
        # subroutine2(),
        # indirect("https://httpstatus.us/205"),
        get.call("https://httpstatus.us/204"),
    )
    print(results)


main.dispatch()
