from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from src.core.models import MapData
from src.ui.map_canvas import MapCanvas


class MissionPlannerView(QWidget):
  back_requested = Signal()

  def __init__(self, parent: QWidget | None = None):
    super().__init__(parent)
    self._map_data: MapData | None = None
    self._setup_ui()

  def _setup_ui(self):
    layout = QVBoxLayout(self)
    layout.setContentsMargins(0, 0, 0, 0)

    toolbar = QHBoxLayout()
    toolbar.setContentsMargins(12, 8, 12, 8)

    self.btn_back = QPushButton("← Change Map")
    self.btn_back.clicked.connect(self.back_requested.emit)
    toolbar.addWidget(self.btn_back)

    self.map_info_label = QLabel("No map loaded")
    self.map_info_label.setStyleSheet("font-weight: 500;")
    toolbar.addWidget(self.map_info_label)

    toolbar.addStretch()

    self.coord_label = QLabel("X: -- m | Y: -- m")
    self.coord_label.setStyleSheet("font-family: monospace;")
    toolbar.addWidget(self.coord_label)

    layout.addLayout(toolbar)

    self.canvas = MapCanvas(self)
    self.canvas.coordinates_hovered.connect(self._on_coords_hovered)
    self.canvas.canvas_clicked.connect(self._on_canvas_clicked)
    layout.addWidget(self.canvas)

  def set_map(self, map_data: MapData):
    self._map_data = map_data
    self.canvas.load_map(map_data)

    meta = map_data.metadata
    self.map_info_label.setText(
        f"Map: {meta.image_path.name} | Res: {meta.resolution}m/px | "
        f"Origin: ({meta.origin[0]}, {meta.origin[1]})"
    )

  def _on_coords_hovered(self, x: float, y: float):
    self.coord_label.setText(f"X: {x:+.2f} m | Y: {y:+.2f} m")

  def _on_canvas_clicked(self, x: float, y: float):
    # Hook for placing waypoints in subsequent steps
    print(f"User clicked metric coordinate: X={x}, Y={y}")