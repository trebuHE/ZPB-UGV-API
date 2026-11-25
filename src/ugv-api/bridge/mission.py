"""Mission sequencing and background worker thread."""

import threading

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
    self._continue_event = threading.Event()
    self._pause_resume_event = threading.Event()
    self._paused_while_waiting = False
    self._run_id = 0

  def _wait_for_resume(self, run_id: int) -> bool:
    while True:
      with self._mission_lock:
        if run_id != self._run_id:
          return False
        if self._status.state == MissionState.CANCELLED:
          return False
        if self._status.state != MissionState.PAUSED:
          return True
      self._pause_resume_event.wait()
      self._pause_resume_event.clear()

  def _run_mission_sequence(self, mission: MissionDefinition, run_id: int):
    logger = self._node.get_logger()
    log_info(f"Starting mission sequence: {mission.name}", logger=logger)
    try:
      for index, wp in enumerate(mission.waypoints):
        while True:
          with self._mission_lock:
            if run_id != self._run_id:
              return
            if self._status.state == MissionState.CANCELLED:
              log_info(f"Mission {mission.name} cancelled before waypoint {wp.id}", logger=logger)
              return
            paused = self._status.state == MissionState.PAUSED
            if not paused:
              self._status.current_waypoint_id = wp.id
              self._status.current_waypoint_index = index
              self._status.measurement_script = None

          if paused:
            log_info(f"Mission {mission.name} is paused before waypoint {wp.id}", logger=logger)
            if not self._wait_for_resume(run_id):
              return
            log_info(f"Resuming mission towards waypoint {wp.id}...", logger=logger)
            continue

          cancel_generation = self._navigation.get_cancel_generation()

          with self._mission_lock:
            if run_id != self._run_id:
              return
            if self._status.state == MissionState.CANCELLED:
              log_info(f"Mission {mission.name} cancelled before waypoint {wp.id}", logger=logger)
              return
            paused = self._status.state == MissionState.PAUSED
          if paused:
            continue

          log_info(f"Navigating to waypoint {wp.id} (x={wp.x}, y={wp.y})", logger=logger)
          success = self._navigation.navigate_to_waypoint(wp, cancel_generation)

          if success:
            break

          with self._mission_lock:
            if run_id != self._run_id:
              return
            state = self._status.state
            if state == MissionState.CANCELLED:
              log_info(f"Mission {mission.name} cancelled while navigating to waypoint {wp.id}", logger=logger)
              return
            generation_changed = cancel_generation != self._navigation.get_cancel_generation()
            if state != MissionState.PAUSED and not generation_changed:
              self._status.state = MissionState.FAILED
              self._status.error_message = f"Failed to reach waypoint {wp.id}"
              self._status.measurement_script = None
              failed = True
            else:
              failed = False

          if failed:
            log_error(f"Failed to reach waypoint {wp.id}", logger=logger)
            return

          if state == MissionState.PAUSED:
            log_info(f"Mission {mission.name} paused while navigating to waypoint {wp.id}", logger=logger)
            if not self._wait_for_resume(run_id):
              return
          log_info(f"Resuming mission towards waypoint {wp.id}...", logger=logger)

        if wp.wait:
          resumed = False
          while not resumed:
            with self._mission_lock:
              if run_id != self._run_id:
                return
              if self._status.state == MissionState.CANCELLED:
                log_info(f"Mission {mission.name} cancelled at waypoint {wp.id}", logger=logger)
                return
              self._continue_event.clear()
              if self._status.state == MissionState.PAUSED:
                self._paused_while_waiting = True
              else:
                self._paused_while_waiting = False
                self._status.state = MissionState.WAITING_AT_WAYPOINT
              self._status.measurement_script = wp.measurement_script
              paused = self._paused_while_waiting

            if paused:
              log_info(f"Reached waypoint {wp.id} while paused. Waiting for continue command...", logger=logger)
            else:
              log_info(f"Reached waypoint {wp.id}. Waiting for continue command...", logger=logger)
            self._continue_event.wait()

            with self._mission_lock:
              if run_id != self._run_id:
                return
              if self._status.state == MissionState.CANCELLED:
                log_info(f"Mission {mission.name} cancelled at waypoint {wp.id}", logger=logger)
                return
              if self._status.state == MissionState.PAUSED:
                continue
              self._paused_while_waiting = False
              self._status.state = MissionState.RUNNING
              self._status.measurement_script = None
              resumed = True

          log_info(f"Continuing mission from waypoint {wp.id}...", logger=logger)
        else:
          log_info(f"Reached waypoint {wp.id} (transition). Proceeding immediately...", logger=logger)

      with self._mission_lock:
        if run_id != self._run_id:
          return
        if self._status.state == MissionState.CANCELLED:
          log_info(f"Mission {mission.name} cancelled", logger=logger)
          return
        self._status.state = MissionState.COMPLETED
        self._status.measurement_script = None
        self._paused_while_waiting = False
      log_info(f"Mission {mission.name} completed successfully", logger=logger)

    except Exception as e:  # noqa: BLE001
      with self._mission_lock:
        if run_id != self._run_id:
          return
        if self._status.state == MissionState.CANCELLED:
          log_info(f"Mission {mission.name} cancelled", logger=logger)
          return
        self._status.state = MissionState.FAILED
        self._status.error_message = f"Unexpected execution error: {e}"
        self._status.measurement_script = None
        self._paused_while_waiting = False
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

      if self._status.state in (MissionState.RUNNING, MissionState.WAITING_AT_WAYPOINT, MissionState.PAUSED):
        return log_warn("Cannot start mission! One is already in progress.", logger=logger)

      nav_status = self._hardware.is_navigation_active()
      if not nav_status.success:
        return log_warn(f"Cannot start mission! Navigation lifecycle inactive: {nav_status.message}.", logger=logger)

      slam_status = self._hardware.is_slam_active()
      if not slam_status.success:
        return log_warn(f"Cannot start mission! SLAM lifecycle inactive: {slam_status.message}.", logger=logger)

      if not self._navigation.wait_for_server(timeout_sec=2.0):
        return log_warn("Cannot start mission! Nav2 action server navigate_to_pose unavailable.", logger=logger)

      if self._telemetry.get_state().e_stop:
        return log_warn("Cannot start mission! E-Stop is engaged.", logger=logger)

      self._run_id += 1
      run_id = self._run_id
      self._pause_resume_event.clear()
      self._continue_event.clear()
      self._paused_while_waiting = False
      self._status = MissionStatus(
        state=MissionState.RUNNING,
        mission_name=mission.name,
        current_waypoint_index=0,
        total_waypoints=len(mission.waypoints),
        current_waypoint_id=mission.waypoints[0].id,
      )

      self._mission_thread = threading.Thread(
        target=self._run_mission_sequence,
        args=(mission, run_id),
        daemon=True,
      )
      self._mission_thread.start()

    return log_info(f"Mission {mission.name} accepted and started in a mission thread", logger=logger)

  def pause(self) -> CommandResult:
    logger = self._node.get_logger()
    with self._mission_lock:
      if self._status.state not in (MissionState.RUNNING, MissionState.WAITING_AT_WAYPOINT):
        return log_warn(
          f"Cannot pause mission. No mission is running (current state: {self._status.state.value}).",
          logger=logger,
        )

      paused_while_waiting = self._status.state == MissionState.WAITING_AT_WAYPOINT
      self._pause_resume_event.clear()
      self._paused_while_waiting = paused_while_waiting
      self._status.state = MissionState.PAUSED
      waypoint_id = self._status.current_waypoint_id

    if not paused_while_waiting:
      self._navigation.cancel_current_goal()

    return log_info(f"Mission paused at waypoint '{waypoint_id}'.", logger=logger)

  def continue_mission(self, waypoint_id: str | None = None) -> CommandResult:
    logger = self._node.get_logger()
    with self._mission_lock:
      state = self._status.state
      if state not in (MissionState.WAITING_AT_WAYPOINT, MissionState.PAUSED):
        return log_warn(
          f"Cannot continue mission. Robot is not waiting or paused (current state: {state.value}).",
          logger=logger,
        )

      if waypoint_id is not None and self._status.current_waypoint_id != waypoint_id:
        return log_warn(
          f"Waypoint ID mismatch. Expected '{self._status.current_waypoint_id}', got '{waypoint_id}'.",
          logger=logger,
        )

      if state == MissionState.PAUSED:
        self._status.state = MissionState.RUNNING
        if self._paused_while_waiting:
          self._continue_event.set()
        else:
          self._pause_resume_event.set()
      else:
        self._continue_event.set()

      return log_info(
        f"Continuing mission from waypoint '{self._status.current_waypoint_id}'.",
        logger=logger,
      )

  def stop(self) -> CommandResult:
    logger = self._node.get_logger()
    with self._mission_lock:
      if self._status.state not in (MissionState.RUNNING, MissionState.WAITING_AT_WAYPOINT, MissionState.PAUSED):
        return log_warn(
          f"Cannot stop mission. No mission is running (current state: {self._status.state.value}).",
          logger=logger,
        )

      self._status.state = MissionState.CANCELLED
      self._status.measurement_script = None
      self._paused_while_waiting = False
      thread = self._mission_thread

    self._continue_event.set()
    self._pause_resume_event.set()
    self._navigation.cancel_current_goal()

    if thread is not None and thread.is_alive() and thread is not threading.current_thread():
      thread.join(timeout=2.0)

    return log_info("Mission cancelled and Nav2 goal cancellation requested.", logger=logger)

  @property
  def is_mission_loaded(self) -> bool:
    with self._mission_lock:
      return self._loaded_mission_definition is not None

  def get_status(self) -> MissionStatus:
    return self._status
