import dispatch
import httpx

@dispatch.function
def get_repo(repo_owner: str, repo_name: str):
    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}"
    api_response = httpx.get(url)
    api_response.raise_for_status()
    repo_info = api_response.json()
    return repo_info


@dispatch.function
def get_stargazers(repo_info):
    url = repo_info["stargazers_url"]
    response = httpx.get(url)
    response.raise_for_status()
    stargazers = response.json()
    return stargazers


@dispatch.function
async def reduce_stargazers(repos):
    result = await dispatch.gather(*[get_stargazers(repo) for repo in repos])
    reduced_stars = set()
    for repo in result:
        for stars in repo:
            reduced_stars.add(stars["login"])
    return reduced_stars


@dispatch.function
async def fanout():
    # Using gather, we fan-out the following requests:
    repos = await dispatch.gather(
        get_repo("dispatchrun", "coroutine"),
        get_repo("dispatchrun", "dispatch-py"),
        get_repo("dispatchrun", "wzprof"),
    )
    return await reduce_stargazers(repos)

print(dispatch.run(fanout()))
