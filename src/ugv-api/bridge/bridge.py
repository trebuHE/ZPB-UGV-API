"""ROS 2 bridge: rclpy node exposing robot state, services, and mission control."""

import copy
import math
import threading
import time

import rclpy
from action_msgs.msg import GoalStatus
from api.models import MissionDefinition, RobotState, Waypoint
from geometry_msgs.msg import PoseStamped
from nav2_msgs.action import NavigateToPose
from nav_msgs.msg import Odometry
from rclpy.action import ActionClient
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

    self._mission_lock = threading.Lock()
    self._is_mission_running = False
    self._mission_thread: threading.Thread | None = None

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

    # Action clients
    self._nav_action_client = ActionClient(
      self._node,
      NavigateToPose,
      f"{self._ns}/navigate_to_pose",
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

  def _navigate_to_waypoint(self, wp:  Waypoint) -> bool:
    """Helper function that sends single waypoint to Nav2 NavigateToPose action."""
    goal_msg = NavigateToPose.Goal()
    goal_msg.pose = PoseStamped()
    goal_msg.pose.header.frame_id = "map"
    goal_msg.pose.header.stamp = self._node.get_clock().now().to_msg()
    goal_msg.pose.pose.position.x = float(wp.x)
    goal_msg.pose.pose.position.y = float(wp.y)
    goal_msg.pose.pose.position.z = 0.0

    # quaternion conversion
    half_yaw = wp.yaw * 0.5
    goal_msg.pose.pose.orientation.z = math.sin(half_yaw)
    goal_msg.pose.pose.orientation.w = math.cos(half_yaw)

    # send goal and set accepted callback
    goal_accepted_event = threading.Event()
    send_goal_future = self._nav_action_client.send_goal_async(goal_msg)
    send_goal_future.add_done_callback(lambda _: goal_accepted_event.set())

    goal_accepted_event.wait()
    goal_handle = send_goal_future.result()

    if not goal_handle.accepted:
      self._node.get_logger().error(f"Goal for waypoint {wp.id} rejected by Nav2")
      return False

    # set navigation result callback
    result_event = threading.Event()
    result_future = goal_handle.get_result_async()
    result_future.add_done_callback(lambda _: result_event.set())

    result_event.wait()
    status = result_future.result().status
    return status == GoalStatus.STATUS_SUCCEEDED

  def _run_mission_sequence(self, mission: MissionDefinition):
    self._node.get_logger().info(f"Starting mission sequence: {mission.name}")
    try:
      for wp in mission.waypoints:
        self._node.get_logger().info(f"Navigating to waypoint {wp.id} (x={wp.x}, y={wp.y})")
        success = self._navigate_to_waypoint(wp)
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

      nav_status = self.is_navigation_active()
      if not nav_status["success"]:
        return {"success": False, "message": f"Navigation lifecycle inactive: {nav_status['message']}"}

      slam_status = self.is_slam_active()
      if not slam_status["success"]:
        return {"success": False, "message": f"SLAM lifecycle inactive: {slam_status['message']}"}

      if not self._nav_action_client.wait_for_server(timeout_sec=2.0):
        return {"success": False, "message": "Nav2 action server navigate_to_pose unavailable"}

      self._is_mission_running = True
      self._mission_thread = threading.Thread(
        target=self._run_mission_sequence,
        args=(mission,),
        daemon=True,
      )
      self._mission_thread.start()

    return {"success": True, "message": f"Mission {mission.name} accepted and started in a mission thread"}
  
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