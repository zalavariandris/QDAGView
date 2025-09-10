from typing import *
from qtpy.QtGui import *
from qtpy.QtCore import *
from qtpy.QtWidgets import *

from .base_widget import BaseWidget
from .cell_widget import CellWidget
from .inlet_widget import InletWidget
from .outlet_widget import OutletWidget

class NodeWidget(BaseWidget):
    def __init__(self, parent: QGraphicsItem | None = None):
        super().__init__(parent=parent)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)

        layout = cast(QGraphicsLinearLayout, self.layout())
        layout.setOrientation(Qt.Orientation.Vertical)

        self._cells_layout = QGraphicsLinearLayout(Qt.Orientation.Vertical)
        layout.addItem(self._cells_layout)

        ports_layout = QGraphicsLinearLayout(Qt.Orientation.Horizontal)
        layout.addItem(ports_layout)

        self._inlets_layout = QGraphicsLinearLayout(Qt.Orientation.Vertical)
        self._outlets_layout = QGraphicsLinearLayout(Qt.Orientation.Vertical)
        ports_layout.addItem(self._inlets_layout)
        ports_layout.addItem(self._outlets_layout)

    def insertInlet(self, pos: int, inlet: InletWidget):
        layout = self._inlets_layout
        layout.insertItem(pos, inlet)

    def removeInlet(self, inlet:InletWidget):
        layout = self._inlets_layout
        layout.removeItem(inlet)

    def inlets(self) -> list[InletWidget]:
        layout = self._inlets_layout
        return [layout.itemAt(i) for i in range(layout.count())]

    def insertOutlet(self, pos: int, outlet: OutletWidget):
        layout = self._outlets_layout
        layout.insertItem(pos, outlet)

    def removeOutlet(self, outlet: OutletWidget):
        layout = self._outlets_layout
        layout.removeItem(outlet)

    def outlets(self) -> list[OutletWidget]:
        layout = self._outlets_layout
        return [layout.itemAt(i) for i in range(layout.count())]

    def insertCell(self, pos, cell):
        layout = self._cells_layout
        layout.insertItem(pos, cell)
    
    def removeCell(self, cell):
        layout = self._cells_layout
        layout.removeItem(cell)

    def cells(self) -> list[CellWidget]:
        layout = self._cells_layout
        return [layout.itemAt(i) for i in range(layout.count())]

    def paint(self, painter: QPainter, option: QStyleOption, widget=None):
        rect = option.rect       
        painter.setBrush(self.palette().alternateBase())
        if self.isSelected():
            painter.setBrush(self.palette().highlight())
        painter.drawRoundedRect(rect, 6, 6)