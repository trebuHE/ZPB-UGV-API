from typing import Dict, List, Optional
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from src.core.models import MeasurementConfig, MeasurementDefinition, ParamValue


class MeasurementDialog(QDialog):
  """Modal dialog to select a measurement script and parameter values for a waypoint."""

  def __init__(
      self,
      waypoint_id: int,
      definitions: List[MeasurementDefinition],
      current: Optional[MeasurementConfig] = None,
      parent: QWidget | None = None,
  ):
    super().__init__(parent)
    self.setWindowTitle(f"Waypoint #{waypoint_id} — Measurement")
    self.setMinimumWidth(360)

    self._definitions = definitions
    self._current = current
    self._param_widgets: Dict[str, QSpinBox | QDoubleSpinBox] = {}

    self._setup_ui()

  def _setup_ui(self):
    layout = QVBoxLayout(self)
    layout.setSpacing(12)

    layout.addWidget(QLabel("Select measurement to execute at this waypoint:"))

    self.combo = QComboBox()
    self.combo.addItem("None (Wait only)", None)
    selected_idx = 0
    for idx, defn in enumerate(self._definitions, start=1):
      self.combo.addItem(f"{defn.name} ({defn.id})", defn)
      if self._current is not None and defn.id == self._current.id:
        selected_idx = idx
    layout.addWidget(self.combo)

    self.params_group = QGroupBox("Parameters")
    self.params_layout = QFormLayout(self.params_group)
    layout.addWidget(self.params_group)

    buttons = QDialogButtonBox(
        QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
    )
    buttons.accepted.connect(self.accept)
    buttons.rejected.connect(self.reject)
    layout.addWidget(buttons)

    self.combo.currentIndexChanged.connect(self._rebuild_parameters)
    self.combo.setCurrentIndex(selected_idx)
    self._rebuild_parameters()

  def _rebuild_parameters(self):
    while self.params_layout.rowCount() > 0:
      self.params_layout.removeRow(0)
    self._param_widgets.clear()

    defn: Optional[MeasurementDefinition] = self.combo.currentData()
    if defn is None or not defn.parameters:
      self.params_group.setVisible(False)
      self.adjustSize()
      return

    self.params_group.setVisible(True)
    saved_params = (
        self._current.parameters
        if self._current is not None and self._current.id == defn.id
        else {}
    )

    for p_name, spec in defn.parameters.items():
      initial_val = saved_params.get(p_name, spec.default_val)
      if spec.is_int:
        widget = QSpinBox()
        widget.setRange(int(spec.min_val), int(spec.max_val))
        widget.setValue(int(initial_val))
      else:
        widget = QDoubleSpinBox()
        widget.setDecimals(3)
        widget.setRange(float(spec.min_val), float(spec.max_val))
        widget.setValue(float(initial_val))

      label = f"{p_name} [{spec.min_val}–{spec.max_val}]:"
      self.params_layout.addRow(label, widget)
      self._param_widgets[p_name] = widget

    self.adjustSize()

  def get_measurement(self) -> Optional[MeasurementConfig]:
    defn: Optional[MeasurementDefinition] = self.combo.currentData()
    if defn is None:
      return None

    params: Dict[str, ParamValue] = {
        p_name: widget.value() for p_name, widget in self._param_widgets.items()
    }
    return MeasurementConfig(id=defn.id, name=defn.name, parameters=params)