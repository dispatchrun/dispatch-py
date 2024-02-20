"""Github repository stats example.

This example demonstrates how to use async functions orchestrated by Dispatch.

Make sure to follow the setup instructions at
https://docs.stealthrocket.cloud/dispatch/stateful-functions/getting-started/

Run with:

uvicorn app:app


Logs will show a pipeline of functions being called and their results.

"""

import httpx
from fastapi import FastAPI
from dispatch.fastapi import Dispatch

app = FastAPI()

dispatch = Dispatch(app)


@dispatch.function()
def get_repo_info(repo_owner: str, repo_name: str):
    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}"
    api_response = httpx.get(url)
    api_response.raise_for_status()
    repo_info = api_response.json()
    return repo_info


@dispatch.function()
def get_contributors(repo_info: dict):
    contributors_url = repo_info["contributors_url"]
    response = httpx.get(contributors_url)
    response.raise_for_status()
    contributors = response.json()
    return contributors


@dispatch.coroutine()
async def main():
    repo_info = await get_repo_info.call("stealthrocket", "coroutine")
    print(f"""Repository: {repo_info['full_name']}
Stars: {repo_info['stargazers_count']}
Watchers: {repo_info['watchers_count']}
Forks: {repo_info['forks_count']}""")

    contributors = await get_contributors.call(repo_info)
    print(f"Contributors: {len(contributors)}")
    return


@app.get("/")
def root():
    main.dispatch()
    return "OK"
