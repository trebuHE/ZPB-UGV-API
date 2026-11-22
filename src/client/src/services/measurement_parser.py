from pathlib import Path
from typing import List
import yaml
from src.core.models import MeasurementDefinition, ParameterSpec


class MeasurementParser:
  """Parses measurement_definitions.yaml into typed MeasurementDefinition objects."""

  @staticmethod
  def load_from_file(yaml_path: Path) -> List[MeasurementDefinition]:
    if not yaml_path.exists():
      raise FileNotFoundError(f"Measurement definitions file not found: {yaml_path}")

    with open(yaml_path, "r", encoding="utf-8") as f:
      data = yaml.safe_load(f) or {}

    raw_measurements = data.get("measurements")
    if not isinstance(raw_measurements, list):
      raise ValueError("Invalid measurement definitions YAML: missing 'measurements' list.")

    definitions: List[MeasurementDefinition] = []
    for entry in raw_measurements:
      m_id = str(entry["id"])
      m_name = str(entry["name"])
      params: dict[str, ParameterSpec] = {}

      for p_name, p_cfg in (entry.get("parameters") or {}).items():
        p_min = p_cfg["min"]
        p_val = p_cfg["value"]
        p_max = p_cfg["max"]
        is_int = all(
            isinstance(v, int) and not isinstance(v, bool)
            for v in (p_min, p_val, p_max)
        )
        params[p_name] = ParameterSpec(
            name=p_name,
            min_val=int(p_min) if is_int else float(p_min),
            default_val=int(p_val) if is_int else float(p_val),
            max_val=int(p_max) if is_int else float(p_max),
            is_int=is_int,
        )

      definitions.append(
          MeasurementDefinition(id=m_id, name=m_name, parameters=params)
      )

    return definitions