# AI-Powered Hospital Bed Capacity Forecasting Dashboard & Intelligent Inter-Ward Transfer System

> **Cloud Database Architecture: Neon PostgreSQL + FastAPI + React SPA + Alembic Migrations**

[![FastAPI](https://img.shields.io/badge/FastAPI-0.110.0-009688?style=flat-square&logo=fastapi)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18.2.0-61DAFB?style=flat-square&logo=react)](https://reactjs.org/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.4.3-3178C6?style=flat-square&logo=typescript)](https://www.typescriptlang.org/)
[![Neon PostgreSQL](https://img.shields.io/badge/Neon_PostgreSQL-Cloud_DB-00E599?style=flat-square&logo=postgresql)](https://neon.tech/)
[![Alembic](https://img.shields.io/badge/Alembic-Migrations-646CFF?style=flat-square)](https://alembic.sqlalchemy.org/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=flat-square&logo=docker)](https://www.docker.com/)

---

## 📋 Project Overview

The **AI-Powered Hospital Bed Capacity Forecasting Dashboard & Intelligent Inter-Ward Transfer System** is an enterprise healthcare SaaS platform designed to optimize hospital bed occupancy, predict patient surge demands, and streamline patient transfers between hospital wards.

The backend connects directly to **Neon PostgreSQL** (cloud-hosted serverless PostgreSQL) with SSL support, SQLAlchemy ORM, and Alembic database migrations.

---

## 🏛️ System Architecture

```
                               ┌─────────────────────────────┐
                               │     React 18 + Vite SPA     │
                               │   (TypeScript + Tailwind)   │
                               └──────────────┬──────────────┘
                                              │ Axios / React Query
                                              ▼
                               ┌─────────────────────────────┐
                               │   FastAPI ASGI Server       │
                               │ (Python 3.11 + Pydantic v2) │
                               └──────────────┬──────────────┘
                                              │ SQLAlchemy ORM (SSL)
                                              ▼
                               ┌─────────────────────────────┐
                               │   Neon PostgreSQL (Cloud)   │
                               │     (?sslmode=require)      │
                               └─────────────────────────────┘
```

---

## 📁 Directory Structure

```text
hospital-bed-system/
├── client/                     # React Frontend Application (Vite + TS + Tailwind)
│   ├── src/                    # Components, Hooks, Context, Pages, Routes, Services
│   ├── .env                    # Frontend environment variables
│   └── Dockerfile              # Production container build
│
├── server/                     # FastAPI Backend Application
│   ├── alembic/                # Alembic database migration scripts & env.py
│   ├── app/
│   │   ├── api/                # API router & versioned endpoints
│   │   │   └── v1/
│   │   │       ├── endpoints/
│   │   │       │   └── health.py # Health Check Endpoint (GET /health)
│   │   │       └── router.py
│   │   ├── core/               # Application configuration & security
│   │   │   └── config.py
│   │   ├── database/           # Neon Database engine, session, Base & config
│   │   │   ├── config.py       # Dotenv DATABASE_URL loader
│   │   │   ├── database.py     # SQLAlchemy Engine, SessionLocal, Base & get_db
│   │   │   └── session.py      # Module export alias
│   │   ├── models/             # ORM Database Models (User model baseline)
│   │   ├── schemas/            # Pydantic validation schemas
│   │   └── main.py             # FastAPI App instance with lifespan DB verify & health
│   ├── .env                    # Backend environment variables (DATABASE_URL)
│   ├── .env.example            # Environment variables template
│   ├── alembic.ini             # Alembic migration configuration
│   ├── Dockerfile              # Python container setup
│   └── requirements.txt        # Python dependencies
│
├── docs/                       # Project documentation & OpenAPI references
├── .gitignore                  # Git ignore rules (.env, .venv, __pycache__, *.pyc)
├── docker-compose.yml          # Container orchestration (Client + Server)
└── README.md                   # Enterprise System Documentation
```

---

## 🐘 Neon PostgreSQL Cloud Setup

This project uses **Neon PostgreSQL** instead of a local PostgreSQL server. Follow these steps to set up your database:

### Step 1: Create a Neon Account
1. Visit [https://neon.tech](https://neon.tech) and sign up for a free account.
2. Sign in to your Neon Console.

### Step 2: Create a Project & Database
1. Click **"New Project"**.
2. Give your project a name (e.g., `hospital-bed-system`).
3. Select your preferred region (e.g., `US East (N. Virginia)`).
4. Neon will automatically create a default database named `neondb` and a database user (e.g., `neondb_owner`).

### Step 3: Copy Connection String
1. In your Neon Project Dashboard, navigate to **Connection Details**.
2. Select **Connection string** and ensure **Pooled connection** or **Direct connection** is chosen.
3. Copy the full connection URL. It will look like:
   ```text
   postgresql://neondb_owner:npg_xYz123AbCdEf@ep-sample-123456.us-east-2.aws.neon.tech/neondb?sslmode=require
   ```

### Step 4: Configure `DATABASE_URL` in `.env`
1. Open `server/.env` in your editor (or create it from `server/.env.example`).
2. Set the `DATABASE_URL` environment variable to your copied Neon connection string:
   ```env
   DATABASE_URL=postgresql://neondb_owner:YOUR_PASSWORD@ep-sample-123456.us-east-2.aws.neon.tech/neondb?sslmode=require
   ```
   > ⚠️ **Security Notice**: Never commit `server/.env` to source control. It is ignored by `.gitignore`.

---

## ⚙️ Environment Variables

### Backend (`server/.env`)
```env
DATABASE_URL=postgresql://neondb_owner:YOUR_ACTUAL_PASSWORD@YOUR_HOST.neon.tech/neondb?sslmode=require
SECRET_KEY=dev_secret_key_change_in_production_hospital_bed_system_987654321
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
CORS_ORIGINS=["http://localhost:3000","http://127.0.0.1:3000"]
```

### Frontend (`client/.env`)
```env
VITE_API_BASE_URL=http://localhost:8000/api/v1
```

---

## 🚀 Running the Application

### 1. Backend Setup & Startup (FastAPI)

```bash
# Navigate to server directory
cd server

# Create Python virtual environment
python -m venv venv

# Activate virtual environment
# Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# macOS / Linux:
# source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run FastAPI development server
uvicorn app.main:app --reload --port 8000
```

Verify backend health at: [http://localhost:8000/health](http://localhost:8000/health)  
Interactive Swagger API documentation: [http://localhost:8000/docs](http://localhost:8000/docs)

#### Health Check Response Format (GET `/health`):
```json
{
    "status": "healthy",
    "database": "connected",
    "service": "Hospital Bed Capacity Forecasting API",
    "version": "1.0.0"
}
```

---

### 2. Alembic Database Migrations

Alembic reads `DATABASE_URL` dynamically from `server/.env`.

```bash
# Navigate to server directory with activated venv
cd server

# Check current revision status
alembic current

# Create a new migration revision automatically from models
alembic revision --autogenerate -m "Initial schema setup"

# Apply migrations to Neon PostgreSQL
alembic upgrade head
```

---

### 3. Frontend Setup (React + Vite)

```bash
# Navigate to client directory
cd client

# Install npm dependencies
npm install

# Start Vite development server
npm run dev
```

Open application in browser: [http://localhost:3000](http://localhost:3000)

---

## 🐳 Docker Deployment

`docker-compose.yml` launches the React frontend and FastAPI backend containers. The backend connects directly to Neon cloud PostgreSQL.

```bash
# Build and start containers
docker-compose up --build -d

# View container logs
docker-compose logs -f

# Stop containers
docker-compose down
```

Services exposed:
- **Frontend Dashboard**: [http://localhost:3000](http://localhost:3000)
- **FastAPI Backend**: [http://localhost:8000](http://localhost:8000)
- **Swagger Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 📄 License
Distributed under the MIT License. See [LICENSE](LICENSE) for details.
