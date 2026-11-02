import math
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsItemGroup,
    QGraphicsPathItem,
    QGraphicsSimpleTextItem,
)
from src.core.models import Waypoint


class WaypointItem(QGraphicsItemGroup):

  RADIUS = 10.0
  ARROW_LENGTH = 30.0

  def __init__(
      self,
      waypoint: Waypoint,
      scene_pos: QPointF,
      scene_angle_deg: float,
      parent=None,
  ):
    super().__init__(parent)
    self.waypoint = waypoint
    self.setPos(scene_pos)

    pin_color = QColor("#007ACC")  # Professional blue
    pin_border = QColor("#FFFFFF")
    text_color = QColor("#FFFFFF")

    circle = QGraphicsEllipseItem(
        -self.RADIUS, -self.RADIUS, self.RADIUS * 2, self.RADIUS * 2, self
    )
    circle.setBrush(QBrush(pin_color))
    circle.setPen(QPen(pin_border, 2.0))

    label = QGraphicsSimpleTextItem(str(waypoint.id), self)
    font = QFont("Arial", 9, QFont.Weight.Bold)
    label.setFont(font)
    label.setBrush(QBrush(text_color))
    rect = label.boundingRect()
    label.setPos(-rect.width() / 2, -rect.height() / 2)

    self.arrow_group = QGraphicsItemGroup(self)
    self._build_arrow()
    self.arrow_group.setRotation(scene_angle_deg)

    self.setZValue(10.0)

  def _build_arrow(self):
    stem_pen = QPen(QColor("#007ACC"), 3.0)
    stem_pen.setCapStyle(Qt.PenCapStyle.RoundCap)

    path = QPainterPath()
    path.moveTo(self.RADIUS, 0)
    path.lineTo(self.ARROW_LENGTH, 0)
    stem_item = QGraphicsPathItem(path, self.arrow_group)
    stem_item.setPen(stem_pen)

    head_size = 6.0
    arrow_head = QPolygonF([
        QPointF(self.ARROW_LENGTH, 0),
        QPointF(self.ARROW_LENGTH - head_size, -head_size),
        QPointF(self.ARROW_LENGTH - head_size, head_size),
    ])
    head_item = QGraphicsPathItem(self.arrow_group)
    head_path = QPainterPath()
    head_path.addPolygon(arrow_head)
    head_item.setPath(head_path)
    head_item.setBrush(QBrush(QColor("#007ACC")))
    head_item.setPen(QPen(Qt.PenStyle.NoPen))