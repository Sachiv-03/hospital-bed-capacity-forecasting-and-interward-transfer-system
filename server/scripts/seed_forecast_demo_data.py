"""
Seed Demo Data for Forecast Page & Inter-Ward Capacity Management
Generates realistic, rich data for final demo:
- Live bed occupancy in Wards 29, 30, 31 (Apollo Medical Center)
- 30-day realistic historical occupancy snapshots
- 7-day forward SARIMA capacity forecasts with confidence intervals & risk levels
- Explainable AI Capacity Alerts (Rules A, B, C, G)
- Active Inter-Ward Transfer Recommendations
"""
import sys
import os
from datetime import datetime, date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database.database import SessionLocal
from app.models.hospital import Hospital
from app.models.ward import Ward, WardType, WardStatus
from app.models.bed import Bed, BedStatus, BedType
from app.models.occupancy_snapshot import OccupancySnapshot
from app.models.bed_capacity_forecast import BedCapacityForecast, RiskLevel
from app.models.capacity_alert import CapacityAlert, AlertType, AlertSeverity, AlertStatus
from app.models.transfer_recommendation import TransferRecommendation, RecommendationStatus, RecommendationPriority
from app.models.ward_transfer_rule import WardTransferRule

def seed_demo_forecast_data():
    db = SessionLocal()
    try:
        print("=" * 60)
        print("SEEDING FORECAST PAGE FINAL DEMO DATA")
        print("=" * 60)

        # 1. Verify Hospital 1
        hospital = db.query(Hospital).filter(Hospital.id == 1).first()
        if not hospital:
            print("Error: Hospital 1 not found!")
            return

        print(f"Target Hospital: {hospital.name} (id={hospital.id})")

        # Get the wards
        w_er = db.query(Ward).filter(Ward.hospital_id == 1, Ward.ward_type == "EMERGENCY").first()
        w_gen = db.query(Ward).filter(Ward.hospital_id == 1, Ward.ward_type == "GENERAL").first()
        w_icu = db.query(Ward).filter(Ward.hospital_id == 1, Ward.ward_type == "ICU").first()

        if not (w_er and w_gen and w_icu):
            print("Error: Required wards (ER, GENERAL, ICU) not found for Hospital 1!")
            return

        print(f"  - Ward ER:  {w_er.name} (id={w_er.id}, cap={w_er.capacity})")
        print(f"  - Ward GEN: {w_gen.name} (id={w_gen.id}, cap={w_gen.capacity})")
        print(f"  - Ward ICU: {w_icu.name} (id={w_icu.id}, cap={w_icu.capacity})")

        # 2. Update Live Beds Status
        print("\n[1/5] Updating Live Bed Statuses...")
        # ICU: 10 Occupied, 1 Cleaning, 1 Available (Capacity 12) -> 83.3% Occupancy
        icu_beds = db.query(Bed).filter(Bed.ward_id == w_icu.id).order_by(Bed.id).all()
        for idx, bed in enumerate(icu_beds):
            if idx < 10:
                bed.status = BedStatus.OCCUPIED.value
            elif idx == 10:
                bed.status = BedStatus.CLEANING.value
            else:
                bed.status = BedStatus.AVAILABLE.value

        # General Ward: 24 Occupied, 2 Cleaning, 4 Available (Capacity 30) -> 80.0% Occupancy
        gen_beds = db.query(Bed).filter(Bed.ward_id == w_gen.id).order_by(Bed.id).all()
        for idx, bed in enumerate(gen_beds):
            if idx < 24:
                bed.status = BedStatus.OCCUPIED.value
            elif idx < 26:
                bed.status = BedStatus.CLEANING.value
            else:
                bed.status = BedStatus.AVAILABLE.value

        # Emergency: 14 Occupied, 1 Reserved, 5 Available (Capacity 20) -> 70.0% Occupancy
        er_beds = db.query(Bed).filter(Bed.ward_id == w_er.id).order_by(Bed.id).all()
        for idx, bed in enumerate(er_beds):
            if idx < 14:
                bed.status = BedStatus.OCCUPIED.value
            elif idx == 14:
                bed.status = BedStatus.RESERVED.value
            else:
                bed.status = BedStatus.AVAILABLE.value

        db.commit()
        print("  [+] Bed statuses successfully configured.")

        # 3. Seed Realistic 30-Day Historical Snapshots up to Today
        print("\n[2/5] Seeding 30-Day Historical Occupancy Snapshots...")
        # Remove old snapshots for these 3 wards in the last 35 days to prevent duplicates
        today = date.today()
        cutoff_date = today - timedelta(days=35)
        cutoff_dt = datetime(cutoff_date.year, cutoff_date.month, cutoff_date.day, 0, 0, 0)

        deleted_sn = db.query(OccupancySnapshot).filter(
            OccupancySnapshot.ward_id.in_([w_icu.id, w_gen.id, w_er.id]),
            OccupancySnapshot.snapshot_time >= cutoff_dt
        ).delete(synchronize_session=False)
        print(f"  - Cleared {deleted_sn} recent snapshots to ensure clean time series.")

        new_snapshots = []
        for i in range(30, -1, -1):
            snap_date = today - timedelta(days=i)
            snap_dt = datetime(snap_date.year, snap_date.month, snap_date.day, 12, 0, 0)

            # ICU (capacity 12): cycles 7-9 beds early on, then climbs to 10 beds recently
            if i > 10:
                icu_occ = 8 if i % 2 == 0 else 7
            elif i > 4:
                icu_occ = 9 if i % 3 != 0 else 8
            else:
                icu_occ = 10  # recent high occupancy
            
            new_snapshots.append(OccupancySnapshot(
                hospital_id=1,
                ward_id=w_icu.id,
                snapshot_time=snap_dt,
                total_beds=w_icu.capacity,
                occupied_beds=icu_occ,
                available_beds=w_icu.capacity - icu_occ,
                occupancy_percentage=round((icu_occ / float(w_icu.capacity)) * 100.0, 2),
            ))

            # General Inpatient (capacity 30): cycles 20-24 beds
            if i > 7:
                gen_occ = 21 + (i % 4)
            else:
                gen_occ = 24  # stabilized around 80%
            
            new_snapshots.append(OccupancySnapshot(
                hospital_id=1,
                ward_id=w_gen.id,
                snapshot_time=snap_dt,
                total_beds=w_gen.capacity,
                occupied_beds=gen_occ,
                available_beds=w_gen.capacity - gen_occ,
                occupancy_percentage=round((gen_occ / float(w_gen.capacity)) * 100.0, 2),
            ))

            # Emergency (capacity 20): cycles 12-16 beds
            er_occ = 13 + ((i * 3) % 4)
            if i == 0:
                er_occ = 14
            
            new_snapshots.append(OccupancySnapshot(
                hospital_id=1,
                ward_id=w_er.id,
                snapshot_time=snap_dt,
                total_beds=w_er.capacity,
                occupied_beds=er_occ,
                available_beds=w_er.capacity - er_occ,
                occupancy_percentage=round((er_occ / float(w_er.capacity)) * 100.0, 2),
            ))

        db.add_all(new_snapshots)
        db.commit()
        print(f"  [+] {len(new_snapshots)} high-fidelity historical snapshots created.")

        # 4. Generate Fresh, Rich Forward Capacity Forecasts
        print("\n[3/5] Generating Forward SARIMA Projections for 1, 3, and 7-day horizons...")
        # Clear recent forecasts for these wards so fresh pipeline forecasts dominate
        deleted_fc = db.query(BedCapacityForecast).filter(
            BedCapacityForecast.ward_id.in_([w_icu.id, w_gen.id, w_er.id]),
            BedCapacityForecast.forecast_date >= today
        ).delete(synchronize_session=False)
        print(f"  - Cleared {deleted_fc} forward forecasts.")

        gen_time = datetime.utcnow()

        # ICU Forecasts: Starts at 10 beds (83.3%), peaks at 11.6 beds (96.7% CRITICAL) on Day 5
        icu_projections = [
            (1, 10.4, 86.7, 80.0, 93.3, RiskLevel.HIGH.value),
            (2, 10.8, 90.0, 82.5, 97.5, RiskLevel.HIGH.value),
            (3, 11.2, 93.3, 85.0, 100.0, RiskLevel.HIGH.value),
            (4, 11.5, 95.8, 87.5, 100.0, RiskLevel.CRITICAL.value),
            (5, 11.6, 96.7, 88.0, 100.0, RiskLevel.CRITICAL.value),
            (6, 11.1, 92.5, 84.0, 100.0, RiskLevel.HIGH.value),
            (7, 10.5, 87.5, 80.0, 95.0, RiskLevel.HIGH.value),
        ]

        # General Ward Forecasts: Starts at 24 beds (80.0%), peaks at 26.2 beds (87.3% HIGH)
        gen_projections = [
            (1, 24.5, 81.7, 76.7, 86.7, RiskLevel.MODERATE.value),
            (2, 25.1, 83.7, 78.0, 89.0, RiskLevel.MODERATE.value),
            (3, 25.8, 86.0, 80.0, 92.0, RiskLevel.HIGH.value),
            (4, 26.2, 87.3, 81.0, 93.5, RiskLevel.HIGH.value),
            (5, 25.5, 85.0, 79.0, 91.0, RiskLevel.HIGH.value),
            (6, 24.8, 82.7, 77.0, 88.5, RiskLevel.MODERATE.value),
            (7, 24.0, 80.0, 74.0, 86.0, RiskLevel.MODERATE.value),
        ]

        # Emergency Forecasts: Starts at 14 beds (70.0%), peaks at 16.2 beds (81.0% MODERATE)
        er_projections = [
            (1, 14.8, 74.0, 65.0, 83.0, RiskLevel.NORMAL.value),
            (2, 15.5, 77.5, 68.0, 87.0, RiskLevel.MODERATE.value),
            (3, 16.2, 81.0, 71.0, 91.0, RiskLevel.MODERATE.value),
            (4, 15.8, 79.0, 69.0, 89.0, RiskLevel.MODERATE.value),
            (5, 14.9, 74.5, 65.0, 84.0, RiskLevel.NORMAL.value),
            (6, 14.2, 71.0, 62.0, 80.0, RiskLevel.NORMAL.value),
            (7, 13.8, 69.0, 60.0, 78.0, RiskLevel.NORMAL.value),
        ]

        new_forecasts = []
        for ward_obj, proj_list in [(w_icu, icu_projections), (w_gen, gen_projections), (w_er, er_projections)]:
            for horizon_day, pred_beds, pred_pct, low, high, risk in proj_list:
                f_date = today + timedelta(days=horizon_day)
                new_forecasts.append(BedCapacityForecast(
                    hospital_id=1,
                    ward_id=ward_obj.id,
                    forecast_date=f_date,
                    generated_at=gen_time,
                    horizon_days=7,
                    predicted_occupied_beds=pred_beds,
                    predicted_occupancy_percentage=pred_pct,
                    lower_bound=low,
                    upper_bound=high,
                    risk_level=risk,
                    model_name="SARIMA",
                    model_version="1.0",
                    training_data_start=today - timedelta(days=30),
                    training_data_end=today,
                ))

        db.add_all(new_forecasts)
        db.commit()
        print(f"  [+] {len(new_forecasts)} forward forecast projections created across all 3 wards.")

        # 5. Seed Explainable Capacity Alerts
        print("\n[4/5] Seeding Explainable Capacity Alerts...")
        # Clear existing alerts for Hospital 1
        db.query(CapacityAlert).filter(CapacityAlert.hospital_id == 1).delete(synchronize_session=False)

        alert_icu = CapacityAlert(
            hospital_id=1,
            ward_id=w_icu.id,
            alert_type=AlertType.FORECAST_CRITICAL_OCCUPANCY.value,
            severity=AlertSeverity.CRITICAL.value,
            status=AlertStatus.ACTIVE.value,
            trigger_value=96.7,
            threshold_value=95.0,
            message=(
                f"{w_icu.name} has a physical capacity of 12 beds and currently has 10 occupied beds (83.3% occupancy). "
                f"SARIMA forecast projects peak occupancy of 96.7% (11.6 beds) within 5 days on {(today + timedelta(days=5)).strftime('%b %d, %Y')}. "
                "Triggered risk rules: Imminent Critical Capacity Saturation (Rule B) & Low Available Beds (Rule C: only 1 operational bed available). "
                "Immediate administrative action recommended: prepare inter-ward step-down transfers."
            ),
            explanation_json="""{
                "rule_id": "RULE_B_CRITICAL_FORECAST",
                "headline": "Imminent Critical Saturation in Intensive Care Unit",
                "human_readable_explanation": "Intensive Care Unit is operating at 83.3%% live capacity with only 1 bed currently available. The primary SARIMA time-series model projects patient demand rising to 96.7%% (11.6 beds occupied) by Day 5. This triggers a Critical Capacity Warning. Hospital management should expedite step-down transfers to General Inpatient Ward.",
                "evidence": {
                    "current_occupancy_percentage": 83.3,
                    "current_occupied_beds": 10,
                    "ward_capacity": 12,
                    "predicted_occupancy_percentage": 96.7,
                    "predicted_occupied_beds": 11.6,
                    "forecast_target_date": "%s",
                    "days_to_threshold": 4,
                    "available_beds_now": 1,
                    "uncertainty_span": 12.0
                },
                "recommended_actions": [
                    "Identify stable ICU patients eligible for step-down to General Ward.",
                    "Expedite turnover and sanitization of cleaning bed #11.",
                    "Review pending elective surgical admissions requiring post-op ICU placement."
                ]
            }""" % (today + timedelta(days=5)).isoformat(),
            created_at=datetime.utcnow() - timedelta(hours=2),
        )

        alert_gen = CapacityAlert(
            hospital_id=1,
            ward_id=w_gen.id,
            alert_type=AlertType.FORECAST_HIGH_OCCUPANCY.value,
            severity=AlertSeverity.WARNING.value,
            status=AlertStatus.ACTIVE.value,
            trigger_value=87.3,
            threshold_value=85.0,
            message=(
                f"{w_gen.name} has a capacity of 30 beds and currently has 24 occupied beds (80.0% occupancy). "
                f"SARIMA forecast predicts occupancy crossing 85% threshold on {(today + timedelta(days=4)).strftime('%b %d, %Y')} reaching 87.3% (26.2 beds). "
                "Triggered risk rule: High Forecasted Occupancy (Rule A). Monitor discharge velocity."
            ),
            explanation_json="""{
                "rule_id": "RULE_A_HIGH_FORECAST",
                "headline": "Projected High Occupancy in Inpatient General Ward",
                "human_readable_explanation": "Inpatient Ward capacity is currently at 80.0%% (24/30 beds). Time-series models project occupancy to reach 87.3%% by Day 4. While bed capacity remains safe for incoming step-downs, discharge velocity should be monitored.",
                "evidence": {
                    "current_occupancy_percentage": 80.0,
                    "current_occupied_beds": 24,
                    "ward_capacity": 30,
                    "predicted_occupancy_percentage": 87.3,
                    "predicted_occupied_beds": 26.2,
                    "forecast_target_date": "%s",
                    "days_to_threshold": 3,
                    "available_beds_now": 4,
                    "uncertainty_span": 12.5
                },
                "recommended_actions": [
                    "Coordinate planned patient discharges scheduled for the next 48 hours.",
                    "Prepare 2 beds in Section B for expected transfers from ICU."
                ]
            }""" % (today + timedelta(days=4)).isoformat(),
            created_at=datetime.utcnow() - timedelta(hours=4),
        )

        db.add_all([alert_icu, alert_gen])
        db.commit()
        print("  [+] Explainable capacity alerts successfully generated and persisted.")

        # 6. Ensure Transfer Compatibility Rules and Recommendations
        print("\n[5/5] Configuring Inter-Ward Transfer Recommendations...")
        rule = db.query(WardTransferRule).filter(
            WardTransferRule.hospital_id == 1,
            WardTransferRule.source_ward_type == "ICU",
            WardTransferRule.destination_ward_type == "GENERAL"
        ).first()

        if not rule:
            rule = WardTransferRule(
                hospital_id=1,
                source_ward_type="ICU",
                destination_ward_type="GENERAL",
                allowed=True,
                priority=1,
                minimum_available_beds=2,
                maximum_destination_occupancy=85.0,
                reason="Standard clinical step-down pathway post-stabilization."
            )
            db.add(rule)
            db.commit()
            print("  [+] Added Transfer Rule: ICU -> GENERAL.")

        # Clear existing recommendations for hospital 1
        db.query(TransferRecommendation).filter(
            TransferRecommendation.hospital_id == 1
        ).delete(synchronize_session=False)

        # Add 2 realistic transfer recommendations
        rec1 = TransferRecommendation(
            hospital_id=1,
            source_ward_id=w_icu.id,
            destination_ward_id=w_gen.id,
            source_current_occupancy=83.3,
            source_predicted_occupancy=96.7,
            destination_current_occupancy=80.0,
            destination_predicted_occupancy=87.3,
            available_beds=4,
            safe_transfer_capacity=2,
            recommended_transfer_count=1,
            priority_score=94.5,
            priority_level="HIGH",
            status=RecommendationStatus.PENDING.value,
            reason="Proactive step-down transfer: Patient hemodynamically stable; frees high-demand ICU bed ahead of 96.7% projected weekend saturation.",
            forecast_horizon_days=7,
            forecast_confidence_lower=80.0,
            forecast_confidence_upper=100.0,
            expires_at=datetime.utcnow() + timedelta(hours=24),
            recommended_at=datetime.utcnow() - timedelta(minutes=45),
        )

        rec2 = TransferRecommendation(
            hospital_id=1,
            source_ward_id=w_icu.id,
            destination_ward_id=w_gen.id,
            source_current_occupancy=83.3,
            source_predicted_occupancy=96.7,
            destination_current_occupancy=80.0,
            destination_predicted_occupancy=87.3,
            available_beds=4,
            safe_transfer_capacity=2,
            recommended_transfer_count=1,
            priority_score=88.0,
            priority_level="MEDIUM",
            status=RecommendationStatus.PENDING.value,
            reason="Step-down eligible post-cardiac observation. Target Inpatient Ward has 4 verified available beds.",
            forecast_horizon_days=7,
            forecast_confidence_lower=80.0,
            forecast_confidence_upper=100.0,
            expires_at=datetime.utcnow() + timedelta(hours=36),
            recommended_at=datetime.utcnow() - timedelta(minutes=90),
        )

        db.add_all([rec1, rec2])
        db.commit()
        print("  [+] Active transfer recommendations successfully populated.")

        print("\n" + "=" * 60)
        print("DEMO DATA SEEDING COMPLETE!")
        print("=" * 60)
        print(f"Hospital: Apollo Medical Center (ID: 1)")
        print(f"Wards: ICU ({w_icu.id}), Inpatient ({w_gen.id}), Emergency ({w_er.id})")
        print(f"Forecasts: 7-day multi-horizon SARIMA models with uncertainty intervals")
        print(f"Alerts: 2 active explainable capacity alerts with evidence cards")
        print(f"Transfers: 2 pending high-priority recommendation actions")
        print("=" * 60)

    finally:
        db.close()

if __name__ == "__main__":
    seed_demo_forecast_data()
