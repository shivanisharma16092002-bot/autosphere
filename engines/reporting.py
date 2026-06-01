import os
import json
import pandas as pd
from typing import List, Dict, Any
from models.supplier import Supplier

def export_rankings_to_csv(rankings: List[Dict[str, Any]], filepath: str = "sourcing_report.csv") -> str:
    """
    Formats and exports the multi-criteria procurement scoring results into
    an enterprise-grade CSV report using Pandas.
    
    Parameters:
    - rankings: The optimization scores output from the ProcurementEngine.
    - filepath: The target filename/path for the CSV file.
    
    Returns:
    - Absolute file path of the generated report.
    """
    report_data = []
    
    for rank, item in enumerate(rankings, 1):
        s = item["supplier"]
        report_data.append({
            "Sourcing Rank": f"#{rank}",
            "Supplier ID": s.id,
            "Supplier Name": s.name,
            "Location": s.location,
            "Component Type": s.component_type,
            "Base Cost per Unit ($)": round(s.base_cost, 2),
            "Updated Risk Score": round(s.risk_score, 4),
            "Monthly Capacity (Units)": s.capacity,
            "Utility Score: Cost (Normalized)": round(item["cost_score"], 4),
            "Utility Score: Risk (Normalized)": round(item["risk_score"], 4),
            "Utility Score: Capacity (Normalized)": round(item["capacity_score"], 4),
            "Composite Optimization Score": round(item["composite_score"], 4)
        })
        
    df = pd.DataFrame(report_data)
    df.to_csv(filepath, index=False)
    return os.path.abspath(filepath)

def save_supplier_state(suppliers: List[Supplier], filepath: str = "suppliers_state.json") -> str:
    """
    Serializes the active supplier pool (including dynamically adjusted risk scores)
    into a local JSON state file to simulate database persistence.
    """
    serialized_data = [s.model_dump() for s in suppliers]
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(serialized_data, f, indent=4, ensure_ascii=False)
    return os.path.abspath(filepath)

def load_supplier_state(filepath: str = "suppliers_state.json") -> List[Supplier]:
    """
    De-serializes supplier profiles from the local JSON state file.
    Returns an empty list if the state file does not exist.
    """
    if not os.path.exists(filepath):
        return []
        
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return [Supplier(**item) for item in data]
    except Exception:
        # Fall back to empty list on corrupted files
        return []
