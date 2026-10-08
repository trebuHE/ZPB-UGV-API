# UGV API — Architecture

**Project goal:** an HTTP API to operate a Husarion Panther UGV (Gazebo simulation now, the physical robot later), including running missions defined as waypoint lists and executing external measurement scripts (Python) at and between waypoints.

## 1. Ground rules

- Husarion images (nav, docking, gazebo) are used **as-is** and are not modified. They come from the `panther-autonomy-pkg` submodule (a fork of the official template); only parameters/config files are adjusted.
- Project code lives in this repository under `src/ugv-api/`.
- External scripts **never control robot motion** - they may read telemetry, use attached measurement devices and produce artifacts only.

## 2. Architecture

```
Client (HTTP/WS) ──► API container (custom image) ──► Husarion images (DDS / ROS 2)
                       ├─ FastAPI
                       └─ Bridge  = rclpy node + mission logic
```

- **One new Docker image**, built on top of `ros:jazzy-ros-base`, run as a sidecar: `network_mode: host`, `ipc: host`, the same DDS (CycloneDDS) environment as the rest of the stack - it sees the robot's topics without any changes on the Husarion side.
- **One process, two loops**: the ROS node runs in its own thread, FastAPI in the main one. Contact points between them are plain function calls plus an event queue.
- The **Bridge** is a Python class (living inside the ROS node) that the FastAPI code imports like a regular library. All ROS knowledge (topics, QoS, Nav2, docking) stays exclusively in the bridge.

## 3. Bridge → API contract

**TBD**

## 4. Missions and external scripts

- A mission is a YAML/JSON file: a list of waypoints plus attached actions (`on_arrival`, `during_transit`).
- Mission sequencing (drive → execute → next) is handled by the **bridge**, not by Nav2.
- Scripts have **no access to motion control** - read-only telemetry, designated measurement devices and artifact output only.
- The runner guarantees: time/resource limits, log capture into the event stream, error handling (status ok/failed/timeout) and artifact storage via the API.

### Open questions (TBD)

- Isolation method for script execution (separate process vs dedicated container).
- Shape of the script SDK and script manifest.
- To be settled once the measurement hardware is chosen.

## 5. Next steps

- Dictionary of events and commands (full names and fields) — basis for implementation.
- Mission file schema (Pydantic/YAML).
- Measurement hardware on the robot → shape of the script SDK.