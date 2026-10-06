# Real Dataset Ingestion Guide

## Overview
This document details how the **Hospital Bed Capacity Forecasting and Inter-Ward Transfer System** ingests real-world synthetic healthcare datasets (Synthea) and custom CSV time-series into PostgreSQL for historical bed occupancy tracking and time-series forecasting.

---

## 1. Dataset Source & Location
- **Source**: Synthea open-source synthetic EHR dataset (`encounters.csv`, `organizations.csv`, `patients.csv`).
- **Workspace Location**: [`datasets/synthea/`](file:///d:/projects/hospital%20bed%20capacity%20forecasting%20and%20interward%20transfer%20system/datasets/synthea)

### Key Files Used:
1. `organizations.csv`: Real-world Massachusetts healthcare facilities (`NAME`, `ADDRESS`, `CITY`, `STATE`, `Id`).
2. `encounters.csv`: Clinical encounters (`START`, `STOP`, `PATIENT`, `ORGANIZATION`, `ENCOUNTERCLASS`, `DESCRIPTION`, `REASONDESCRIPTION`).
   - Filtered for **Inpatient** and **Emergency** admissions.

---

## 2. Database Schema Changes (Alembic Migration: `k1l2m3n4o5p6`)
To maintain strict separation between demo/simulated data and imported real data:
1. **`hospitals.external_hospital_id`**: Stores external hospital UUIDs (e.g. Synthea Organization ID).
2. **`wards.external_ward_id`**: Stores external ward identifiers.
3. **`occupancy_snapshots.data_source`**: Identifies data origin (`SYNTHEA`, `CSV_IMPORT`, `SIMULATED`).

---

## 3. Ingestion Methods

### Option A: Command Line Interface (CLI)
Run the dedicated runner script:
```powershell
cd server
venv\Scripts\python.exe scripts\import_synthea.py --limit-orgs 2 --start-year 2018 --end-year 2020
```

#### CLI Flags:
- `--hospital-id <id>`: (Optional) Target a specific existing hospital in the database instead of creating new Synthea hospitals.
- `--limit-orgs <n>`: Maximum number of organizations to register (default: 3).
- `--start-year <yyyy>`: Start year for encounter filtering (default: 2018).
- `--end-year <yyyy>`: End year for encounter filtering (default: 2020).

### Option B: FastAPI REST Endpoints

#### 1. Ingest Synthea Encounters:
```http
POST /api/v1/ingestion/import/synthea?start_year=2018&end_year=2020&create_events=true
Authorization: Bearer <ADMIN_OR_SUPER_ADMIN_TOKEN>
```

#### 2. Ingest Custom CSV Time-Series:
```http
POST /api/v1/ingestion/import/csv
Authorization: Bearer <ADMIN_OR_SUPER_ADMIN_TOKEN>
Content-Type: multipart/form-data

file: <your_file.csv>
hospital_id: 1
ward_id: 2
```
*Expected CSV columns: `date` (or `snapshot_time`), `occupied_beds`, `total_beds`.*

---

## 4. Verification & Forecasting Integration

Ingesting the Synthea dataset creates **848+ continuous days** of daily snapshots across wards:
- **Emergency Ward**: 20 beds
- **Inpatient Medical Ward**: 30 beds
- **Intensive Care Unit (ICU)**: 12 beds

### Verify Ward Forecast Generation:
```powershell
cd server
venv\Scripts\python.exe -c "
from app.database.session import SessionLocal
from app.services.forecasting.forecast_service import ForecastService

db = SessionLocal()
fc = ForecastService.get_ward_latest_forecast(db=db, ward_id=21, horizon=7)
print('Forecast Status:', fc['status'])
print('Model:', fc['model'], fc['model_version'])
print('Forecast Series:', fc['forecasts'])
db.close()
"
```
Output:
- Status: `SUCCESS`
- Model: `SARIMA 1.0`
- Horizons: 1-day, 3-day, 7-day predictions with upper and lower confidence intervals and capacity risk levels (`NORMAL`, `WARNING`, `HIGH`, `CRITICAL`).
