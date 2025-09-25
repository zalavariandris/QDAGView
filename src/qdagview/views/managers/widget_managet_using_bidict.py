from bidict import bidict
from . import WidgetManagerProtocol
from typing import Hashable, List
from qtpy.QtWidgets import QGraphicsItem


class BidictWidgetManager(WidgetManagerProtocol):
    """Handles widgets mapping to model indexes."""
    def __init__(self):
        self._widgets: bidict[Hashable, QGraphicsItem] = bidict()
    
    def insertWidget(self, key:Hashable, widget:QGraphicsItem):
        """Insert a widget into the manager."""
        self._widgets[key] = widget

    def removeWidget(self, key:Hashable, widget:QGraphicsItem):
        """Remove a widget from the manager."""
        del self._widgets[key]

    def getWidget(self, key: Hashable) -> QGraphicsItem|None:
        # convert to persistent index
        return self._widgets.get(key, None)   
    
    def getKey(self, widget:QGraphicsItem) -> Hashable|None:
        """
        Get the index of the node widget in the model.
        This is used to identify the node in the model.
        """
        return self._widgets.inverse.get(widget, None)

    def widgets(self) -> List[QGraphicsItem]:
        return list(self._widgets.values())
    
    def clear(self):
        self._widgets.clear()