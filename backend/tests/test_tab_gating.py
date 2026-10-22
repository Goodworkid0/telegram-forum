import pytest
from httpx import AsyncClient


async def _login(client, tid):
    r = await client.post(f"/api/auth/dev-login?telegram_id={tid}")
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _uid(client, headers):
    return (await client.get("/api/users/me", headers=headers)).json()["id"]


async def _tab_names(client, headers):
    r = await client.get("/api/forum/tabs", headers=headers)
    assert r.status_code == 200, r.text
    return {t["name"] for t in r.json()}


@pytest.mark.asyncio
async def test_admin_only_tab(client: AsyncClient):
    admin = await _login(client, 444444444)
    user = await _login(client, 890001)

    r = await client.post("/api/admin/tabs",
                          json={"name": "Staff Lounge", "slug": "staff-lounge", "min_role": "ADMIN"},
                          headers=admin)
    assert r.status_code == 200, r.text

    assert "Staff Lounge" in await _tab_names(client, admin)       # admin sees it
    assert "Staff Lounge" not in await _tab_names(client, user)    # member doesn't


@pytest.mark.asyncio
async def test_badge_gated_tab(client: AsyncClient):
    admin = await _login(client, 444444444)
    user = await _login(client, 890002)
    uid = await _uid(client, user)

    badge = await client.post("/api/badges", json={"name": "VIP Pass", "icon": "star"}, headers=admin)
    assert badge.status_code == 200, badge.text
    badge_id = badge.json()["id"]

    r = await client.post("/api/admin/tabs",
                          json={"name": "VIP Zone", "slug": "vip-zone", "min_role": "TRIAL",
                                "required_badge_id": badge_id},
                          headers=admin)
    assert r.status_code == 200, r.text

    # Without the badge the user can't see the tab; admin always can.
    assert "VIP Zone" not in await _tab_names(client, user)
    assert "VIP Zone" in await _tab_names(client, admin)

    # After the admin grants the badge, the tab appears for the user.
    aw = await client.post(f"/api/badges/{badge_id}/award/{uid}", headers=admin)
    assert aw.status_code == 200, aw.text
    assert "VIP Zone" in await _tab_names(client, user)
