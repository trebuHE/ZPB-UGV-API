from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

@dataclass(frozen=True)
class Waypoint:
  id: int
  x: float  # World X in meters
  y: float  # World Y in meters
  yaw: float  # Heading in radians (-pi to pi)


@dataclass(frozen=True)
class MapMetadata:
  image_path: Path
  resolution: float  # meters per pixel
  origin: Tuple[float, float, float]  # [x, y, yaw]
  negate: int = 0
  occupied_thresh: float = 0.65
  free_thresh: float = 0.25


@dataclass
class MapData:
  metadata: MapMetadata
  image_width: int
  image_height: int

  def pixel_to_world(self, u: float, v: float) -> Tuple[float, float]:
    """Converts image coordinates (u, v) with top-left origin to real-world metric coordinates (Xw, Yw)."""
    origin_x, origin_y, _ = self.metadata.origin
    res = self.metadata.resolution
    x_w = origin_x + (u * res)
    y_w = origin_y + ((self.image_height - v) * res)
    return round(x_w, 4), round(y_w, 4)

  def world_to_pixel(self, x_w: float, y_w: float) -> Tuple[float, float]:
    """Converts real-world metric coordinates (Xw, Yw) to image pixel coordinates (u, v)."""
    origin_x, origin_y, _ = self.metadata.origin
    res = self.metadata.resolution
    u = (x_w - origin_x) / res
    v = self.image_height - ((y_w - origin_y) / res)
    return u, v