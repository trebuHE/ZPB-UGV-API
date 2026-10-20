"""Telemetry subscription and state caching for the robot."""

import copy
import threading

from api.models import RobotState
from nav_msgs.msg import Odometry
from rclpy.node import Node
from sensor_msgs.msg import BatteryState
from std_msgs.msg import Bool

from bridge.utils import get_latched_qos, get_volatile_qos, quaternion_to_yaw


class TelemetryManager:
  """Subscribes to robot telemetry topics and maintains thread-safe robot state."""

  def __init__(self, node: Node, namespace: str = ""):
    self._node = node
    self._ns = namespace
    self._lock = threading.Lock()

    self._pose = None
    self._battery = None
    self._e_stop = None

    volatile_qos = get_volatile_qos(depth=10)
    latched_qos = get_latched_qos(depth=1)

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

  def _on_odometry(self, msg: Odometry):
    p = msg.pose.pose.position
    q = msg.pose.pose.orientation
    yaw = quaternion_to_yaw(q.x, q.y, q.z, q.w)
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

  def get_state(self) -> RobotState:
    with self._lock:
      raw_state = {
        "pose": copy.deepcopy(self._pose),
        "battery": copy.deepcopy(self._battery),
        "e_stop": self._e_stop,
      }
      return RobotState.model_validate(raw_state)
