"""Mission sequencing and background worker thread."""

import threading
import time

from api.models import MissionDefinition
from bridge.hardware import HardwareManager
from bridge.navigation import NavigationManager
from rclpy.node import Node


class MissionManager:
  """Manages mission execution, validation, and threaded sequencing."""

  def __init__(self, node: Node, navigation: NavigationManager, hardware: HardwareManager):
    self._node = node
    self._navigation = navigation
    self._hardware = hardware

    self._mission_lock = threading.Lock()
    self._is_mission_running = False
    self._mission_thread: threading.Thread | None = None

  def _run_mission_sequence(self, mission: MissionDefinition):
    self._node.get_logger().info(f"Starting mission sequence: {mission.name}")
    try:
      for wp in mission.waypoints:
        self._node.get_logger().info(f"Navigating to waypoint {wp.id} (x={wp.x}, y={wp.y})")
        success = self._navigation.navigate_to_waypoint(wp)
        if not success:
          self._node.get_logger().error(f"Mission failed at waypoint {wp.id}")
          return

        self._node.get_logger().info(f"Reached waypoint {wp.id}. Waiting 2 seconds...")
        time.sleep(2.0)

      self._node.get_logger().info(f"Mission {mission.name} completed successfully")
    finally:
      with self._mission_lock:
        self._is_mission_running = False

  def start_mission(self, mission: MissionDefinition) -> dict:
    with self._mission_lock:
      if self._is_mission_running:
        return {"success": False, "message": "Another mission is currently running"}

      nav_status = self._hardware.is_navigation_active()
      if not nav_status["success"]:
        return {"success": False, "message": f"Navigation lifecycle inactive: {nav_status['message']}"}

      slam_status = self._hardware.is_slam_active()
      if not slam_status["success"]:
        return {"success": False, "message": f"SLAM lifecycle inactive: {slam_status['message']}"}

      if not self._navigation.wait_for_server(timeout_sec=2.0):
        return {"success": False, "message": "Nav2 action server navigate_to_pose unavailable"}

      self._is_mission_running = True
      self._mission_thread = threading.Thread(
        target=self._run_mission_sequence,
        args=(mission,),
        daemon=True,
      )
      self._mission_thread.start()

    return {"success": True, "message": f"Mission {mission.name} accepted and started in a mission thread"}
