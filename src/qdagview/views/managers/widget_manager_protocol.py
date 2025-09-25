

from asyncio import Protocol
from typing import Hashable, List
from qtpy.QtWidgets import QGraphicsItem


class WidgetManagerProtocol(Protocol):
    """Protocol for widget managers."""
    def insertWidget(self, key:Hashable, widget:QGraphicsItem):
        ...
    def removeWidget(self, key:Hashable, widget:QGraphicsItem):
        ...
    def getWidget(self, key: Hashable) -> QGraphicsItem|None:
        ...
    def getKey(self, widget:QGraphicsItem) -> Hashable|None:
        ...
    def widgets(self) -> List[QGraphicsItem]:
        ...
    def clear(self):
        ...