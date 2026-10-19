from pydantic import BaseModel, Field


class PoseData(BaseModel):
  x: float
  y: float
  yaw: float
  frame: str
  stamp: float

class BatteryData(BaseModel):
  voltage: float
  current: float
  percentage: float
  status: int
  stamp: float

class RobotState(BaseModel):
  pose: PoseData | None = None
  battery: BatteryData | None = None
  e_stop: bool | None = None

class Waypoint(BaseModel):
  id: str
  x: float = Field(..., description="X coordinate in meters")
  y: float = Field(..., description="X coordinate in meters")
  yaw: float = Field(default=0.0, description="Target angle in radians")

class MissionDefinition(BaseModel):
  name: str = Field(..., min_length=1)
  waypoints: list[Waypoint] = Field(..., min_length=1)