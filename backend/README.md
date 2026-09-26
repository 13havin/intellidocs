# IntelliDocs Backend

FastAPI backend for IntelliDocs, a document and research workspace under active development. The current API provides a health check, application metadata, and a prototype user creation endpoint.

## Tech stack

- **FastAPI** for routing and API documentation
- **Uvicorn** for serving the application
- **Pydantic** for request and response validation, including email validation
- **pytest and HTTPX** for API tests

## Local setup

You need Python with `pip` and `venv` available. The repository does not currently pin a Python version or dependency versions.

From the repository root, enter the backend directory:

```sh
cd backend
python -m venv .venv
```

Activate the virtual environment:

**Windows PowerShell**

```powershell
.\.venv\Scripts\Activate.ps1
```

**macOS / Linux**

```sh
source .venv/bin/activate
```

On systems where Python is available as `python3`, use `python3 -m venv .venv` to create the environment.

Install dependencies and start the development server from `backend/`:

```sh
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

The API runs at <http://127.0.0.1:8000>. The `--reload` option restarts the server when source files change and is intended for local development.

### Configuration

No environment variables, database, or external services are required by the current application. `.env` is ignored by Git, but application code does not currently load or use it.

## API

- [Swagger UI](http://127.0.0.1:8000/docs) — interactive API documentation
- [ReDoc](http://127.0.0.1:8000/redoc) — reference documentation
- [OpenAPI schema](http://127.0.0.1:8000/openapi.json)

These links are available while the server is running.

| Method | Endpoint | Description | Success status |
| --- | --- | --- | --- |
| `GET` | `/health/` | Returns `{"status": "healthy"}` | `200` |
| `GET` | `/api/v1/info/` | Returns `{"name": "IntelliDocs", "version": "0.1.0"}` | `200` |
| `POST` | `/api/v1/users/` | Validates a name and email, then returns a prototype user response | `201` |

Use the trailing slashes shown above to avoid redirects.

### Create a user

Send a JSON request to `POST /api/v1/users/` with `Content-Type: application/json`:

```json
{
  "name": "Alex",
  "email": "alex@example.com"
}
```

Example using PowerShell:

```powershell
Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8000/api/v1/users/" `
  -ContentType "application/json" `
  -Body '{"name":"Alex","email":"alex@example.com"}'
```

Response (`201 Created`):

```json
{
  "id": 1,
  "name": "Alex",
  "email": "alex@example.com"
}
```

Both fields are required, and `email` must be a valid email address. Invalid requests return `422 Unprocessable Entity`.

**Current limitation:** this endpoint always returns `id: 1` and does not store a user. Authentication, duplicate email checks, and persistent user accounts are not implemented.

## Tests

With dependencies installed and the virtual environment active, run from `backend/`:

```sh
python -m pytest
```

The tests use FastAPI's `TestClient`; a running server is not required. Current coverage includes health and metadata responses, a valid user creation request, and rejection of an invalid email address.

## Project structure

```text
backend/
├── app/
│   ├── main.py          # FastAPI application and router registration
│   ├── routers/
│   │   ├── health.py    # Health check
│   │   ├── info.py      # Application metadata
│   │   └── users.py     # Prototype user creation
│   └── schemas/
│       ├── info.py      # Metadata response model
│       └── users.py     # User request and response models
├── tests/              # API tests
├── requirements.txt    # Runtime and test dependencies
└── README.md
```

## Planned capabilities

The project is intended to grow to support persistent user accounts, workspaces, document management, search, and AI-powered document analysis. These capabilities are not part of the current implementation.
