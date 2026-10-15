"""ROS 2 bridge: rclpy node exposing robot state and (later) mission control."""

import math
import threading

import rclpy
from nav_msgs.msg import Odometry
from rclpy.node import Node


class Bridge:
  """Owns the rclpy node and provides thread-safe access to robot state."""

  def __init__(self, namespace: str = "panther"):
    self._namespace = namespace
    self._lock = threading.Lock()
    self._state = None  # last odometry-derived state, dict or None

    rclpy.init()
    self._node = Node("ugv_api_bridge")
    
    # Topic names include the namespace prefix, e.g. /panther/odometry/filtered
    self._node.create_subscription(
      Odometry,
      f"/{namespace}/odometry/filtered",
      self._on_odometry,
      10,
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
      self._state = {
        "x": p.x,
        "y": p.y,
        "yaw": yaw,
        "frame": msg.header.frame_id,
        "stamp": msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9,
      }

  def get_state(self):
    with self._lock:
      return dict(self._state) if self._state else None

  def shutdown(self):
    self._node.destroy_node()
    rclpy.try_shutdown()