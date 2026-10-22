import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_referral_stats_requires_auth(client: AsyncClient):
    response = await client.get("/api/users/me/referrals")
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_referral_stats_returns_structure(client: AsyncClient):
    login_resp = await client.post("/api/auth/dev-login?telegram_id=700003")
    token = login_resp.json()["access_token"]

    response = await client.get(
        "/api/users/me/referrals",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "referral_code" in data
    assert "referral_link" in data
    assert "referral_earnings" in data
    assert "direct_referrals" in data
    assert "indirect_referrals" in data
    assert "level1_percent" in data
    assert "level2_percent" in data
    assert "recent_commissions" in data
