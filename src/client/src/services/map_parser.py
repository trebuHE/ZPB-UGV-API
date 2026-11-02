from pathlib import Path
from typing import Optional
from PIL import Image
from src.core.models import MapData, MapMetadata
import yaml

class MapParser:

  @staticmethod
  def load_map_from_file_or_dir(target_path: Path) -> MapData:
    """Accepts either a directory containing a map or a direct path to a YAML file."""
    if not target_path.exists():
      raise FileNotFoundError(f"Path does not exist: {target_path}")

    yaml_path: Optional[Path] = None
    if target_path.is_dir():
      candidates = list(target_path.glob("*.yaml")) + list(
          target_path.glob("*.yml")
      )
      if not candidates:
        raise FileNotFoundError(f"No .yaml map files found in {target_path}")
      yaml_path = next((c for c in candidates if c.stem == "map"), candidates[0])
    else:
      if target_path.suffix.lower() not in [".yaml", ".yml"]:
        raise ValueError(f"Selected file is not a YAML file: {target_path.name}")
      yaml_path = target_path

    return MapParser._parse_yaml(yaml_path)

  @staticmethod
  def _parse_yaml(yaml_path: Path) -> MapData:
    with open(yaml_path, "r", encoding="utf-8") as f:
      data = yaml.safe_load(f)

    required_fields = ["image", "resolution", "origin"]
    missing = [field for field in required_fields if field not in data]
    if missing:
      raise ValueError(f"Invalid map YAML: missing fields {missing}")

    image_filename = data["image"]
    image_path = (yaml_path.parent / image_filename).resolve()
    if not image_path.exists():
      raise FileNotFoundError(
          f"Associated map image '{image_filename}' not found in"
          f" {yaml_path.parent}"
      )

    with Image.open(image_path) as img:
      width, height = img.size

    origin_raw = data["origin"]
    if len(origin_raw) < 3:
      raise ValueError("Map origin must contain [x, y, yaw]")

    metadata = MapMetadata(
        image_path=image_path,
        resolution=float(data["resolution"]),
        origin=(
            float(origin_raw[0]),
            float(origin_raw[1]),
            float(origin_raw[2]),
        ),
        negate=int(data.get("negate", 0)),
        occupied_thresh=float(data.get("occupied_thresh", 0.65)),
        free_thresh=float(data.get("free_thresh", 0.25)),
    )

    return MapData(
        metadata=metadata, image_width=width, image_height=height
    )