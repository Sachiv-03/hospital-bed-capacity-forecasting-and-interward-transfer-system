# Explainable AI Alerts for Hospital Bed Capacity Forecasting

## 1. Overview
The Explainable AI (XAI) Alert Engine provides transparent, deterministic, and traceable decision support for hospital administrators, bed managers, and nursing supervisors. Rather than presenting opaque risk scores, the engine evaluates real-world hospital telemetry—including live occupied beds, physical ward capacity, recent historical occupancy trajectories, and primary SARIMA time-series forecasts with 95% confidence intervals—to explain why an alert was triggered, which operational thresholds were met, and what administrative actions are recommended.

> **Operational Notice**: Configured thresholds are administrative demonstration settings. They must be reviewed and approved by authorized clinical and operational leadership before clinical deployment. The system does not make automated patient transfer decisions and does not claim clinical causation.

---

## 2. Reused Forecasting & Data Services
The engine directly integrates with existing project services without duplicating models or database infrastructure:
* **Time-Series Forecaster (`TimeSeriesForecaster`)**: Evaluates statsmodels SARIMAX (seasonal order `(1,0,0,7)` or fallback `(1,1,0)/(1,0,0)`) and exponential smoothing models.
* **Forecast Service (`ForecastService`)**: Reuses `generate_ward_forecast` and `get_ward_latest_forecast` to obtain point predictions and upper/lower bounds.
* **Historical Data Pipeline (`ForecastingDataPreparation`)**: Ingests historical daily snapshots, validates domain bounds (`0 <= occupied <= capacity`), and computes historical velocity across recent observation windows.
* **Database Models**: Extends `CapacityAlert` (`server/app/models/capacity_alert.py`) with structured `explanation_json`, `acknowledged_at`, and `acknowledged_by_id`.

---

## 3. Enabled Risk Rules

The engine evaluates deterministic rules across observed and forecasted signals:

| Rule Code | Rule Name | Evaluated Signal | Default Operational Threshold | Severity |
| :--- | :--- | :--- | :--- | :--- |
| `RULE_A_HIGH_FORECAST` | High Forecasted Occupancy | Projected occupancy % on forecast target date | `>= 85.0%` (`ALERT_HIGH_THRESHOLD`) | `WARNING` |
| `RULE_B_CRITICAL_FORECAST` | Critical Forecasted Occupancy | Projected occupancy % on forecast target date | `>= 95.0%` (`ALERT_CRITICAL_THRESHOLD`) | `CRITICAL` |
| `RULE_C_LOW_AVAILABILITY` | Low Bed Availability | Current available beds (`capacity - occupied`) | `<= 2 beds` (`ALERT_LOW_AVAILABILITY_THRESHOLD`) | `WARNING` |
| `RULE_D_RAPID_INCREASE` | Rapid Historical Occupancy Growth | Observed occupancy % change over recent window | `>= +15.0%` points over 3 days | `WARNING` |
| `RULE_E_CAPACITY_EXCEEDANCE` | Physical Capacity Exceedance | Projected occupied beds > physical capacity | `predicted_beds > capacity` | `CRITICAL` |
| `RULE_F_HIGH_UNCERTAINTY` | High Forecast Uncertainty | 95% prediction interval span (`upper - lower`) | `>= 25.0%` points (`ALERT_UNCERTAINTY_THRESHOLD`) | `INFO` |
| `RULE_G_INSUFFICIENT_DATA` | Insufficient / Invalid Data | Historical snapshots count or physical capacity | `< 7 days` or `capacity <= 0` | `INFO` / `CRITICAL` |

---

## 4. Threshold Configuration

All thresholds are centrally defined and configurable via environment variables and `server/app/core/config.py`:

```python
ALERT_MODERATE_THRESHOLD: float = 70.0
ALERT_HIGH_THRESHOLD: float = 85.0
ALERT_CRITICAL_THRESHOLD: float = 95.0
ALERT_LOW_AVAILABILITY_THRESHOLD: int = 2
ALERT_RAPID_INCREASE_THRESHOLD: float = 15.0  # Percentage point increase over recent window
ALERT_RAPID_INCREASE_DAYS: int = 3           # Days to measure recent occupancy velocity
ALERT_UNCERTAINTY_THRESHOLD: float = 25.0    # CI width (upper_bound - lower_bound %) indicating high uncertainty
ALERT_FORECAST_HORIZON_DAYS: int = 7         # Default forecast horizon evaluated for capacity risk
```

---

## 5. Risk Severity Precedence

Risk level is assigned deterministically without arbitrary black-box scoring:
1. `CRITICAL`: Triggered when projected occupied beds exceed physical capacity (`RULE_E`) or forecasted occupancy reaches `>= 95.0%` (`RULE_B`), or live occupancy reaches critical threshold.
2. `HIGH`: Triggered when forecasted occupancy reaches `>= 85.0%` (`RULE_A`), or live occupancy reaches high threshold.
3. `MODERATE`: Triggered when bed availability is low (`RULE_C`), rapid occupancy surge occurred (`RULE_D`), or high uncertainty exists (`RULE_F`).
4. `LOW`: Assigned when all metrics and forecasts are within normal boundaries.
5. `INSUFFICIENT_DATA`: Assigned when observations are insufficient (< 7 days) or physical capacity is invalid.

