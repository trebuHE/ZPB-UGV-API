"""Utility functions and QoS definitions for the ROS 2 bridge."""

import math

from api.models import CommandResult
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy


def quaternion_to_yaw(x: float, y: float, z: float, w: float) -> float:
  """Convert quaternion components (x, y, z, w) to planar yaw angle in radians."""
  return math.atan2(
    2.0 * (w * z + x * y),
    1.0 - 2.0 * (y * y + z * z),
  )


def yaw_to_quaternion_z_w(yaw: float) -> tuple[float, float]:
  """Convert planar yaw angle in radians to quaternion (z, w) components assuming x=0, y=0."""
  half_yaw = yaw * 0.5
  return math.sin(half_yaw), math.cos(half_yaw)


def get_volatile_qos(depth: int = 10) -> QoSProfile:
  return QoSProfile(
    reliability=ReliabilityPolicy.RELIABLE,
    durability=DurabilityPolicy.VOLATILE,
    depth=depth,
  )


def get_latched_qos(depth: int = 1) -> QoSProfile:
  return QoSProfile(
    reliability=ReliabilityPolicy.RELIABLE,
    durability=DurabilityPolicy.TRANSIENT_LOCAL,
    depth=depth,
  )


def log_info(message: str, success: bool = True, logger=None) -> CommandResult:
  if logger is not None:
    logger.info(message)
  return CommandResult(success=success, message=message)


def log_warn(message: str, success: bool = False, logger=None) -> CommandResult:
  if logger is not None:
    logger.warn(message)  # noqa: G010
  return CommandResult(success=success, message=message)


def log_error(message: str, success: bool = False, logger=None) -> CommandResult:
  if logger is not None:
    logger.error(message)
  return CommandResult(success=success, message=message)
