import requests

import dispatch


@dispatch.function
def publish(url, payload):
    r = requests.post(url, data=payload)
    r.raise_for_status()
    return r.text


@dispatch.function
async def getting_started():
    return await publish("https://httpstat.us/200", {"hello": "world"})


if __name__ == "__main__":
    print(dispatch.run(getting_started()))
