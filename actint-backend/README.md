# Backend Package — ACTINT

This directory contains the standalone Python backend package for the
ACTINT project.

## Overview

The backend is packaged as a Python project using `pyproject.toml`.

This package uses a `src/` layout, so backend modules should be run through
the package namespace after installation. Do not run backend files directly
by file path.

## Install

Create a Python 3.12 environment and install the package in editable mode.

From the `backend/` directory:

```bash
conda create -n actint python=3.12 -y
conda activate actint
cd backend
pip install -e .
```

You can also install it directly from the repository root:

```bash
conda create -n actint python=3.12 -y
conda activate actint
pip install -e ./actint-backend
```

## Usage

Run backend modules through the package namespace:

```bash
python -m backend.benchmarking.benchmark_agents --run-all-benchmarks
python -m backend.agent.agent
```

To run the websocket / LLM backend server:

```bash
python -m backend.transport.web_socket
```

If needed, you can also run the ASGI app with Uvicorn:

```bash
uvicorn backend.transport.web_socket:app --host 0.0.0.0 --port 3050
```

## Example Import

```python
from backend.mcp_servers.ais import ais_mcp_server
```

## Notes

- The backend package is independent from the frontend Next.js app in
  `frontend/`.
- Install the package before running modules so Python can resolve imports
  from the `backend` package correctly.
- Do not run backend modules by file path, for example:

  ```bash
  python src/backend/agent/agent.py
  ```

  Instead, use:

  ```bash
  python -m backend.agent.agent
  ```

- Package metadata and dependencies are defined in `pyproject.toml`.
- For development, use editable install with `pip install -e .`.
