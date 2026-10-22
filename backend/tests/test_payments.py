import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_deposit_creation_requires_auth(client: AsyncClient):
    """Creating a deposit without auth should fail."""
    response = await client.post("/api/payments/nowpayments/create", json={
        "amount": 100, "pay_currency": "btc"
    })
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_deposit_minimum_enforced(client: AsyncClient):
    """Deposits under $10 should be rejected."""
    login_resp = await client.post("/api/auth/dev-login?telegram_id=700001")
    token = login_resp.json()["access_token"]

    response = await client.post(
        "/api/payments/nowpayments/create",
        json={"amount": 5, "pay_currency": "btc"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 400  # minimum is $10


@pytest.mark.asyncio
async def test_webhook_signature_required(client: AsyncClient):
    """Webhook without signature should be rejected."""
    response = await client.post("/api/payments/nowpayments/webhook", json={})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_deposit_list_requires_auth(client: AsyncClient):
    response = await client.get("/api/payments/nowpayments/deposits")
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_membership_upgrade_removed(client: AsyncClient):
    """The $50 membership upgrade was superseded by the $80 premium purchase."""
    login_resp = await client.post("/api/auth/dev-login?telegram_id=700002")
    token = login_resp.json()["access_token"]

    response = await client.post(
        "/api/payments/membership/upgrade",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 404
