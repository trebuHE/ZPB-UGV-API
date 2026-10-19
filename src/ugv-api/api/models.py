from pydantic import BaseModel


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