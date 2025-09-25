from enum import Enum
from typing import *
from qtpy.QtGui import *
from qtpy.QtCore import *
from qtpy.QtWidgets import *

import logging
logger = logging.getLogger(__name__)


from bidict import bidict

from ..core import indexToPath, indexFromPath
from . import WidgetIndexManagerProtocol


class PersistentWidgetIndexManager(WidgetIndexManagerProtocol):
    """Handles widgets mapping to model indexes."""
    def __init__(self):
        self._widgets: bidict[QPersistentModelIndex, QGraphicsItem] = bidict()
    
    def insertWidget(self, index:QModelIndex|QPersistentModelIndex, widget:QGraphicsItem):
        """Insert a widget into the manager."""
        self._widgets[QPersistentModelIndex(index)] = widget

    def removeWidget(self, index:QModelIndex|QPersistentModelIndex):
        """Remove a widget from the manager."""
        del self._widgets[QPersistentModelIndex(index)]

    def getWidget(self, index: QModelIndex) -> QGraphicsItem|None:
        if not index.isValid():
            logger.warning(f"Index is invalid: {index}")
            return None
        
        # convert to persistent index
        persistent_idx = QPersistentModelIndex(index)
        return self._widgets.get(persistent_idx, None)   
    
    def getIndex(self, widget:QGraphicsItem) -> QModelIndex|None:
        """
        Get the index of the node widget in the model.
        This is used to identify the node in the model.
        """
        persistent_idx = self._widgets.inverse.get(widget, None)
        return QModelIndex(persistent_idx) if persistent_idx else None

    def widgets(self) -> List[QGraphicsItem]:
        return list(self._widgets.values())
    
    def clear(self):
        self._widgets.clear()

