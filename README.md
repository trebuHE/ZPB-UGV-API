# Team Research Project UGV API

This repository is a part of Team Reserch Project by students of Gdańsk University of Technology. The objective of the project is to implement mechanisms that allow for controlling an autonomous vehicle from an external application through a developed API.

## Scope

1. Getting familiar with the architecture of the selected autonomous vehicle control
system, e.g., ROS2/ArduPilot.
2. Proposing a communication method with the vehicle's operating system.
3. Developing the architecture and specification of the API.
4. Implementing intermediary mechanisms.
5. Implementing an example API client.

## Repo structure

- [`/deliverables`](./deliverables/) - contains project deliverables required by the university.
- [`/docs`](./docs/) - contains project documentation.
- [`/src/panther-autonomy-pkg`](./src/panther-autonomy-pkg/) - submodule with autonomy packages.
- [`/src/ugv-api/api`](./src/ugv-api/api/) - API code.
- [`/src/ugv-api/bridge`](./src/ugv-api/bridge/) - ROS2 bridge.

## Cloning

This repo has submodules, to clone the repo with all submodules use `git clone --recurse-submodules`.

## Quick start

Requires Docker with Compose, [`just`](https://github.com/casey/just), Python 3 with `venv`, and an X session for Gazebo. Configure the GPU in [`src/panther-autonomy-pkg/compose.simulation.yaml` (./src/panther-autonomy-pkg/compose.simulation.yaml) as described in its [README](./src/panther-autonomy-pkg/README.md).

From the repository root, start everything with a single command:

```bash
just start-all
```

This starts the Husarion simulation (`just start-simulation`), the API container (`compose.api-sim.yaml`), and the GUI client (`src/client/main.py`). The client's virtual environment is created automatically on first run.

Closing the client or the API and simulation containers. To leave them running, use `KEEP=1 just start-all`; stop them later with `just stop-all`.

## Authors

- [Hubert Mucha](https://github.com/trebuHE)
- [Adrian Czekański](https://github.com/401adii)