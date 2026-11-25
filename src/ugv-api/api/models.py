from enum import Enum
from typing import Any

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

class MeasurementScript(BaseModel):
  id: str
  name: str
  parameters: dict[str, Any] = Field(default_factory=dict)

class Waypoint(BaseModel):
  id: str
  x: float = Field(..., description="X coordinate in meters (positive ahead direction)")
  y: float = Field(..., description="Y coordinate in meters (positive left direction)")
  yaw: float = Field(default=0.0, description="Target angle in radians")
  wait: bool = Field(default=True, description="Whether the robot should wait at this waypoint for a continue command")
  measurement_script: MeasurementScript | None = Field(default=None, description="Optional measurement script configuration for this waypoint")

class MissionDefinition(BaseModel):
  name: str = Field(..., min_length=1)
  waypoints: list[Waypoint] = Field(..., min_length=1)

class MissionState(str, Enum):
  IDLE = "idle"
  RUNNING = "running"
  WAITING_AT_WAYPOINT = "waiting_at_waypoint"
  COMPLETED = "completed"
  FAILED = "failed"
  CANCELLED = "cancelled"

class MissionStatus(BaseModel):
  """Runtime status and execution progress of a mission."""
  state: MissionState = MissionState.IDLE
  mission_name: str | None = None
  current_waypoint_index: int = 0
  total_waypoints: int = 0
  current_waypoint_id: str | None = None
  measurement_script: MeasurementScript | None = None
  error_message: str | None = None

class CommandResult(BaseModel):
  """Standard response for commands and service triggers."""
  success: bool
  message: str