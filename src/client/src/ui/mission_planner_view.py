import json
from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer, QUrl, Signal
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
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
from PySide6.QtGui import QBrush, QColor, QIcon, QPainter, QPen, QPixmap, QPolygonF
from src.core.models import MapData, Waypoint
from src.services.api_client import APIClient
from src.services.api_worker import APIWorker
from src.ui.map_canvas import MapCanvas
from src.ui.telemetry_panel import TelemetryPanel


class MissionPlannerView(QWidget):
  back_requested = Signal()

  def __init__(self, parent: QWidget | None = None):
    super().__init__(parent)
    self._map_data: MapData | None = None
    self.api_client = APIClient("http://localhost:8000")
    self.worker: APIWorker | None = None

    self._state_pending = False
    self._mission_pending = False

    self._setup_ui()
    self._setup_polling()

  def _setup_ui(self):
    main_layout = QVBoxLayout(self)
    main_layout.setContentsMargins(0, 0, 0, 0)
    main_layout.setSpacing(0)

    # --- 1. TOP TOOLBAR ---
    toolbar_frame = QFrame()
    toolbar_frame.setFixedHeight(48)
    toolbar_frame.setSizePolicy(
        QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
    )
    toolbar_frame.setStyleSheet("""
      QFrame { background-color: #f8f9fa; border-bottom: 1px solid #dee2e6; }
      QPushButton { padding: 5px 12px; border: 1px solid #ced4da; border-radius: 4px; background-color: #ffffff; font-weight: 500; }
      QPushButton:hover:!checked { background-color: #e9ecef; }
      QPushButton#btn_wp_wait:checked { background-color: #007ACC; color: white; border-color: #005999; }
      QPushButton#btn_wp_transit:checked { background-color: #28a745; color: white; border-color: #1e7e34; }
    """)

    toolbar = QHBoxLayout(toolbar_frame)
    toolbar.setContentsMargins(12, 0, 12, 0)
    toolbar.setAlignment(Qt.AlignmentFlag.AlignVCenter)
    toolbar.setSpacing(8)

    self.btn_back = QPushButton("← Change Map")
    self.btn_back.clicked.connect(self._on_back)
    toolbar.addWidget(self.btn_back)
    toolbar.addWidget(QLabel("|"))

    # Waypoint type selector (LMB places selected type; RMB always pans)
    self.wp_type_group = QButtonGroup(self)

    self.wp_type_group = QButtonGroup(self)

    self.btn_wp_wait = QPushButton()
    self.btn_wp_wait.setObjectName("btn_wp_wait")
    self.btn_wp_wait.setIcon(self._build_wait_icon())
    self.btn_wp_wait.setIconSize(QSize(20, 20))
    self.btn_wp_wait.setFixedSize(36, 32)
    self.btn_wp_wait.setToolTip("Wait Waypoint — stops for measurement / continue")
    self.btn_wp_wait.setCheckable(True)
    self.btn_wp_wait.setChecked(True)
    self.wp_type_group.addButton(self.btn_wp_wait)
    toolbar.addWidget(self.btn_wp_wait)

    self.btn_wp_transit = QPushButton()
    self.btn_wp_transit.setObjectName("btn_wp_transit")
    self.btn_wp_transit.setIcon(self._build_transit_icon())
    self.btn_wp_transit.setIconSize(QSize(20, 20))
    self.btn_wp_transit.setFixedSize(36, 32)
    self.btn_wp_transit.setToolTip("Transit Waypoint — proceeds immediately")
    self.btn_wp_transit.setCheckable(True)
    self.wp_type_group.addButton(self.btn_wp_transit)
    toolbar.addWidget(self.btn_wp_transit)

    self.btn_wp_wait.clicked.connect(lambda: self.canvas.set_waypoint_wait(True))
    self.btn_wp_transit.clicked.connect(lambda: self.canvas.set_waypoint_wait(False))

    self.btn_wp_wait.clicked.connect(lambda: self.canvas.set_waypoint_wait(True))
    self.btn_wp_transit.clicked.connect(lambda: self.canvas.set_waypoint_wait(False))

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

    hint_label = QLabel("LMB: Add  |  RMB: Pan  |  Wheel: Zoom")
    hint_label.setStyleSheet("color: #6c757d; font-size: 12px;")
    toolbar.addWidget(hint_label)
    toolbar.addWidget(QLabel("|"))

    self.coord_label = QLabel("X: -- m | Y: -- m")
    self.coord_label.setStyleSheet("font-family: monospace; font-size: 13px;")
    toolbar.addWidget(self.coord_label)

    main_layout.addWidget(toolbar_frame, 0)

    # --- 2. MAIN 3-PANE SPLITTER ---
    self.splitter = QSplitter(Qt.Orientation.Horizontal)
    self.splitter.setSizePolicy(
        QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
    )
    self.splitter.setHandleWidth(4)

    # Left: Telemetry Panel
    self.telemetry_panel = TelemetryPanel(self)
    self.splitter.addWidget(self.telemetry_panel)

    # Center: Map Canvas
    self.canvas = MapCanvas(self)
    self.canvas.coordinates_hovered.connect(self._on_coords_hovered)
    self.canvas.waypoint_added.connect(self._on_waypoint_added)
    self.canvas.waypoints_cleared.connect(self._on_waypoints_cleared)
    self.splitter.addWidget(self.canvas)

    # Right: Mission Waypoints Dock
    side_panel = QFrame()
    side_panel.setFrameShape(QFrame.Shape.StyledPanel)
    side_panel.setStyleSheet("background-color: #ffffff;")
    side_panel.setMinimumWidth(300)
    side_panel.setMaximumWidth(460)

    side_layout = QVBoxLayout(side_panel)
    side_layout.setContentsMargins(12, 12, 12, 12)
    side_layout.setSpacing(8)

    table_title = QLabel("Mission Waypoints")
    table_title.setStyleSheet("font-weight: bold; font-size: 14px;")
    side_layout.addWidget(table_title)

    self.table = QTableWidget(0, 5)
    self.table.setHorizontalHeaderLabels(["#", "Type", "X (m)", "Y (m)", "Yaw"])
    self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
    self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
    self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
    self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
    self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
    self.table.verticalHeader().setVisible(False)
    self.table.setAlternatingRowColors(True)
    side_layout.addWidget(self.table)

    action_layout = QHBoxLayout()
    self.btn_upload = QPushButton("⬆ Upload")
    self.btn_upload.setStyleSheet("background-color: #17a2b8; color: white; padding: 10px;")
    self.btn_upload.clicked.connect(self._on_upload)

    self.btn_start = QPushButton("▶ Start")
    self.btn_start.setStyleSheet("background-color: #28a745; color: white; padding: 10px;")
    self.btn_start.setEnabled(False)
    self.btn_start.clicked.connect(self._on_start)

    self.btn_continue = QPushButton("⏭ Continue")
    self.btn_continue.setStyleSheet("background-color: #ffc107; color: black; font-weight: bold; padding: 10px;")
    self.btn_continue.setEnabled(False)
    self.btn_continue.clicked.connect(self._on_continue)

    action_layout.addWidget(self.btn_upload)
    action_layout.addWidget(self.btn_start)
    action_layout.addWidget(self.btn_continue)
    side_layout.addLayout(action_layout)

    self.splitter.addWidget(side_panel)
    self.splitter.setSizes([240, 620, 340])

    main_layout.addWidget(self.splitter, 1)

  def _setup_polling(self):
    self.network_manager = QNetworkAccessManager(self)
    self.network_manager.finished.connect(self._on_network_reply)

    self.telemetry_timer = QTimer(self)
    self.telemetry_timer.setInterval(200)
    self.telemetry_timer.timeout.connect(self._poll_backend)

  def set_map(self, map_data: MapData):
    self._map_data = map_data
    self.canvas.load_map(map_data)
    self.btn_wp_wait.setChecked(True)
    self.canvas.set_waypoint_wait(True)
    self.table.setRowCount(0)
    self.telemetry_timer.start()
    self._on_fit_view()

  def _on_back(self):
    self.telemetry_timer.stop()
    self.back_requested.emit()

  def _on_fit_view(self):
    if self._map_data:
      self.canvas.fitInView(
          self.canvas.scene().sceneRect(), Qt.AspectRatioMode.KeepAspectRatio
      )

  def _on_coords_hovered(self, x: float, y: float):
    self.coord_label.setText(f"X: {x:+.2f} m | Y: {y:+.2f} m")

  def _on_waypoint_added(self, wp: Waypoint):
    self.btn_start.setEnabled(False)
    row = self.table.rowCount()
    self.table.insertRow(row)
    self.table.setItem(row, 0, QTableWidgetItem(str(wp.id)))
    self.table.setItem(row, 1, QTableWidgetItem("Wait" if wp.wait else "Transit"))
    self.table.setItem(row, 2, QTableWidgetItem(f"{wp.x:.2f}"))
    self.table.setItem(row, 3, QTableWidgetItem(f"{wp.y:.2f}"))
    self.table.setItem(row, 4, QTableWidgetItem(f"{wp.yaw:.2f}"))

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

  def _on_continue(self):
    self.btn_continue.setEnabled(False)
    self.worker = APIWorker(self.api_client.continue_mission)
    self.worker.finished.connect(lambda _: None)
    self.worker.error.connect(self._on_api_error)
    self.worker.start()

  def _on_api_error(self, error_msg: str):
    self.btn_upload.setEnabled(True)
    self.btn_start.setEnabled(False)
    QMessageBox.critical(self, "API Error", f"Request failed:\n{error_msg}")

  # --- Non-Blocking Telemetry & Status Polling ---
  def _poll_backend(self):
    if not self._state_pending:
      self._state_pending = True
      self.network_manager.get(QNetworkRequest(QUrl(f"{self.api_client.base_url}/state")))

    if not self._mission_pending:
      self._mission_pending = True
      self.network_manager.get(QNetworkRequest(QUrl(f"{self.api_client.base_url}/mission/status")))

  def _on_network_reply(self, reply: QNetworkReply):
    path = reply.url().path()
    is_state = path.endswith("/state")
    is_mission = path.endswith("/mission/status")

    if is_state:
      self._state_pending = False
    elif is_mission:
      self._mission_pending = False

    if reply.error() == QNetworkReply.NetworkError.NoError:
      try:
        payload = json.loads(reply.readAll().data().decode("utf-8"))
        if is_state:
          self.telemetry_panel.update_robot_state(payload)
          pose = payload.get("pose")
          if pose:
            self.canvas.update_robot_pose(pose["x"], pose["y"], pose["yaw"])
        elif is_mission:
          self.telemetry_panel.update_mission_status(payload)
          self.btn_continue.setEnabled(payload.get("state") == "waiting_at_waypoint")
      except Exception:
        pass
    else:
      if is_state:
        self.telemetry_panel.set_disconnected()

    reply.deleteLater()

  @staticmethod
  def _build_wait_icon() -> QIcon:
    """Circle with pause bars (Wait Waypoint)."""
    icon = QIcon()
    for state, color_hex in (
        (QIcon.State.Off, "#007ACC"),
        (QIcon.State.On, "#FFFFFF"),
    ):
      pm = QPixmap(48, 48)
      pm.setDevicePixelRatio(2.0)
      pm.fill(Qt.GlobalColor.transparent)

      p = QPainter(pm)
      p.setRenderHint(QPainter.RenderHint.Antialiasing)
      color = QColor(color_hex)

      p.setPen(QPen(color, 2.0))
      p.setBrush(Qt.BrushStyle.NoBrush)
      p.drawEllipse(QRectF(2.5, 2.5, 19.0, 19.0))

      p.setPen(Qt.PenStyle.NoPen)
      p.setBrush(QBrush(color))
      p.drawRoundedRect(QRectF(8.0, 7.5, 3.0, 9.0), 1.0, 1.0)
      p.drawRoundedRect(QRectF(13.0, 7.5, 3.0, 9.0), 1.0, 1.0)
      p.end()

      icon.addPixmap(pm, QIcon.Mode.Normal, state)
    return icon

  @staticmethod
  def _build_transit_icon() -> QIcon:
    """Circle with forward arrow (Transit Waypoint)."""
    icon = QIcon()
    for state, color_hex in (
        (QIcon.State.Off, "#28a745"),
        (QIcon.State.On, "#FFFFFF"),
    ):
      pm = QPixmap(48, 48)
      pm.setDevicePixelRatio(2.0)
      pm.fill(Qt.GlobalColor.transparent)

      p = QPainter(pm)
      p.setRenderHint(QPainter.RenderHint.Antialiasing)
      color = QColor(color_hex)

      p.setPen(QPen(color, 2.0))
      p.setBrush(Qt.BrushStyle.NoBrush)
      p.drawEllipse(QRectF(2.5, 2.5, 19.0, 19.0))

      p.setPen(Qt.PenStyle.NoPen)
      p.setBrush(QBrush(color))
      arrow = QPolygonF([
          QPointF(9.0, 7.5),
          QPointF(16.5, 12.0),
          QPointF(9.0, 16.5),
      ])
      p.drawPolygon(arrow)
      p.end()

      icon.addPixmap(pm, QIcon.Mode.Normal, state)
    return icon