from enum import Enum
from typing import *
from qtpy.QtGui import *
from qtpy.QtCore import *
from qtpy.QtWidgets import *

import logging
logger = logging.getLogger(__name__)


from bidict import bidict

from ...core import indexToPath, indexFromPath


class PersistentWidgetManager:
    """Handles widgets mapping to model indexes."""
    def __init__(self):
        self._widgets: bidict[QPersistentModelIndex, QGraphicsItem] = bidict()
    
    def insertWidget(self, index:QModelIndex|QPersistentModelIndex, widget:QGraphicsItem):
        """Insert a widget into the manager."""
        self._widgets[QPersistentModelIndex(index)] = widget

    def removeWidget(self, index:QModelIndex|QPersistentModelIndex, widget:QGraphicsItem):
        """Remove a widget from the manager."""
        del self._widgets[QPersistentModelIndex(index)]

    def getWidget(self, index: QModelIndex) -> QGraphicsItem:
        if not index.isValid():
            logger.warning(f"Index is invalid: {index}")
            return None
        
        # convert to persistent index
        persistent_idx = QPersistentModelIndex(index)
        return self._widgets.get(persistent_idx, None)   
    
    def getIndex(self, widget:QGraphicsItem) -> QModelIndex:
        """
        Get the index of the node widget in the model.
        This is used to identify the node in the model.
        """
        idx = self._widgets.inverse[widget]
        return QModelIndex(idx)

    def widgets(self) -> List[QGraphicsItem]:
        return list(self._widgets.values())
    
    def clearWidgets(self):
        self._widgets.clear()

