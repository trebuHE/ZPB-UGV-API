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
docker compose -f compose.api-sim.yaml build
docker compose -f compose.api-sim.yaml up api
```

The API container uses `network_mode: host` and the same CycloneDDS setup as
the Husarion stack, so it discovers the robot's topics automatically.

## Development

Code directories (`api/`, `bridge/`) are mounted as volumes and served with
`uvicorn --reload`: code edits take effect without rebuilding the image.
Only changes to `requirements.txt` or the `Dockerfile` require a rebuild.

Open the repository in VS Code with **Reopen in Container** to use the
development container (`compose.dev.yaml`, project name `ugv-api-dev`).

## Quick test

With the simulation running and the API container up:

```bash
curl http://localhost:8000/health   # {"status": "ok"}
curl http://localhost:8000/state    # current robot pose (x, y, yaw)
```

Values in `/state` must change while the robot moves in Gazebo/RViz.

## Troubleshooting

*Build fails with `additional privileges requested: pass "--allow=fs.read=..."`.* Known incompatibility between buildx >= 0.37.2 and Docker Compose
(< the release containing the fix for
[docker/compose#14285](https://github.com/docker/compose/issues/14285)) when the
Dockerfile lies outside the build context — which is always the case for
Dev Container builds. Workaround until Compose is updated:

```bash
export BUILDX_BAKE_ENTITLEMENTS_FS=0   # add to ~/.bashrc for persistence
```

Remove the variable once the installed Compose version includes the fix
(verify with `docker compose version`).