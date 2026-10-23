"""Mission sequencing and background worker thread."""

import threading
import time

import yaml
from api.models import CommandResult, MissionDefinition, MissionState, MissionStatus
from rclpy.node import Node

from bridge.hardware import HardwareManager
from bridge.navigation import NavigationManager
from bridge.telemetry import TelemetryManager
from bridge.utils import log_error, log_info, log_warn


class MissionManager:
  """Manages mission execution, validation, and threaded sequencing."""

  def __init__(self, node: Node, navigation: NavigationManager, hardware: HardwareManager, telemetry: TelemetryManager):
    self._node = node
    self._navigation = navigation
    self._hardware = hardware
    self._telemetry = telemetry

    self._loaded_mission_definition: MissionDefinition | None = None
    self._status = MissionStatus()
    self._mission_lock = threading.Lock()
    self._mission_thread: threading.Thread | None = None

  def _run_mission_sequence(self, mission: MissionDefinition):
    logger = self._node.get_logger()
    log_info(f"Starting mission sequence: {mission.name}", logger=logger)
    try:
      for index, wp in enumerate(mission.waypoints):
        with self._mission_lock:
          self._status.current_waypoint_id = wp.id
          self._status.current_waypoint_index = index

        log_info(f"Navigating to waypoint {wp.id} (x={wp.x}, y={wp.y})", logger=logger)
        success = self._navigation.navigate_to_waypoint(wp)

        if not success:
          with self._mission_lock:
            self._status.state = MissionState.FAILED
            self._status.error_message = f"Failed to reach waypoint {wp.id}"
          log_error(f"Failed to reach waypoint {wp.id}", logger=logger)
          return

        log_info(f"Reached waypoint {wp.id}. Waiting 2 seconds...", logger=logger)
        time.sleep(2.0)

      with self._mission_lock:
        self._status.state = MissionState.COMPLETED
      log_info(f"Mission {mission.name} completed successfully", logger=logger)

    except Exception as e:  # noqa: BLE001
      with self._mission_lock:
        self._status.state = MissionState.FAILED
        self._status.error_message = f"Unexpected execution error: {e}"
      log_error(f"Mission crashed: {e}", logger=logger)

  def load(self, content: str) -> CommandResult:
    logger = self._node.get_logger()
    try:
      raw_data = yaml.safe_load(content)

    except yaml.YAMLError as e:
      return log_error(f"Invalid YAML Syntax: {e!s}", logger=logger)

    if not isinstance(raw_data, dict):
      return log_error("Invalid YAML structure. Root element must be a dictionary.", logger=logger)

    try:
      with self._mission_lock:
        self._loaded_mission_definition = MissionDefinition(**raw_data)

    except Exception as e:  # noqa: BLE001
      return log_error(f"Mission Schema Validation failed: {e!s}", logger=logger)

    return log_info(f"Mission {self._loaded_mission_definition.name} loaded successfully.", logger=logger)

  def start(self, mission: MissionDefinition | None = None) -> CommandResult:
    logger = self._node.get_logger()
    with self._mission_lock:
      if mission is None:
        mission = self._loaded_mission_definition

      if self._status.state == MissionState.RUNNING:
        return log_warn("Cannot start mission! One is already running.", logger=logger)

      nav_status = self._hardware.is_navigation_active()
      if not nav_status.success:
        return log_warn(f"Cannot start mission! Navigation lifecycle inactive: {nav_status.message}.", logger=logger)

      slam_status = self._hardware.is_slam_active()
      if not slam_status.success:
        return log_warn(f"Cannot start mission! SLAM lifecycle inactive: {slam_status.message}.", logger=logger)

      if not self._navigation.wait_for_server(timeout_sec=2.0):
        return log_warn("Cannot start mission! Nav2 action server navigate_to_pose unavailable.", logger=logger)

      if self._telemetry.get_state().e_stop:
        return log_warn("Cannot start mission! E-Stop is engaded.", logger=logger)
       
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

    return log_info(f"Mission {mission.name} accepted and started in a mission thread", logger=logger)

  @property
  def is_mission_loaded(self) -> bool:
    with self._mission_lock:
      return self._loaded_mission_definition is not None

  def get_status(self) -> MissionStatus:
    return self._status
