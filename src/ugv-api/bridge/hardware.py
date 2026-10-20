"""Hardware service clients and lifecycle checks for the robot."""

import threading

import rclpy
import rclpy.client
from rclpy.node import Node
from rclpy.task import Future
from std_srvs.srv import Trigger


class HardwareManager:
  """Manages ROS 2 service clients for e-stop and lifecycle state checks."""

  def __init__(self, node: Node, namespace: str = ""):
    self._node = node
    self._ns = namespace

    self._srv_e_stop_trigger = self._node.create_client(
      Trigger, f"{self._ns}/hardware/e_stop_trigger"
    )
    self._srv_e_stop_reset = self._node.create_client(
      Trigger, f"{self._ns}/hardware/e_stop_reset"
    )
    self._srv_nav_active = self._node.create_client(
      Trigger, f"{self._ns}/lifecycle_manager_navigation/is_active"
    )
    self._srv_slam_active = self._node.create_client(
      Trigger, f"{self._ns}/lifecycle_manager_slam/is_active"
    )

  def _call_trigger(self, client: rclpy.client.Client, timeout_sec: float = 2.0) -> dict:
    """Helper function that fires ROS 2 service trigger and waits for response with a timeout."""
    if not client.wait_for_service(timeout_sec=timeout_sec):
      return {"success": False, "message": f"Service {client.srv_name} unavailable"}

    event = threading.Event()
    future: Future = client.call_async(Trigger.Request())
    future.add_done_callback(lambda _: event.set())

    if not event.wait(timeout=timeout_sec):
      future.cancel()
      return {"success": False, "message": f"Service {client.srv_name} call timed out after {timeout_sec} seconds!"}

    res: Trigger.Response = future.result()
    return {"success": res.success, "message": res.message}

  def trigger_e_stop(self, timeout_sec: float = 2.0) -> dict:
    return self._call_trigger(self._srv_e_stop_trigger, timeout_sec)

  def reset_e_stop(self, timeout_sec: float = 2.0) -> dict:
    return self._call_trigger(self._srv_e_stop_reset, timeout_sec)

  def is_navigation_active(self, timeout_sec: float = 2.0) -> dict:
    return self._call_trigger(self._srv_nav_active, timeout_sec)

  def is_slam_active(self, timeout_sec: float = 2.0) -> dict:
    return self._call_trigger(self._srv_slam_active, timeout_sec)
