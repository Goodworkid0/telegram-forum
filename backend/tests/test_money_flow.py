from decimal import Decimal

import pytest
from httpx import AsyncClient

from app.money import to_money, apply_percent
from tests.helpers import open_deal_via_invite


def test_money_helpers_rounding():
    assert to_money(0.1) + to_money(0.2) == Decimal("0.30")        # no float drift
    assert apply_percent(100, 10) == Decimal("10.00")
    assert apply_percent(Decimal("10.05"), 10) == Decimal("1.01")  # 1.005 -> half-up
    assert to_money(None) == Decimal("0.00")
    assert apply_percent(50, 0) == Decimal("0.00")


async def _login(client, tid):
    r = await client.post(f"/api/auth/dev-login?telegram_id={tid}")
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _uid(client, headers):
    r = await client.get("/api/users/me", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()["id"]


@pytest.mark.asyncio
async def test_escrow_fee_exact_decimal_and_reconciles(client: AsyncClient, db):
    """Full escrow lifecycle with a 10% fee: amounts must be exact Decimal and
    both parties' ledgers must reconcile."""
    from app.models import AppSettings

    # 10% escrow fee.
    s = await db.get(AppSettings, 1)
    if not s:
        s = AppSettings(id=1)
        db.add(s)
    s.escrow_fee_percent = 10.0
    await db.commit()

    admin = await _login(client, 444444444)
    buyer = await _login(client, 850001)
    seller = await _login(client, 850002)
    buyer_id = await _uid(client, buyer)
    seller_id = await _uid(client, seller)

    # Fund the buyer with $100.00.
    adj = await client.put(f"/api/admin/users/{buyer_id}/balance",
                           params={"amount": 100.0, "reason": "seed"}, headers=admin)
    assert adj.status_code == 200, adj.text

    # Invite (accepted) -> fund -> deliver -> complete.
    deal_id = await open_deal_via_invite(client, buyer, seller, title="Widget", amount=100.0)
    assert (await client.post(f"/api/escrow/deals/{deal_id}/fund", headers=buyer)).status_code == 200
    assert (await client.post(f"/api/escrow/deals/{deal_id}/deliver", headers=seller)).status_code == 200
    assert (await client.post(f"/api/escrow/deals/{deal_id}/complete", headers=buyer)).status_code == 200

    # Buyer spent 100, seller received net 90 (10% fee). Exact.
    seller_me = (await client.get("/api/users/me", headers=seller)).json()
    buyer_me = (await client.get("/api/users/me", headers=buyer)).json()
    assert seller_me["balance"] == 90.0, seller_me["balance"]
    assert buyer_me["balance"] == 0.0, buyer_me["balance"]
    assert buyer_me["pending_balance"] == 0.0, buyer_me["pending_balance"]

    # Both ledgers reconcile exactly (balance and pending).
    for uid in (buyer_id, seller_id):
        rec = (await client.get(f"/api/admin/users/{uid}/ledger", headers=admin)).json()["reconciliation"]
        assert rec["balance"]["consistent"] is True, (uid, rec)
        assert rec["pending"]["consistent"] is True, (uid, rec)


@pytest.mark.asyncio
async def test_withdraw_fee_decimal_and_broadcast(client: AsyncClient, db):
    """Withdrawal applies the % fee exactly, debits balance, broadcasts (in-memory
    SSE path must not choke on Decimal), and reconciles."""
    from app.models import AppSettings
    s = await db.get(AppSettings, 1)
    if not s:
        s = AppSettings(id=1); db.add(s)
    s.withdrawal_fee_percent = 5.0
    s.min_withdrawal_amount = 10.0
    await db.commit()

    admin = await _login(client, 444444444)
    u = await _login(client, 870001)
    uid = await _uid(client, u)
    await client.put(f"/api/admin/users/{uid}/balance", params={"amount": 100.0, "reason": "seed"}, headers=admin)

    addr = "4" + "A" * 94  # valid-shaped XMR address (95 chars, starts with 4)
    w = await client.post("/api/wallet/withdraw", json={"amount": 40.0, "address": addr}, headers=u)
    assert w.status_code == 200, w.text

    me = (await client.get("/api/users/me", headers=u)).json()
    assert me["balance"] == 60.0, me["balance"]  # 100 - 40

    wl = (await client.get("/api/wallet/withdrawals", headers=u)).json()
    assert wl[0]["amount"] == 40.0
    assert wl[0]["fee_amount"] == 2.0    # 5% of 40
    assert wl[0]["net_amount"] == 38.0

    rec = (await client.get(f"/api/admin/users/{uid}/ledger", headers=admin)).json()["reconciliation"]
    assert rec["balance"]["consistent"] is True, rec


@pytest.mark.asyncio
async def test_paid_display_name_change(client: AsyncClient, db):
    """Display name can't be changed for free, only via the paid $20 endpoint,
    which deducts exactly $20 and reconciles."""
    admin = await _login(client, 444444444)
    u = await _login(client, 880001)
    uid = await _uid(client, u)
    await client.put(f"/api/admin/users/{uid}/balance", params={"amount": 45.0, "reason": "seed"}, headers=admin)

    # Free profile update must NOT change the display name (field removed from schema).
    before = (await client.get("/api/users/me", headers=u)).json()["first_name"]
    await client.put("/api/auth/profile", json={"first_name": "FreebieHacker"}, headers=u)
    after_free = (await client.get("/api/users/me", headers=u)).json()["first_name"]
    assert after_free == before, "free profile update should not change first_name"

    # Two paid changes, $20 each.
    assert (await client.post("/api/users/me/display-name", json={"first_name": "Neo"}, headers=u)).status_code == 200
    assert (await client.post("/api/users/me/display-name", json={"first_name": "Trinity"}, headers=u)).status_code == 200
    me = (await client.get("/api/users/me", headers=u)).json()
    assert me["first_name"] == "Trinity"
    assert me["balance"] == 5.0  # 45 - 40

    rec = (await client.get(f"/api/admin/users/{uid}/ledger", headers=admin)).json()["reconciliation"]
    assert rec["balance"]["consistent"] is True

    # Doppelganger badge awarded and stacked to ×2 (two name changes).
    profile = (await client.get(f"/api/users/{uid}", headers=u)).json()
    dopp = [b for b in profile["badges"] if b["badge"]["name"] == "Doppelganger"]
    assert len(dopp) == 1, profile["badges"]
    assert dopp[0]["quantity"] == 2, dopp[0]

    # Insufficient balance is rejected (5 left, costs 20).
    poor = await client.post("/api/users/me/display-name", json={"first_name": "Morpheus"}, headers=u)
    assert poor.status_code == 400
    assert "balance" in poor.json()["detail"].lower()
