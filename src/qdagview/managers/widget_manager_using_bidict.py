from enum import Enum
from typing import *
from qtpy.QtGui import *
from qtpy.QtCore import *
from qtpy.QtWidgets import *

import logging
logger = logging.getLogger(__name__)


from bidict import bidict

from ..core import indexToPath, indexFromPath
from . import WidgetManagerProtocol


# imprt types
IndexT = TypeVar("IndexT")

class BiDictWidgetManager(Generic[IndexT], WidgetManagerProtocol):
    """Handles widgets mapping to model indexes."""
    def __init__(self):
        self._widgets: bidict[IndexT, QGraphicsItem] = bidict()
    
    def insertWidget(self, index:IndexT, widget:QGraphicsItem):
        """Insert a widget into the manager."""
        self._widgets[index] = widget

    def removeWidget(self, index:IndexT):
        """Remove a widget from the manager."""
        del self._widgets[index]

    def getWidget(self, index: IndexT) -> QGraphicsItem|None:
        return self._widgets.get(index, None)   
    
    def getIndex(self, widget:QGraphicsItem) -> IndexT|None:
        """
        Get the index of the node widget in the model.
        This is used to identify the node in the model.
        """
        return self._widgets.inverse.get(widget, None)

    def widgets(self) -> List[QGraphicsItem]:
        return list(self._widgets.values())
    
    def clear(self):
        self._widgets.clear()

