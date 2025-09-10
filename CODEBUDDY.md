# CodeBuddy Code Instructions

## Development Commands
for exposing problems, avoid try catch as much as possible

### Fullstack Development
- `pnpm run install:all`: Install all dependencies (frontend and backend)
- `pnpm run dev`: Run both frontend and backend development servers concurrently
- `pnpm run build`: Build both frontend and backend for production

### Backend (Python/FastAPI)
- `uv run uvicorn main:app --host 0.0.0.0 --port 14250 --reload`: Run backend server with auto-reload
- `uv sync --quiet`: Sync Python dependencies
- `black .`: Format Python code
- `ruff .`: Lint Python code

### Frontend (React/Vite)
- `pnpm dev`: Run frontend development server
- `pnpm build`: Build frontend for production

## Architecture Overview

### Fullstack Structure
- Monorepo with `backend/` (Python) and `frontend/` (React) directories
- Uses pnpm for Node.js package management and UV for Python dependency management

### Backend Architecture
- FastAPI application serving REST API and SSE streams
- SQLModel for database models (SQLite)
- Organized into:
  - `api.py`: Core API endpoints
  - `models.py`: Database models and Pydantic schemas
  - `data_management/`: Data processing and analysis services
  - `factors/`: Crypto analysis factor implementations
- Features:
  - Background task system for long-running crypto analysis
  - SSE for real-time task updates
  - Authentication system

### Frontend Architecture
- React application using Vite
- Key features:
  - Dynamic rendering based on backend factor metadata
  - Real-time updates via SSE
  - Theme support (light/dark mode)
- Structure:
  - `app/components/`: UI components
  - `app/services/`: API client services
  - `app/hooks/`: Custom React hooks

### Data Flow
1. Frontend submits analysis request via `/run` endpoint
2. Backend creates background task and returns task ID
3. Frontend subscribes to task updates via `/task/{id}/events` SSE stream
4. Backend processes crypto data using factors from `factors/` directory
5. Results stored in SQLite database and streamed to frontend