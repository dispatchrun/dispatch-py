import dispatch.test

from .auto_retry import auto_retry
from .fanout import fanout
from .getting_started import getting_started
from .github_stats import github_stats


@dispatch.test.function
async def test_auto_retry():
    assert await auto_retry() == "SUCCESS"


@dispatch.test.function
async def test_fanout():
    contributors = await fanout()
    assert len(contributors) >= 15
    assert "achille-roussel" in contributors


@dispatch.test.function
async def test_getting_started():
    assert await getting_started() == "200 OK"


@dispatch.test.function
async def test_github_stats():
    contributors = await github_stats()
    assert len(contributors) >= 6
