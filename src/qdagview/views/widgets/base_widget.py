from typing import cast, List
from qtpy.QtGui import *
from qtpy.QtCore import *
from qtpy.QtWidgets import *

from .cell_widget import CellWidget


class BaseWidget(QGraphicsWidget):
    def __init__(self, parent: QGraphicsItem | None = None):
        super().__init__(parent=parent)
        # create layout
        layout = QGraphicsLinearLayout(Qt.Orientation.Vertical)
        self.setLayout(layout)
        layout.updateGeometry()        
        
    def insertCell(self, pos:int, cell:CellWidget):
        layout = cast(QGraphicsLinearLayout, self.layout())
        layout.insertItem(pos, cell)
        layout.setStretchFactor(cell, 1)
        layout.setAlignment(cell, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
        layout.updateGeometry()
        self.updateGeometry()

    def removeCell(self, cell:CellWidget):
        layout = cast(QGraphicsLinearLayout, self.layout())
        layout.removeItem(cell)

    def cells(self) -> List[CellWidget]:
        layout = cast(QGraphicsLinearLayout, self.layout())
        return [layout.itemAt(i) for i in range(layout.count())]

    def paint(self, painter:QPainter, option, /, widget:QWidget|None = None):
        painter.setBrush(QColor("lightblue"))
        painter.drawRect(option.rect)
