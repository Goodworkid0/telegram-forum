"""Tests for live-chat moderation: staff can delete other users' messages.

Regression guard for the role-check casing bug — the delete endpoint compared
`role.value` against lowercase strings, but UserRole values are uppercase, so
moderator/admin deletion of others' messages silently 403'd.
"""
import pytest
from httpx import AsyncClient

from app.models import User, UserRole, ChatMessage


async def _login(client, tid):
    r = await client.post(f"/api/auth/dev-login?telegram_id={tid}")
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _uid(client, headers):
    r = await client.get("/api/users/me", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()["id"]


@pytest.mark.asyncio
async def test_non_staff_cannot_delete_others_message(client: AsyncClient):
    author = await _login(client, 880001)
    posted = await client.post("/api/chat/messages", json={"content": "hello world"}, headers=author)
    assert posted.status_code == 200, posted.text
    msg_id = posted.json()["id"]

    stranger = await _login(client, 880002)
    resp = await client.delete(f"/api/chat/messages/{msg_id}", headers=stranger)
    assert resp.status_code == 403, resp.text


@pytest.mark.asyncio
async def test_admin_can_delete_others_message(client: AsyncClient, db):
    author = await _login(client, 880010)
    posted = await client.post("/api/chat/messages", json={"content": "spam spam"}, headers=author)
    assert posted.status_code == 200, posted.text
    msg_id = posted.json()["id"]

    admin = await _login(client, 880011)
    admin_id = await _uid(client, admin)
    admin_row = await db.get(User, admin_id)
    admin_row.role = UserRole.ADMIN
    await db.commit()

    resp = await client.delete(f"/api/chat/messages/{msg_id}", headers=admin)
    assert resp.status_code == 200, resp.text

    deleted = await db.get(ChatMessage, msg_id)
    await db.refresh(deleted)
    assert deleted.is_deleted is True
