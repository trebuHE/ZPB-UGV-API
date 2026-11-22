import math
from typing import List
from PySide6.QtCore import QLineF, QPoint, QPointF, Qt, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPen, QPixmap, QWheelEvent
from PySide6.QtWidgets import (
    QGraphicsLineItem,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
    QWidget,
)
from src.core.models import MapData, Waypoint
from src.ui.robot_item import RobotItem
from src.ui.waypoint_item import WaypointItem


class MapCanvas(QGraphicsView):
  coordinates_hovered = Signal(float, float)  # (x_w, y_w) in meters
  waypoint_added = Signal(Waypoint)  # Emitted when a waypoint is confirmed
  waypoints_cleared = Signal()

  def __init__(self, parent: QWidget | None = None):
    super().__init__(parent)
    self._scene = QGraphicsScene(self)
    self.setScene(self._scene)

    self._map_data: MapData | None = None
    self._pixmap_item: QGraphicsPixmapItem | None = None
    self._waypoint_wait: bool = True

    self._waypoints: List[Waypoint] = []
    self._waypoint_items: List[WaypointItem] = []
    self._connection_lines: List[QGraphicsLineItem] = []

    self._drag_start_scene: QPointF | None = None
    self._preview_arrow_line: QGraphicsLineItem | None = None

    self._is_panning: bool = False
    self._pan_start_pos: QPoint | None = None

    self.setRenderHint(QPainter.RenderHint.Antialiasing)
    self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
    self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
    self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    self.setDragMode(QGraphicsView.DragMode.NoDrag)
    self.setCursor(Qt.CursorShape.CrossCursor)
    self.setMouseTracking(True)

    self._robot_item = RobotItem()
    self._scene.addItem(self._robot_item)
    self._robot_item.hide()

  def set_waypoint_wait(self, wait: bool):
    """Sets whether newly placed waypoints pause for /mission/continue."""
    self._waypoint_wait = wait

  def load_map(self, map_data: MapData):
    self._map_data = map_data
    self.clear_waypoints()

    if self._pixmap_item:
      self._scene.removeItem(self._pixmap_item)

    pixmap = QPixmap(str(map_data.metadata.image_path))
    self._pixmap_item = self._scene.addPixmap(pixmap)
    self._pixmap_item.setZValue(-10.0)

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

  def mousePressEvent(self, event: QMouseEvent):
    if event.button() == Qt.MouseButton.RightButton:
      self._is_panning = True
      self._pan_start_pos = event.position().toPoint()
      self.setCursor(Qt.CursorShape.ClosedHandCursor)
      event.accept()
      return

    if (
        event.button() == Qt.MouseButton.LeftButton
        and self._map_data
        and not self._is_panning
    ):
      scene_pt = self.mapToScene(event.pos())
      if (
          0 <= scene_pt.x() <= self._map_data.image_width
          and 0 <= scene_pt.y() <= self._map_data.image_height
      ):
        self._drag_start_scene = scene_pt
        event.accept()
        return

    super().mousePressEvent(event)

  def mouseMoveEvent(self, event: QMouseEvent):
    if self._is_panning and self._pan_start_pos is not None:
      current_pos = event.position().toPoint()
      delta = current_pos - self._pan_start_pos
      self._pan_start_pos = current_pos
      self.horizontalScrollBar().setValue(
          self.horizontalScrollBar().value() - delta.x()
      )
      self.verticalScrollBar().setValue(
          self.verticalScrollBar().value() - delta.y()
      )
      event.accept()
      return

    super().mouseMoveEvent(event)
    if not self._map_data:
      return

    scene_pt: QPointF = self.mapToScene(event.pos())

    if (
        0 <= scene_pt.x() <= self._map_data.image_width
        and 0 <= scene_pt.y() <= self._map_data.image_height
    ):
      x_w, y_w = self._map_data.pixel_to_world(scene_pt.x(), scene_pt.y())
      self.coordinates_hovered.emit(x_w, y_w)

    if self._drag_start_scene is not None:
      preview_color = QColor("#007ACC") if self._waypoint_wait else QColor("#28a745")
      if not self._preview_arrow_line:
        pen = QPen(preview_color, 2.0, Qt.PenStyle.DashLine)
        self._preview_arrow_line = self._scene.addLine(
            QLineF(self._drag_start_scene, scene_pt), pen
        )
        self._preview_arrow_line.setZValue(20.0)
      else:
        self._preview_arrow_line.setLine(
            QLineF(self._drag_start_scene, scene_pt)
        )

  def mouseReleaseEvent(self, event: QMouseEvent):
    if event.button() == Qt.MouseButton.RightButton and self._is_panning:
      self._is_panning = False
      self._pan_start_pos = None
      self.setCursor(Qt.CursorShape.CrossCursor)
      event.accept()
      return

    if (
        event.button() == Qt.MouseButton.LeftButton
        and self._drag_start_scene is not None
    ):
      release_pt = self.mapToScene(event.pos())

      dx = release_pt.x() - self._drag_start_scene.x()
      dy = release_pt.y() - self._drag_start_scene.y()
      drag_dist = math.hypot(dx, dy)

      if drag_dist > 5.0:
        scene_angle_deg = math.degrees(math.atan2(dy, dx))
        world_yaw = math.atan2(-dy, dx)
      else:
        scene_angle_deg = 0.0
        world_yaw = 0.0

      x_w, y_w = self._map_data.pixel_to_world(
          self._drag_start_scene.x(), self._drag_start_scene.y()
      )
      wp = Waypoint(
          id=len(self._waypoints) + 1,
          x=x_w,
          y=y_w,
          yaw=round(world_yaw, 3),
          wait=self._waypoint_wait,
      )

      self._add_waypoint_to_scene(wp, self._drag_start_scene, scene_angle_deg)
      self._waypoints.append(wp)
      self.waypoint_added.emit(wp)

      if self._preview_arrow_line:
        self._scene.removeItem(self._preview_arrow_line)
        self._preview_arrow_line = None
      self._drag_start_scene = None
      event.accept()
      return

    super().mouseReleaseEvent(event)

  def _add_waypoint_to_scene(
      self, wp: Waypoint, scene_pos: QPointF, scene_angle_deg: float
  ):
    if self._waypoint_items:
      prev_pos = self._waypoint_items[-1].pos()
      pen = QPen(QColor("#007ACC"), 1.8, Qt.PenStyle.DashDotLine)
      line_item = self._scene.addLine(QLineF(prev_pos, scene_pos), pen)
      line_item.setZValue(5.0)
      self._connection_lines.append(line_item)

    wp_item = WaypointItem(wp, scene_pos, scene_angle_deg)
    self._scene.addItem(wp_item)
    self._waypoint_items.append(wp_item)

  def clear_waypoints(self):
    for item in self._waypoint_items:
      self._scene.removeItem(item)
    for line in self._connection_lines:
      self._scene.removeItem(line)
    self._waypoints.clear()
    self._waypoint_items.clear()
    self._connection_lines.clear()
    self.waypoints_cleared.emit()

  def undo_last_waypoint(self):
    if not self._waypoint_items:
      return

    last_item = self._waypoint_items.pop()
    self._scene.removeItem(last_item)
    self._waypoints.pop()

    if self._connection_lines:
      last_line = self._connection_lines.pop()
      self._scene.removeItem(last_line)

  def get_waypoints(self) -> List[Waypoint]:
    return list(self._waypoints)

  def resizeEvent(self, event):
    super().resizeEvent(event)
    if self._map_data and not self._scene.sceneRect().isEmpty():
      self.fitInView(
          self._scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio
      )

  def update_robot_pose(self, x_w: float, y_w: float, yaw: float):
    if not self._map_data:
      return

    u, v = self._map_data.world_to_pixel(x_w, y_w)
    self._robot_item.show()
    self._robot_item.update_pose(QPointF(u, v), yaw)