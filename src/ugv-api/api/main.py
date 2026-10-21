"""FastAPI application for the UGV API."""

from contextlib import asynccontextmanager

from api.models import CommandResult, MissionDefinition, MissionStatus, RobotState
from bridge.bridge import Bridge
from fastapi import FastAPI

BRIDGE = None


@asynccontextmanager
async def lifespan(app: FastAPI):
  global BRIDGE
  BRIDGE = Bridge(namespace="panther")
  yield
  BRIDGE.shutdown()


app = FastAPI(title="UGV API", lifespan=lifespan)


@app.get("/health")
def health():
  return {"status": "ok"}


@app.get("/state", response_model=RobotState)
def state():
  return BRIDGE.get_state()

@app.post("/e-stop/reset", response_model=CommandResult)
def reset_e_stop():
  result = BRIDGE.reset_e_stop()
  return result

@app.post("/mission/start", response_model=CommandResult)
def start_mission(mission: MissionDefinition):
  return BRIDGE.start_mission(mission=mission)

@app.get("/mission/status", response_model=MissionStatus)
def mission_status():
  return BRIDGE.get_mission_status()