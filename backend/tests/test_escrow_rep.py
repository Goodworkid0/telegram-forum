"""Rep between escrow counterparties: closed-deal partners are exempt from the
min-posts requirement; everyone else is not."""
import pytest
from httpx import AsyncClient

from tests.helpers import open_deal_via_invite


async def _login(client, tid):
    r = await client.post(f"/api/auth/dev-login?telegram_id={tid}")
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _uid(client, headers):
    r = await client.get("/api/users/me", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()["id"]


@pytest.mark.asyncio
async def test_deal_partners_can_rep_without_min_posts(client: AsyncClient):
    admin = await _login(client, 444444444)
    buyer = await _login(client, 860001)
    seller = await _login(client, 860002)
    outsider = await _login(client, 860003)
    buyer_id = await _uid(client, buyer)
    seller_id = await _uid(client, seller)

    adj = await client.put(f"/api/admin/users/{buyer_id}/balance",
                           params={"amount": 50.0, "reason": "seed"}, headers=admin)
    assert adj.status_code == 200, adj.text

    deal_id = await open_deal_via_invite(client, buyer, seller, title="Rep test", amount=50.0)

    # Deal not closed yet -> deal_id reference is rejected.
    early = await client.post(f"/api/reputation/users/{seller_id}",
                              json={"is_positive": True, "deal_id": deal_id}, headers=buyer)
    assert early.status_code == 400, early.text

    assert (await client.post(f"/api/escrow/deals/{deal_id}/fund", headers=buyer)).status_code == 200
    assert (await client.post(f"/api/escrow/deals/{deal_id}/deliver", headers=seller)).status_code == 200
    assert (await client.post(f"/api/escrow/deals/{deal_id}/complete", headers=buyer)).status_code == 200

    # Both partners have 0 posts but can rep each other via the deal.
    r = await client.post(f"/api/reputation/users/{seller_id}",
                          json={"is_positive": True, "comment": "smooth deal", "deal_id": deal_id},
                          headers=buyer)
    assert r.status_code == 200, r.text

    r = await client.post(f"/api/reputation/users/{buyer_id}",
                          json={"is_positive": True, "deal_id": deal_id}, headers=seller)
    assert r.status_code == 200, r.text

    # 24h cooldown still applies to the same pair.
    again = await client.post(f"/api/reputation/users/{seller_id}",
                              json={"is_positive": True, "deal_id": deal_id}, headers=buyer)
    assert again.status_code == 400, again.text

    # A non-party cannot use someone else's deal to bypass the gate.
    r = await client.post(f"/api/reputation/users/{seller_id}",
                          json={"is_positive": True, "deal_id": deal_id}, headers=outsider)
    assert r.status_code == 400, r.text

    # Without a deal the min-posts gate still applies.
    r = await client.post(f"/api/reputation/users/{seller_id}",
                          json={"is_positive": True}, headers=outsider)
    assert r.status_code == 403, r.text

    # Nonexistent deal reference.
    r = await client.post(f"/api/reputation/users/{seller_id}",
                          json={"is_positive": True, "deal_id": 999999}, headers=buyer)
    assert r.status_code == 400, r.text


@pytest.mark.asyncio
async def test_hidden_handle_not_leaked_in_escrow(client: AsyncClient):
    """A user who hides their Telegram handle must appear by display name in
    escrow serializations seen by the counterparty."""
    admin = await _login(client, 444444444)
    buyer = await _login(client, 870010)
    seller = await _login(client, 870011)
    buyer_id = await _uid(client, buyer)

    # Buyer hides their handle at setup and goes by display name "Ghost".
    r = await client.post("/api/auth/setup",
                          json={"pin": "secret1", "first_name": "Ghost", "show_telegram": False},
                          headers=buyer)
    assert r.status_code == 200, r.text
    buyer_handle = r.json()["username"]

    await client.put(f"/api/admin/users/{buyer_id}/balance",
                     params={"amount": 30.0, "reason": "seed"}, headers=admin)

    deal_id = await open_deal_via_invite(client, buyer, seller, title="Privacy test", amount=30.0)

    # Seller's view of the deal must show the display name, not the handle.
    view = (await client.get(f"/api/escrow/deals/{deal_id}", headers=seller)).json()
    assert view["buyer_username"] == "Ghost", view["buyer_username"]
    assert buyer_handle not in str(view.get("messages", "")), "handle leaked in system messages"


@pytest.mark.asyncio
async def test_escrow_invite_flow(client: AsyncClient):
    """Invite codes: create -> preview -> accept creates an ACCEPTED deal with
    correct roles; self-accept and reuse are rejected."""
    admin = await _login(client, 444444444)
    creator = await _login(client, 870020)   # will be the buyer
    redeemer = await _login(client, 870021)  # will be the seller
    creator_id = await _uid(client, creator)

    await client.put(f"/api/admin/users/{creator_id}/balance",
                     params={"amount": 40.0, "reason": "seed"}, headers=admin)

    # Creator without balance can't create a buyer-role invite.
    poor = await _login(client, 870022)
    r = await client.post("/api/escrow/invites",
                          json={"role": "buyer", "title": "No funds", "amount": 40.0}, headers=poor)
    assert r.status_code == 400, r.text

    r = await client.post("/api/escrow/invites",
                          json={"role": "buyer", "title": "Invite deal", "amount": 40.0, "hold_days": 2},
                          headers=creator)
    assert r.status_code == 200, r.text
    code = r.json()["code"]
    assert len(code) == 8

    # Preview works for others; creator can't accept their own invite.
    p = await client.get(f"/api/escrow/invites/{code}", headers=redeemer)
    assert p.status_code == 200 and p.json()["creator_role"] == "buyer"
    r = await client.post(f"/api/escrow/invites/{code}/accept", headers=creator)
    assert r.status_code == 400

    # Redeem: deal exists in ACCEPTED with correct roles.
    r = await client.post(f"/api/escrow/invites/{code}/accept", headers=redeemer)
    assert r.status_code == 200, r.text
    deal = r.json()
    assert deal["status"] == "accepted"
    redeemer_id = await _uid(client, redeemer)
    assert deal["buyer_id"] == creator_id and deal["seller_id"] == redeemer_id

    # Single use.
    r = await client.post(f"/api/escrow/invites/{code}/accept", headers=redeemer)
    assert r.status_code == 404
    p = await client.get(f"/api/escrow/invites/{code}", headers=redeemer)
    assert p.status_code == 404


@pytest.mark.asyncio
async def test_moderator_cannot_resolve_own_dispute(client: AsyncClient):
    """A moderator who is a party to a disputed deal cannot resolve it (they
    could otherwise release the held funds to themselves)."""
    admin = await _login(client, 444444444)
    # Promote the seller to MODERATOR so they're a party AND can call resolve.
    modseller = await _login(client, 881001)
    buyer = await _login(client, 881002)
    ms_id = await _uid(client, modseller)
    buyer_id = await _uid(client, buyer)
    await client.put(f"/api/admin/users/{ms_id}/role", params={"role": "MODERATOR"}, headers=admin)
    await client.put(f"/api/admin/users/{buyer_id}/balance",
                     params={"amount": 50.0, "reason": "seed"}, headers=admin)

    deal_id = await open_deal_via_invite(client, buyer, modseller, title="Self resolve", amount=50.0)
    assert (await client.post(f"/api/escrow/deals/{deal_id}/fund", headers=buyer)).status_code == 200
    assert (await client.post(f"/api/escrow/deals/{deal_id}/dispute",
                              json={"content": "x"}, headers=buyer)).status_code == 200

    # The moderator-seller must NOT be able to resolve to themselves.
    r = await client.post(f"/api/escrow/deals/{deal_id}/resolve",
                          json={"release_to": "seller", "note": "mine"}, headers=modseller)
    assert r.status_code == 403, r.text

    # A neutral admin still can.
    r = await client.post(f"/api/escrow/deals/{deal_id}/resolve",
                          json={"release_to": "seller", "note": "ok"}, headers=admin)
    assert r.status_code == 200, r.text
