import yaml
import requests
from typing import List
from src.core.models import Waypoint


class APIClient:
  """HTTP communication handling with FastAPI"""

  def __init__(self, base_url: str = "http://localhost:8000"):
    self.base_url = base_url.rstrip("/")

  def upload_mission_data(self, name: str, waypoints: List[Waypoint]) -> dict:
    """Translates interactive UI waypoints into the YAML schema and uploads it."""
    url = f"{self.base_url}/mission/upload"

    # Format strictly to the API's expected Pydantic schema
    mission_dict = {
        "name": name,
        "waypoints": [
            {
                "id": str(wp.id),
                "x": float(round(wp.x, 3)),
                "y": float(round(wp.y, 3)),
                "yaw": float(round(wp.yaw, 3)),
                "wait": True  # Require robot to wait for /mission/continue
            }
            for wp in waypoints
        ],
    }

    # Generate YAML string in-memory
    yaml_content = yaml.dump(mission_dict, sort_keys=False)

    # Pass string buffer as an UploadFile equivalent
    files = {
        "file": (
            "interactive_mission.yaml",
            yaml_content.encode("utf-8"),
            "application/x-yaml",
        )
    }
    response = requests.post(url, files=files)

    response.raise_for_status()
    return response.json()

  def start_mission(self) -> dict:
    """Triggers the execution of the uploaded mission."""
    url = f"{self.base_url}/mission/start"
    response = requests.post(url)
    response.raise_for_status()
    return response.json()

  def continue_mission(self, waypoint_id: str | None = None) -> dict:
    """Tells the robot to proceed if waiting at a waypoint."""
    url = f"{self.base_url}/mission/continue"
    params = {"waypoint_id": waypoint_id} if waypoint_id else {}
    response = requests.post(url, params=params)
    response.raise_for_status()
    return response.json()