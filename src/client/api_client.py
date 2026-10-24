import requests
from pathlib import Path

class APIClient:
  '''HTTP communication handling with FastAPI'''
  def __init__(self, base_url: str):
    self.base_url = base_url.rstrip("/")

  def upload_mission(self, file_path: str) -> dict:
    url = f"{self.base_url}/mission/upload"
    path = Path(file_path)

    with open(path, "rb") as f:
      files = {"file": (path.name, f, "application/x-yaml")}
      response = requests.post(url, files=files)

    response.raise_for_status()
    return response.json()

  def start_mission(self) -> dict:
    url = f"{self.base_url}/mission/start"
    response = requests.post(url)

    response.raise_for_status()
    return response.json()
