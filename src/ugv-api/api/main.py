"""FastAPI application for the UGV API."""

from contextlib import asynccontextmanager

from api.models import CommandResult, MissionStatus, RobotState
from bridge.bridge import Bridge
from fastapi import FastAPI, File, HTTPException, UploadFile

BRIDGE = None

@asynccontextmanager
async def lifespan(app: FastAPI):
  global BRIDGE

  BRIDGE = Bridge(namespace="panther")
  yield
  BRIDGE.shutdown()


app = FastAPI(title="UGV API", lifespan=lifespan)


@app.post("/mission/upload", response_model=CommandResult)
async def mission_upload(file: UploadFile = File(...)):  # noqa: B008

  if not file.filename.endswith(('.yaml', '.yml')):
    raise HTTPException(status_code=400, detail="Invalid file type.")

  content = await file.read()

  return BRIDGE.load_mission(content)


@app.post("/mission/start", response_model=CommandResult)
def start_mission():
  return BRIDGE.start_mission()


@app.post("/map/upload", response_model=CommandResult)
async def map_upload(
    yaml_file: UploadFile = File(...),  # noqa: B008
    image_file: UploadFile = File(...),  # noqa: B008
):

  if not (yaml_file.filename or "").endswith(('.yaml', '.yml')):
    raise HTTPException(status_code=400, detail="Invalid map YAML file type.")

  yaml_content = await yaml_file.read()
  image_content = await image_file.read()

  return BRIDGE.upload_map(yaml_content, image_content, image_file.filename or "")


@app.post("/mission/stop", response_model=CommandResult)
def stop_mission():
  return BRIDGE.stop_mission()


@app.post("/mission/pause", response_model=CommandResult)
def pause_mission():
  return BRIDGE.pause_mission()


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


@app.post("/mission/continue", response_model=CommandResult)
def continue_mission(waypoint_id: str | None = None):
  return BRIDGE.continue_mission(waypoint_id)