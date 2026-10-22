import pytest
from httpx import AsyncClient


async def _login(client, tid):
    r = await client.post(f"/api/auth/dev-login?telegram_id={tid}")
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.mark.asyncio
async def test_mod_lock_pin_delete_thread(client: AsyncClient):
    """Mod actions on a thread (pin/lock/delete) must all return 200 — deleting
    used to 404 because the serializer filtered out the just-deleted thread,
    which crashed the client."""
    admin = await _login(client, 444444444)

    sid = (await client.post("/api/admin/sections", json={"name": "ModSec", "slug": "modsec"}, headers=admin)).json()["id"]
    bslug = (await client.post("/api/admin/boards", json={"section_id": sid, "name": "ModBoard", "slug": "modboard"}, headers=admin)).json()["slug"]
    tid = (await client.post(f"/api/forum/boards/{bslug}/threads", json={"title": "T", "content": "x"}, headers=admin)).json()["id"]

    assert (await client.patch(f"/api/forum/threads/{tid}/mod", json={"is_pinned": True}, headers=admin)).status_code == 200
    assert (await client.patch(f"/api/forum/threads/{tid}/mod", json={"status": "locked"}, headers=admin)).status_code == 200

    deleted = await client.patch(f"/api/forum/threads/{tid}/mod", json={"status": "deleted"}, headers=admin)
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["status"] == "deleted"