---

## 6. Structured Explanation Payload Schema

Each alert returned by `GET /api/v1/alerts`, `GET /api/v1/alerts/{id}`, or `POST /api/v1/alerts/evaluate` includes a comprehensive explanation:

```json
{
  "headline": "High Capacity Warning: ICU Approaches High Risk Threshold",
  "human_readable_explanation": "ICU has a physical capacity of 20 beds and currently has 17 occupied beds (85.0% occupancy). The existing SARIMA time-series forecast projects 18.2 occupied beds on 2026-08-11, corresponding to 91.0% occupancy with approximately 2 available bed(s) remaining. The 95% forecast prediction interval spans 82.5% to 94.0% (uncertainty span: 11.5%). Triggered risk rules: High Forecasted Occupancy (Predicted peak occupancy of 91.0% exceeds warning threshold); Low Bed Availability (Current available beds: 2).",
  "suggested_actions": [
    "Review scheduled admissions and planned discharges for 2026-08-11.",
    "Verify ward nursing and support staffing levels for ICU.",
    "Audit pending discharge clearances with clinical care teams.",
    "Confirm actual physical bed availability directly with ICU charge nurse."
  ],
  "triggered_rules": [
    {
      "rule_id": "RULE_A_HIGH_FORECAST",
      "rule_name": "High Forecasted Occupancy",
      "severity": "WARNING",
      "condition_met": "Predicted peak occupancy of 91.0% exceeds warning threshold (threshold: >= 85.0%)",
      "trigger_value": 91.0,
      "threshold_value": 85.0,
      "description": "Ward is projected to experience severe bed pressure requiring administrative review."
    }
  ],
  "evidence": {
    "hospital_id": 1,
    "hospital_name": "Apollo Medical Center",
    "ward_id": 2,
    "ward_name": "ICU",
    "ward_type": "ICU",
    "ward_capacity": 20,
    "current_occupied_beds": 17,
    "current_available_beds": 2,
    "current_occupancy_percentage": 85.0,
    "forecast_target_date": "2026-08-11",
    "forecast_horizon_days": 7,
    "predicted_occupied_beds": 18.2,
    "predicted_occupancy_percentage": 91.0,
    "predicted_available_beds": 1.8,
    "lower_bound_percentage": 82.5,
    "upper_bound_percentage": 94.0,
    "uncertainty_interval_width": 11.5,
    "historical_trend_percentage_change": 8.0,
    "historical_trend_days": 3,
    "time_to_threshold_days": 1,
    "time_to_threshold_date": "2026-08-11",
    "is_capacity_exceeded": false,
    "data_quality_notes": [],
    "model_used": "SARIMA",
    "evaluated_at": "2026-10-20T10:30:00Z"
  }
}
```

---

## 7. Alert Lifecycle, Deduplication & Acknowledgement

* **Strict Deduplication**: When evaluating a ward, if an `ACTIVE` or `ACKNOWLEDGED` alert for that ward and alert type exists, the system updates its trigger values, threshold, message, and `explanation_json` rather than creating duplicate records.
* **Auto-Resolution**: When live and forecasted metrics fall below all alert thresholds during evaluation, active alerts for that ward are transitioned to `RESOLVED` with `resolved_at = timestamp`.
* **Acknowledgement**: Hospital staff can acknowledge an open alert via `POST /api/v1/alerts/{alert_id}/acknowledge`. This records `acknowledged_at` and `acknowledged_by_id`.
* **Audit Trail**: Resolved and acknowledged alerts retain their complete historical explanation payload.

---

## 8. Multi-Hospital Security & Data Isolation
* Users can only access alerts and run risk evaluations for their authorized hospital (`current_user.hospital_id`).
* `SUPER_ADMIN` can access across hospitals by supplying `hospital_id`.
* Attempting cross-hospital access or querying wards outside the user's hospital returns HTTP `403 Forbidden`.
* Explanations and alerts use aggregated ward bed metrics only; no individual patient PHI is stored or transmitted in alert payloads.

---

## 9. Verification & Test Coverage
Comprehensive backend test suite `server/app/tests/test_explainable_alerts.py` validates all 26 operational scenarios:
* Low-risk baseline ward verification.
* Forecasted high and critical risk threshold exceedances.
* Low bed availability and capacity exceedance flags.
* Rapid observed growth velocity calculations.
* Missing dates and insufficient observation fallback handling.
* Zero/invalid physical capacity safeguards.
* High uncertainty interval detection.
* Exact match between explanation text, triggered rules, and input data.
* Deterministic consistency across identical inputs.
* Deduplication, acknowledgement, and resolution state machines.
* Hospital tenant isolation and cross-hospital ward access rejection.
* Regression testing across Auth, Forecasting, Ingestion, Occupancy, and Transfers.
