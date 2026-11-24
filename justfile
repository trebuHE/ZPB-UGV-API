set shell := ["bash", "-euo", "pipefail", "-c"]

# Start simulation, API container and GUI client, then clean up on exit
start-all:
    ./scripts/start-all.sh

# Stop the API and simulation containers
stop-all:
    docker compose -f src/ugv-api/compose.api-sim.yaml down
    cd src/panther-autonomy-pkg && docker compose -f compose.simulation.yaml down
