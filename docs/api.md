# API Documentation - Phase 1 Foundation

## Base URLs
- Local Development: `http://localhost:8000/api/v1`
- Interactive Swagger UI: `http://localhost:8000/docs`
- ReDoc UI: `http://localhost:8000/redoc`

---

## Endpoints Summary

### 1. Root Health Check
- **URL**: `/health`
- **Method**: `GET`
- **Description**: Returns root system status.
- **Response Format**: `application/json`
- **Response Body**:
```json
{
  "status": "healthy",
  "service": "Hospital Bed Capacity Forecasting API",
  "version": "1.0.0"
}
```

### 2. API v1 Health Check
- **URL**: `/api/v1/health`
- **Method**: `GET`
- **Description**: Versioned health monitoring route.
- **Response Body**:
```json
{
  "status": "healthy",
  "service": "Hospital Bed Capacity Forecasting API",
  "version": "1.0.0"
}
```

## Capacity Alerts & Explainable AI Endpoints
- `GET /api/v1/alerts` - List active, acknowledged, and resolved capacity alerts with tenant isolation and filter parameters (`hospital_id`, `ward_id`, `status`, `severity`).
- `GET /api/v1/alerts/{alert_id}` - Retrieve detailed alert evidence, triggered rules, and administrative action checklist.
- `GET /api/v1/alerts/{alert_id}/explanation` - Retrieve complete explainable decision-support payload and confidence intervals.
- `POST /api/v1/alerts/{alert_id}/acknowledge` - Acknowledge active capacity alert with user attribution and timestamp.
- `POST /api/v1/alerts/{alert_id}/resolve` - Manually resolve active/acknowledged capacity alert.
- `POST /api/v1/alerts/evaluate` - Trigger on-demand explainable risk evaluation across hospital wards using live metrics and SARIMA forecasts.

---

## Active Service Endpoints Summary
- `POST /api/v1/auth/login` - User authentication & JWT issuance
- `GET /api/v1/hospitals` - Multi-hospital registry
- `GET /api/v1/wards` - Ward capacity registry
- `GET /api/v1/beds` - Bed occupancy registry
- `GET /api/v1/wards/{ward_id}/forecast` - AI SARIMA 1-day, 3-day, 7-day bed capacity forecasts
- `GET /api/v1/hospitals/{hospital_id}/forecast` - Hospital-wide aggregate capacity projection
- `GET /api/v1/transfers/recommendations` - Inter-ward transfer decision-support recommendations
- `POST /api/v1/transfers/recommendations/patient-destination` - Phase 11 explainable destination ward recommendations for patient transfers with live capacity & SARIMA forecasts
- `GET /api/v1/transfers/patient-transfers/{transfer_id}/recommendations` - Phase 11 explainable destination ward recommendations for an existing patient transfer request
- `POST /api/v1/ingestion/events` - Bed state transition telemetry ingestion

