from __future__ import annotations

import logging
import weakref
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

from typing import *

from qtpy.QtGui import *
from qtpy.QtCore import *
from qtpy.QtWidgets import *

from .widgets import (
    NodeWidget, InletWidget, OutletWidget, LinkWidget, CellWidget, BaseWidget
)

if TYPE_CHECKING:
    from .graphview_delegate import GraphDelegate


class WidgetFactory(QObject):
    portPositionChanged = Signal(QPersistentModelIndex)

    ## Widget Factory
    def createNodeWidget(self, parent_widget: QGraphicsScene, index: QModelIndex) -> 'NodeWidget':
        if not isinstance(parent_widget, QGraphicsScene):
            raise TypeError("Parent widget must be a QGraphicsScene")
        if not index.isValid():
            raise ValueError("Index must be valid")
        
        widget = NodeWidget()
        parent_widget.addItem(widget)
        return widget

    def destroyNodeWidget(self, parent_widget: QGraphicsScene, widget: NodeWidget):
        if not isinstance(parent_widget, QGraphicsScene):
            raise TypeError("Parent widget must be a QGraphicsScene")
        if not isinstance(widget, NodeWidget):
            raise TypeError("Widget must be a NodeWidget")
        
        parent_widget.removeItem(widget)
        # Schedule widget for deletion - this automatically disconnects all signals
        widget.deleteLater()

    def createInletWidget(self, parent_widget: NodeWidget, index: QModelIndex) -> 'InletWidget':
        if not isinstance(parent_widget, NodeWidget):
            raise TypeError("Parent widget must be a NodeWidget")
        if not index.isValid():
            raise ValueError("Index must be valid")
        
        widget = InletWidget()
        parent_widget.insertInlet(index.row(), widget)
        
        # Store the persistent index directly on the widget
        # This avoids closure issues entirely
        persistent_index = QPersistentModelIndex(index)
        widget.setProperty("modelIndex", persistent_index)
        
        # Connect using a simple lambda that gets the property
        widget.scenePositionChanged.connect(
            lambda: self.portPositionChanged.emit(widget.property("modelIndex")) 
            if widget.property("modelIndex").isValid() else None
        )
        return widget
    
    def destroyInletWidget(self, parent_widget: NodeWidget, widget: InletWidget):
        if not isinstance(parent_widget, NodeWidget):
            raise TypeError("Parent widget must be a NodeWidget")
        if not isinstance(widget, InletWidget):
            raise TypeError("Widget must be an InletWidget")
        
        parent_widget.removeInlet(widget)
        # Schedule widget for deletion - this automatically disconnects all signals
        widget.deleteLater()
    
    def createOutletWidget(self, parent_widget: NodeWidget, index: QModelIndex) -> 'OutletWidget':
        if not isinstance(parent_widget, NodeWidget):
            raise TypeError("Parent widget must be a NodeWidget")
        if not index.isValid():
            raise ValueError("Index must be valid")
        
        widget = OutletWidget()
        # Fix: Use actual row position instead of hardcoded 0
        outlet_position = index.row()
        parent_widget.insertOutlet(outlet_position, widget)
        
        # Store the persistent index directly on the widget
        # This avoids closure issues entirely
        persistent_index = QPersistentModelIndex(index)
        widget.setProperty("modelIndex", persistent_index)
        
        # Connect using a simple lambda that gets the property
        widget.scenePositionChanged.connect(
            lambda: self.portPositionChanged.emit(widget.property("modelIndex")) 
            if widget.property("modelIndex").isValid() else None
        )
        return widget
    
    def destroyOutletWidget(self, parent_widget: NodeWidget, widget: OutletWidget):
        if not isinstance(parent_widget, NodeWidget):
            raise TypeError("Parent widget must be a NodeWidget")
        if not isinstance(widget, OutletWidget):
            raise TypeError("Widget must be an OutletWidget")
        
        parent_widget.removeOutlet(widget)
        # Schedule widget for deletion - this automatically disconnects all signals
        widget.deleteLater()
        
    def createLinkWidget(self, scene: QGraphicsScene, index: QModelIndex) -> LinkWidget:
        """Create a link widget. Links are added directly to the scene."""
        if not isinstance(scene, QGraphicsScene):
            raise TypeError("Scene must be a QGraphicsScene")
        if not index.isValid():
            raise ValueError("Index must be valid")
        
        link_widget = LinkWidget()
        scene.addItem(link_widget)
        return link_widget
    
    def destroyLinkWidget(self, scene: QGraphicsScene, widget: LinkWidget):
        if not isinstance(scene, QGraphicsScene):
            raise TypeError("Scene must be a QGraphicsScene")
        if not isinstance(widget, LinkWidget):
            raise TypeError("Widget must be a LinkWidget")
                
        scene.removeItem(widget)
        # Schedule widget for deletion to prevent memory leaks
        widget.deleteLater()

    def createCellWidget(self, parent_widget: BaseWidget, index: QModelIndex) -> CellWidget:
        if not isinstance(parent_widget, BaseWidget):
            raise TypeError("Parent widget must be a BaseWidget")
        if not index.isValid():
            raise ValueError("Index must be valid")
        
        cell = CellWidget()
        parent_widget.insertCell(index.column(), cell)
        return cell

    def destroyCellWidget(self, parent_widget: BaseWidget, widget: CellWidget):
        if not isinstance(parent_widget, BaseWidget):
            raise TypeError("Parent widget must be a BaseWidget")
        if not isinstance(widget, CellWidget):
            raise TypeError("Widget must be a CellWidget")
        
        parent_widget.removeCell(widget)
        # Schedule widget for deletion - this automatically disconnects all signals
        widget.deleteLater()
