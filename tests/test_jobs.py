from agentgate.jobs import run_all


async def test_all_jobs_complete():
    results = await run_all(
        n=20,
        limit=5,
        timeout=5.0,
        max_sleep=0.2,
    )
    assert len(results) == 20
    assert all(r["status"] == "done" for r in results)


async def test_timeouts_are_reported():
    results = await run_all(
        n=5,
        limit=5,
        timeout=0.05,
        max_sleep=1.0,
    )
    assert any(r["status"] == "timeout" for r in results)
