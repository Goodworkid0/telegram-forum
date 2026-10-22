"""Shared test helpers."""


async def open_deal_via_invite(client, buyer_headers, seller_headers, title="Deal", amount=100.0, hold_days=None, description=None):
    """Open an escrow deal through the invite flow (the only creation path):
    the buyer creates a buyer-role invite, the seller accepts it. Returns the
    deal id; the deal starts in ACCEPTED state (buyer funds next)."""
    payload = {"role": "buyer", "title": title, "amount": amount}
    if hold_days is not None:
        payload["hold_days"] = hold_days
    if description is not None:
        payload["description"] = description
    inv = await client.post("/api/escrow/invites", json=payload, headers=buyer_headers)
    assert inv.status_code == 200, inv.text
    acc = await client.post(f"/api/escrow/invites/{inv.json()['code']}/accept", headers=seller_headers)
    assert acc.status_code == 200, acc.text
    return acc.json()["id"]
