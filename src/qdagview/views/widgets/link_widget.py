from typing import *
from qtpy.QtGui import *
from qtpy.QtCore import *
from qtpy.QtWidgets import *

from .base_widget import BaseWidget
from .cell_widget import CellWidget
from ...utils import makeArrowShape


class LinkWidget(BaseWidget):
    def __init__(self, parent: QGraphicsItem | None = None):
        super().__init__(parent=parent)
        # self.setZValue(-1)  # Ensure links are drawn below nodes
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self._line = QLineF(0, 0, 100, 100)
        self._label = QLabel("Link")
        # self._source: QGraphicsItem | None = None
        # self._target: QGraphicsItem | None = None
        self.setAcceptHoverEvents(True)
        # self.layout().
    
    def insertCell(self, pos:int, cell:CellWidget):
        layout = cast(QGraphicsLinearLayout, self.layout())
        layout.insertItem(pos, cell)
        layout.setStretchFactor(cell, 0)  # Don't stretch the cell
        layout.setAlignment(cell, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)

    def removeCell(self, cell:CellWidget):
        layout = cast(QGraphicsLinearLayout, self.layout())
        layout.removeItem(cell)

    def cells(self) -> list[CellWidget]:
        layout = cast(QGraphicsLinearLayout, self.layout())
        return [layout.itemAt(i) for i in range(layout.count())]

    def line(self) -> QLineF:
        """Get the line of the link widget."""
        return self._line
    
    def setLine(self, line:QLineF):
        """Set the line of the link widget."""
        
        self.prepareGeometryChange()
        self._line = line

        _ = QRectF(line.p1(), line.p2())
        _ = _.normalized()
        self.layout().setGeometry(_)

        self.update()

    def boundingRect(self):
        _ = QRectF(self._line.p1(), self._line.p2())
        _ = _.normalized()
        _ = _.adjusted(-5,-5,5,5)
        return _
    
    def shape(self)->QPainterPath:
        path = QPainterPath()
        path.moveTo(self._line.p1())
        path.lineTo(self._line.p2())
        stroker = QPainterPathStroker()
        stroker.setWidth(4)
        return stroker.createStroke(path)
    
    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget=None):
        if self.isSelected():
            painter.setBrush(self.palette().accent())
        elif option.state & QStyle.StateFlag.State_MouseOver:
            painter.setBrush(Qt.red)
        else:
            painter.setBrush(self.palette().text())
        painter.setPen(Qt.PenStyle.NoPen)
        arrow = makeArrowShape(self._line, 2)
        painter.drawPath(arrow)
