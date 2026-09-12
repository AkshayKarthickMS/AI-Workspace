# AegisOS API

## Local setup

From `apps/api` with Python 3.12 installed:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000
```

The service health endpoint is available at `http://localhost:8000/health`.
