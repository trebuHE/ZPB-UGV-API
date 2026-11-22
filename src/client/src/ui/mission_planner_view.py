from dataclasses import replace
import json
from pathlib import Path
from typing import List
from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QBrush, QColor, QIcon, QPainter, QPen, QPixmap, QPolygonF
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
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
from src.core.models import MapData, MeasurementDefinition, Waypoint
from src.services.api_client import APIClient
from src.services.api_worker import APIWorker
from src.services.measurement_parser import MeasurementParser
from src.ui.map_canvas import MapCanvas
from src.ui.measurement_dialog import MeasurementDialog
from src.ui.telemetry_panel import TelemetryPanel


class MissionPlannerView(QWidget):
  back_requested = Signal()

  ACTIVE_STATES = ("running", "waiting_at_waypoint", "executing_script")
  FORCE_CONTINUE_STATES = ("waiting_at_waypoint", "executing_script")

  def __init__(self, parent: QWidget | None = None):
    super().__init__(parent)
    self._map_data: MapData | None = None
    self._measurement_defs: List[MeasurementDefinition] = []
    self.api_client = APIClient("http://localhost:8000")
    self.worker: APIWorker | None = None

    self._mission_uploaded = False
    self._mission_state = "idle"
    self._current_waypoint_id: str | None = None
    self._api_busy = False

    self._state_pending = False
    self._mission_pending = False

    self._setup_ui()
    self._setup_polling()
    self._try_autoload_measurements()
    self._update_control_buttons()

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
      QPushButton#btn_wp_wait, QPushButton#btn_wp_transit { padding: 0px; }
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

    self.btn_load_meas = QPushButton("Measurements...")
    self.btn_load_meas.setToolTip("Load measurement_definitions.yaml")
    self.btn_load_meas.clicked.connect(self._on_load_measurements)
    toolbar.addWidget(self.btn_load_meas)
    toolbar.addWidget(QLabel("|"))

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

    self.telemetry_panel = TelemetryPanel(self)
    self.splitter.addWidget(self.telemetry_panel)

    self.canvas = MapCanvas(self)
    self.canvas.coordinates_hovered.connect(self._on_coords_hovered)
    self.canvas.waypoint_added.connect(self._on_waypoint_added)
    self.canvas.waypoints_cleared.connect(self._on_waypoints_cleared)
    self.splitter.addWidget(self.canvas)

    side_panel = QFrame()
    side_panel.setFrameShape(QFrame.Shape.StyledPanel)
    side_panel.setStyleSheet("background-color: #ffffff;")
    side_panel.setMinimumWidth(330)
    side_panel.setMaximumWidth(500)

    side_layout = QVBoxLayout(side_panel)
    side_layout.setContentsMargins(12, 12, 12, 12)
    side_layout.setSpacing(8)

    table_title = QLabel("Mission Waypoints (double-click Wait row to edit)")
    table_title.setStyleSheet("font-weight: bold; font-size: 13px;")
    side_layout.addWidget(table_title)

    self.table = QTableWidget(0, 6)
    self.table.setHorizontalHeaderLabels(["#", "Type", "X", "Y", "Yaw", "Script"])
    self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
    self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
    self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
    self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
    self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
    self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
    self.table.verticalHeader().setVisible(False)
    self.table.setAlternatingRowColors(True)
    self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    self.table.cellDoubleClicked.connect(self._on_table_row_double_clicked)
    side_layout.addWidget(self.table)

    # 2x2 Mission Controls Grid
    btn_grid = QGridLayout()
    btn_grid.setSpacing(6)

    self.btn_upload = QPushButton("⬆ Upload Mission")
    self.btn_upload.setStyleSheet(
        "QPushButton { background-color: #17a2b8; color: white; padding: 9px; font-weight: bold; }"
        "QPushButton:disabled { background-color: #b8dce2; color: #f8f9fa; }"
    )
    self.btn_upload.clicked.connect(self._on_upload)

    self.btn_start = QPushButton("▶ Start Mission")
    self.btn_start.setStyleSheet(
        "QPushButton { background-color: #28a745; color: white; padding: 9px; font-weight: bold; }"
        "QPushButton:disabled { background-color: #b5dfc0; color: #f8f9fa; }"
    )
    self.btn_start.clicked.connect(self._on_start)

    self.btn_stop = QPushButton("■ Stop Mission")
    self.btn_stop.setStyleSheet(
        "QPushButton { background-color: #dc3545; color: white; padding: 9px; font-weight: bold; }"
        "QPushButton:disabled { background-color: #e8b3b8; color: #f8f9fa; }"
    )
    self.btn_stop.clicked.connect(self._on_stop)

    self.btn_continue = QPushButton("⏭ Force Continue")
    self.btn_continue.setStyleSheet(
        "QPushButton { background-color: #ffc107; color: black; padding: 9px; font-weight: bold; }"
        "QPushButton:disabled { background-color: #f3e2a9; color: #7a7a7a; }"
    )
    self.btn_continue.clicked.connect(self._on_force_continue)

    btn_grid.addWidget(self.btn_upload, 0, 0)
    btn_grid.addWidget(self.btn_start, 0, 1)
    btn_grid.addWidget(self.btn_stop, 1, 0)
    btn_grid.addWidget(self.btn_continue, 1, 1)
    side_layout.addLayout(btn_grid)

    self.splitter.addWidget(side_panel)
    self.splitter.setSizes([240, 620, 380])

    main_layout.addWidget(self.splitter, 1)

  def _setup_polling(self):
    self.network_manager = QNetworkAccessManager(self)
    self.network_manager.finished.connect(self._on_network_reply)

    self.telemetry_timer = QTimer(self)
    self.telemetry_timer.setInterval(200)
    self.telemetry_timer.timeout.connect(self._poll_backend)

  def _try_autoload_measurements(self):
    default_path = Path("measurement_definitions.yaml")
    if default_path.exists():
      try:
        self._measurement_defs = MeasurementParser.load_from_file(default_path)
        self.btn_load_meas.setText(f"Measurements ({len(self._measurement_defs)})")
      except Exception:
        pass

  def _on_load_measurements(self):
    file_path, _ = QFileDialog.getOpenFileName(
        self, "Select Measurement Definitions YAML", "", "YAML Files (*.yaml *.yml)"
    )
    if not file_path:
      return
    try:
      self._measurement_defs = MeasurementParser.load_from_file(Path(file_path))
      self.btn_load_meas.setText(f"Measurements ({len(self._measurement_defs)})")
    except Exception as e:
      QMessageBox.critical(self, "Invalid Measurements File", f"Failed to load definitions:\n{e}")

  def _invalidate_upload(self):
    self._mission_uploaded = False
    self._update_control_buttons()

  def _update_control_buttons(self):
    is_active = self._mission_state in self.ACTIVE_STATES
    can_force_continue = self._mission_state in self.FORCE_CONTINUE_STATES

    self.btn_upload.setEnabled(not self._api_busy and not is_active)
    self.btn_start.setEnabled(
        not self._api_busy and self._mission_uploaded and not is_active
    )
    self.btn_stop.setEnabled(not self._api_busy and is_active)
    self.btn_continue.setEnabled(not self._api_busy and can_force_continue)

  def set_map(self, map_data: MapData):
    self._map_data = map_data
    self.canvas.load_map(map_data)
    self.btn_wp_wait.setChecked(True)
    self.canvas.set_waypoint_wait(True)
    self.table.setRowCount(0)
    self._invalidate_upload()
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

  def _populate_table_row(self, row: int, wp: Waypoint):
    script_text = wp.measurement_script.id if wp.measurement_script else "—"
    self.table.setItem(row, 0, QTableWidgetItem(str(wp.id)))
    self.table.setItem(row, 1, QTableWidgetItem("Wait" if wp.wait else "Transit"))
    self.table.setItem(row, 2, QTableWidgetItem(f"{wp.x:.2f}"))
    self.table.setItem(row, 3, QTableWidgetItem(f"{wp.y:.2f}"))
    self.table.setItem(row, 4, QTableWidgetItem(f"{wp.yaw:.2f}"))
    self.table.setItem(row, 5, QTableWidgetItem(script_text))

  def _on_waypoint_added(self, wp: Waypoint):
    row = self.table.rowCount()
    if wp.wait and self._measurement_defs:
      dialog = MeasurementDialog(wp.id, self._measurement_defs, parent=self)
      if dialog.exec() != QDialog.DialogCode.Accepted:
        self.canvas.undo_last_waypoint()
        return
      wp = replace(wp, measurement_script=dialog.get_measurement())
      self.canvas.update_waypoint(row, wp)

    self.table.insertRow(row)
    self._populate_table_row(row, wp)
    self._invalidate_upload()

  def _on_table_row_double_clicked(self, row: int, _col: int):
    waypoints = self.canvas.get_waypoints()
    if not (0 <= row < len(waypoints)):
      return
    wp = waypoints[row]
    if not wp.wait:
      return
    if not self._measurement_defs:
      QMessageBox.information(
          self,
          "No Definitions Loaded",
          "Load a measurement_definitions.yaml file first using the toolbar button.",
      )
      return

    dialog = MeasurementDialog(
        wp.id, self._measurement_defs, current=wp.measurement_script, parent=self
    )
    if dialog.exec() == QDialog.DialogCode.Accepted:
      updated_wp = replace(wp, measurement_script=dialog.get_measurement())
      self.canvas.update_waypoint(row, updated_wp)
      self._populate_table_row(row, updated_wp)
      self._invalidate_upload()

  def _on_undo(self):
    self.canvas.undo_last_waypoint()
    current_rows = self.table.rowCount()
    if current_rows > 0:
      self.table.removeRow(current_rows - 1)
    self._invalidate_upload()

  def _on_clear(self):
    self.canvas.clear_waypoints()
    self._invalidate_upload()

  def _on_waypoints_cleared(self):
    self.table.setRowCount(0)
    self._invalidate_upload()

  # --- API Execution Handlers ---
  def _run_api_call(self, callable_fn, on_success, *args):
    self._api_busy = True
    self._update_control_buttons()
    self.worker = APIWorker(callable_fn, *args)
    self.worker.finished.connect(on_success)
    self.worker.error.connect(self._on_api_error)
    self.worker.start()

  def _on_upload(self):
    waypoints = self.canvas.get_waypoints()
    if not waypoints:
      QMessageBox.warning(self, "No Waypoints", "Add at least one waypoint on the map first.")
      return
    self._mission_uploaded = False
    self._run_api_call(
        self.api_client.upload_mission_data,
        self._on_upload_success,
        "GUI Mission",
        waypoints,
    )

  def _on_upload_success(self, result: dict):
    self._api_busy = False
    if result.get("success", False):
      self._mission_uploaded = True
      QMessageBox.information(self, "Upload Complete", result.get("message", "Mission uploaded."))
    else:
      self._mission_uploaded = False
      QMessageBox.warning(self, "Upload Rejected", result.get("message", "Mission upload failed."))
    self._update_control_buttons()

  def _on_start(self):
    if not self._mission_uploaded:
      QMessageBox.warning(self, "Not Uploaded", "Upload the mission before starting.")
      return
    self._run_api_call(self.api_client.start_mission, self._on_start_success)

  def _on_start_success(self, result: dict):
    self._api_busy = False
    if result.get("success", False):
      self._mission_state = "running"
    else:
      QMessageBox.warning(self, "Start Rejected", result.get("message", "Could not start mission."))
    self._update_control_buttons()

  def _on_stop(self):
    self._run_api_call(self.api_client.stop_mission, self._on_stop_success)

  def _on_stop_success(self, result: dict):
    self._api_busy = False
    if not result.get("success", False):
      QMessageBox.warning(self, "Stop Rejected", result.get("message", "Could not stop mission."))
    self._update_control_buttons()

  def _on_force_continue(self):
    self._run_api_call(
        self.api_client.continue_mission,
        self._on_continue_success,
        self._current_waypoint_id,
    )

  def _on_continue_success(self, result: dict):
    self._api_busy = False
    if not result.get("success", False):
      QMessageBox.warning(self, "Continue Rejected", result.get("message", "Could not continue."))
    self._update_control_buttons()

  def _on_api_error(self, error_msg: str):
    self._api_busy = False
    self._update_control_buttons()
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
          self._mission_state = str(payload.get("state", "idle"))
          self._current_waypoint_id = payload.get("current_waypoint_id")
          self._update_control_buttons()
      except Exception:
        pass
    else:
      if is_state:
        self.telemetry_panel.set_disconnected()

    reply.deleteLater()