import os
import json
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from models.supplier import Supplier
from models.demand import MarketDemand
from engines.forecasting import forecast_next_demand
from engines.feedback import FeedbackParser
from engines.procurement import ProcurementEngine
from engines.reporting import export_rankings_to_csv, save_supplier_state, load_supplier_state

app = FastAPI(title="AutoSphere AI Dashboard Backend")

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DEFAULT_STATE_FILE = "suppliers_state.json"
HISTORICAL_DEMAND = [8200, 8500, 8700, 8900, 9200, 9400]
DEMAND_PROFILE = MarketDemand(
    component_type="Brake Pads",
    target_cost=42.00,
    required_quantity=9500,
    historical_demand=HISTORICAL_DEMAND
)

def get_default_suppliers() -> List[Supplier]:
    return [
        Supplier(id="S1", name="Apex Parts Corp", location="Detroit, USA", component_type="Brake Pads", base_cost=45.00, risk_score=0.15, capacity=10000),
        Supplier(id="S2", name="Vertex Automotive", location="Munich, Germany", component_type="Brake Pads", base_cost=48.00, risk_score=0.08, capacity=12000),
        Supplier(id="S3", name="Zephyr Braking Co", location="Shanghai, China", component_type="Brake Pads", base_cost=38.00, risk_score=0.35, capacity=8000),
        Supplier(id="S4", name="Quantum Tech Inc", location="Tokyo, Japan", component_type="Microchips", base_cost=12.50, risk_score=0.05, capacity=50000),
        Supplier(id="S5", name="GlobalTech Solutions", location="Seoul, South Korea", component_type="Microchips", base_cost=11.00, risk_score=0.20, capacity=45000)
    ]

# Keep weights in a mutable global config
GLOBAL_WEIGHTS = {
    "cost": 0.40,
    "risk": 0.40,
    "capacity": 0.20
}

# Ensure suppliers state exists
def load_active_suppliers() -> List[Supplier]:
    suppliers = load_supplier_state(DEFAULT_STATE_FILE)
    if not suppliers:
        suppliers = get_default_suppliers()
        save_supplier_state(suppliers, DEFAULT_STATE_FILE)
    return suppliers

class FeedbackRequest(BaseModel):
    text: str

class OptimizationRequest(BaseModel):
    component_type: str
    cost_weight: float = Field(..., ge=0.0, le=1.0)
    risk_weight: float = Field(..., ge=0.0, le=1.0)
    capacity_weight: float = Field(..., ge=0.0, le=1.0)

class NewSupplierRequest(BaseModel):
    name: str = Field(..., min_length=1)
    location: str = Field(..., min_length=1)
    component_type: str = Field(..., min_length=1)
    base_cost: float = Field(..., gt=0.0)
    risk_score: float = Field(..., ge=0.0, le=1.0)
    capacity: int = Field(..., gt=0)

@app.get("/", response_class=HTMLResponse)
async def read_index():
    index_path = os.path.join(os.path.dirname(__file__), "templates", "index.html")
    if not os.path.exists(index_path):
        raise HTTPException(status_code=404, detail="index.html not found. Please verify placement under templates/index.html")
    with open(index_path, "r", encoding="utf-8") as f:
        html_content = f.read()
    return html_content

@app.get("/api/state")
async def get_state():
    suppliers = load_active_suppliers()
    forecasted = forecast_next_demand(HISTORICAL_DEMAND)
    
    # Calculate unique component types in system
    components = sorted(list(set(s.component_type for s in suppliers)))
    
    # Calculate Flagged Risks: risk_score >= 0.35
    flagged_risks = sum(1 for s in suppliers if s.risk_score >= 0.35)
    
    return {
        "suppliers": [s.model_dump() for s in suppliers],
        "weights": GLOBAL_WEIGHTS,
        "kpis": {
            "forecasted_demand": forecasted,
            "total_suppliers": len(suppliers),
            "flagged_risks": flagged_risks
        },
        "components": components,
        "historical_demand": HISTORICAL_DEMAND
    }

@app.post("/api/feedback/analyze")
async def analyze_feedback(payload: FeedbackRequest):
    suppliers = load_active_suppliers()
    parser = FeedbackParser(suppliers)
    result = parser.parse_feedback(payload.text)
    
    if result["matched_supplier"] and result["risk_penalty"] > 0:
        save_supplier_state(suppliers, DEFAULT_STATE_FILE)
        
    return {
        "success": True,
        "result": {
            "feedback": result["feedback"],
            "matched_supplier": result["matched_supplier"],
            "supplier_id": result["supplier_id"],
            "matched_component": result["matched_component"],
            "sentiment_severity": result["sentiment_severity"],
            "detected_keywords": result["detected_keywords"],
            "risk_penalty": result["risk_penalty"],
            "old_risk_score": result["old_risk_score"],
            "new_risk_score": result["new_risk_score"]
        }
    }

