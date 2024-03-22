"""Github repository stats example.

This example demonstrates how to use async functions orchestrated by Dispatch.

Make sure to follow the setup instructions at
https://docs.dispatch.run/dispatch/stateful-functions/getting-started/

Run with:

uvicorn app:app


Logs will show a pipeline of functions being called and their results.

"""

import httpx
from fastapi import FastAPI

from dispatch.fastapi import Endpoint

app = FastAPI()

dispatch = Endpoint(app)


def get_gh_api(url):
    print(f"GET {url}")
    response = httpx.get(url)
    X_RateLimit_Remaining = response.headers.get("X-RateLimit-Remaining")
    if response.status_code == 403 and X_RateLimit_Remaining == "0":
        raise EOFError("Rate limit exceeded")
    response.raise_for_status()
    return response.json()


@dispatch.function
async def get_repo_info(repo_owner: str, repo_name: str):
    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}"
    repo_info = get_gh_api(url)
    return repo_info


@dispatch.function
async def get_contributors(repo_info: dict):
    url = repo_info["contributors_url"]
    contributors = get_gh_api(url)
    return contributors


@dispatch.function
async def main():
    repo_info = await get_repo_info("stealthrocket", "coroutine")
    print(
        f"""Repository: {repo_info['full_name']}
Stars: {repo_info['stargazers_count']}
Watchers: {repo_info['watchers_count']}
Forks: {repo_info['forks_count']}"""
    )

    contributors = await get_contributors(repo_info)
    print(f"Contributors: {len(contributors)}")
    return


@app.get("/")
def root():
    main.dispatch()
    return "OK"
