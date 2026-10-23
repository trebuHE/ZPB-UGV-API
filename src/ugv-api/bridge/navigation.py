"""Navigation action client wrapper for Nav2."""

import threading

from action_msgs.msg import GoalStatus
from api.models import Waypoint
from geometry_msgs.msg import PoseStamped
from nav2_msgs.action import NavigateToPose
from rclpy.action import ActionClient
from rclpy.node import Node

from bridge.utils import log_error, yaw_to_quaternion_z_w


class NavigationManager:
  """Manages Nav2 ActionClient for sending goals and navigating to poses."""

  def __init__(self, node: Node, namespace: str = ""):
    self._node = node
    self._ns = namespace

    self._nav_action_client = ActionClient(
      self._node,
      NavigateToPose,
      f"{self._ns}/navigate_to_pose",
    )

  def wait_for_server(self, timeout_sec: float = 2.0) -> bool:
    return self._nav_action_client.wait_for_server(timeout_sec=timeout_sec)

  def navigate_to_waypoint(self, wp: Waypoint) -> bool:
    """Sends a single waypoint to Nav2 NavigateToPose action and waits for result."""
    goal_msg = NavigateToPose.Goal()
    goal_msg.pose = PoseStamped()
    goal_msg.pose.header.frame_id = "panther/map"
    goal_msg.pose.header.stamp = self._node.get_clock().now().to_msg()
    goal_msg.pose.pose.position.x = float(wp.x)
    goal_msg.pose.pose.position.y = float(wp.y)
    goal_msg.pose.pose.position.z = 0.0

    z_quat, w_quat = yaw_to_quaternion_z_w(wp.yaw)
    goal_msg.pose.pose.orientation.z = z_quat
    goal_msg.pose.pose.orientation.w = w_quat

    goal_accepted_event = threading.Event()
    send_goal_future = self._nav_action_client.send_goal_async(goal_msg)
    send_goal_future.add_done_callback(lambda _: goal_accepted_event.set())

    goal_accepted_event.wait()
    goal_handle = send_goal_future.result()

    if not goal_handle.accepted:
      log_error(f"Goal for waypoint {wp.id} rejected by Nav2", logger=self._node.get_logger())
      return False

    result_event = threading.Event()
    result_future = goal_handle.get_result_async()
    result_future.add_done_callback(lambda _: result_event.set())

    result_event.wait()
    status = result_future.result().status
    return status == GoalStatus.STATUS_SUCCEEDED
