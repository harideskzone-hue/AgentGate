from typing import Annotated

import structlog
from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from agentgate.db import get_session
from agentgate.jobs import run_all
from agentgate.logging_setup import configure_logging, log
from agentgate.models import Scenario
from agentgate.tables import RunRow, ScenarioRow

configure_logging()

app = FastAPI(title="AgentGate")


class RunRequest(BaseModel):
    scenario: Scenario
    k: int = Field(default=1, ge=1, le=20)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/runs", status_code=201)
async def create_run(
    req: RunRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    s = req.scenario
    if await session.get(ScenarioRow, s.id) is None:
        session.add(
            ScenarioRow(
                id=s.id,
                type=s.type.value,
                goal=s.goal,
                max_steps=s.max_steps,
                tags=s.tags,
            )
        )
        await session.flush()
    run = RunRow(scenario_id=s.id, status="running")
    session.add(run)
    await session.commit()

    structlog.contextvars.bind_contextvars(run_id=run.id, scenario_id=s.id)
    log.info("run_started", k=req.k)

    results = await run_all(n=req.k, limit=5, timeout=3.0)

    run.results = results
    run.status = "done"
    await session.commit()

    log.info(
        "run_finished",
        status=run.status,
        timeouts=sum(r["status"] == "timeout" for r in results),
    )
    structlog.contextvars.clear_contextvars()

    return {
        "run_id": run.id,
        "scenario_id": s.id,
        "status": run.status,
        "results": results,
    }


@app.get("/runs/{run_id}")
async def get_run(
    run_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    run = await session.get(RunRow, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return {
        "run_id": run.id,
        "scenario_id": run.scenario_id,
        "status": run.status,
        "results": run.results,
    }
