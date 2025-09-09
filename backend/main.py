from __future__ import annotations
import logging
import warnings
from typing import List
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from typing import Dict, List
from fastapi.middleware.cors import CORSMiddleware
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from models import RunRequest, RunResponse, TaskResult, Message, AuthRequest, AuthResponse, create_db_and_tables, User, get_session
from sqlmodel import select
from api import (
    read_root, run_analysis, get_task_status, get_latest_results, list_all_tasks,
    stop_analysis, login_user
)
from factors import list_factors

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Suppress warnings
warnings.filterwarnings('ignore')

app = FastAPI(title="Crypto Analysis")

# Initialize database
create_db_and_tables()
logger.info("Database initialized successfully")

def create_admin_user():
    """Create admin user from environment variables if provided"""
    admin_username = os.getenv('ADMIN_USERNAME')
    admin_email = os.getenv('ADMIN_EMAIL')
    
    if admin_username and admin_email:
        try:
            with next(get_session()) as session:
                # Check if admin user already exists
                statement = select(User).where(
                    User.name == admin_username,
                    User.email == admin_email
                )
                existing_user = session.exec(statement).first()
                
                if not existing_user:
                    # Create new admin user
                    admin_user = User(name=admin_username, email=admin_email)
                    session.add(admin_user)
                    session.commit()
                    logger.info(f"Admin user created: {admin_username} ({admin_email})")
                else:
                    logger.info(f"Admin user already exists: {admin_username} ({admin_email})")
        except Exception as e:
            logger.error(f"Failed to create admin user: {e}")
    else:
        logger.info("No admin user credentials provided in environment variables")

# Create admin user if credentials are provided
create_admin_user()

# CORS configuration
origins = [
    "http://localhost:14245",
    "https://btc.subx.fun",
    "http://127.0.0.1:14245",
]

# Allow all origins in development
if os.getenv("ENVIRONMENT") == "development":
    origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files if they exist (for production)
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    # Mount specific static folders used by the SPA
    assets_dir = os.path.join(static_dir, "assets")
    icons_dir = os.path.join(static_dir, "icons")
    if os.path.isdir(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")
    if os.path.isdir(icons_dir):
        app.mount("/icons", StaticFiles(directory=icons_dir), name="icons")

    # Backward compatible mount (optional)
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    # Direct file endpoints for PWA files
    @app.get("/manifest.json", include_in_schema=False)
    async def serve_manifest():
        path = os.path.join(static_dir, "manifest.json")
        if os.path.isfile(path):
            return FileResponse(path)
        return {"detail": "manifest.json not found"}

    @app.get("/sw.js", include_in_schema=False)
    async def serve_sw():
        path = os.path.join(static_dir, "sw.js")
        if os.path.isfile(path):
            return FileResponse(path)
        return {"detail": "sw.js not found"}

    @app.get("/favicon.ico", include_in_schema=False)
    async def serve_favicon():
        path = os.path.join(static_dir, "favicon.ico")
        if os.path.isfile(path):
            return FileResponse(path)
        return {"detail": "favicon.ico not found"}

# Explicit root route: return index.html
@app.get("/", include_in_schema=False)
async def root_index():
    if os.path.exists(static_dir):
        index_path = os.path.join(static_dir, "index.html")
        if os.path.isfile(index_path):
            return FileResponse(index_path)
    return {"message": "Crypto Analysis API", "docs": "/docs"}


@app.post("/run", response_model=RunResponse)
def run(request: RunRequest) -> RunResponse:
    return run_analysis(request)


@app.get("/task/{task_id}", response_model=TaskResult)
def get_task(task_id: str) -> TaskResult:
    return get_task_status(task_id)


@app.post("/task/{task_id}/stop", response_model=TaskResult)
def stop_task(task_id: str) -> TaskResult:
    return stop_analysis(task_id)


@app.get("/results", response_model=TaskResult | Message)
def get_results():
    return get_latest_results()


@app.get("/tasks", response_model=List[TaskResult])
def list_tasks() -> List[TaskResult]:
    return list_all_tasks()


@app.get("/factors")
def get_factors() -> Dict[str, object]:
    """Return factor metadata for frontend dynamic rendering"""
    factors = list_factors()
    # Normalize to simple JSON metadata
    items = []
    for f in factors:
        items.append({
            "id": f.id,
            "name": f.name,
            "description": f.description,
            "columns": f.columns,
        })
    return {"items": items}

# Authentication routes
@app.post("/api/auth/login", response_model=AuthResponse)
def login(request: AuthRequest) -> AuthResponse:
    """User login/register with username and email"""
    return login_user(request)


# Serve frontend for production
@app.get("/{full_path:path}")
async def serve_frontend(full_path: str):
    """Serve frontend files for production"""
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    
    # If static directory doesn't exist, return API info
    if not os.path.exists(static_dir):
        return {"message": "Crypto Analysis API", "docs": "/docs"}
    
    # Handle root path - serve index.html
    if full_path == "":
        index_path = os.path.join(static_dir, "index.html")
        if os.path.isfile(index_path):
            return FileResponse(index_path)
        # Fallback to API info if frontend not built
        return {"message": "Crypto Analysis API", "docs": "/docs"}
    
    # Try to serve the requested file
    file_path = os.path.join(static_dir, full_path)
    if os.path.isfile(file_path):
        return FileResponse(file_path)
    
    # For SPA routing, serve index.html for non-API routes
    if not full_path.startswith("api/") and not full_path.startswith("docs"):
        index_path = os.path.join(static_dir, "index.html")
        if os.path.isfile(index_path):
            return FileResponse(index_path)
    
    # Return 404 for API routes or missing files
    return {"detail": "Not found"}