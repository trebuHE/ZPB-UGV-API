"""FastAPI application for the UGV API."""

from contextlib import asynccontextmanager

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


@app.get("/state")
def state():
  s = BRIDGE.get_state()
  if s is None:
    return {"error": "no odometry received yet"}
  return s