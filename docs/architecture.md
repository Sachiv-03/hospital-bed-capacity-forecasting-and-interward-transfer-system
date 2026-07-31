# Enterprise Architecture Document

## System Overview
The **AI-Powered Hospital Bed Capacity Forecasting Dashboard & Intelligent Inter-Ward Transfer System** is an enterprise-grade healthcare SaaS platform.

Phase 1 establishes a decoupled, modular multi-tier architecture:

```
[ React + Vite + TypeScript (Client) ] 
                 │
                 ▼ (HTTP / REST API via Axios & React Query)
[ FastAPI Backend (ASGI Server - Uvicorn) ]
                 │
                 ▼ (Dependency Injection - get_db)
[ SQLAlchemy ORM Layer & Connection Pool ]
                 │
                 ▼ (TCP / PostgreSQL Driver)
[ PostgreSQL Database (hospital_db) ]
```

## Layer Separation & Design Patterns

### 1. Presentation Layer (`client/`)
- **Vite + React 18**: Fast compilation, HMR, and TypeScript safety.
- **Tailwind CSS & Utility Functions**: Responsive, accessible healthcare UI with dark/light themes.
- **React Router v6**: Single Page Application (SPA) routing.
- **TanStack Query (React Query)**: Caching, background updates, and state management for API calls.

### 2. API & Routing Layer (`server/app/api/`)
- **FastAPI**: Asynchronous Python framework with automatic OpenAPI spec generation.
- **Health Check Router**: Independent monitoring endpoint (`GET /health`).
- **CORS Middleware**: Domain restriction and security header configuration.

### 3. Business & Core Configuration (`server/app/core/`)
- **Pydantic Settings**: Strongly-typed environment configuration validation from `.env`.

### 4. Persistence Layer (`server/app/database/`)
- **SQLAlchemy 2.0 ORM**: Engine initialization, connection pooling with `pool_pre_ping=True`, and session management (`SessionLocal`).
- **Alembic**: Prepared for database schema migration tracking.

### 5. Infrastructure & Containerization (`docker/`, `docker-compose.yml`)
- Containerized service orchestration for database, backend API, and web frontend with bridge networking and health check dependencies.
