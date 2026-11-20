from httpx import ASGITransport, AsyncClient

from agentgate.api import app

SCENARIO = {
    "id": "t1",
    "type": "benign",
    "goal": "Resolve ticket number 42",
}


async def test_health(client):
    response = await client.get("/health")
    assert response.json() == {"status": "ok"}


async def test_create_and_fetch_run(client):
    response = await client.post(
        "/runs",
        json={"scenario": SCENARIO, "k": 3},
    )
    assert response.status_code == 201
    run_id = response.json()["run_id"]
    got = await client.get(f"/runs/{run_id}")
    assert got.status_code == 200
    assert got.json()["scenario_id"] == "t1"
    assert got.json()["status"] == "done"


async def test_k_too_large_rejected(client):
    response = await client.post(
        "/runs",
        json={"scenario": SCENARIO, "k": 100},
    )
    assert response.status_code == 422


async def test_get_run_not_found(client):
    response = await client.get("/runs/999")
    assert response.status_code == 404


async def test_run_survives_restart(client):
    response = await client.post(
        "/runs",
        json={"scenario": SCENARIO, "k": 2},
    )
    assert response.status_code == 201
    run_id = response.json()["run_id"]

    # Simulating a fresh client / new connection to the server
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as fresh_client:
        got = await fresh_client.get(f"/runs/{run_id}")
        assert got.status_code == 200
        assert got.json()["run_id"] == run_id
        assert got.json()["status"] == "done"
