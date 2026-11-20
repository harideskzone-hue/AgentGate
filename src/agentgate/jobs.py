import asyncio
import random


async def fake_job(
    job_id: int,
    max_sleep: float = 1.0,
) -> dict:
    await asyncio.sleep(random.uniform(0.1, max_sleep))
    return {
        "job_id": job_id,
        "status": "done",
    }


async def run_all(
    n: int,
    limit: int,
    timeout: float,
    max_sleep: float = 1.0,
) -> list[dict]:
    semaphore = asyncio.Semaphore(limit)

    async def guarded(job_id: int) -> dict:
        async with semaphore:
            try:
                return await asyncio.wait_for(
                    fake_job(job_id, max_sleep),
                    timeout=timeout,
                )
            except TimeoutError:
                return {
                    "job_id": job_id,
                    "status": "timeout",
                }

    results = await asyncio.gather(*(guarded(i) for i in range(n)))
    return results
