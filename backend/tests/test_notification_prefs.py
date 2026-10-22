"""Notification preferences saved in Settings must actually suppress delivery."""
import pytest
from httpx import AsyncClient
from sqlalchemy import select, func

from app.models import Notification
from app.telegram import create_notification


async def _login(client, tid):
    r = await client.post(f"/api/auth/dev-login?telegram_id={tid}")
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _uid(client, headers):
    r = await client.get("/api/users/me", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()["id"]


async def _count(db, uid, type_):
    return await db.scalar(
        select(func.count()).select_from(Notification).where(
            Notification.user_id == uid, Notification.type == type_
        )
    )


@pytest.mark.asyncio
async def test_notification_preferences_suppress_delivery(client: AsyncClient, db):
    headers = await _login(client, 870001)
    uid = await _uid(client, headers)

    r = await client.put("/api/auth/profile",
                         json={"notification_preferences": {"likes": False, "reputation": True}},
                         headers=headers)
    assert r.status_code == 200, r.text

    # Opted-out type: dropped entirely.
    await create_notification(db, user_id=uid, type="post_like", title="like!")
    # Same preference key covers thread likes too.
    await create_notification(db, user_id=uid, type="thread_like", title="like!")
    # Explicitly-enabled type: delivered.
    await create_notification(db, user_id=uid, type="reputation", title="+rep")
    # Type with no preference entry: delivered (defaults on).
    await create_notification(db, user_id=uid, type="badge", title="badge!")
    # Non-optional type: always delivered.
    await create_notification(db, user_id=uid, type="escrow", title="deal")
    await db.commit()

    assert await _count(db, uid, "post_like") == 0
    assert await _count(db, uid, "thread_like") == 0
    assert await _count(db, uid, "reputation") == 1
    assert await _count(db, uid, "badge") == 1
    assert await _count(db, uid, "escrow") == 1


@pytest.mark.asyncio
async def test_no_preferences_set_delivers_everything(client: AsyncClient, db):
    headers = await _login(client, 870002)
    uid = await _uid(client, headers)

    await create_notification(db, user_id=uid, type="post_like", title="like!")
    await db.commit()
    assert await _count(db, uid, "post_like") == 1