@app.post("/api/procurement/optimize")
async def optimize_procurement(payload: OptimizationRequest):
    # Verify weights sum up to ~1.0
    w_sum = payload.cost_weight + payload.risk_weight + payload.capacity_weight
    if abs(w_sum - 1.0) > 1e-4:
        raise HTTPException(status_code=400, detail=f"Weights must sum to 1.0! Got sum = {w_sum:.4f}")
    
    # Update global weights
    GLOBAL_WEIGHTS["cost"] = round(payload.cost_weight, 4)
    GLOBAL_WEIGHTS["risk"] = round(payload.risk_weight, 4)
    GLOBAL_WEIGHTS["capacity"] = round(payload.capacity_weight, 4)
    
    suppliers = load_active_suppliers()
    procurement_engine = ProcurementEngine(suppliers)
    procurement_engine.WEIGHT_COST = GLOBAL_WEIGHTS["cost"]
    procurement_engine.WEIGHT_RISK = GLOBAL_WEIGHTS["risk"]
    procurement_engine.WEIGHT_CAPACITY = GLOBAL_WEIGHTS["capacity"]
    
    rankings = procurement_engine.optimize_sourcing(payload.component_type)
    
    # Format rankings for JSON response
    formatted_rankings = []
    for rank, item in enumerate(rankings, 1):
        s = item["supplier"]
        formatted_rankings.append({
            "rank": rank,
            "supplier": s.model_dump(),
            "cost_score": item["cost_score"],
            "risk_score": item["risk_score"],
            "capacity_score": item["capacity_score"],
            "composite_score": item["composite_score"]
        })
        
    return {
        "success": True,
        "rankings": formatted_rankings
    }

@app.post("/api/suppliers")
async def add_supplier(payload: NewSupplierRequest):
    suppliers = load_active_suppliers()
    
    # Generate new unique ID
    existing_ids = {s.id for s in suppliers}
    idx = len(suppliers) + 1
    new_id = f"S{idx}"
    while new_id in existing_ids:
        idx += 1
        new_id = f"S{idx}"
        
    new_supplier = Supplier(
        id=new_id,
        name=payload.name,
        location=payload.location,
        component_type=payload.component_type,
        base_cost=payload.base_cost,
        risk_score=payload.risk_score,
        capacity=payload.capacity
    )
    
    suppliers.append(new_supplier)
    save_supplier_state(suppliers, DEFAULT_STATE_FILE)
    
    return {
        "success": True,
        "supplier": new_supplier.model_dump()
    }

@app.post("/api/reset")
async def reset_database():
    suppliers = get_default_suppliers()
    save_supplier_state(suppliers, DEFAULT_STATE_FILE)
    
    # Reset weights
    GLOBAL_WEIGHTS["cost"] = 0.40
    GLOBAL_WEIGHTS["risk"] = 0.40
    GLOBAL_WEIGHTS["capacity"] = 0.20
    
    return {
        "success": True,
        "message": "Database and weights restored to factory defaults."
    }

@app.get("/api/export")
async def export_report(component_type: str = "Brake Pads"):
    suppliers = load_active_suppliers()
    procurement_engine = ProcurementEngine(suppliers)
    procurement_engine.WEIGHT_COST = GLOBAL_WEIGHTS["cost"]
    procurement_engine.WEIGHT_RISK = GLOBAL_WEIGHTS["risk"]
    procurement_engine.WEIGHT_CAPACITY = GLOBAL_WEIGHTS["capacity"]
    
    rankings = procurement_engine.optimize_sourcing(component_type)
    if not rankings:
        raise HTTPException(status_code=400, detail=f"No suppliers match component type: {component_type}")
        
    csv_path = "sourcing_report.csv"
    export_rankings_to_csv(rankings, csv_path)
    
    if not os.path.exists(csv_path):
        raise HTTPException(status_code=500, detail="Failed to generate sourcing report CSV.")
        
    return FileResponse(
        path=csv_path,
        filename=f"sourcing_report_{component_type.replace(' ', '_').lower()}.csv",
        media_type="text/csv"
    )
