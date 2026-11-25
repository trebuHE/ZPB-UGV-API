"""Map file validation, storage, and Nav2 map_server loading."""

import os
import tempfile
import threading
from pathlib import Path

import yaml
from api.models import CommandResult
from nav2_msgs.srv import ClearEntireCostmap, LoadMap
from rclpy.node import Node

from bridge.utils import log_error, log_info, log_warn

ALLOWED_IMAGE_SUFFIXES = {".png", ".pgm", ".bmp"}
LOAD_MAP_TIMEOUT_SEC = 5.0
CLEAR_COSTMAP_TIMEOUT_SEC = 2.0


class MapManager:
  """Manages map file validation, storage, and Nav2 map_server loading."""

  def __init__(self, node: Node, namespace: str = "", map_dir: str | Path | None = None):
    self._node = node
    self._ns = namespace
    self._map_dir = Path(map_dir or os.environ.get("MAP_DIR", "/maps"))

    self._load_map_client = self._node.create_client(
      LoadMap, f"{self._ns}/map_server/load_map"
    )
    self._clear_global_costmap_client = self._node.create_client(
      ClearEntireCostmap, f"{self._ns}/global_costmap/clear_entirely_global_costmap"
    )
    self._clear_local_costmap_client = self._node.create_client(
      ClearEntireCostmap, f"{self._ns}/local_costmap/clear_entirely_local_costmap"
    )

  def is_ready(self, timeout_sec: float = 1.0) -> bool:
    return self._load_map_client.wait_for_service(timeout_sec=timeout_sec)

  def upload(
    self,
    yaml_content: bytes | str,
    image_content: bytes,
    image_filename: str,
  ) -> CommandResult:
    logger = self._node.get_logger()

    suffix = Path(image_filename).suffix.lower()
    if suffix not in ALLOWED_IMAGE_SUFFIXES:
      return log_error(
        f"Unsupported map image format '{suffix or image_filename}'."
        f" Expected one of: {', '.join(sorted(ALLOWED_IMAGE_SUFFIXES))}.",
        logger=logger,
      )

    try:
      raw_data = yaml.safe_load(yaml_content)
    except yaml.YAMLError as e:
      return log_error(f"Invalid map YAML syntax: {e!s}", logger=logger)

    if not isinstance(raw_data, dict):
      return log_error(
        "Invalid map YAML structure. Root element must be a dictionary.",
        logger=logger,
      )

    validation_error = self._validate_map_metadata(raw_data)
    if validation_error is not None:
      return log_error(validation_error, logger=logger)

    if not self.is_ready(timeout_sec=2.0):
      return log_error(
        "Cannot load map. Nav2 map_server is unavailable;"
        " navigation must run in localization mode (SLAM=False).",
        logger=logger,
      )

    self._map_dir.mkdir(parents=True, exist_ok=True)
    staging_root = self._map_dir / ".upload"
    staging_root.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(dir=staging_root) as tmp_dir:
      staging_dir = Path(tmp_dir)
      image_name = f"map{suffix}"
      staged_image_path = staging_dir / image_name
      staged_yaml_path = staging_dir / "map.yaml"

      staged_image_path.write_bytes(image_content)
      raw_data["image"] = image_name
      staged_yaml_path.write_text(
        yaml.safe_dump(raw_data, sort_keys=False),
        encoding="utf-8",
      )

      load_result = self._load_map(staged_yaml_path)
      if not load_result.success:
        return load_result

      staged_image_path.replace(self._map_dir / image_name)
      staged_yaml_path.replace(self._map_dir / "map.yaml")

    self._clear_costmaps()
    return log_info(
      f"Map loaded successfully from '{self._map_dir / 'map.yaml'}'.",
      logger=logger,
    )

  def _validate_map_metadata(self, raw_data: dict) -> str | None:
    missing_fields = [
      field for field in ("image", "resolution", "origin") if field not in raw_data
    ]
    if missing_fields:
      return f"Invalid map YAML: missing fields {missing_fields}."

    try:
      resolution = float(raw_data["resolution"])
    except (TypeError, ValueError):
      return "Invalid map YAML: resolution must be numeric."

    if resolution <= 0.0:
      return "Invalid map YAML: resolution must be greater than zero."

    origin = raw_data["origin"]
    if not isinstance(origin, (list, tuple)) or len(origin) < 3:
      return "Invalid map YAML: origin must contain [x, y, yaw]."

    try:
      [float(value) for value in origin[:3]]
    except (TypeError, ValueError):
      return "Invalid map YAML: origin values must be numeric."

    return None

  def _load_map(self, yaml_path: Path) -> CommandResult:
    logger = self._node.get_logger()
    request = LoadMap.Request()
    request.map_url = str(yaml_path)

    event = threading.Event()
    future = self._load_map_client.call_async(request)
    future.add_done_callback(lambda _: event.set())

    if not event.wait(timeout=LOAD_MAP_TIMEOUT_SEC):
      future.cancel()
      return log_error(
        f"Timed out waiting for Nav2 map_server to load '{yaml_path}'.",
        logger=logger,
      )

    response = future.result()
    if response.result != LoadMap.Response.RESULT_SUCCESS:
      return log_error(
        f"Nav2 map_server failed to load '{yaml_path}' (result code {response.result}).",
        logger=logger,
      )

    return log_info(f"Nav2 map_server loaded '{yaml_path}'.", logger=logger)

  def _clear_costmaps(self):
    logger = self._node.get_logger()
    for client in (
      self._clear_global_costmap_client,
      self._clear_local_costmap_client,
    ):
      if not client.service_is_ready():
        continue

      event = threading.Event()
      future = client.call_async(ClearEntireCostmap.Request())
      future.add_done_callback(lambda _: event.set())  # noqa: B023

      if not event.wait(timeout=CLEAR_COSTMAP_TIMEOUT_SEC):
        future.cancel()
        log_warn(f"Timed out clearing costmap service {client.srv_name}.", logger=logger)
