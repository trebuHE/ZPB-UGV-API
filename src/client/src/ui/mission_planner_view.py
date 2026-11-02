from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from src.core.models import MapData, Waypoint

try:
  from src.ui.map_canvas import CanvasMode, MapCanvas
except ImportError:
  from src.ui.map_canvas import CanvasMode, MapCanvas


class MissionPlannerView(QWidget):
  back_requested = Signal()

  def __init__(self, parent: QWidget | None = None):
    super().__init__(parent)
    self._map_data: MapData | None = None
    self._setup_ui()

  def _setup_ui(self):
    main_layout = QVBoxLayout(self)
    main_layout.setContentsMargins(0, 0, 0, 0)
    main_layout.setSpacing(0)

    # -------------------------------------------------------------
    # 1. TOP TOOLBAR (Locked to 48px height)
    # -------------------------------------------------------------
    toolbar_frame = QFrame()
    toolbar_frame.setFixedHeight(48)
    toolbar_frame.setSizePolicy(
        QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
    )
    toolbar_frame.setStyleSheet("""
            QFrame {
                background-color: #f8f9fa;
                border-bottom: 1px solid #dee2e6;
            }
            QPushButton {
                padding: 5px 12px;
                border: 1px solid #ced4da;
                border-radius: 4px;
                background-color: #ffffff;
                font-weight: 500;
            }
            QPushButton:checked {
                background-color: #007ACC;
                color: white;
                border-color: #005999;
            }
            QPushButton:hover:!checked {
                background-color: #e9ecef;
            }
        """)

    toolbar = QHBoxLayout(toolbar_frame)
    toolbar.setContentsMargins(12, 0, 12, 0)
    toolbar.setAlignment(Qt.AlignmentFlag.AlignVCenter)
    toolbar.setSpacing(8)

    self.btn_back = QPushButton("← Change Map")
    self.btn_back.clicked.connect(self.back_requested.emit)
    toolbar.addWidget(self.btn_back)

    toolbar.addWidget(QLabel("|"))

    self.mode_group = QButtonGroup(self)
    self.btn_pan = QPushButton("Pan Map")
    self.btn_pan.setCheckable(True)
    self.btn_pan.setChecked(True)
    self.mode_group.addButton(self.btn_pan)
    toolbar.addWidget(self.btn_pan)

    self.btn_add_wp = QPushButton("📍 Add Waypoints")
    self.btn_add_wp.setCheckable(True)
    self.mode_group.addButton(self.btn_add_wp)
    toolbar.addWidget(self.btn_add_wp)

    self.btn_pan.clicked.connect(
        lambda: self.canvas.set_mode(CanvasMode.PAN)
    )
    self.btn_add_wp.clicked.connect(
        lambda: self.canvas.set_mode(CanvasMode.ADD_WAYPOINT)
    )

    toolbar.addWidget(QLabel("|"))

    self.btn_fit = QPushButton("Fit to View")
    self.btn_fit.clicked.connect(self._on_fit_view)
    toolbar.addWidget(self.btn_fit)

    self.btn_undo = QPushButton("Undo")
    self.btn_undo.clicked.connect(self._on_undo)
    toolbar.addWidget(self.btn_undo)

    self.btn_clear = QPushButton("Clear All")
    self.btn_clear.clicked.connect(self._on_clear)
    toolbar.addWidget(self.btn_clear)

    toolbar.addStretch()

    self.coord_label = QLabel("X: -- m | Y: -- m")
    self.coord_label.setStyleSheet(
        "font-family: monospace; font-size: 13px;"
    )
    toolbar.addWidget(self.coord_label)

    # Stretch factor 0: never expands vertically
    main_layout.addWidget(toolbar_frame, 0)

    # -------------------------------------------------------------
    # 2. MAIN SPLITTER (Absorbs 100% of remaining vertical space)
    # -------------------------------------------------------------
    self.splitter = QSplitter(Qt.Orientation.Horizontal)
    self.splitter.setSizePolicy(
        QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
    )
    self.splitter.setHandleWidth(4)

    # Left Canvas
    self.canvas = MapCanvas(self)
    self.canvas.coordinates_hovered.connect(self._on_coords_hovered)
    self.canvas.waypoint_added.connect(self._on_waypoint_added)
    self.canvas.waypoints_cleared.connect(self._on_waypoints_cleared)
    self.splitter.addWidget(self.canvas)

    # Right Dock
    side_panel = QFrame()
    side_panel.setFrameShape(QFrame.Shape.StyledPanel)
    side_panel.setStyleSheet("background-color: #ffffff;")
    side_panel.setMinimumWidth(280)
    side_panel.setMaximumWidth(420)

    side_layout = QVBoxLayout(side_panel)
    side_layout.setContentsMargins(12, 12, 12, 12)
    side_layout.setSpacing(8)

    table_title = QLabel("Mission Waypoints")
    table_title.setStyleSheet("font-weight: bold; font-size: 14px;")
    side_layout.addWidget(table_title)

    self.table = QTableWidget(0, 4)
    self.table.setHorizontalHeaderLabels(
        ["#", "X (m)", "Y (m)", "Yaw (rad)"]
    )
    self.table.horizontalHeader().setSectionResizeMode(
        0, QHeaderView.ResizeMode.ResizeToContents
    )
    self.table.horizontalHeader().setSectionResizeMode(
        1, QHeaderView.ResizeMode.Stretch
    )
    self.table.horizontalHeader().setSectionResizeMode(
        2, QHeaderView.ResizeMode.Stretch
    )
    self.table.horizontalHeader().setSectionResizeMode(
        3, QHeaderView.ResizeMode.Stretch
    )
    self.table.verticalHeader().setVisible(False)
    self.table.setAlternatingRowColors(True)
    side_layout.addWidget(self.table)

    self.splitter.addWidget(side_panel)
    self.splitter.setSizes([900, 300])

    # Stretch factor 1: absorbs all remaining window height
    main_layout.addWidget(self.splitter, 1)

  def set_map(self, map_data: MapData):
    self._map_data = map_data
    self.canvas.load_map(map_data)
    self.btn_pan.setChecked(True)
    self.canvas.set_mode(CanvasMode.PAN)
    self.table.setRowCount(0)
    self._on_fit_view()

  def _on_fit_view(self):
    if self._map_data:
      self.canvas.fitInView(
          self.canvas.scene().sceneRect(), Qt.AspectRatioMode.KeepAspectRatio
      )

  def _on_coords_hovered(self, x: float, y: float):
    self.coord_label.setText(f"X: {x:+.2f} m | Y: {y:+.2f} m")

  def _on_waypoint_added(self, wp: Waypoint):
    row = self.table.rowCount()
    self.table.insertRow(row)
    self.table.setItem(row, 0, QTableWidgetItem(str(wp.id)))
    self.table.setItem(row, 1, QTableWidgetItem(f"{wp.x:.2f}"))
    self.table.setItem(row, 2, QTableWidgetItem(f"{wp.y:.2f}"))
    self.table.setItem(row, 3, QTableWidgetItem(f"{wp.yaw:.2f}"))

  def _on_undo(self):
    self.canvas.undo_last_waypoint()
    current_rows = self.table.rowCount()
    if current_rows > 0:
      self.table.removeRow(current_rows - 1)

  def _on_clear(self):
    self.canvas.clear_waypoints()

  def _on_waypoints_cleared(self):
    self.table.setRowCount(0)