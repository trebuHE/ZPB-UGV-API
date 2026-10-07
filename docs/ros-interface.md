# Panther ROS Interface Reference

Observed ROS 2 interface of the Panther platform (simulation stack). This document serves as the basis for the bridge command/event dictionary(`src/ugv-api/bridge/`).

## Topics

| Topic | Message type | Rate | QoS (reliability / durability) | Notes |
|---|---|---|---|---|
| `/panther/odometry/wheels` | `nav_msgs/msg/Odometry` (TBD) | TBD | TBD | raw wheel-encoder odometry; drifts over time |
| `/panther/odometry/filtered` | `nav_msgs/msg/Odometry` (TBD) | TBD | TBD | EKF output (wheel + IMU fusion); **preferred source for the bridge** |
| `/panther/map` | TBD | — | TBD | occupancy map (SLAM/AMCL) |
| `/panther/map_updates` | TBD | — | TBD | incremental map updates |
| `/panther/plan` | TBD | — | TBD | Nav2 planner path |
| `/panther/plan_smoothed` | TBD | — | TBD | smoothed path |
| `/panther/optimal_trajectory` | TBD | — | TBD | controller trajectory |
| battery | TBD (`ros2 topic list \| grep -i batter`) | — | — | topic not yet identified |

### Commands used to fill TBD fields

```bash
ros2 topic info /panther/odometry/filtered --verbose   # type + QoS
ros2 topic hz /panther/odometry/filtered               # publish rate
```

## Actions

| Action | Type | Planned use |
|---|---|---|---|
| `/panther/navigate_to_pose` | `nav2_msgs/action/NavigateToPose` (TBD) | core action for mission sequencing (drive to a single point) |
| `/panther/follow_waypoints` | `nav2_msgs/action/FollowWaypoints` (TBD) | fallback: Nav2-native multi-waypoint traversal |
| `/panther/follow_path` | `nav2_msgs/action/FollowPath` | low level; not used directly |
| `/panther/drive_on_heading` | `nav2_msgs/action/DriveOnHeading` | straight-line travel |
| `/panther/spin` | `nav2_msgs/action/Spin` | in-place rotation; candidate for waypoint actions |
| `/panther/wait` | `nav2_msgs/action/Wait` | timed wait; candidate for waypoint actions |
| `/panther/compute_path_to_pose` | `nav2_msgs/action/ComputePathToPose` | planning only; not used directly |
| `/panther/compute_path_through_poses` | `nav2_msgs/action/ComputePathThroughPoses`| planning only |
| `/panther/smooth_path` | `nav2_msgs/action/SmoothPath` | planning only |
| `/panther/back` | TBD | TBD |
| `/panther/follow_gps_waypoints` | TBD | GPS-based; out of project scope |

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