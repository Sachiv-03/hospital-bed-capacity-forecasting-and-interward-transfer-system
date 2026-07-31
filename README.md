# AI-Powered Hospital Bed Capacity Forecasting Dashboard & Intelligent Inter-Ward Transfer System

> **Phase 1: Production-Ready Project Foundation & Architecture**

[![FastAPI](https://img.shields.io/badge/FastAPI-0.110.0-009688?style=flat-square&logo=fastapi)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18.2.0-61DAFB?style=flat-square&logo=react)](https://reactjs.org/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.4.3-3178C6?style=flat-square&logo=typescript)](https://www.typescriptlang.org/)
[![Vite](https://img.shields.io/badge/Vite-5.2.0-646CFF?style=flat-square&logo=vite)](https://vitejs.dev/)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-3.4.1-38B2AC?style=flat-square&logo=tailwind-css)](https://tailwindcss.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16.0-4169E1?style=flat-square&logo=postgresql)](https://www.postgresql.org/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=flat-square&logo=docker)](https://www.docker.com/)

---

## 📋 Project Overview

The **AI-Powered Hospital Bed Capacity Forecasting Dashboard & Intelligent Inter-Ward Transfer System** is an enterprise healthcare SaaS platform designed to optimize hospital bed occupancy, predict patient surge demands, and streamline patient transfers between hospital wards.

Phase 1 establishes a clean, scalable, production-ready enterprise foundation. It delivers the complete project structure, decoupled frontend and backend architectures, database connectivity management, environment configuration, health monitoring APIs, dark/light themed SaaS layout, and Docker containerization.

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
                                              │ SQLAlchemy ORM
                                              ▼
                               ┌─────────────────────────────┐
                               │    PostgreSQL Database      │
                               │        (hospital_db)        │
                               └─────────────────────────────┘
```

---

## 📁 Directory Structure

```text
hospital-bed-system/
├── client/                     # React Frontend Application (Vite + TS + Tailwind)
│   ├── public/                 # Static assets & favicon
│   ├── src/
│   │   ├── assets/             # Images and branding media
│   │   ├── components/         # Reusable UI components
│   │   ├── context/            # React context providers
│   │   ├── hooks/              # Custom React hooks
│   │   ├── layouts/            # Dashboard Base Layout (Sidebar, Navbar, Footer)
│   │   ├── pages/              # Page views (Dashboard, Patients, Beds, Wards, etc.)
│   │   ├── routes/             # React Router navigation configuration
│   │   ├── services/           # Axios API client & health queries
│   │   ├── types/              # TypeScript definitions & interfaces
│   │   ├── utils/              # Helper utilities (cn class merger)
│   │   ├── App.tsx             # Root component with Providers
│   │   ├── index.css           # Tailwind CSS directives & HSL themes
│   │   └── main.tsx            # React application DOM entrypoint
│   ├── .env                    # Frontend environment variables
│   ├── Dockerfile              # Multi-stage production container build
│   ├── package.json            # Node dependencies
│   ├── tailwind.config.js      # Healthcare SaaS color palette
│   └── vite.config.ts          # Vite bundler & proxy configuration
│
├── server/                     # FastAPI Backend Application
│   ├── app/
│   │   ├── api/                # API router & versioned endpoints
│   │   │   └── v1/
│   │   │       ├── endpoints/
│   │   │       │   └── health.py  # Health Check Endpoint (GET /health)
│   │   │       └── router.py
│   │   ├── core/               # App configuration & settings
│   │   │   └── config.py
│   │   ├── database/           # SQLAlchemy Engine, SessionLocal, Base & get_db
│   │   │   └── session.py
│   │   ├── middleware/         # Custom ASGI middleware
│   │   ├── models/             # ORM Database Models (Reserved for Phase 2)
│   │   ├── schemas/            # Pydantic Schemas (Reserved for Phase 2)
│   │   ├── services/           # Business logic layer
│   │   ├── ml/                 # AI Forecasting models directory
│   │   ├── utils/              # Helper functions
│   │   ├── tests/              # Pytest test suite (Health endpoint test)
│   │   └── main.py             # FastAPI App instance with CORS & Swagger
│   ├── .env                    # Backend environment variables
│   ├── Dockerfile              # Python 3.11 container setup
│   ├── main.py                 # Direct uvicorn launcher script
│   ├── pyproject.toml          # Black, isort, and pytest config
│   └── requirements.txt        # Python dependencies
│
├── docker/
│   └── postgres/
│       └── init.sql            # PostgreSQL database & user initialization script
│
├── docs/                       # Project documentation & OpenAPI references
│   ├── api.md
│   └── architecture.md
│
├── datasets/                   # Raw & processed hospital bed capacity datasets
│   └── .gitkeep
│
├── .gitignore                  # Git ignore rules for Python, Node, & Docker
├── .vscode/                    # VS Code editor settings & extension recommendations
├── docker-compose.yml          # Container orchestration (Client + Server + PostgreSQL)
├── LICENSE                     # MIT License
└── README.md                   # Enterprise System Documentation
```

---

## 🛠️ Technology Stack

### Frontend
- **Framework**: React 18 + TypeScript
- **Build Tool**: Vite 5
- **Styling**: Tailwind CSS (Custom Healthcare Color Palette)
- **Routing**: React Router v6
- **State Management**: TanStack Query v5 (React Query)
- **HTTP Client**: Axios
- **Icons**: Lucide React
- **Data Visualization**: Recharts

### Backend
- **Framework**: FastAPI (Asynchronous Python 3.11)
- **ASGI Server**: Uvicorn
- **ORM**: SQLAlchemy 2.0
- **Migrations**: Alembic
- **Validation**: Pydantic v2 & Pydantic Settings
- **Testing**: Pytest & HTTPX
- **Code Quality**: Black & isort

### Database & DevOps
- **Database**: PostgreSQL 16
- **Containerization**: Docker & Docker Compose
- **Configuration**: Environment variables (`.env`)

---

## ⚙️ Environment Variables

### Backend (`server/.env`)
```env
DATABASE_URL=postgresql://hospital_user:hospital_password@localhost:5432/hospital_db
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

## 🚀 Getting Started & Local Setup

### Prerequisites
- Node.js (v18+ or v20+) & npm
- Python 3.11+
- PostgreSQL 16 (or Docker)

---

### 1. Database Setup (PostgreSQL)

If using a local PostgreSQL installation, run the following SQL commands to create the database and user:

```sql
CREATE DATABASE hospital_db;
CREATE USER hospital_user WITH PASSWORD 'hospital_password';
GRANT ALL PRIVILEGES ON DATABASE hospital_db TO hospital_user;
```

---

### 2. Backend Setup (FastAPI)

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

---

### 3. Frontend Setup (React + Vite)

```bash
# Open a new terminal and navigate to client directory
cd client

# Install npm dependencies
npm install

# Start Vite development server
npm run dev
```

Open application in browser: [http://localhost:3000](http://localhost:3000)

---

## 🐳 Docker Deployment

To launch the complete platform (PostgreSQL, FastAPI Backend, React Frontend) in containerized mode:

```bash
# Build and start containers in background
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
- **PostgreSQL Database**: `localhost:5432`

---

## 🧪 Testing & Verification

```bash
# Run backend pytest suite
cd server
pytest

# Code formatting checks
black --check .
isort --check .

# Frontend type checking & linting
cd ../client
npm run build
```

---

## 🗺️ Project Roadmap

- [x] **Phase 1: Project Foundation & Architecture** (Current)
  - Complete project setup, FastAPI backend, React Vite frontend, PostgreSQL configuration, Docker support, Base SaaS layout, and Health check API.
- [ ] **Phase 2: Database Schema & Authentication**
  - User roles (Doctor, Nurse, Admin), Patient & Ward ORM models, JWT auth flow.
- [ ] **Phase 3: Real-Time Bed & Ward Management**
  - Ward capacity tracking, bed status CRUD, patient admission & discharge pipelines.
- [ ] **Phase 4: AI Bed Capacity Forecasting & Inter-Ward Transfers**
  - Machine learning occupancy forecasting models (LSTM/Prophet), intelligent ward transfer optimization algorithms.

---

## 📄 License
Distributed under the MIT License. See [LICENSE](LICENSE) for details.
