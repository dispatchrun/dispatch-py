import requests

import dispatch


# Use the `dispatch.function` decorator declare a stateful function.
@dispatch.function
def publish(url, payload) -> str:
    r = requests.post(url, data=payload)
    r.raise_for_status()
    return r.text


# Use the `dispatch.run` function to run the function with automatic error
# handling and retries.
res = dispatch.run(publish("https://httpstat.us/200", {"hello": "world"}))
print(res)
