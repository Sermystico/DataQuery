# DataQuery — AI-Powered Analytics Assistant

DataQuery is an analytics assistant that translates natural language business questions into safe, read-only SQL queries against an e-commerce PostgreSQL database, executes them, and returns tabular results with plain-English explanations.

---

## Prerequisites (Verified)

- **Python**: 3.12 (`CPython 3.12.15` managed via `uv`)
- **Node.js**: `v24.21.0` (npm `11.19.0`)
- **Docker**: `Docker version 29.8.0`, `Docker Compose v5.5.1`
- **Git**: `git version 2.55.0.windows.5`

---

## Verified Commands & Quickstart

### 1. Environment Configuration
Copy `.env.example` to `.env` (gitignored):
```bash
cp .env.example .env
```
> **Port Note**: If a native PostgreSQL instance is already running on port `5432` on your machine, set `DB_PORT=5434` in `.env`. The `docker-compose.yml` service reads `DB_PORT` dynamically.

### 2. Database Service
Start the PostgreSQL 16 container:
```bash
docker compose up -d db
```

Verify container health and connectivity:
```bash
# Verify health status
docker ps --filter "name=dataquery-db"

# Run Python connectivity check
./backend/.venv/Scripts/python.exe backend/scripts/check_db.py
```

### 3. Backend (FastAPI + Python 3.12)
Create virtual environment and install dependencies:
```bash
uv venv backend/.venv --python 3.12
uv pip install -r backend/requirements-dev.txt
```

Run test suite and linter:
```bash
# Run pytest (markers: unit, integration, security, evaluation)
./backend/.venv/Scripts/pytest.exe

# Run ruff check
./backend/.venv/Scripts/ruff.exe check .
```

### 4. Frontend (React + TypeScript + Vite)
Build frontend production bundle:
```bash
cd frontend
npm install
npm run build
```

---

## Repository Layout

```
DataQuery/
├── docs/                 # Phase 0 Architecture, ADRs, Security, API Contract, Eval Plan
├── backend/
│   ├── app/              # FastAPI application (empty packages in Phase 1)
│   ├── migrations/       # Database migrations
│   ├── seed/             # Seed datasets
│   ├── scripts/          # Database utility scripts
│   ├── tests/            # Pytest test suite (unit, integration, security, evaluation)
│   ├── requirements.txt
│   └── requirements-dev.txt
├── frontend/             # Vite + React + TypeScript UI
├── eval/                 # Evaluation harness & datasets
├── docker-compose.yml    # PostgreSQL 16 container definition
└── README.md
```
