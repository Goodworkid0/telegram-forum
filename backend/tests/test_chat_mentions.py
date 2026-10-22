"""Tests for @mention notifications in live chat.

When a chat message contains @username, the mentioned (active) user should get
a 'mention' notification linking to /chat — but never the sender themselves.
"""
import pytest
from sqlalchemy import select
from httpx import AsyncClient

from app.models import User, Notification


async def _login(client, tid):
    r = await client.post(f"/api/auth/dev-login?telegram_id={tid}")
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _uid(client, headers):
    r = await client.get("/api/users/me", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()["id"]


async def _set_username(db, user_id, username):
    row = await db.get(User, user_id)
    row.username = username
    await db.commit()


async def _mentions_for(db, user_id):
    result = await db.execute(
        select(Notification).where(
            Notification.user_id == user_id,
            Notification.type == "mention",
        )
    )
    return result.scalars().all()


@pytest.mark.asyncio
async def test_mention_creates_notification(client: AsyncClient, db):
    bob = await _login(client, 882001)
    bob_id = await _uid(client, bob)
    await _set_username(db, bob_id, "bob_target")

    alice = await _login(client, 882002)
    alice_id = await _uid(client, alice)

    posted = await client.post(
        "/api/chat/messages",
        json={"content": "hey @bob_target check this out"},
        headers=alice,
    )
    assert posted.status_code == 200, posted.text

    notifs = await _mentions_for(db, bob_id)
    assert len(notifs) == 1
    n = notifs[0]
    assert n.link == "/chat"
    assert n.related_user_id == alice_id


@pytest.mark.asyncio
async def test_self_mention_does_not_notify(client: AsyncClient, db):
    sam = await _login(client, 882010)
    sam_id = await _uid(client, sam)
    await _set_username(db, sam_id, "sam_solo")

    posted = await client.post(
        "/api/chat/messages",
        json={"content": "talking to myself @sam_solo"},
        headers=sam,
    )
    assert posted.status_code == 200, posted.text

    assert await _mentions_for(db, sam_id) == []


@pytest.mark.asyncio
async def test_unknown_mention_is_harmless(client: AsyncClient, db):
    alice = await _login(client, 882020)

    posted = await client.post(
        "/api/chat/messages",
        json={"content": "hello @nobody_here_xyz"},
        headers=alice,
    )
    # No matching user -> no notification, no error.
    assert posted.status_code == 200, posted.text
