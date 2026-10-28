# UGV API - Architecture

**Project goal:** An HTTP API to operate a Husarion Panther UGV (Gazebo simulation now, the physical robot later), executing waypoint-based navigation missions and synchronizing with an external measurement computer mounted on the robot.

## 1. Ground rules

- Husarion images (nav, docking, gazebo) are used **as-is** and are not modified. They come from the `panther-autonomy-pkg` submodule (a fork of the official template); only parameters/config files are adjusted.
- Project code lives in this repository under `src/ugv-api/`.
- External measurement scripts run on a dedicated, auxiliary payload computer (not on the UGV onboard computer).
- External scripts **never control robot motion** - they may read telemetry, use attached measurement devices and produce artifacts only.

## 2. Architecture

```
Operator / Dashboard ──┐
                       ├──► API Container (FastAPI + Bridge) ──► Husarion Stack (ROS 2 / DDS)
Payload Computer     ──┘        ├─ FastAPI (REST / State endpoints)
                                └─ Bridge (rclpy node + mission sequencer)
```

- **One new Docker image**, built on top of `ros:jazzy-ros-base`, run as a sidecar: `network_mode: host`, `ipc: host`, and the same CycloneDDS environment as the Husarion stack.
- **One process, two execution models**: The ROS 2 node runs in its own background thread (`rclpy.spin`), while FastAPI runs on the main `asyncio` event loop. Thread-safe synchronization events and locks isolate ROS callbacks from HTTP handlers.
- The **Bridge** encapsulates all robotics domain knowledge (topics, QoS, Nav2 action clients, lifecycle services). FastAPI endpoints interact with the bridge via high-level method calls and Pydantic data schemas.

## 3. Bridge → API contract

For a detailed specification of FastAPI endpoints, Pydantic data models, and the internal ROS 2 bridge modular architecture, see the [API Reference](./api-reference.md).

## 4. Missions and external scripts

- A mission is uploaded via HTTP as a YAML file (`/mission/upload`), parsed and validated against Pydantic models in the bridge.
- Mission sequencing (drive → wait → next waypoint) is handled by the **bridge** via Nav2 `NavigateToPose` actions, with runtime status tracked via `/mission/status`.
- Handshake Protocol at Waypoints:
  1. Bridge drives the robot to waypoint $N$.
  2. Upon arrival, the robot stops, and `MissionStatus.state` transitions to `WAITING_FOR_PAYLOAD` (with `current_waypoint_id` set to $N$).
  3. The external script on the payload computer detects arrival (via polling `GET /mission/status` or WebSocket events).
  4. The payload computer executes its local measurement routines independently.
  5. When finished, the payload computer calls `POST /mission/continue`.
  6. Bridge acknowledges the readiness signal, sets `MissionStatus.state` back to `RUNNING`, and proceeds to waypoint $N+1$.
- **Fault Tolerance:** Each waypoint can specify an optional `wait_timeout_sec`. If the payload computer fails to report readiness within this window, the mission can safely abort or transition to `FAILED`.

### Open questions (TBD)

- Network topology: IP configuration and static routing between the Panther onboard PC and the payload computer over the internal Ethernet switch.
- Timeout policy: Should a timeout from the payload computer trigger an emergency stop, abort the mission to `FAILED`, or skip to the next waypoint?
- Synchronization granularity: Does the payload computer also require synchronization for transit-phase measurements, or strictly stop-and-measure at waypoints?
