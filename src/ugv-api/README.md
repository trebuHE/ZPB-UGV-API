# UGV API

HTTP API for operating a Husarion Panther UGV (ROS 2 Jazzy). Runs as a Docker
sidecar next to the Husarion autonomy stack — see
[Architecture](../../docs/architecture.md) for the full design and
[ROS interface reference](../../docs/ros-interface.md) for the discovered topics,
services and actions.

## What this container does

- Exposes the robot state and mission control over HTTP (FastAPI).
- Translates API commands into ROS 2 actions/services via the internal bridge
  (rclpy node in the same process).
- Runs external measurement scripts at mission waypoints (planned).

## Build and run

Requires a running Husarion simulation stack first (`just start-simulation`
in `src/panther-autonomy-pkg/`).

```bash
# src/ugv-api$
docker compose -f compose.simulation.yaml build
docker compose -f compose.simulation.yaml up api
```

The API container uses `network_mode: host` and the same CycloneDDS setup as
the Husarion stack, so it discovers the robot's topics automatically.

## Development

Code directories (`api/`, `bridge/`) are mounted as volumes and served with
`uvicorn --reload`: code edits take effect without rebuilding the image.
Only changes to `requirements.txt` or the `Dockerfile` require a rebuild.

## Smoke test

With the simulation running and the API container up:

```bash
docker compose -f compose.simulation.yaml run --rm api \
bash -c "source /opt/ros/jazzy/setup.bash && ros2 topic list"
```

The output must contain `/panther/...` topics. This verifies DDS
connectivity between the sidecar and the Husarion stack.