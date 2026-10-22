"""ROS 2 bridge facade coordinating telemetry, hardware, navigation, and missions."""

import threading

import rclpy
import yaml
from api.models import CommandResult, MissionDefinition, MissionStatus, RobotState
from rclpy.node import Node

from bridge.hardware import HardwareManager
from bridge.mission import MissionManager
from bridge.navigation import NavigationManager
from bridge.telemetry import TelemetryManager


class Bridge:
  """Owns the rclpy node and delegates to modular manager components."""

  def __init__(self, namespace: str = "panther"):
    ns = f"/{namespace.strip('/')}" if namespace.strip("/") else ""

    if not rclpy.ok():
      rclpy.init()

    self._node = Node("ugv_api_bridge")

    self.telemetry = TelemetryManager(self._node, ns)
    self.hardware = HardwareManager(self._node, ns)
    self.navigation = NavigationManager(self._node, ns)
    self.mission = MissionManager(self._node, self.navigation, self.hardware)

    self.mission_definition: MissionDefinition | None = None

    self._thread = threading.Thread(
      target=rclpy.spin, args=(self._node,), daemon=True
    )
    self._thread.start()

  def get_state(self) -> RobotState:
    return self.telemetry.get_state()

  def trigger_e_stop(self, timeout_sec: float = 2.0) -> CommandResult:
    return self.hardware.trigger_e_stop(timeout_sec)

  def reset_e_stop(self, timeout_sec: float = 2.0) -> CommandResult:
    return self.hardware.reset_e_stop(timeout_sec)

  def is_navigation_active(self, timeout_sec: float = 2.0) -> CommandResult:
    return self.hardware.is_navigation_active(timeout_sec)

  def is_slam_active(self, timeout_sec: float = 2.0) -> CommandResult:
    return self.hardware.is_slam_active(timeout_sec)

  def load_mission(self, content: str) -> CommandResult:
    try:
      raw_data = yaml.safe_load(content)
    except yaml.YAMLError as e:
      return CommandResult(success=False, message=f"Invalid YAML Syntax: {str(e)}")

    if not isinstance(raw_data, dict):
      return CommandResult(success=False, message="Invalid YAML structure. Root element must be a dictionary.")

    try:
      self.mission_definition = MissionDefinition(**raw_data)
    except Exception as e:
      return CommandResult(success=False, message=f"Mission Schema Validation failed: {str(e)}")

    return CommandResult(success=True, message=f"Mission {self.mission_definition.name} loaded successfully.")

  def start_mission(self) -> CommandResult:
    if self.mission_definition is None:
      return CommandResult(success=False, message="Cannot start mission. No mission loaded.")

    return self.mission.start_mission(self.mission_definition)

  def get_mission_status(self) -> MissionStatus:
    return self.mission.get_status()

  def shutdown(self):
    if rclpy.ok():
      rclpy.try_shutdown()
    if self._thread.is_alive():
      self._thread.join(timeout=2.0)
    self._node.destroy_node()
