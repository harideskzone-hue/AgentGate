# AgentGate

AgentGate is an evaluation harness for testing and red-teaming AI agents against attack and benign scenarios.

## Prerequisites

- Python 3.12+ and [uv](https://github.com/astral-sh/uv)
- Docker (Docker Desktop, Colima, or OrbStack)

## Quickstart

### 1. Clone and Run with Docker Compose

```bash
git clone <your-repo> agentgate && cd agentgate
docker compose up -d --build
docker compose run --rm api uv run --no-dev alembic upgrade head
curl http://localhost:8000/health
```

The interactive API documentation is available at `http://localhost:8000/docs`.

### 2. Local Development

```bash
uv sync
uv run alembic upgrade head
uv run pytest -v
uv run ruff check .
```
