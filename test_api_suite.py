import pytest
from fastapi.testclient import TestClient
import os
import csv

from app import app, get_default_suppliers, DEFAULT_STATE_FILE
from models.supplier import Supplier

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_and_teardown():
    # Setup: Reset state before each test
    client.post("/api/reset")
    yield
    # Teardown: Clean up generated reports or state if needed
    if os.path.exists("sourcing_report.csv"):
        try:
            os.remove("sourcing_report.csv")
        except OSError:
            pass

def test_get_state():
    response = client.get("/api/state")
    assert response.status_code == 200
    data = response.json()
    assert "suppliers" in data
    assert "weights" in data
    assert "kpis" in data
    assert "components" in data
    assert "historical_demand" in data
    
    # Assert initial KPIs
    assert data["kpis"]["total_suppliers"] == 5
    assert data["kpis"]["flagged_risks"] == 1  # Zephyr Braking Co initially has 0.35 (>= 0.35 is flagged)

def test_nlp_feedback_critical():
    # Apex Parts Corp has S1, initial risk_score is 0.15
    feedback_text = "We experienced a major recall and safety defect on brake pads shipped by Apex Parts Corp last week. It was a severe defect."
    response = client.post("/api/feedback/analyze", json={"text": feedback_text})
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    res = data["result"]
    assert res["matched_supplier"] == "Apex Parts Corp"
    assert res["supplier_id"] == "S1"
    assert "recall" in res["detected_keywords"]
    assert res["sentiment_severity"] == "critical"
    # Penalty mapping: recall is critical -> +0.30, defect is severe -> +0.15. Total penalty is 0.45.
    # New risk score should be min(1.0, 0.15 + 0.45) = 0.60
    assert res["new_risk_score"] == 0.60
    
    # Verify State KPI reflects updated risk
    state_response = client.get("/api/state")
    state_data = state_response.json()
    assert state_data["kpis"]["flagged_risks"] == 2  # Zephyr (0.35) and Apex (0.60) are now flagged

def test_nlp_feedback_no_match():
    feedback_text = "We are very happy with the general market demand forecast for this month."
    response = client.post("/api/feedback/analyze", json={"text": feedback_text})
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["result"]["matched_supplier"] is None

def test_procurement_optimization():
    payload = {
        "component_type": "Brake Pads",
        "cost_weight": 0.4,
        "risk_weight": 0.4,
        "capacity_weight": 0.2
    }
    response = client.post("/api/procurement/optimize", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "rankings" in data
    rankings = data["rankings"]
    assert len(rankings) == 3  # Initial pool has 3 Brake Pads: S1, S2, S3
    
    # Ranks should be sorted by composite_score descending
    scores = [item["composite_score"] for item in rankings]
    assert scores == sorted(scores, reverse=True)

def test_procurement_optimization_invalid_weights():
    payload = {
        "component_type": "Brake Pads",
        "cost_weight": 0.5,
        "risk_weight": 0.5,
        "capacity_weight": 0.2  # Sums to 1.2
    }
    response = client.post("/api/procurement/optimize", json=payload)
    assert response.status_code == 400
    assert "Weights must sum to 1.0" in response.json()["detail"]

def test_add_supplier():
    new_supplier = {
        "name": "Titan Auto Parts",
        "location": "Windsor, Canada",
        "component_type": "Brake Pads",
        "base_cost": 41.50,
        "risk_score": 0.12,
        "capacity": 14000
    }
    response = client.post("/api/suppliers", json=new_supplier)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["supplier"]["name"] == "Titan Auto Parts"
    assert data["supplier"]["id"] == "S6"  # Should be S6 as S1-S5 are default
    
    # Verify the supplier list now contains 6 items
    state_response = client.get("/api/state")
    state_data = state_response.json()
    assert state_data["kpis"]["total_suppliers"] == 6

def test_reset_database():
    # First, add a supplier to change the state
    client.post("/api/suppliers", json={
        "name": "Titan Auto Parts",
        "location": "Windsor, Canada",
        "component_type": "Brake Pads",
        "base_cost": 41.50,
        "risk_score": 0.12,
        "capacity": 14000
    })
    
    # Reset
    response = client.post("/api/reset")
    assert response.status_code == 200
    assert response.json()["success"] is True
    
    # Verify counts restored to 5
    state_response = client.get("/api/state")
    assert state_response.json()["kpis"]["total_suppliers"] == 5

def test_export_report():
    response = client.get("/api/export?component_type=Brake%20Pads")
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/csv; charset=utf-8"
    assert "attachment" in response.headers["content-disposition"]
    assert "sourcing_report_brake_pads.csv" in response.headers["content-disposition"]
    
    # Assert CSV file generated locally
    assert os.path.exists("sourcing_report.csv")
    with open("sourcing_report.csv", "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        headers = next(reader)
        assert "Sourcing Rank" in headers
        assert "Supplier Name" in headers
        assert "Composite Optimization Score" in headers
        
        # Verify it has rows corresponding to Brake Pads (3 suppliers + 1 header = 4 rows)
        rows = list(reader)
        assert len(rows) == 3
