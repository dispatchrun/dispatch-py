"""Fan-out example using the SDK gather feature

This example demonstrates how to use the SDK to fan-out multiple requests.

Run with:

uvicorn fanout:app


You will observe that the get_repo_info calls are executed in parallel.

"""

import httpx
from fastapi import FastAPI

from dispatch import gather
from dispatch.fastapi import Dispatch

app = FastAPI()

dispatch = Dispatch(app)


@dispatch.function
async def get_repo(repo_owner: str, repo_name: str):
    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}"
    api_response = httpx.get(url)
    api_response.raise_for_status()
    repo_info = api_response.json()
    return repo_info


@dispatch.function
async def get_stargazers(repo_info):
    url = repo_info["stargazers_url"]
    response = httpx.get(url)
    response.raise_for_status()
    stargazers = response.json()
    return stargazers


@dispatch.function
async def reduce_stargazers(repos):
    result = await gather(*[get_stargazers(repo) for repo in repos])
    reduced_stars = set()
    for repo in result:
        for stars in repo:
            reduced_stars.add(stars["login"])
    return reduced_stars


@dispatch.function
async def fanout():
    # Using gather, we fan-out the four following requests.
    repos = await gather(
        get_repo("dispatchrun", "coroutine"),
        get_repo("dispatchrun", "dispatch-py"),
        get_repo("dispatchrun", "wzprof"),
    )

    stars = await reduce_stargazers(repos)
    print("Total stars:", len(stars))


@app.get("/")
def root():
    fanout.dispatch()
    return "OK"
