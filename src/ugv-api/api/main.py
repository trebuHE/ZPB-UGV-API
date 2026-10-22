"""FastAPI application for the UGV API."""

from contextlib import asynccontextmanager

import yaml
from api.models import CommandResult, MissionDefinition, MissionStatus, RobotState
from bridge.bridge import Bridge
from fastapi import FastAPI, File, HTTPException, UploadFile

BRIDGE = None
LOADED_MISSION: MissionDefinition | None = None

@asynccontextmanager
async def lifespan(app: FastAPI):
  global BRIDGE

  BRIDGE = Bridge(namespace="panther")
  yield
  BRIDGE.shutdown()


app = FastAPI(title="UGV API", lifespan=lifespan)


@app.post("/mission/upload", response_model=CommandResult)
async def mission_upload(file: UploadFile = File(...)):  # noqa: B008
  global LOADED_MISSION

  if not file.filename.endswith(('.yaml', '.yml')):
    raise HTTPException(status_code=400, detail="Invalid file type.")

  content = await file.read()
  LOADED_MISSION = parse_mission_yaml(content)

  return CommandResult(success=True, message=f"Mission {LOADED_MISSION.name} loaded successfully.")


@app.post("/mission/start", response_model=CommandResult)
def start_mission(mission: MissionDefinition | None = None):
  global LOADED_MISSION

  mission_to_run = mission if mission is not None else LOADED_MISSION

  if mission_to_run is None:
    raise HTTPException(
      status_code=400,
      detail="No mission provided and no mission currently loaded"
    )

  return BRIDGE.start_mission(mission=mission_to_run)


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


@app.get("/mission/status", response_model=MissionStatus)
def mission_status():
  return BRIDGE.get_mission_status()

'''Helper for parsing yaml file to MissionDefinition type'''
def parse_mission_yaml(content: str) -> MissionDefinition:
  try:
    raw_data = yaml.safe_load(content)
  
  except yaml.YAMLError as e:
    raise HTTPException(status_code = 400, detail=f"Invalid YAML syntax: {str(e)}.")

  if not isinstance(raw_data, dict):
    raise HTTPException(status_code=400, detail="Invalid YAML structure. Root element must be a dictionary.")

  try:
    return MissionDefinition(**raw_data)
  except Exception as e:
    raise HTTPException(status_code=422, detail=f"Mission schema validation failed: {str(e)}.")