# pyrefly: ignore [missing-import]
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

import app.models  # Ensure models are loaded for table creation
from app.api.v1.router import api_router
from app.core.config import settings
from app.database.session import Base, engine, get_db

# Create database tables if they do not exist
try:
    Base.metadata.create_all(bind=engine)
except Exception as e:
    print(f"Database table creation notice: {e}")

# OpenAPI Metadata & Tags
tags_metadata = [
    {
        "name": "System Health",
        "description": "API health checks, system diagnostics, and live PostgreSQL ping monitoring.",
    },
    {
        "name": "Authentication & Authorization",
        "description": "JWT Register, Login, Token Refresh, User Profile (/me), and Logout endpoints.",
    },
    {
        "name": "Bed Capacity Forecasting",
        "description": "AI forecasting models reserved for future phase.",
    },
    {
        "name": "Inter-Ward Transfers",
        "description": "Intelligent transfer routing reserved for future phase.",
    },
]

from contextlib import asynccontextmanager
from app.services.scheduler import scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: start automated snapshot scheduler
    try:
        scheduler.start()
    except Exception as e:
        print(f"Scheduler startup notice: {e}")
    yield
    # Shutdown: stop scheduler cleanly
    try:
        scheduler.stop()
    except Exception as e:
        print(f"Scheduler shutdown notice: {e}")


app = FastAPI(
    title="Hospital Bed Capacity Forecasting API",
    version=settings.VERSION,
    description="""
### Enterprise Hospital Bed Capacity Forecasting & Intelligent Inter-Ward Transfer System

Production-Ready Foundation & JWT Authentication Engine (Phase 1 & Phase 2)
Providing scalable micro-architecture, database connection management, RBAC authorization, health check diagnostics, and OpenAPI schemas.
    """,
    openapi_tags=tags_metadata,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)


# Configure CORS Middleware
if settings.CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


# Direct root health endpoint with DB connection check
@app.get(
    "/health",
    tags=["System Health"],
    summary="Root Health Check",
    description="Direct root health endpoint with live PostgreSQL database connectivity check",
)
def root_health(db: Session = Depends(get_db)):
    db_status = "disconnected"
    try:
        db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        db_status = f"disconnected ({str(e)})"

    return {
        "status": "healthy" if db_status == "connected" else "degraded",
        "service": "Hospital Bed Capacity Forecasting API",
        "version": settings.VERSION,
        "database": db_status,
    }


# Root redirect to OpenAPI documentation
@app.get("/", include_in_schema=False)
def root_redirect():
    return RedirectResponse(url="/docs")


# Mount API v1 router
app.include_router(api_router, prefix=settings.API_V1_STR)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
