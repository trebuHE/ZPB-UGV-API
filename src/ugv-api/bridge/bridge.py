"""ROS 2 bridge facade coordinating telemetry, hardware, navigation, and missions."""

import threading

import rclpy
from api.models import MissionDefinition, RobotState
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

    self._thread = threading.Thread(
      target=rclpy.spin, args=(self._node,), daemon=True
    )
    self._thread.start()

  def get_state(self) -> RobotState:
    return self.telemetry.get_state()

  def trigger_e_stop(self, timeout_sec: float = 2.0) -> dict:
    return self.hardware.trigger_e_stop(timeout_sec)

  def reset_e_stop(self, timeout_sec: float = 2.0) -> dict:
    return self.hardware.reset_e_stop(timeout_sec)

  def is_navigation_active(self, timeout_sec: float = 2.0) -> dict:
    return self.hardware.is_navigation_active(timeout_sec)

  def is_slam_active(self, timeout_sec: float = 2.0) -> dict:
    return self.hardware.is_slam_active(timeout_sec)

  def start_mission(self, mission: MissionDefinition) -> dict:
    return self.mission.start_mission(mission)

  def shutdown(self):
    if rclpy.ok():
      rclpy.try_shutdown()
    if self._thread.is_alive():
      self._thread.join(timeout=2.0)
    self._node.destroy_node()
