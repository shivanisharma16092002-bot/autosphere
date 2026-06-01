from typing import List, Dict, Any, Tuple
from models.supplier import Supplier

class ProcurementEngine:
    """
    An optimization engine that filters, normalizes, and scores suppliers.
    It weights criteria: 40% Cost, 40% Risk, and 20% Capacity.
    - Cost (minimized, lower is better) -> Cost Score (higher is better)
    - Risk (minimized, lower is better) -> Risk Score (higher is better)
    - Capacity (maximized, higher is better) -> Capacity Score (higher is better)
    """

    WEIGHT_COST = 0.40
    WEIGHT_RISK = 0.40
    WEIGHT_CAPACITY = 0.20

    def __init__(self, suppliers: List[Supplier]):
        self.suppliers = suppliers

    def optimize_sourcing(self, component_type: str) -> List[Dict[str, Any]]:
        """
        Filters suppliers by the requested component type, performs Min-Max normalization,
        calculates composite sourcing scores, and ranks them in descending order.
        
        Returns a list of dictionaries with supplier data and score breakdowns.
        """
        # 1. Filter suppliers by component type
        matching_suppliers = [
            s for s in self.suppliers if s.component_type.lower() == component_type.lower()
        ]
        
        if not matching_suppliers:
            return []

        # If there's only one supplier, scoring is trivial
        if len(matching_suppliers) == 1:
            s = matching_suppliers[0]
            return [{
                "supplier": s,
                "composite_score": 1.0,
                "cost_score": 1.0,
                "risk_score": 1.0 - s.risk_score,
                "capacity_score": 1.0
            }]

        # 2. Extract bounds for normalization
        costs = [s.base_cost for s in matching_suppliers]
        capacities = [s.capacity for s in matching_suppliers]

        min_cost, max_cost = min(costs), max(costs)
        min_cap, max_cap = min(capacities), max(capacities)

        ranked_results = []

        for s in matching_suppliers:
            # 3. Calculate Normalized Scores (0.0 to 1.0, where 1.0 is the best possible)
            
            # Cost Score (Lower is better, so min cost gets 1.0, max cost gets 0.0)
            if max_cost == min_cost:
                cost_score = 1.0
            else:
                cost_score = 1.0 - ((s.base_cost - min_cost) / (max_cost - min_cost))

            # Risk Score (Lower is better. Since risk_score is already in range [0, 1], we do 1 - risk_score)
            risk_score = 1.0 - s.risk_score

            # Capacity Score (Higher is better, so max capacity gets 1.0, min capacity gets 0.0)
            if max_cap == min_cap:
                capacity_score = 1.0
            else:
                capacity_score = (s.capacity - min_cap) / (max_cap - min_cap)

            # 4. Compute Composite Weighted Score
            composite_score = (
                self.WEIGHT_COST * cost_score +
                self.WEIGHT_RISK * risk_score +
                self.WEIGHT_CAPACITY * capacity_score
            )

            ranked_results.append({
                "supplier": s,
                "composite_score": round(composite_score, 4),
                "cost_score": round(cost_score, 4),
                "risk_score": round(risk_score, 4),
                "capacity_score": round(capacity_score, 4)
            })

        # 5. Sort by composite score in descending order
        ranked_results.sort(key=lambda x: x["composite_score"], reverse=True)
        return ranked_results
