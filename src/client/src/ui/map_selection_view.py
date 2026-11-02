from pathlib import Path
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from src.core.models import MapData
from src.services.map_parser import MapParser


class MapSelectionView(QWidget):
  map_loaded = Signal(MapData)

  def __init__(self, parent: QWidget | None = None):
    super().__init__(parent)
    self._setup_ui()

  def _setup_ui(self):
    main_layout = QVBoxLayout(self)
    main_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

    card = QFrame()
    card.setFrameShape(QFrame.Shape.StyledPanel)
    card.setMaximumWidth(500)
    card_layout = QVBoxLayout(card)
    card_layout.setSpacing(16)
    card_layout.setContentsMargins(32, 32, 32, 32)

    title = QLabel("Select Environment Map")
    title.setStyleSheet("font-size: 18px; font-weight: bold;")
    title.setAlignment(Qt.AlignmentFlag.AlignCenter)
    card_layout.addWidget(title)

    desc = QLabel(
        "Choose a folder containing map.yaml and map image, or select the"
        " .yaml configuration file directly."
    )
    desc.setWordWrap(True)
    desc.setStyleSheet("color: #666;")
    desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
    card_layout.addWidget(desc)

    btn_layout = QHBoxLayout()
    self.btn_select_dir = QPushButton("Select Folder")
    self.btn_select_dir.clicked.connect(self._on_select_folder)
    btn_layout.addWidget(self.btn_select_dir)

    self.btn_select_file = QPushButton("Select YAML File")
    self.btn_select_file.clicked.connect(self._on_select_file)
    btn_layout.addWidget(self.btn_select_file)
    card_layout.addLayout(btn_layout)

    self.status_label = QLabel("")
    self.status_label.setStyleSheet("color: #d9534f;")
    self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    card_layout.addWidget(self.status_label)

    main_layout.addWidget(card)

  def _on_select_folder(self):
    dir_path = QFileDialog.getExistingDirectory(self, "Select Map Folder", "")
    if dir_path:
      self._process_path(Path(dir_path))

  def _on_select_file(self):
    file_path, _ = QFileDialog.getOpenFileName(
        self, "Select Map YAML", "", "Map Config (*.yaml *.yml)"
    )
    if file_path:
      self._process_path(Path(file_path))

  def _process_path(self, path: Path):
    try:
      self.status_label.setText("")
      map_data = MapParser.load_map_from_file_or_dir(path)
      self.map_loaded.emit(map_data)
    except Exception as e:
      self.status_label.setText(str(e))
      QMessageBox.critical(self, "Invalid Map", f"Failed to load map:\n{e}")