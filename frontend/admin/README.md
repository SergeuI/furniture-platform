# Furniture Platform Admin

React admin panel foundation for the Furniture Platform FastAPI backend.

## Run locally

```powershell
cd frontend/admin
npm install
npm run dev
```

The default backend URL is:

```text
http://127.0.0.1:8000
```

To override it, create `.env` from `.env.example` and change:

```text
VITE_API_BASE_URL=http://127.0.0.1:8000
```

## Backend requirements

Run the FastAPI backend on:

```text
http://127.0.0.1:8000
```

Required API endpoints:

```text
POST /auth/login
GET /auth/me
GET /project
GET /project/{project_id}
PUT /project/{project_id}
GET /project/{project_id}/history
POST /project/{project_id}/rollback/{version_id}
DELETE /project/{project_id}
```
