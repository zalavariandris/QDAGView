from typing import *
from qtpy.QtGui import *
from qtpy.QtCore import *
from qtpy.QtWidgets import *

from .base_widget import BaseWidget


class PortWidget(BaseWidget):
    scenePositionChanged = Signal(QPointF)
    def __init__(self, parent: QGraphicsItem | None = None):
        super().__init__(parent=parent)
        # self._links:List[LinkWidget] = []
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsScenePositionChanges, True)

    def itemChange(self, change, value):
        match change:
            case QGraphicsItem.GraphicsItemChange.ItemScenePositionHasChanged:
                if self.scene():
                    # Emit signal when position changes
                    self.scenePositionChanged.emit(value)

                    # # Update all links connected to this port
                    # for link in self._links:
                    #     link.updateLine()

                    
        return super().itemChange(change, value)

    def paint(self, painter, option, /, widget = ...):
        # return
        painter.setBrush(self.palette().alternateBase())
        painter.drawRect(option.rect)