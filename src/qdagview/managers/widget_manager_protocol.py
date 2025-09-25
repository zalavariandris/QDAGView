

from asyncio import Protocol
from typing import Hashable, List
from qtpy.QtWidgets import QGraphicsItem

from qtpy.QtCore import QModelIndex, QPersistentModelIndex

class WidgetIndexManagerProtocol(Protocol):
    """Protocol for widget managers."""
    def insertWidget(self, index:QModelIndex, widget:QGraphicsItem):
        ...
    def removeWidget(self, index:QModelIndex):
        ...
    def getWidget(self, index: QModelIndex) -> QGraphicsItem|None:
        ...
    def getIndex(self, widget:QGraphicsItem) -> QModelIndex|None:
        ...
    def widgets(self) -> List[QGraphicsItem]:
        ...
    def clear(self):
        ...