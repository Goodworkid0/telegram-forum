import pytest
from httpx import AsyncClient


async def _login(client, tid):
    r = await client.post(f"/api/auth/dev-login?telegram_id={tid}")
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.mark.asyncio
async def test_forum_search_returns_unified_results_shape(client: AsyncClient):
    """/api/forum/search must return the flat `results` list + `total` that the
    search UIs (ForumHome / Board) render. A missing `results` key crashes the
    React render (the "Something went wrong" error boundary)."""
    headers = await _login(client, 771001)

    res = await client.get(
        "/api/forum/search",
        params={"q": "anything", "per_page": 15},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    body = res.json()

    # The shape the frontend depends on.
    assert "results" in body, "response missing `results` (frontend crashes without it)"
    assert isinstance(body["results"], list)
    assert "total" in body and isinstance(body["total"], int)

    # Each hit must carry the fields the UI reads.
    for item in body["results"]:
        assert item["type"] in ("thread", "post")
        assert "thread_id" in item
        assert "thread_slug" in item
        assert "thread_title" in item
        assert "snippet" in item
        # board_name is what Board.jsx filters on; key must be present (may be null).
        assert "board_name" in item


@pytest.mark.asyncio
async def test_forum_search_requires_min_length(client: AsyncClient):
    """Queries shorter than 2 chars are rejected (422), never a 500."""
    headers = await _login(client, 771002)
    res = await client.get("/api/forum/search", params={"q": "a"}, headers=headers)
    assert res.status_code == 422, res.text
