import re
from typing import List, Dict, Any, Optional
from models.supplier import Supplier

class FeedbackParser:
    """
    A simulated Natural Language Processing (NLP) engine for analyzing customer feedback.
    Scans text for supplier names/IDs, component types, and risk sentiment indicators
    to dynamically adjust supplier risk metrics.
    """
    
    # Severity classifications for negative sentiment risk keywords
    RISK_KEYWORDS = {
        "critical": ["recall", "hazard", "dangerous", "crack", "fire", "accident", "broken", "critical failure"],
        "severe": ["fail", "defect", "faulty", "poor quality", "failure", "broken", "leak"],
        "moderate": ["wear", "wearing out", "wearing too fast", "slow", "delay", "noisy", "rust", "friction"]
    }
    
    # Severity values to add to the risk score
    PENALTY_MAPPING = {
        "critical": 0.30,
        "severe": 0.15,
        "moderate": 0.08
    }

    def __init__(self, suppliers: List[Supplier]):
        self.suppliers = suppliers

    def parse_feedback(self, feedback_text: str) -> Dict[str, Any]:
        """
        Parses customer feedback text to identify the affected supplier and component,
        detect negative sentiment risk indicators, and calculate a risk penalty.
        
        Returns a dict summarizing the findings.
        """
        text_lower = feedback_text.lower()
        
        # 1. Identify Supplier by Name or ID
        matched_supplier: Optional[Supplier] = None
        for supplier in self.suppliers:
            # Match exact name (case-insensitive) or exact ID
            name_pattern = re.compile(rf"\b{re.escape(supplier.name.lower())}\b")
            id_pattern = re.compile(rf"\b{re.escape(supplier.id.lower())}\b")
            
            if name_pattern.search(text_lower) or id_pattern.search(text_lower):
                matched_supplier = supplier
                break
                
        # 2. Identify Component Type
        matched_component: Optional[str] = None
        # We can extract potential components from the supplier list
        component_types = list(set(s.component_type for s in self.suppliers))
        for comp in component_types:
            comp_pattern = re.compile(rf"\b{re.escape(comp.lower())}\b")
            if comp_pattern.search(text_lower):
                matched_component = comp
                break
                
        # 3. Scan for Sentiment Risk Keywords
        detected_keywords = []
        highest_severity = None
        total_penalty = 0.0
        
        for severity, keywords in self.RISK_KEYWORDS.items():
            for word in keywords:
                word_pattern = re.compile(rf"\b{re.escape(word)}\b")
                if word_pattern.search(text_lower):
                    detected_keywords.append(word)
                    total_penalty += self.PENALTY_MAPPING[severity]
                    if highest_severity is None or self.PENALTY_MAPPING[severity] > self.PENALTY_MAPPING[highest_severity]:
                        highest_severity = severity

        # Deduplicate keywords
        detected_keywords = list(set(detected_keywords))
        
        # 4. Apply changes if supplier found
        old_risk = None
        new_risk = None
        if matched_supplier and total_penalty > 0:
            old_risk = matched_supplier.risk_score
            # Dynamically update the supplier's risk score (clamped between 0.0 and 1.0)
            new_val = min(1.0, matched_supplier.risk_score + total_penalty)
            matched_supplier.risk_score = round(new_val, 4)
            new_risk = matched_supplier.risk_score

        return {
            "feedback": feedback_text,
            "matched_supplier": matched_supplier.name if matched_supplier else None,
            "supplier_id": matched_supplier.id if matched_supplier else None,
            "matched_component": matched_component,
            "sentiment_severity": highest_severity,
            "detected_keywords": detected_keywords,
            "risk_penalty": round(total_penalty, 4),
            "old_risk_score": old_risk,
            "new_risk_score": new_risk
        }
