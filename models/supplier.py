from pydantic import BaseModel, Field, field_validator

class Supplier(BaseModel):
    id: str = Field(..., description="Unique supplier identifier")
    name: str = Field(..., description="Name of the supplier company")
    location: str = Field(..., description="Geographical location of the supplier")
    component_type: str = Field(..., description="Type of automotive component supplied (e.g. Brake Pads, Microchips)")
    base_cost: float = Field(..., gt=0.0, description="Base manufacturing/supply cost per unit")
    risk_score: float = Field(..., ge=0.0, le=1.0, description="Risk index between 0.0 (no risk) and 1.0 (extreme risk)")
    capacity: int = Field(..., gt=0, description="Maximum monthly production capacity in units")

    @field_validator("risk_score")
    @classmethod
    def validate_risk_score(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError("risk_score must be between 0.0 and 1.0")
        return round(v, 4)
