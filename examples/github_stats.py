import httpx

import dispatch
from dispatch.error import ThrottleError


def get_gh_api(url):
    print(f"GET {url}")
    response = httpx.get(url)
    X_RateLimit_Remaining = response.headers.get("X-RateLimit-Remaining")
    if response.status_code == 403 and X_RateLimit_Remaining == "0":
        raise ThrottleError("Rate limit exceeded")
    response.raise_for_status()
    return response.json()


@dispatch.function
def get_repo_info(repo_owner, repo_name):
    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}"
    repo_info = get_gh_api(url)
    return repo_info


@dispatch.function
def get_contributors(repo_info):
    url = repo_info["contributors_url"]
    contributors = get_gh_api(url)
    return contributors


@dispatch.function
async def github_stats():
    repo_info = await get_repo_info("dispatchrun", "coroutine")
    print(
        f"""Repository: {repo_info['full_name']}
Stars: {repo_info['stargazers_count']}
Watchers: {repo_info['watchers_count']}
Forks: {repo_info['forks_count']}"""
    )
    return await get_contributors(repo_info)


if __name__ == "__main__":
    contributors = dispatch.run(github_stats())
    print(f"Contributors: {len(contributors)}")
