from typing import Dict, Any, Tuple
from app.models.transfer_recommendation import RecommendationPriority


class TransferScoringService:
    """
    Transparent, rule-based 0-100 scoring algorithm for inter-ward transfer recommendations.
    
    Formula Component Weights:
    - Source Urgency: 0–40 points
    - Destination Availability: 0–25 points
    - Destination Future Capacity: 0–20 points
    - Ward Compatibility: 0–15 points
    """

    @staticmethod
    def calculate_score(
        source_current_occ: float,
        source_pred_occ: float,
        source_risk_level: str,
        dest_current_occ: float,
        dest_pred_occ: float,
        dest_available_beds: int,
        safe_transfer_capacity: int,
        compatibility_allowed: bool,
        rule_priority: int = 1,
    ) -> Tuple[float, RecommendationPriority, Dict[str, Any]]:
        if not compatibility_allowed or safe_transfer_capacity <= 0:
            return 0.0, RecommendationPriority.LOW, {
                "source_urgency": 0.0,
                "destination_capacity": 0.0,
                "future_capacity": 0.0,
                "compatibility": 0.0
            }

        # 1. Source Urgency (0–40 points)
        source_urgency = 0.0
        max_source_occ = max(source_current_occ, source_pred_occ)
        if source_risk_level == "CRITICAL" or max_source_occ >= 95.0:
            source_urgency = 40.0
        elif source_risk_level == "HIGH" or max_source_occ >= 88.0:
            source_urgency = 32.0 + min(8.0, (max_source_occ - 88.0) * 1.14)
        elif source_risk_level == "MODERATE" or max_source_occ >= 80.0:
            source_urgency = 20.0 + min(12.0, (max_source_occ - 80.0) * 1.5)
        else:
            source_urgency = min(20.0, (max_source_occ / 80.0) * 20.0)

        # 2. Destination Capacity (0–25 points)
        # Prefers lower current occupancy and higher safe transfer capacity
        dest_capacity_score = 0.0
        occ_headroom = max(0.0, 85.0 - dest_current_occ)
        occ_points = min(15.0, (occ_headroom / 35.0) * 15.0)  # max 15 pts for < 50% occ
        safe_bed_points = min(10.0, (safe_transfer_capacity / 5.0) * 10.0)  # max 10 pts for 5+ safe beds
        dest_capacity_score = round(occ_points + safe_bed_points, 2)

        # 3. Destination Future Capacity (0–20 points)
        # Prefers destination wards whose future predicted occupancy remains low
        future_capacity_score = 0.0
        if dest_pred_occ < 70.0:
            future_capacity_score = 20.0
        elif dest_pred_occ < 80.0:
            future_capacity_score = 15.0 + (80.0 - dest_pred_occ) * 0.5
        elif dest_pred_occ < 85.0:
            future_capacity_score = 8.0 + (85.0 - dest_pred_occ) * 1.4
        else:
            future_capacity_score = max(0.0, 8.0 - (dest_pred_occ - 85.0) * 1.6)

        # 4. Ward Compatibility (0–15 points)
        # Higher priority rules or direct compatibility match
        compatibility_score = min(15.0, 10.0 + (rule_priority - 1) * 2.5)

        # Total 0–100
        total_score = round(source_urgency + dest_capacity_score + future_capacity_score + compatibility_score, 1)
        total_score = max(0.0, min(100.0, total_score))

        # Priority Level Classification
        if total_score >= 85.0:
            priority = RecommendationPriority.CRITICAL
        elif total_score >= 70.0:
            priority = RecommendationPriority.HIGH
        elif total_score >= 50.0:
            priority = RecommendationPriority.MEDIUM
        else:
            priority = RecommendationPriority.LOW

        breakdown = {
            "source_urgency": round(source_urgency, 1),
            "destination_capacity": round(dest_capacity_score, 1),
            "future_capacity": round(future_capacity_score, 1),
            "compatibility": round(compatibility_score, 1),
            "max_possible": 100.0
        }

        return total_score, priority, breakdown
