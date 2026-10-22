import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_admin_content_search_browse_and_query(client: AsyncClient):
    """Admin content search returns the expected shape for both browse-all
    (empty query) and a search query, on the SQLite/ILIKE fallback path."""
    login = await client.post("/api/auth/dev-login?telegram_id=444444444")
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    # Browse all (empty query) — must not error and returns the response shape.
    browse = await client.get("/api/admin/content", headers=headers)
    assert browse.status_code == 200, browse.text
    body = browse.json()
    assert "items" in body and "total" in body
    assert isinstance(body["items"], list)

    # With a query (and combined type=all pagination path).
    queried = await client.get(
        "/api/admin/content",
        params={"q": "nonexistent_term_xyz", "content_type": "all"},
        headers=headers,
    )
    assert queried.status_code == 200, queried.text
    assert queried.json()["items"] == []
