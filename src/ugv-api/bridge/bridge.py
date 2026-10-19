"""ROS 2 bridge: rclpy node exposing robot state, services, and mission control."""

import copy
import math
import threading

import rclpy
from api.models import RobotState
from nav_msgs.msg import Odometry
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from rclpy.task import Future
from sensor_msgs.msg import BatteryState
from std_msgs.msg import Bool
from std_srvs.srv import Trigger


class Bridge:
  """Owns the rclpy node and provides thread-safe access to robot state."""

  def __init__(self, namespace: str = "panther"):
    self._ns = f"/{namespace.strip('/')}" if namespace.strip("/") else ""
    self._lock = threading.Lock()
    self._robot_state: RobotState = None
    self._pose = None
    self._battery =  None
    self._e_stop = None

    if not rclpy.ok():
      rclpy.init()
    
    self._node = Node("ugv_api_bridge")

    volatile_qos = QoSProfile(
      reliability = ReliabilityPolicy.RELIABLE,
      durability = DurabilityPolicy.VOLATILE,
      depth = 10,
    )

    latched_qos = QoSProfile(
      reliability = ReliabilityPolicy.RELIABLE,
      durability = DurabilityPolicy.TRANSIENT_LOCAL,
      depth = 1,
    )

    # Topic subscriptions
    self._node.create_subscription(
      Odometry,
      f"{self._ns}/odometry/filtered",
      self._on_odometry,
      volatile_qos,
    )

    self._node.create_subscription(
      BatteryState,
      f"{self._ns}/battery/battery_status",
      self._on_battery,
      volatile_qos,
    )

    self._node.create_subscription(
      Bool,
      f"{self._ns}/hardware/e_stop",
      self._on_e_stop,
      latched_qos,
    )

    self._thread = threading.Thread(
        target=rclpy.spin, args=(self._node,), daemon=True
      )
    self._thread.start()

    # Service clients
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

  def _on_odometry(self, msg: Odometry):
    p = msg.pose.pose.position
    q = msg.pose.pose.orientation
    yaw = math.atan2(
      2.0 * (q.w * q.z + q.x * q.y),
      1.0 - 2.0 * (q.y * q.y + q.z * q.z),
    )
    with self._lock:
      self._pose = {
        "x": p.x,
        "y": p.y,
        "yaw": yaw,
        "frame": msg.header.frame_id,
        "stamp": msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9,
      }

  def _on_battery(self, msg: BatteryState):
    with self._lock:
      self._battery = {
        "voltage": msg.voltage,
        "current": msg.current,
        "percentage": msg.percentage,
        "status": msg.power_supply_status,
        "stamp": msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9,
      }

  def _on_e_stop(self, msg: Bool):
    with self._lock:
      self._e_stop = msg.data

  def _call_trigger(self, client: rclpy.client.Client, timeout_sec: float = 2.0) -> dict:
    """Helper function that fires ROS2 service trigger and waits for the response with a timeout."""
    
    # Check if ROS2 service is avaliable
    if not client.wait_for_service(timeout_sec=timeout_sec):
      return {"success": False, "message": f"Service {client.srv_name} unavailable"}

    event = threading.Event()

    future: Future = client.call_async(Trigger.Request())
    future.add_done_callback(lambda _: event.set())

    # Timeout
    if not event.wait(timeout=timeout_sec):
      future.cancel()
      return {"success": False, "message": f"Service {client.srv_name} call timed out after {timeout_sec} seconds!"}

    res: Trigger.Response = future.result()
    return {"success": res.success, "message": res.message}

  def get_state(self) -> RobotState:
    with self._lock:
      raw_state = {
        "pose": copy.deepcopy(self._pose),
        "battery": copy.deepcopy(self._battery),
        "e_stop": self._e_stop,
      }
      return RobotState.model_validate(raw_state)

  def trigger_e_stop(self, timeout_sec: float = 2.0) -> dict:
    return self._call_trigger(self._srv_e_stop_trigger, timeout_sec)

  def reset_e_stop(self, timeout_sec: float = 2.0) -> dict:
    return self._call_trigger(self._srv_e_stop_reset, timeout_sec)

  def is_navigation_active(self, timeout_sec: float = 2.0) -> dict:
    return self._call_trigger(self._srv_nav_active, timeout_sec)

  def is_slam_active(self, timeout_sec: float = 2.0) -> dict:
    return self._call_trigger(self._srv_slam_active, timeout_sec)

  def shutdown(self):
    if rclpy.ok():
      rclpy.try_shutdown()
    if self._thread.is_alive():
      self._thread.join(timeout=2.0)
    self._node.destroy_node()