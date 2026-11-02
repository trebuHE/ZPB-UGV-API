from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QMouseEvent, QPainter, QPixmap, QWheelEvent
from PySide6.QtWidgets import (
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
    QWidget,
)
from src.core.models import MapData


class MapCanvas(QGraphicsView):
  coordinates_hovered = Signal(float, float)  # Emits real-world metric (x, y)
  canvas_clicked = Signal(float, float)  # Emits real-world metric (x, y) on click

  def __init__(self, parent: QWidget | None = None):
    super().__init__(parent)
    self._scene = QGraphicsScene(self)
    self.setScene(self._scene)

    self._map_data: MapData | None = None
    self._pixmap_item: QGraphicsPixmapItem | None = None

    # Render settings
    self.setRenderHint(QPainter.RenderHint.Antialiasing)
    self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
    self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
    self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
    self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    self.setMouseTracking(True)

  def load_map(self, map_data: MapData):
    self._map_data = map_data
    self._scene.clear()

    pixmap = QPixmap(str(map_data.metadata.image_path))
    self._pixmap_item = self._scene.addPixmap(pixmap)
    self._scene.setSceneRect(
        0, 0, map_data.image_width, map_data.image_height
    )
    self.fitInView(self._scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

  def wheelEvent(self, event: QWheelEvent):
    zoom_factor = 1.15
    if event.angleDelta().y() > 0:
      self.scale(zoom_factor, zoom_factor)
    else:
      self.scale(1 / zoom_factor, 1 / zoom_factor)

  def mouseMoveEvent(self, event: QMouseEvent):
    super().mouseMoveEvent(event)
    if not self._map_data:
      return

    scene_pt: QPointF = self.mapToScene(event.pos())
    if 0 <= scene_pt.x() <= self._map_data.image_width and 0 <= scene_pt.y() <= self._map_data.image_height:
      x_w, y_w = self._map_data.pixel_to_world(scene_pt.x(), scene_pt.y())
      self.coordinates_hovered.emit(x_w, y_w)

  def mousePressEvent(self, event: QMouseEvent):
    if event.button() == Qt.MouseButton.LeftButton and self._map_data:
      scene_pt = self.mapToScene(event.pos())
      if (
          0 <= scene_pt.x() <= self._map_data.image_width
          and 0 <= scene_pt.y() <= self._map_data.image_height
      ):
        x_w, y_w = self._map_data.pixel_to_world(scene_pt.x(), scene_pt.y())
        self.canvas_clicked.emit(x_w, y_w)
    super().mousePressEvent(event)