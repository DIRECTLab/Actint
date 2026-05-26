## Core Rules
- Install the backend package before running anything: `pip install -e ./actint-backend`
- Backend uses a `src/` layout. Always run via module path: `python -m backend...`
- Do not run files by path (imports will break): `python backend/...` is wrong
- Python 3.12 is required (see `actint-backend/pyproject.toml`)
- Backend (`actint-backend/`) and frontend (`frontend/`) are separate toolchains

## Setup
- Create env (example):
  - `conda create -n actint python=3.12 -y && conda activate actint`
- Install backend (editable):
  - `pip install -e ./actint-backend`

## Run Commands (Backend)
- Agent:
  - `python -m backend.agent.agent`
- Websocket server:
  - `python -m backend.transport.web_socket`
  - or: `uvicorn backend.transport.web_socket:app --host 0.0.0.0 --port 3050`
- Benchmarks:
  - `python -m backend.benchmarking.benchmark_agents --run-all-benchmarks`

## Run Commands (Frontend)
- `cd frontend && npm install && npm run dev`

## Runtime / Infra Gotchas
- Phoenix telemetry is expected by the agent:
  - Start separately: `python -m phoenix.server.main serve`
  - VS Code terminal is recommended (handles port forwarding)
- Some functionality depends on local data under `data/` and CSV assets under `data_collection/data/`
- Postgres is referenced via `psycopg`, but not automatically provisioned

## Architecture Notes
- Real code root: `actint-backend/src/backend/`
- Key areas:
  - `agent/` → LLM agent entrypoints and prompts
  - `transport/` → FastAPI + websocket / Socket.IO layer
  - `data_collection/`, `data_processing/` → AIS ingestion and querying
  - `benchmarking/` → simulations and evaluation (non-critical runtime path)

## Testing
- No central test runner config is defined
- Use `pytest` from repo root or `actint-backend/`
- Tests are scattered (e.g., `tests/`, `data_collection/testing/`) and may be incomplete
- Prefer running targeted test files directly

## Common Failure Modes
- Import errors → backend not installed in editable mode
- Module not found → running files directly instead of `-m`
- Agent appears idle → Phoenix server not running
