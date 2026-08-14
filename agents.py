from typing import Optional
from pydantic import BaseModel
from models import Waypoint, RouteSegment, ToddlerConstraints, CostConstraints

class AgentResult(BaseModel):
    agent_name: str
    approved: bool
    score: float
    modifications_required: Optional[str] = None

class ToddlerWelfareAgent:
    def __init__(self, constraints: ToddlerConstraints):
        self.constraints = constraints

    def evaluate_segment(self, segment: RouteSegment) -> AgentResult:
        if segment.drive_time_hours > self.constraints.max_daily_drive_hours:
            return AgentResult(
                agent_name="ToddlerWelfareAgent",
                approved=False,
                score=0.2,
                modifications_required=f"Drive time ({segment.drive_time_hours}h) exceeds daily max of {self.constraints.max_daily_drive_hours}h. Inject a buffer town stay."
            )
        
        mods = None
        if segment.drive_time_hours > self.constraints.max_continuous_drive_hours:
            mods = "Force a 45-minute park/playground stop at the midpoint of this leg."
            
        return AgentResult(agent_name="ToddlerWelfareAgent", approved=True, score=0.9, modifications_required=mods)

class BudgetOptimizerAgent:
    def __init__(self, constraints: CostConstraints):
        self.constraints = constraints

    def evaluate_accommodation(self, destination: Waypoint, in_park_cost: float, gateway_town_cost: float) -> dict:
        """Determines if staying outside the park saves enough to justify the drive"""
        savings = in_park_cost - gateway_town_cost
        
        # If we prefer a kitchen (to prep toddler meals) and savings are significant
        if savings > 50.0 and self.constraints.prefer_kitchen:
            return {
                "stay_location": f"Gateway Town near {destination.name}",
                "approved": True,
                "savings": savings,
                "reason": f"Saves ${savings:.2f}/night & provides a kitchen for toddler meal prep."
            }
        
        return {
            "stay_location": destination.name,
            "approved": True,
            "savings": 0.0,
            "reason": "In-park convenience outweighs minor external savings."
        }