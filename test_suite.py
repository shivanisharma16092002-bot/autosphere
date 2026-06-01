import unittest
import os
import pandas as pd
from pydantic import ValidationError

from models.supplier import Supplier
from models.demand import MarketDemand
from engines.forecasting import forecast_next_demand
from engines.feedback import FeedbackParser
from engines.procurement import ProcurementEngine
from engines.reporting import export_rankings_to_csv, save_supplier_state, load_supplier_state

class TestAutoSphereModels(unittest.TestCase):
    def test_supplier_validation_success(self):
        """Verify that valid inputs create a correct Supplier instance."""
        s = Supplier(
            id="S1",
            name="Test Supplier",
            location="Detroit",
            component_type="Brake Pads",
            base_cost=45.0,
            risk_score=0.25,
            capacity=1000
        )
        self.assertEqual(s.id, "S1")
        self.assertEqual(s.risk_score, 0.25)
        self.assertEqual(s.capacity, 1000)

    def test_supplier_validation_risk_clamping(self):
        """Verify that risk scores must be between 0.0 and 1.0."""
        with self.assertRaises(ValidationError):
            Supplier(
                id="S1",
                name="Test Supplier",
                location="Detroit",
                component_type="Brake Pads",
                base_cost=45.0,
                risk_score=1.5,  # Out of range
                capacity=1000
            )
            
        with self.assertRaises(ValidationError):
            Supplier(
                id="S1",
                name="Test Supplier",
                location="Detroit",
                component_type="Brake Pads",
                base_cost=45.0,
                risk_score=-0.1,  # Out of range
                capacity=1000
            )


class TestDemandForecasting(unittest.TestCase):
    def test_forecasting_positive_trend(self):
        """Verify linear trend line projections for a growing sequence."""
        historical = [100, 110, 120, 130]
        val = forecast_next_demand(historical)
        self.assertEqual(val, 140)

    def test_forecasting_negative_trend_fallback(self):
        """Verify that a negative projection falls back to SMA and does not return < 0."""
        historical = [10, 8, 4, 1]
        val = forecast_next_demand(historical)
        self.assertGreaterEqual(val, 0)
        self.assertEqual(val, 4)

    def test_forecasting_single_value(self):
        """Verify fallback when only 1 historical data point is present."""
        historical = [50]
        val = forecast_next_demand(historical)
        self.assertEqual(val, 50)


class TestFeedbackParser(unittest.TestCase):
    def setUp(self):
        self.suppliers = [
            Supplier(id="S1", name="Apex Corp", location="Detroit", component_type="Brake Pads", base_cost=40.0, risk_score=0.1, capacity=5000),
            Supplier(id="S2", name="Vertex Corp", location="Munich", component_type="Brake Pads", base_cost=50.0, risk_score=0.2, capacity=6000)
        ]
        self.parser = FeedbackParser(self.suppliers)

    def test_feedback_matching_and_critical_risk(self):
        """Verify feedback parses critical keyword and applies correct risk penalty."""
        feedback = "Apex Corp experienced a critical hazard recall on their brake pads."
        result = self.parser.parse_feedback(feedback)
        
        self.assertEqual(result["matched_supplier"], "Apex Corp")
        self.assertEqual(result["supplier_id"], "S1")
        self.assertEqual(result["matched_component"], "Brake Pads")
        self.assertEqual(result["sentiment_severity"], "critical")
        self.assertIn("recall", result["detected_keywords"])
        self.assertIn("hazard", result["detected_keywords"])
        
        # Penalties accumulated: critical (0.3) + critical (0.3) = 0.6
        self.assertEqual(result["risk_penalty"], 0.6)
        self.assertEqual(result["old_risk_score"], 0.1)
        self.assertEqual(result["new_risk_score"], 0.7)


class TestProcurementEngine(unittest.TestCase):
    def setUp(self):
        self.suppliers = [
            Supplier(id="S1", name="Apex", location="Detroit", component_type="Brake Pads", base_cost=30.0, risk_score=0.4, capacity=5000),
            Supplier(id="S2", name="Vertex", location="Munich", component_type="Brake Pads", base_cost=50.0, risk_score=0.1, capacity=10000),
            Supplier(id="S3", name="Zephyr", location="Shanghai", component_type="Brake Pads", base_cost=40.0, risk_score=0.1, capacity=5000)
        ]
        self.engine = ProcurementEngine(self.suppliers)

    def test_optimization_ranking_logic(self):
        """Verify sorting and normalization mathematical correctness."""
        results = self.engine.optimize_sourcing("Brake Pads")
        
        self.assertEqual(len(results), 3)
        
        s3_item = next(item for item in results if item["supplier"].id == "S3")
        self.assertEqual(s3_item["cost_score"], 0.5)
        self.assertEqual(s3_item["risk_score"], 0.9)
        self.assertEqual(s3_item["capacity_score"], 0.0)
        self.assertEqual(s3_item["composite_score"], 0.56)

        scores = [item["composite_score"] for item in results]
        self.assertEqual(scores, sorted(scores, reverse=True))


class TestReportingAndPersistence(unittest.TestCase):
    def setUp(self):
        self.state_file = "test_suppliers_state.json"
        self.report_file = "test_report.csv"
        self.suppliers = [
            Supplier(id="S1", name="Apex", location="Detroit", component_type="Brake Pads", base_cost=30.0, risk_score=0.4, capacity=5000),
            Supplier(id="S2", name="Vertex", location="Munich", component_type="Brake Pads", base_cost=50.0, risk_score=0.1, capacity=10000)
        ]

    def tearDown(self):
        if os.path.exists(self.state_file):
            os.remove(self.state_file)
        if os.path.exists(self.report_file):
            os.remove(self.report_file)

    def test_state_saving_and_loading(self):
        """Verify that supplier database profiles can be saved and loaded from JSON files."""
        filepath = save_supplier_state(self.suppliers, self.state_file)
        self.assertTrue(os.path.exists(filepath))
        
        loaded = load_supplier_state(self.state_file)
        self.assertEqual(len(loaded), 2)
        self.assertEqual(loaded[0].name, "Apex")
        self.assertEqual(loaded[1].risk_score, 0.1)

    def test_csv_report_generation(self):
        """Verify that sourcing optimization rankings compile into CSV spreadsheets."""
        engine = ProcurementEngine(self.suppliers)
        rankings = engine.optimize_sourcing("Brake Pads")
        filepath = export_rankings_to_csv(rankings, self.report_file)
        self.assertTrue(os.path.exists(filepath))
        
        df = pd.read_csv(filepath)
        self.assertEqual(len(df), 2)
        self.assertIn("Sourcing Rank", df.columns)
        self.assertIn("Supplier Name", df.columns)
        self.assertEqual(df.iloc[0]["Supplier Name"], "Apex")

if __name__ == "__main__":
    unittest.main()
