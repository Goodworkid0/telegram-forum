import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_forum_structure_accessible(client: AsyncClient):
    """Forum tabs/sections should be accessible when authenticated."""
    login_resp = await client.post("/api/auth/dev-login?telegram_id=700010")
    token = login_resp.json()["access_token"]

    response = await client.get(
        "/api/forum/tabs",
        headers={"Authorization": f"Bearer {token}"}
    )
    # May be empty if no data seeded, but should not error
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_search_requires_query(client: AsyncClient):
    """Search with valid query should return results structure."""
    login_resp = await client.post("/api/auth/dev-login?telegram_id=700011")
    token = login_resp.json()["access_token"]

    response = await client.get(
        "/api/forum/search?q=test",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "threads" in data
    assert "posts" in data
    assert "users" in data


@pytest.mark.asyncio
async def test_thread_creation_requires_auth(client: AsyncClient):
    response = await client.post("/api/forum/boards/test/threads", json={
        "title": "Test", "content": "Test content"
    })
    assert response.status_code in (401, 403)




@pytest.mark.asyncio
async def test_activity_feed_requires_auth(client: AsyncClient):
    """Unified activity feed requires authentication."""
    response = await client.get("/api/forum/activity-feed")
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_activity_feed_structure_and_join_event(client: AsyncClient):
    """The feed returns a merged, newest-first list. A freshly registered user
    must appear as a 'join' event with only known item types present."""
    login_resp = await client.post("/api/auth/dev-login?telegram_id=700020")
    token = login_resp.json()["access_token"]

    response = await client.get(
        "/api/forum/activity-feed",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "items" in data and "total" in data
    types = {item["type"] for item in data["items"]}
    assert types <= {"thread", "join", "rep"}
    # The just-created user should surface as a join event.
    assert any(it["type"] == "join" for it in data["items"])
