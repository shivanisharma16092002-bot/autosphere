from typing import List
from pydantic import BaseModel, Field

class MarketDemand(BaseModel):
    component_type: str = Field(..., description="Type of component demanded")
    target_cost: float = Field(..., gt=0.0, description="Target budget/cost per unit")
    required_quantity: int = Field(..., gt=0, description="Volume of units required")
    historical_demand: List[int] = Field(default_factory=list, description="List of past monthly demand values")
