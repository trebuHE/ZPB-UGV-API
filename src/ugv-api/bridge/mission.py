"""Mission sequencing and background worker thread."""

import threading
import time

import yaml
from api.models import CommandResult, MissionDefinition, MissionState, MissionStatus
from rclpy.node import Node

from bridge.hardware import HardwareManager
from bridge.navigation import NavigationManager


class MissionManager:
  """Manages mission execution, validation, and threaded sequencing."""

  def __init__(self, node: Node, navigation: NavigationManager, hardware: HardwareManager):
    self._node = node
    self._navigation = navigation
    self._hardware = hardware

    self._mission_definition: MissionDefinition | None = None
    self._status = MissionStatus()
    self._mission_lock = threading.Lock()
    self._mission_thread: threading.Thread | None = None

  def _run_mission_sequence(self, mission: MissionDefinition):
    self._node.get_logger().info(f"Starting mission sequence: {mission.name}")
    try:
      for index, wp in enumerate(mission.waypoints):
        with self._mission_lock:
          self._status.current_waypoint_id = wp.id
          self._status.current_waypoint_index = index

        self._node.get_logger().info(f"Navigating to waypoint {wp.id} (x={wp.x}, y={wp.y})")
        success = self._navigation.navigate_to_waypoint(wp)

        if not success:
          with self._mission_lock:
            self._status.state = MissionState.FAILED
            self._status.error_message = f"Failed to reach waypoint {wp.id}"
          self._node.get_logger().error(f"Failed to reach waypoint {wp.id}")
          return

        

        self._node.get_logger().info(f"Reached waypoint {wp.id}. Waiting 2 seconds...")
        time.sleep(2.0)

      with self._mission_lock:
        self._status.state = MissionState.COMPLETED
      self._node.get_logger().info(f"Mission {mission.name} completed successfully")


    except Exception as e:  # noqa: BLE001
      with self._mission_lock:
        self._status.state = MissionState.FAILED
        self._status.error_message = f"Unexpected execution error: {e}"
      self._node.get_logger().error(f"Mission crashed: {e}")

  def load_mission(self, content: str) -> CommandResult:
    try:
      raw_data = yaml.safe_load(content)

    except yaml.YAMLError as e:
      return CommandResult(success=False, message=f"Invalid YAML Syntax: {e!s}")

    if not isinstance(raw_data, dict):
      return CommandResult(success=False, message="Invalid YAML structure. Root element must be a dictionary.")

    try:
      with self._mission_lock:
        self._mission_definition = MissionDefinition(**raw_data)

    except Exception as e:  # noqa: BLE001
      return CommandResult(success=False, message=f"Mission Schema Validation failed: {e!s}")

    return CommandResult(success=True, message=f"Mission {self._mission_definition.name} loaded successfully.")

  def start_mission(self, mission: MissionDefinition | None = None) -> CommandResult:
    with self._mission_lock:
      if mission is None:
        mission = self._mission_definition

      if self._status.state == MissionState.RUNNING:
        return CommandResult(success=False, message="Cannot start mission! One is already running.")

      nav_status = self._hardware.is_navigation_active()
      if not nav_status.success:
        return CommandResult(success=False, message=f"Navigation lifecycle inactive: {nav_status['message']}")

      slam_status = self._hardware.is_slam_active()
      if not slam_status.success:
        return CommandResult(success=False, message=f"SLAM lifecycle inactive: {slam_status['message']}")

      if not self._navigation.wait_for_server(timeout_sec=2.0):
        return CommandResult(success=False, message="Nav2 action server navigate_to_pose unavailable")

      self._status = MissionStatus(
        state=MissionState.RUNNING,
        mission_name=mission.name,
        current_waypoint_index=0,
        total_waypoints=len(mission.waypoints),
        current_waypoint_id=mission.waypoints[0].id,
      )

      self._mission_thread = threading.Thread(
        target=self._run_mission_sequence,
        args=(mission,),
        daemon=True,
      )
      self._mission_thread.start()

    return CommandResult(success=True, message=f"Mission {mission.name} accepted and started in a mission thread")

  @property
  def is_mission_loaded(self) -> bool:
    with self._mission_lock:
      return self._mission_definition is not None

  def get_status(self) -> MissionStatus:
    return self._status
