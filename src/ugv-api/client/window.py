from PySide6.QtWidgets import (
  QMainWindow, QWidget, QVBoxLayout, QPushButton,
  QFileDialog, QLabel, QMessageBox
)
from api_client import APIClient
from api_worker import APIWorker
from config import load_config

class Window(QMainWindow):
  def __init__(self):
    super().__init__()
    self.setWindowTitle("UGV Mission Control")
    self.resize(350, 150)

    cfg = load_config()

    base_url = cfg.get("api", {}).get("base_url", "http://localhost:8000")
    self.api_client = APIClient(base_url)

    self.selected_file: str | None = None
    self._setup_ui()

  def _setup_ui(self):
    central_widget = QWidget()
    self.setCentralWidget(central_widget)
    layout = QVBoxLayout(central_widget)

    self.status_label = QLabel("Select a mission file.")
    layout.addWidget(self.status_label)

    self.btn_select = QPushButton("Select Mission File (.yaml / .yml)")
    self.btn_select.clicked.connect(self.select_file)
    layout.addWidget(self.btn_select)

    self.btn_upload = QPushButton("Upload Mission")
    self.btn_upload.clicked.connect(self.upload_mission)
    self.btn_upload.setEnabled(False)
    layout.addWidget(self.btn_upload)

    self.btn_start = QPushButton("Start Mission")
    self.btn_start.clicked.connect(self.start_mission)
    layout.addWidget(self.btn_start)

  def select_file(self):
    file_path, _ = QFileDialog.getOpenFileName(
      self, "Select Mission File", "", "YAML Files (*.yaml *.yml)"
    )
    if file_path:
      self.selected_file = file_path
      self.status_label.setText(f"Selected: {self.selected_file}")
      self.btn_upload.setEnabled(True)

  def upload_mission(self):
    if not self.selected_file:
      return

    self._set_buttons_enabled(False)
    self.status_label.setText("Uploading mission...")

    self.worker = APIWorker(self.api_client.upload_mission, self.selected_file)
    self.worker.finished.connect(self.on_upload_success)
    self.worker.error.connect(self.on_api_error)
    self.worker.start()

  def start_mission(self):
    self._set_buttons_enabled(False)
    self.status_label.setText("Starting mission...")

    self.worker = APIWorker(self.api_client.start_mission)
    self.worker.finished.connect(self.on_start_success)
    self.worker.error.connect(self.on_api_error)
    self.worker.start()

  def on_upload_success(self, result: dict):
    self._set_buttons_enabled(True)
    msg = result.get("message", "Upload complete.")
    self.status_label.setText("Upload successful.")
    QMessageBox.information(self, "Success", msg)

  def on_start_success(self, result: dict):
    self._set_buttons_enabled(True)
    msg = result.get("message", "Mission started.")
    self.status_label.setText("Mission started.")
    QMessageBox.information(self, "Success", msg)

  def on_api_error(self, error_msg: str):
    self._set_buttons_enabled(True)
    self.status_label.setText("API Error occurred.")
    QMessageBox.critical(self, "Error", f"Request failed:\n{error_msg}")

  def _set_buttons_enabled(self, enabled: bool):
    """Helper to toggle buttons during active API calls to prevent double-clicks."""
    self.btn_select.setEnabled(enabled)
    self.btn_start.setEnabled(enabled)

    self.btn_upload.setEnabled(enabled and self.selected_file is not None)