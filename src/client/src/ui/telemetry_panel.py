import math
from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer, QUrl, Signal
from PySide6.QtWidgets import (
    QFormLayout,
    QFrame,
    QGroupBox,
    QLabel,
    QVBoxLayout,
    QWidget,
)


class TelemetryPanel(QFrame):
  """Side panel displaying live robot telemetry and mission status."""

  def __init__(self, parent: QWidget | None = None):
    super().__init__(parent)
    self.setFrameShape(QFrame.Shape.StyledPanel)
    self.setStyleSheet("""
      TelemetryPanel { background-color: #ffffff; }
      QGroupBox {
        font-weight: bold;
        border: 1px solid #dee2e6;
        border-radius: 4px;
        margin-top: 8px;
        padding-top: 8px;
      }
      QGroupBox::title {
        subcontrol-origin: margin;
        left: 8px;
        padding: 0 4px;
      }
    """)
    self.setMinimumWidth(220)
    self.setMaximumWidth(300)
    self._setup_ui()

  def _setup_ui(self):
    layout = QVBoxLayout(self)
    layout.setContentsMargins(12, 12, 12, 12)
    layout.setSpacing(10)

    title = QLabel("Robot Telemetry")
    title.setStyleSheet("font-weight: bold; font-size: 14px;")
    layout.addWidget(title)

    self.lbl_conn = QLabel("● Disconnected")
    self.lbl_conn.setStyleSheet("color: #dc3545; font-weight: bold;")
    layout.addWidget(self.lbl_conn)

    # --- Pose ---
    pose_group = QGroupBox("Pose")
    pose_form = QFormLayout(pose_group)
    self.lbl_x = QLabel("--")
    self.lbl_y = QLabel("--")
    self.lbl_yaw = QLabel("--")
    self.lbl_frame = QLabel("--")
    for lbl in (self.lbl_x, self.lbl_y, self.lbl_yaw, self.lbl_frame):
      lbl.setStyleSheet("font-family: monospace;")
    pose_form.addRow("X:", self.lbl_x)
    pose_form.addRow("Y:", self.lbl_y)
    pose_form.addRow("Yaw:", self.lbl_yaw)
    pose_form.addRow("Frame:", self.lbl_frame)
    layout.addWidget(pose_group)

    # --- Battery & Safety ---
    hw_group = QGroupBox("Hardware")
    hw_form = QFormLayout(hw_group)
    self.lbl_bat_pct = QLabel("--")
    self.lbl_bat_v = QLabel("--")
    self.lbl_bat_a = QLabel("--")
    self.lbl_estop = QLabel("--")
    for lbl in (self.lbl_bat_pct, self.lbl_bat_v, self.lbl_bat_a):
      lbl.setStyleSheet("font-family: monospace;")
    hw_form.addRow("Battery:", self.lbl_bat_pct)
    hw_form.addRow("Voltage:", self.lbl_bat_v)
    hw_form.addRow("Current:", self.lbl_bat_a)
    hw_form.addRow("E-Stop:", self.lbl_estop)
    layout.addWidget(hw_group)

    # --- Mission ---
    mission_group = QGroupBox("Mission")
    mission_form = QFormLayout(mission_group)
    self.lbl_m_state = QLabel("--")
    self.lbl_m_wp = QLabel("--")
    self.lbl_m_err = QLabel("")
    self.lbl_m_err.setWordWrap(True)
    self.lbl_m_err.setStyleSheet("color: #dc3545; font-size: 11px;")
    mission_form.addRow("State:", self.lbl_m_state)
    mission_form.addRow("Waypoint:", self.lbl_m_wp)
    layout.addWidget(mission_group)
    layout.addWidget(self.lbl_m_err)

    layout.addStretch()

  def set_disconnected(self):
    self.lbl_conn.setText("● Disconnected")
    self.lbl_conn.setStyleSheet("color: #dc3545; font-weight: bold;")

  def update_robot_state(self, state: dict):
    self.lbl_conn.setText("● Connected")
    self.lbl_conn.setStyleSheet("color: #28a745; font-weight: bold;")

    pose = state.get("pose")
    if pose:
      yaw = pose["yaw"]
      self.lbl_x.setText(f"{pose['x']:+.3f} m")
      self.lbl_y.setText(f"{pose['y']:+.3f} m")
      self.lbl_yaw.setText(f"{yaw:+.2f} rad ({math.degrees(yaw):+.1f}°)")
      self.lbl_frame.setText(str(pose.get("frame", "--")))
    else:
      self.lbl_x.setText("No odom")
      self.lbl_y.setText("--")
      self.lbl_yaw.setText("--")
      self.lbl_frame.setText("--")

    battery = state.get("battery")
    if battery:
      raw_pct = battery.get("percentage")
      if raw_pct is not None:
        pct = raw_pct * 100.0 if raw_pct <= 1.0 else raw_pct
        self.lbl_bat_pct.setText(f"{pct:.1f} %")
      else:
        self.lbl_bat_pct.setText("--")
      self.lbl_bat_v.setText(f"{battery['voltage']:.2f} V")
      self.lbl_bat_a.setText(f"{battery['current']:.2f} A")
    else:
      self.lbl_bat_pct.setText("--")
      self.lbl_bat_v.setText("--")
      self.lbl_bat_a.setText("--")

    e_stop = state.get("e_stop")
    if e_stop is True:
      self.lbl_estop.setText("ENGAGED")
      self.lbl_estop.setStyleSheet("color: #dc3545; font-weight: bold;")
    elif e_stop is False:
      self.lbl_estop.setText("RELEASED")
      self.lbl_estop.setStyleSheet("color: #28a745; font-weight: bold;")
    else:
      self.lbl_estop.setText("--")
      self.lbl_estop.setStyleSheet("")

  def update_mission_status(self, status: dict):
    state_str = str(status.get("state", "idle"))
    self.lbl_m_state.setText(state_str)

    total = status.get("total_waypoints", 0)
    idx = status.get("current_waypoint_index", 0)
    wp_id = status.get("current_waypoint_id")
    if total > 0 and wp_id is not None:
      self.lbl_m_wp.setText(f"{wp_id} ({idx + 1}/{total})")
    else:
      self.lbl_m_wp.setText("--")

    err = status.get("error_message")
    self.lbl_m_err.setText(f"Error: {err}" if err else "")