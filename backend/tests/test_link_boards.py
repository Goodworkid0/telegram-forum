"""Tests for 'link' boards — shortcut rows that point at another page (e.g.
/leaderboard, /giveaways, or an external URL) instead of holding threads."""
import pytest
from httpx import AsyncClient


async def _admin(client):
    r = await client.post("/api/auth/dev-login?telegram_id=444444444")
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _make_section(client, headers, slug):
    r = await client.post("/api/admin/sections",
                          json={"name": f"Sec {slug}", "slug": slug}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()["id"]


@pytest.mark.asyncio
async def test_create_link_board_internal_and_external(client: AsyncClient):
    headers = await _admin(client)
    section_id = await _make_section(client, headers, "linksec1")

    internal = await client.post("/api/admin/boards", json={
        "section_id": section_id, "name": "Leaderboard", "slug": "lb-link",
        "board_type": "link", "link_target": "/leaderboard",
    }, headers=headers)
    assert internal.status_code == 200, internal.text
    assert internal.json()["board_type"] == "link"
    assert internal.json()["link_target"] == "/leaderboard"

    external = await client.post("/api/admin/boards", json={
        "section_id": section_id, "name": "Channel", "slug": "tg-link",
        "board_type": "link", "link_target": "https://t.me/example",
    }, headers=headers)
    assert external.status_code == 200, external.text
    assert external.json()["link_target"] == "https://t.me/example"


@pytest.mark.asyncio
async def test_link_board_requires_valid_target(client: AsyncClient):
    headers = await _admin(client)
    section_id = await _make_section(client, headers, "linksec2")

    # Missing target on a link board is rejected (pydantic 422).
    missing = await client.post("/api/admin/boards", json={
        "section_id": section_id, "name": "Bad", "slug": "bad-link", "board_type": "link",
    }, headers=headers)
    assert missing.status_code == 422, missing.text

    # A target that is neither an in-app path nor an http(s) URL is rejected.
    malformed = await client.post("/api/admin/boards", json={
        "section_id": section_id, "name": "Bad2", "slug": "bad-link-2",
        "board_type": "link", "link_target": "javascript:alert(1)",
    }, headers=headers)
    assert malformed.status_code == 422, malformed.text


@pytest.mark.asyncio
async def test_forum_board_still_defaults_to_forum_type(client: AsyncClient):
    headers = await _admin(client)
    section_id = await _make_section(client, headers, "linksec3")

    r = await client.post("/api/admin/boards", json={
        "section_id": section_id, "name": "General", "slug": "general-fb",
    }, headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["board_type"] == "forum"
    assert r.json()["link_target"] is None
