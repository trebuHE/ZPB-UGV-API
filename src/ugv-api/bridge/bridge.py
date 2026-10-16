"""ROS 2 bridge: rclpy node exposing robot state, services, and mission control."""

import copy
import math
import threading

import rclpy
from nav_msgs.msg import Odometry
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import BatteryState
from std_msgs.msg import Bool


class Bridge:
  """Owns the rclpy node and provides thread-safe access to robot state."""

  def __init__(self, namespace: str = "panther"):
    self._ns = f"/{namespace.strip('/')}" if namespace.strip("/") else ""
    self._lock = threading.Lock()
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


  def get_state(self) -> dict:
    with self._lock:
      return {
        "pose": copy.deepcopy(self._pose),
        "battery": copy.deepcopy(self._battery),
        "e_stop": self._e_stop,
      }

  def shutdown(self):
    if rclpy.ok():
      rclpy.try_shutdown()
    if self._thread.is_alive():
      self._thread.join(timeout=2.0)
    self._node.destroy_node()