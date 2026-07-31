from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app.api.v1.router import api_router
from app.core.config import settings

# OpenAPI Metadata & Tags
tags_metadata = [
    {
        "name": "System Health",
        "description": "API health checks, system diagnostics, and readiness monitoring.",
    },
    {
        "name": "Bed Capacity Forecasting",
        "description": "Phase 1 Foundation Placeholder - AI forecasting models reserved for Phase 2.",
    },
    {
        "name": "Inter-Ward Transfers",
        "description": "Phase 1 Foundation Placeholder - Intelligent transfer routing reserved for Phase 2.",
    },
]

app = FastAPI(
    title="Hospital Bed Capacity Forecasting API",
    version=settings.VERSION,
    description="""
### Enterprise Hospital Bed Capacity Forecasting & Intelligent Inter-Ward Transfer System

Production-Ready Foundation (Phase 1)
Providing scalable micro-architecture, database connection management, health check diagnostics, and OpenAPI schemas.
    """,
    openapi_tags=tags_metadata,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
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

# Also expose direct root /health route for simple health checks
@app.get(
    "/health",
    tags=["System Health"],
    summary="Root Health Check",
    description="Direct root health endpoint",
)
def root_health():
    return {
        "status": "healthy",
        "service": "Hospital Bed Capacity Forecasting API",
        "version": settings.VERSION,
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
