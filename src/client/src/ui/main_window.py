from PySide6.QtWidgets import QMainWindow, QStackedWidget
from src.core.models import MapData
from src.ui.map_selection_view import MapSelectionView
from src.ui.mission_planner_view import MissionPlannerView


class MainWindow(QMainWindow):

  def __init__(self):
    super().__init__()
    self.setWindowTitle("Husarion UGV Mission Control")
    self.resize(1000, 700)

    self.stack = QStackedWidget(self)
    self.setCentralWidget(self.stack)

    self.selection_view = MapSelectionView(self)
    self.planner_view = MissionPlannerView(self)

    self.stack.addWidget(self.selection_view)  # Index 0
    self.stack.addWidget(self.planner_view)  # Index 1

    self.selection_view.map_loaded.connect(self._on_map_loaded)
    self.planner_view.back_requested.connect(self._on_back_to_selection)

    self.stack.setCurrentIndex(0)

  def _on_map_loaded(self, map_data: MapData):
    self.planner_view.set_map(map_data)
    self.stack.setCurrentIndex(1)

  def _on_back_to_selection(self):
    self.stack.setCurrentIndex(0)