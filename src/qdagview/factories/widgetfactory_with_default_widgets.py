from __future__ import annotations

import logging
import weakref
logger = logging.getLogger(__name__)

from typing import *

from qtpy.QtGui import *
from qtpy.QtCore import *
from qtpy.QtWidgets import *

from ..widgets import (
    NodeWidget, PortWidget, LinkWidget, CellWidget
)

class WidgetFactory(QObject):
    portPositionChanged = Signal(object)

    ## Widget Factory
    def createNodeWidget(self, parent_widget: QGraphicsScene, index, graphview=None) -> 'NodeWidget':
        if not isinstance(parent_widget, QGraphicsScene):
            raise TypeError("Parent widget must be a QGraphicsScene")
        # if not index.isValid():
        #     raise ValueError("Index must be valid")
        
        widget = NodeWidget()
        parent_widget.addItem(widget)
        return widget

    def destroyNodeWidget(self, parent_widget: QGraphicsScene, widget: NodeWidget):
        if not isinstance(parent_widget, QGraphicsScene):
            raise TypeError("Parent widget must be a QGraphicsScene")
        
        if not isinstance(widget, NodeWidget):
            raise TypeError("Widget must be a NodeWidget")
        
        parent_widget.removeItem(widget)

    def createInletWidget(self, parent_widget: NodeWidget, index: QModelIndex, graphview=None) -> PortWidget:
        if not isinstance(parent_widget, NodeWidget):
            raise TypeError("Parent widget must be a NodeWidget")
        # if not index.isValid():
        #     raise ValueError("Index must be valid")

        # get inlet position from graph controller TODO: this is a bit hacky, we should have a cleaner way to get the port position without relying on the graph controller
        graph_controller = graphview._graph_controller
        node_ref = graph_controller.inletNode(index)
        inlets = graph_controller.inlets(node_ref) # Ensure inlets are loaded for the node
        pos = inlets.index(index)
        if pos == -1:
            raise ValueError(f"Port {index} is not an inlet of node {node_ref}")
        
        widget = PortWidget()
        parent_widget.insertInlet(pos, widget)
        
        # Store the persistent index directly on the widget
        # This avoids closure issues entirely
        widget.setProperty("modelIndex", index)
        
        # Connect using a simple lambda that gets the property
        widget.scenePositionChanged.connect(
            lambda: self.portPositionChanged.emit(widget.property("modelIndex")) 
            # if widget.property("modelIndex").isValid() else None
        )
        return widget
    
    def destroyInletWidget(self, parent_widget: NodeWidget, widget: PortWidget):
        if not isinstance(parent_widget, NodeWidget):
            raise TypeError("Parent widget must be a NodeWidget")
        if not isinstance(widget, PortWidget):
            raise TypeError("Widget must be an PortWidget")
        
        parent_widget.removeInlet(widget)
        # Schedule widget for deletion - this automatically disconnects all signals
        widget.deleteLater()
    
    def createOutletWidget(self, parent_widget: NodeWidget, index: QModelIndex, graphview=None) -> PortWidget:
        if not isinstance(parent_widget, NodeWidget):
            raise TypeError("Parent widget must be a NodeWidget")
        # if not index.isValid():
        #     raise ValueError("Index must be valid")
        
        widget = PortWidget()
        # get outlet position from graph controller TODO: this is a bit hacky, we should have a cleaner way to get the port position without relying on the graph controller
        graph_controller = graphview._graph_controller
        node_ref = graph_controller.outletNode(index)
        outlets = graph_controller.outlets(node_ref) # Ensure outlets are loaded for the node
        pos = outlets.index(index)
        if pos == -1:
            raise ValueError(f"Port {index} is not an outlet of node {node_ref}")

        parent_widget.insertOutlet(pos, widget)
        
        # Store the persistent index directly on the widget
        # This avoids closure issues entirely
        widget.setProperty("modelIndex", index)
        
        # Connect using a simple lambda that gets the property
        widget.scenePositionChanged.connect(
            lambda: self.portPositionChanged.emit(widget.property("modelIndex")) 
            # if widget.property("modelIndex").isValid() else None
        )
        return widget
    
    def destroyOutletWidget(self, parent_widget: NodeWidget, widget: PortWidget):
        if not isinstance(parent_widget, NodeWidget):
            raise TypeError("Parent widget must be a NodeWidget")
        if not isinstance(widget, PortWidget):
            raise TypeError("Widget must be a PortWidget")

        parent_widget.removeOutlet(widget)
        # Schedule widget for deletion - this automatically disconnects all signals
        widget.deleteLater()
        
    def createLinkWidget(self, scene: QGraphicsScene, index: QModelIndex, graphview=None) -> LinkWidget:
        """Create a link widget. Links are added directly to the scene."""
        if not isinstance(scene, QGraphicsScene):
            raise TypeError("Scene must be a QGraphicsScene")
        # if not index.isValid():
        #     raise ValueError("Index must be valid")
        
        link_widget = LinkWidget()
        scene.addItem(link_widget)  # Links are added to the scene, not to the inlet widget
        return link_widget
    
    def destroyLinkWidget(self, scene: QGraphicsScene, widget: LinkWidget):
        if not isinstance(scene, QGraphicsScene):
            raise TypeError("Scene must be a QGraphicsScene")
        if not isinstance(widget, LinkWidget):
            raise TypeError("Widget must be a LinkWidget")
                
        scene.removeItem(widget)
        # Schedule widget for deletion to prevent memory leaks
        widget.deleteLater()

    def createCellWidget(self, parent_widget: NodeWidget|PortWidget|LinkWidget, index: Hashable, graphview=None) -> CellWidget:
        if not isinstance(parent_widget, (NodeWidget, PortWidget, LinkWidget)):
            raise TypeError("Parent widget must be a NodeWidget, PortWidget, or LinkWidget")
        # if not index.isValid():
        #     raise ValueError("Index must be valid")
        
        cell = CellWidget()
        parent = graphview._graph_controller.attributeOwner(index)
        attributes = graphview._graph_controller.attributes(index.owner)
        pos = attributes.index(index)
        if pos == -1:
            raise ValueError(f"Attribute {index} is not an attribute of {index.owner}")
        parent_widget.insertCell(pos, cell)
        return cell

    def destroyCellWidget(self, parent_widget: NodeWidget|PortWidget|LinkWidget, widget: CellWidget):
        if not isinstance(parent_widget, (NodeWidget, PortWidget, LinkWidget)):
            raise TypeError("Parent widget must be a NodeWidget, PortWidget, or LinkWidget")
        if not isinstance(widget, CellWidget):
            raise TypeError("Widget must be a CellWidget")
        
        parent_widget.removeCell(widget)
        # Schedule widget for deletion - this automatically disconnects all signals
        widget.deleteLater()
