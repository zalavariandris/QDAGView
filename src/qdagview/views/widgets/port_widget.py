from typing import *
from qtpy.QtGui import *
from qtpy.QtCore import *
from qtpy.QtWidgets import *

from .cell_widget import CellWidget


class PortWidget(QGraphicsObject):
    scenePositionChanged = Signal(QPointF)
    def __init__(self, parent: QGraphicsItem | None = None):
        super().__init__(parent=parent)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsScenePositionChanges, True)
        self.setAcceptHoverEvents(True)
        self.setAcceptDrops(True)

        self._cells: List[CellWidget] = []

    def setTextAlignment(self, alignment:Qt.AlignmentFlag):
        match alignment:
            case Qt.AlignmentFlag.AlignLeft:
                ...
            case Qt.AlignmentFlag.AlignRight:
                ...
            case Qt.AlignmentFlag.AlignHCenter:
                ...
            case Qt.AlignmentFlag.AlignTop:
                ...
            case Qt.AlignmentFlag.AlignBottom:
                ...
            case Qt.AlignmentFlag.AlignVCenter:
                ...
            case Qt.AlignmentFlag.AlignBaseline:
                ...
            case Qt.AlignmentFlag.AlignCenter:
                ...
            case _:
                raise ValueError(f"Unsupported alignment: {alignment}")

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value: Any):
        match change:
            case QGraphicsItem.GraphicsItemChange.ItemScenePositionHasChanged:
                if self.scene():
                    # Emit signal when position changes
                    self.scenePositionChanged.emit(value)
                    
        return super().itemChange(change, value)

    # manage cells
    def _arrangeCells(self, first=0, last=-1):
        spacing = 20
        width, height = self.boundingRect().width(), self.boundingRect().height()
        for i, cell in enumerate(self._cells):
            fm = QFontMetricsF(cell.font())
            cell_y = height-cell.boundingRect().height()+fm.descent()
            cell.setPos(width, cell_y + i*spacing)

    def insertCell(self, pos:int, cell: CellWidget):
        self._cells.insert(pos, cell)
        cell.setParentItem(self)
        self._arrangeCells(pos)


        cell.setVisible(False)
    
    def removeCell(self, cell: CellWidget):
        self._cells.remove(cell)
        self._arrangeCells()

    def cells(self) -> List[CellWidget]:
        return [cell for cell in self._cells]

    # customize appearance
    def boundingRect(self):
        return QRectF(0, 0, 8,8)
    
    def paint(self, painter:QPainter, option, /, widget = ...):
        palette = self.scene().palette()
        painter.setBrush(palette.alternateBase())
        painter.drawEllipse(option.rect)

    def hoverEnterEvent(self, event: QGraphicsSceneHoverEvent):
        for cell in self._cells:
            cell.setVisible(True)

    def hoverLeaveEvent(self, event: QGraphicsSceneHoverEvent):
        for cell in self._cells:
            cell.setVisible(False)
