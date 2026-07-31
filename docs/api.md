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

---

## Future Phase API Specification Placeholders
- `POST /api/v1/auth/login` - User authentication (Phase 2)
- `GET /api/v1/beds` - Bed status registry (Phase 2)
- `GET /api/v1/wards` - Ward capacity stats (Phase 2)
- `POST /api/v1/forecast/predict` - AI bed capacity predictions (Phase 3)
- `POST /api/v1/transfers/recommend` - Intelligent transfer solver (Phase 3)
