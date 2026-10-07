# Panther ROS Interface Reference

Observed ROS 2 interface of the Panther platform (simulation stack). This document serves as the basis for the bridge command/event dictionary(`src/ugv-api/bridge/`).

## Topics

| Topic | Message type | Rate | QoS | Notes |
|---|---|---|---|---|
| `/panther/odometry/wheels` | `nav_msgs/msg/Odometry` | 67 Hz | RELIABLE / VOLATILE / depth 1 | raw wheel-encoder odometry; drifts over time |
| `/panther/odometry/filtered` | `nav_msgs/msg/Odometry` | 31 Hz | RELIABLE / VOLATILE / depth 10 | EKF output (wheel + IMU fusion); **preferred source for the bridge** |
| `/panther/battery/battery_status`| `sensor_msgs/msg/BatteryState` | 28 Hz | RELIABLE / VOLATILE / depth 10 | battery vol, cap, % left, status|
| `/panther/hardware/e_stop` | `std_msgs/msg/Bool` | N/A | RELIABLE / TRANSIENT_LOCAL / depth 1 | E-Stop state| 

>RELIABLE - retransmits lost packets
>VOLATILE - subscribers get only the latest messages, no history
>TRANSIENT_LOCAL - transmits buffered messages to subscribers
>depth - number of messages kept in the buffer

### Commands used

```bash
ros2 topic info /panther/odometry/filtered --verbose   # type + QoS
ros2 topic hz /panther/odometry/filtered               # publish rate
```

## Actions

| Action | Type | Planned use |
|---|---|---|
| `/panther/navigate_to_pose` | `nav2_msgs/action/NavigateToPose` | core action for mission sequencing (drive to a single point) |
| `/panther/follow_waypoints` | `nav2_msgs/action/FollowWaypoints` | Nav2-native multi-waypoint traversal, less control over sequencing |
| `/panther/drive_on_heading` | `nav2_msgs/action/DriveOnHeading` | straight-line travel, has collision detection, may be used for testing and/or recovery behavior |
| `/panther/spin` | `nav2_msgs/action/Spin` | in-place rotation, has collisoin detection, may be used for waypoint actions |
| `/panther/wait` | `nav2_msgs/action/Wait` | timed wait, may be used for waypoint actions |
| `/panther/backup` | `nav2_msgs/action/BackUp` |straight-line backup, has **no** collision detection |

### Commands used

```bash
ros2 action info /panther/navigate_to_pose -t
ros2 interface show nav2_msgs/action/DriveOnHeading
```

## Services

TBD: `ros2 service list` — not yet surveyed.

## Frames

TBD — read from odometry messages: `header.frame_id` (expected: `panther/odom`)
and `child_frame_id` (expected: `panther/base_link`).
Mission waypoints are defined in the `map` frame; Nav2 performs the
transformation.

## Design decisions (from recon, 2026-10-07)

1. Mission sequencing is implemented in the **bridge** (not Nav2): loop of
   `navigate_to_pose` -> waypoint script -> next point. `follow_waypoints`
   is kept as a fallback option.
2. Telemetry source: `/panther/odometry/filtered` (not `wheels`).
3. Subscriber QoS must match the publisher's QoS, otherwise no data is
   received.