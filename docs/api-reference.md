# UGV API & Bridge Reference

This document provides a comprehensive reference for the FastAPI endpoints, Pydantic data models, and the internal ROS 2 bridge interface.

## 1. FastAPI Endpoints (`src/ugv-api/api/main.py`)

| Endpoint | Method | Request Body | Response | Description |
|---|---|---|---|---|
| `/health` | `GET` | None | `dict` (`{"status": "ok"}`) | Basic health check for the API sidecar container. |
| `/state` | `GET` | None | [`RobotState`](#2-pydantic-models) | Returns the current cached state of the robot (pose, battery, e-stop). |
| `/e-stop/reset` | `POST` | None | [`CommandResult`](#2-pydantic-models) | Triggers the E-Stop reset service on the UGV hardware interface. |
| `/mission/start` | `POST` | [`MissionDefinition`](#2-pydantic-models) | [`CommandResult`](#2-pydantic-models) | Validates Nav2 & SLAM readiness, checks action servers, and initiates mission execution in a background worker thread. |
| `/mission/status` | `GET` | None | [`MissionStatus`](#2-pydantic-models) | Returns current runtime execution state and progress of the active mission. |


## 2. Pydantic Models (`src/ugv-api/api/models.py`)

### `PoseData`
- `x`: `float` - X coordinate in meters.
- `y`: `float` - Y coordinate in meters.
- `yaw`: `float` - Orientation angle in radians.
- `frame`: `str` - ROS coordinate frame ID (e.g. `panther/map`).
- `stamp`: `float` - Timestamp (seconds elapsed).

### `BatteryData`
- `voltage`: `float` - Battery voltage.
- `current`: `float` - Current draw.
- `percentage`: `float` - Remaining battery percentage (0-100).
- `status`: `int` - Power supply status code.
- `stamp`: `float` - Timestamp (seconds elapsed).

### `RobotState`
- `pose`: [`PoseData`](#posedata) | `None` - Current robot pose from odometry filter.
- `battery`: [`BatteryData`](#batterydata) | `None` - Battery status readings.
- `e_stop`: `bool` | `None` - Emergency stop active status.

### `Waypoint`
- `id`: `str` - Unique waypoint identifier.
- `x`: `float` - Target X coordinate in meters (positive ahead direction).
- `y`: `float` - Target Y coordinate in meters (positive left direction).
- `yaw`: `float` - Target angle in radians (default: `0.0`).

### `MissionDefinition`
- `name`: `str` - Mission name (minimum length: 1).
- `waypoints`: `list[`[`Waypoint`](#waypoint)`]` - Ordered list of waypoints to visit (minimum length: 1).

### `MissionState` (Enum)
- `IDLE` (`"idle"`)
- `RUNNING` (`"running"`)
- `COMPLETED` (`"completed"`)
- `FAILED` (`"failed"`)
- `CANCELLED` (`"cancelled"`)

### `MissionStatus`
- `state`: [`MissionState`](#missionstate-enum) - Current state of the mission.
- `mission_name`: `str` | `None` - Active mission name.
- `current_waypoint_index`: `int` - Index of the waypoint currently being targeted.
- `total_waypoints`: `int` - Total count of waypoints in the mission.
- `current_waypoint_id`: `str` | `None` - ID of the waypoint currently being targeted.
- `error_message`: `str` | `None` - Error message if the mission failed.

### `CommandResult`
- `success`: `bool` - Indicates if the operation succeeded.
- `message`: `str` - Descriptive message or error details.


## 3. ROS 2 Bridge Interface (`src/ugv-api/bridge/`)

The `Bridge` class acts as a facade, owning the single `rclpy` node and background spin thread while delegating specific responsibilities to modular managers:

- **`TelemetryManager` (`telemetry.py`)**: Subscribes to `/panther/odometry/filtered`, `/panther/battery/battery_status`, and `/hardware/e_stop`, caching thread-safe state snapshots.
- **`HardwareManager` (`hardware.py`)**: Manages service clients for E-stop triggers/resets and Nav2 / SLAM lifecycle manager activity probes (`CommandResult` return values).
- **`NavigationManager` (`navigation.py`)**: Wraps the Nav2 `NavigateToPose` action client for waypoint traversal.
- **`MissionManager` (`mission.py`)**: Manages mission validation checks, execution status tracking, and spawns background threads to sequence waypoint navigation.
- **`utils.py`**: Provides quaternion-to-yaw math utilities and reusable QoS profiles.
