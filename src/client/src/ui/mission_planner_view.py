import json
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from src.core.models import MapData, Waypoint
from src.services.api_client import APIClient
from src.services.api_worker import APIWorker

try:
  from src.ui.map_canvas import CanvasMode, MapCanvas
except ImportError:
  from src.ui.map_canvas import CanvasMode, MapCanvas


class MissionPlannerView(QWidget):
  back_requested = Signal()

  def __init__(self, parent: QWidget | None = None):
    super().__init__(parent)
    self._map_data: MapData | None = None
    self.api_client = APIClient("http://localhost:8000")
    self.worker: APIWorker | None = None
    self._setup_ui()

  def _setup_ui(self):
    main_layout = QVBoxLayout(self)
    main_layout.setContentsMargins(0, 0, 0, 0)
    main_layout.setSpacing(0)

    toolbar_frame = QFrame()
    toolbar_frame.setFixedHeight(48)
    toolbar_frame.setSizePolicy(
        QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
    )
    toolbar_frame.setStyleSheet("""
            QFrame { background-color: #f8f9fa; border-bottom: 1px solid #dee2e6; }
            QPushButton { padding: 5px 12px; border: 1px solid #ced4da; border-radius: 4px; background-color: #ffffff; font-weight: 500; }
            QPushButton:checked { background-color: #007ACC; color: white; border-color: #005999; }
            QPushButton:hover:!checked { background-color: #e9ecef; }
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

    self.btn_pan.clicked.connect(lambda: self.canvas.set_mode(CanvasMode.PAN))
    self.btn_add_wp.clicked.connect(lambda: self.canvas.set_mode(CanvasMode.ADD_WAYPOINT))

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
    self.coord_label.setStyleSheet("font-family: monospace; font-size: 13px;")
    toolbar.addWidget(self.coord_label)

    main_layout.addWidget(toolbar_frame, 0)

    # --- 2. MAIN SPLITTER ---
    self.splitter = QSplitter(Qt.Orientation.Horizontal)
    self.splitter.setSizePolicy(
        QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
    )
    self.splitter.setHandleWidth(4)

    # Canvas
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
    self.table.setHorizontalHeaderLabels(["#", "X (m)", "Y (m)", "Yaw (rad)"])
    self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
    self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
    self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
    self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
    self.table.verticalHeader().setVisible(False)
    self.table.setAlternatingRowColors(True)
    side_layout.addWidget(self.table)

    action_layout = QHBoxLayout()
    self.btn_upload = QPushButton("⬆ Upload Mission")
    self.btn_upload.setStyleSheet("background-color: #17a2b8; color: white; padding: 10px;")
    self.btn_upload.clicked.connect(self._on_upload)

    self.btn_start = QPushButton("▶ Start Mission")
    self.btn_start.setStyleSheet("background-color: #28a745; color: white; padding: 10px;")
    self.btn_start.setEnabled(False)
    self.btn_start.clicked.connect(self._on_start)

    action_layout.addWidget(self.btn_upload)
    action_layout.addWidget(self.btn_start)
    side_layout.addLayout(action_layout)

    self.splitter.addWidget(side_panel)
    self.splitter.setSizes([900, 300])

    main_layout.addWidget(self.splitter, 1)

    self.telemetry_timer = QTimer(self)
    self.telemetry_timer.setInterval(200)
    self.telemetry_timer.timeout.connect(self._fetch_state)

  def set_map(self, map_data: MapData):
    self._map_data = map_data
    self.canvas.load_map(map_data)
    self.btn_pan.setChecked(True)
    self.canvas.set_mode(CanvasMode.PAN)
    self.table.setRowCount(0)
    self.telemetry_timer.start()
    self._on_fit_view()

  def _on_fit_view(self):
    if self._map_data:
      self.canvas.fitInView(
          self.canvas.scene().sceneRect(), Qt.AspectRatioMode.KeepAspectRatio
      )

  def _on_coords_hovered(self, x: float, y: float):
    self.coord_label.setText(f"X: {x:+.2f} m | Y: {y:+.2f} m")

  def _on_waypoint_added(self, wp: Waypoint):
    # Disable start if map changes until re-uploaded
    self.btn_start.setEnabled(False) 
    row = self.table.rowCount()
    self.table.insertRow(row)
    self.table.setItem(row, 0, QTableWidgetItem(str(wp.id)))
    self.table.setItem(row, 1, QTableWidgetItem(f"{wp.x:.2f}"))
    self.table.setItem(row, 2, QTableWidgetItem(f"{wp.y:.2f}"))
    self.table.setItem(row, 3, QTableWidgetItem(f"{wp.yaw:.2f}"))

  def _on_undo(self):
    self.btn_start.setEnabled(False)
    self.canvas.undo_last_waypoint()
    current_rows = self.table.rowCount()
    if current_rows > 0:
      self.table.removeRow(current_rows - 1)

  def _on_clear(self):
    self.btn_start.setEnabled(False)
    self.canvas.clear_waypoints()

  def _on_waypoints_cleared(self):
    self.table.setRowCount(0)

  # --- API Execution Handlers ---
  def _on_upload(self):
    waypoints = self.canvas.get_waypoints()
    if not waypoints:
      QMessageBox.warning(self, "No Waypoints", "Please add at least one waypoint on the map first.")
      return

    self.btn_upload.setEnabled(False)
    self.btn_start.setEnabled(False)
    
    self.worker = APIWorker(self.api_client.upload_mission_data, "GUI Mission", waypoints)
    self.worker.finished.connect(self._on_upload_success)
    self.worker.error.connect(self._on_api_error)
    self.worker.start()

  def _on_upload_success(self, result: dict):
    self.btn_upload.setEnabled(True)
    self.btn_start.setEnabled(True)
    msg = result.get("message", "Upload complete.")
    QMessageBox.information(self, "Success", msg)

  def _on_start(self):
    self.btn_upload.setEnabled(False)
    self.btn_start.setEnabled(False)
    
    self.worker = APIWorker(self.api_client.start_mission)
    self.worker.finished.connect(self._on_start_success)
    self.worker.error.connect(self._on_api_error)
    self.worker.start()

  def _on_start_success(self, result: dict):
    self.btn_upload.setEnabled(True)
    self.btn_start.setEnabled(True)
    msg = result.get("message", "Mission started.")
    QMessageBox.information(self, "Mission Running", msg)

  def _on_api_error(self, error_msg: str):
    self.btn_upload.setEnabled(True)
    self.btn_start.setEnabled(False)
    QMessageBox.critical(self, "API Error", f"Request failed:\n{error_msg}")

  def _fetch_state(self):
    try:
      import requests
      response = requests.get(f"{self.api_client.base_url}/state", timeout=1.0)
      if response.status_code == 200:
        state = response.json()
        pose = state.get("pose")
        
        if pose:
          self.canvas.update_robot_pose(pose["x"], pose["y"], pose["yaw"])
        else:
          # API is responding, but ROS bridge hasn't received Odometry yet
          print("Telemetry OK: Waiting for 'pose' data from ROS 2...")
      else:
        print(f"API Error: Status {response.status_code}")
    except Exception as e:
      print(f"Telemetry network error: {e}")