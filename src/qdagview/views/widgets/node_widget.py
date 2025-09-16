from typing import *
from qtpy.QtGui import *
from qtpy.QtCore import *
from qtpy.QtWidgets import *

from .cell_widget import CellWidget
from .port_widget import PortWidget
from ...utils import distribute_items_horizontal

class NodeWidget(QGraphicsItem):
    def __init__(self, parent: QGraphicsItem | None = None):
        super().__init__(parent=parent)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)

        # manage ports
        self._inlets: List[PortWidget] = []
        self._outlets: List[PortWidget] = []

        # manage cells
        self._cells: List[CellWidget] = []

        self._graphview = None

    # manage inlets
    def _arrangeInlets(self, first=0, last=-1):
        for i, inlet in enumerate(self._inlets):
            inlet.setPos(0, -10)
        distribute_items_horizontal(self._inlets, self.boundingRect().adjusted(10, 0, -10, 0), equal_spacing=False)

    def insertInlet(self, pos: int, inlet: PortWidget):
        self._inlets.insert(pos, inlet)
        inlet.setParentItem(self)
        self._arrangeInlets(pos)

    def removeInlet(self, inlet:PortWidget):
        self._inlets.remove(inlet)
        self._arrangeInlets()

    def inlets(self) -> list[PortWidget]:
        return [inlet for inlet in self._inlets]

    # manage outlets
    def _arrangeOutlets(self, first=0, last=-1):
        for i, outlet in enumerate(self._outlets):
            outlet.setPos(0, self.boundingRect().height() + 2)
        distribute_items_horizontal(self._outlets, self.boundingRect().adjusted(10, 0, -10, 0), equal_spacing=False)

    def insertOutlet(self, pos: int, outlet: PortWidget):
        self._outlets.insert(pos, outlet)
        outlet.setParentItem(self)
        self._arrangeOutlets(pos)

    def removeOutlet(self, outlet: PortWidget):
        self._outlets.remove(outlet)
        self._arrangeOutlets()

    def outlets(self) -> list[PortWidget]:
        return [outlet for outlet in self._outlets]

    # manage cells
    def _arrangeCells(self, first=0, last=-1):
        if len(self._cells) == 0:
            return
        
        first_cell = self._cells[0]
        first_cell.setPos(5, -2)  # First cell position


        for i, cell in enumerate(self._cells[1:]):
            cell.setPos(self.boundingRect().width(), -2 + i * 12)

    def insertCell(self, pos, cell:QGraphicsItem):
        self._cells.insert(pos, cell)
        cell.setParentItem(self)
        self._arrangeCells(pos)

    def removeCell(self, cell: CellWidget):
        self._cells.remove(cell)
        self._arrangeCells()

    def cells(self) -> list[CellWidget]:
        return [cell for cell in self._cells]

    # customize appearance
    def boundingRect(self):
        return QRectF(0, 0, 64, 20)
    
    def paint(self, painter: QPainter, option: QStyleOption, widget=None):
        rect = option.rect
        
        palette = self.scene().palette()
        painter.setBrush(palette.alternateBase())
        if self.isSelected():
            painter.setBrush(palette.highlight())

        painter.drawRoundedRect(rect, 6, 6)