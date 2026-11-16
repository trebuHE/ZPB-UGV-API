import math
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QBrush, QColor, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import QGraphicsItemGroup, QGraphicsPathItem


class RobotItem(QGraphicsItemGroup):
  """Renders the live robot pose as an oriented marker."""

  def __init__(self, parent=None):
    super().__init__(parent)
    
    # Robot dimensions (triangle pointing right along +X)
    length = 18.0
    width = 12.0

    triangle = QPolygonF([
        QPointF(length / 2, 0),
        QPointF(-length / 2, -width / 2),
        QPointF(-length / 2, width / 2),
    ])

    path = QPainterPath()
    path.addPolygon(triangle)
    path.closeSubpath()

    self.marker = QGraphicsPathItem(path, self)
    
    # Use a distinct color (e.g., Warning Orange)
    self.marker.setBrush(QBrush(QColor("#FF7F50")))
    self.marker.setPen(QPen(QColor("#FFFFFF"), 1.5))
    
    # Ensure robot is drawn above waypoints and lines
    self.setZValue(50.0)

  def update_pose(self, scene_pos: QPointF, yaw_rad: float):
    self.setPos(scene_pos)
    # Qt's coordinate system is Y-down, ROS is Y-up. 
    # Convert counter-clockwise yaw to Qt rotation degrees.
    self.setRotation(math.degrees(-yaw_rad))