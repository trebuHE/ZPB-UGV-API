from typing import List
import requests
import yaml
from src.core.models import Waypoint


class APIClient:
  """HTTP communication handling with FastAPI."""

  def __init__(self, base_url: str = "http://localhost:8000"):
    self.base_url = base_url.rstrip("/")

  def upload_mission_data(self, name: str, waypoints: List[Waypoint]) -> dict:
    """Translates interactive UI waypoints into the YAML schema and uploads it."""
    url = f"{self.base_url}/mission/upload"

    serialized_waypoints = []
    for wp in waypoints:
      wp_dict = {
          "id": str(wp.id),
          "x": float(round(wp.x, 3)),
          "y": float(round(wp.y, 3)),
          "yaw": float(round(wp.yaw, 3)),
          "wait": bool(wp.wait),
      }
      if wp.measurement_script is not None:
        wp_dict["measurement_script"] = {
            "id": wp.measurement_script.id,
            "name": wp.measurement_script.name,
            "parameters": dict(wp.measurement_script.parameters),
        }
      serialized_waypoints.append(wp_dict)

    mission_dict = {
        "name": name,
        "waypoints": serialized_waypoints,
    }

    yaml_content = yaml.dump(mission_dict, sort_keys=False)
    files = {
        "file": (
            "interactive_mission.yaml",
            yaml_content.encode("utf-8"),
            "application/x-yaml",
        )
    }
    response = requests.post(url, files=files, timeout=5.0)
    response.raise_for_status()
    return response.json()

  def start_mission(self) -> dict:
    """Triggers execution of the uploaded mission."""
    url = f"{self.base_url}/mission/start"
    response = requests.post(url, timeout=5.0)
    response.raise_for_status()
    return response.json()

  def stop_mission(self) -> dict:
    """Requests cancellation of the currently running mission."""
    url = f"{self.base_url}/mission/stop"
    response = requests.post(url, timeout=5.0)
    response.raise_for_status()
    return response.json()

  def continue_mission(self, waypoint_id: str | None = None) -> dict:
    """Forces the mission to proceed from a waiting waypoint."""
    url = f"{self.base_url}/mission/continue"
    params = {"waypoint_id": waypoint_id} if waypoint_id else {}
    response = requests.post(url, params=params, timeout=5.0)
    response.raise_for_status()
    return response.json()