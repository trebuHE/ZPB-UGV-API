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