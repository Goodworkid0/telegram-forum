import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_escrow_list_requires_auth(client: AsyncClient):
    response = await client.get("/api/escrow/deals")
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_escrow_invite_create_requires_auth(client: AsyncClient):
    """Invites are the only deal-creation path and require auth."""
    response = await client.post("/api/escrow/invites", json={
        "role": "buyer",
        "title": "Test",
        "amount": 100.0,
    })
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_escrow_buyer_invite_needs_balance(client: AsyncClient):
    """A buyer-role invite requires the creator to have sufficient balance."""
    r1 = await client.post("/api/auth/dev-login?telegram_id=800001")
    token1 = r1.json()["access_token"]

    response = await client.post(
        "/api/escrow/invites",
        json={"role": "buyer", "title": "Needs Balance", "amount": 100.0},
        headers={"Authorization": f"Bearer {token1}"},
    )
    assert response.status_code == 400
    assert "balance" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_escrow_cannot_accept_own_invite(client: AsyncClient):
    """Cannot open a deal with yourself by redeeming your own invite."""
    r1 = await client.post("/api/auth/dev-login?telegram_id=800003")
    token1 = r1.json()["access_token"]
    headers = {"Authorization": f"Bearer {token1}"}

    create = await client.post(
        "/api/escrow/invites",
        json={"role": "seller", "title": "Self Deal", "amount": 10.0},
        headers=headers,
    )
    assert create.status_code == 200, create.text

    response = await client.post(
        f"/api/escrow/invites/{create.json()['code']}/accept", headers=headers
    )
    assert response.status_code == 400
    assert "own" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_escrow_unknown_invite_code(client: AsyncClient):
    """Redeeming or previewing a non-existent code fails cleanly."""
    r1 = await client.post("/api/auth/dev-login?telegram_id=800004")
    headers = {"Authorization": f"Bearer {r1.json()['access_token']}"}

    assert (await client.get("/api/escrow/invites/NOPE1234", headers=headers)).status_code == 404
    assert (await client.post("/api/escrow/invites/NOPE1234/accept", headers=headers)).status_code == 404


@pytest.mark.asyncio
async def test_escrow_get_requires_auth(client: AsyncClient):
    """Getting a deal requires auth."""
    response = await client.get("/api/escrow/deals/9999")
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_escrow_admin_list_requires_mod(client: AsyncClient):
    """Admin escrow deal list requires moderator access."""
    r1 = await client.post("/api/auth/dev-login?telegram_id=800005")
    token1 = r1.json()["access_token"]

    response = await client.get(
        "/api/admin/escrow/deals",
        headers={"Authorization": f"Bearer {token1}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_escrow_resolve_requires_mod(client: AsyncClient):
    """Resolving a deal requires moderator access."""
    r1 = await client.post("/api/auth/dev-login?telegram_id=800006")
    token1 = r1.json()["access_token"]

    response = await client.post(
        "/api/escrow/deals/9999/resolve",
        json={"release_to": "seller", "note": "test"},
        headers={"Authorization": f"Bearer {token1}"},
    )
    assert response.status_code == 403
