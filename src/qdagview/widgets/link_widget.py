from typing import *
from qtpy.QtGui import *
from qtpy.QtCore import *
from qtpy.QtWidgets import *

from .base_widget import BaseWidget
from .cell_widget import CellWidget
from ..utils import makeArrowShape, makeVerticalRoundedPath


class LinkWidgetStraight(QGraphicsWidget):
    def __init__(self, parent: QGraphicsItem | None = None):
        super().__init__(parent=parent)
        # self.setZValue(-1)  # Ensure links are drawn below nodes
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self._line = QLineF(0, 0, 100, 100)
        self.__cells: List[CellWidget] = []
        self.setAcceptHoverEvents(True)

        self._graphview = None

    
    # manage cells
    def insertCell(self, pos:int, cell:CellWidget):
        self.__cells.insert(pos, cell)
        cell.setParentItem(self)

        for i, cell in enumerate(self.__cells[pos:]):
            center = self._line.pointAt(0.5)
            cell.setPos(center.x(), center.y() + (pos + i) * 20)

    def removeCell(self, cell:CellWidget):
        pos = self.__cells.index(cell)
        self.__cells.remove(cell)
        cell.setParentItem(None)
        cell.deleteLater()
        for i, cell in enumerate(self.__cells[pos:]):
            center = self._line.pointAt(0.5)
            cell.setPos(center.x(), center.y() + (pos + i) * 20)

    def cells(self) -> list[CellWidget]:
        return [cell for cell in self.__cells]

    # manage appearance
    def line(self) -> QLineF:
        """Get the line of the link widget."""
        return self._line
    
    def setLine(self, line:QLineF):
        """Set the line of the link widget."""
        
        self.prepareGeometryChange()
        self._line = line

        _ = QRectF(line.p1(), line.p2())
        _ = _.normalized()
        self.update()

        # adjust offset endpoints
        for i, cell in enumerate(self.__cells):
            center = self._line.pointAt(0.5)
            cell.setPos(center.x(), center.y() + (i) * 20)

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
        palette = option.palette
        if self.isSelected():
            painter.setBrush(palette.accent())
        elif option.state & QStyle.StateFlag.State_MouseOver:
            painter.setBrush(palette.highlight())
        else:
            painter.setBrush(palette.text())
        painter.setPen(Qt.PenStyle.NoPen)
        arrow = makeArrowShape(self._line, 2)
        painter.drawPath(arrow)
        

class LinkWidgetRounded(QGraphicsWidget):
    def __init__(self, parent: QGraphicsItem | None = None):
        super().__init__(parent=parent)
        # self.setZValue(-1)  # Ensure links are drawn below nodes
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self._line = QLineF(0, 0, 100, 100)
        self.__cells: List[CellWidget] = []
        self.setAcceptHoverEvents(True)

        self._graphview = None

    # manage cells
    def insertCell(self, pos:int, cell:CellWidget):
        self.__cells.insert(pos, cell)
        cell.setParentItem(self)

        for i, cell in enumerate(self.__cells[pos:]):
            center = self._line.pointAt(0.5)
            cell.setPos(center.x(), center.y() + (pos + i) * 20)

    def removeCell(self, cell:CellWidget):
        pos = self.__cells.index(cell)
        self.__cells.remove(cell)
        cell.setParentItem(None)
        cell.deleteLater()
        for i, cell in enumerate(self.__cells[pos:]):
            center = self._line.pointAt(0.5)
            cell.setPos(center.x(), center.y() + (pos + i) * 20)

    def cells(self) -> list[CellWidget]:
        return [cell for cell in self.__cells]

    # manage appearance
    def line(self) -> QLineF:
        """Get the line of the link widget."""
        return self._line
    
    def setLine(self, line:QLineF):
        """Set the line of the link widget."""
        
        self.prepareGeometryChange()
        self._line = line

        _ = QRectF(line.p1(), line.p2())
        _ = _.normalized()
        self.update()

    def boundingRect(self):
        _ = QRectF(self._line.p1(), self._line.p2())
        _ = _.normalized()
        # _ = _.adjusted(-5,-5,5,5)
        return _
    
    def shape(self)->QPainterPath:
        path:QPainterPath = makeVerticalRoundedPath(self._line, width=4)
        return path
    
    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget=None):
        palette = option.palette
        if self.isSelected():
            color = palette.accent().color()
        elif option.state & QStyle.StateFlag.State_MouseOver:
            color = palette.highlight().color()
        else:
            color = palette.text().color()


        painter.setPen(QPen(color, 2))
        arrow = makeVerticalRoundedPath(self._line, 2)
        painter.drawPath(arrow)
        
