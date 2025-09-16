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

import weakref
from ...views.graphview import GraphView


class NodeWidgetWithDelegate(NodeWidget):
    def __init__(self, graphview: GraphView, parent: QGraphicsItem | None = None):
        super().__init__(parent)
        self._graphview = weakref.ref(graphview)

    def paint(self, painter: QPainter, option: QStyleOption, widget=None):
        if self._graphview and self._graphview() and self._graphview()._delegate:
            self._graphview()._delegate.paintNode(painter, option, widget)
        else:
            super().paint(painter, option, widget)


class InletWidgetWithDelegate(PortWidget):
    def __init__(self, graphview: GraphView, parent: QGraphicsItem | None = None):
        super().__init__(parent)
        self._graphview = weakref.ref(graphview)

    def paint(self, painter: QPainter, option: QStyleOption, widget=None):
        if self._graphview and self._graphview() and self._graphview()._delegate:
            self._graphview()._delegate.paintInlet(painter, option, widget)
        else:
            super().paint(painter, option, widget)


class OutletWidgetWithDelegate(PortWidget):
    def __init__(self, graphview: GraphView, parent: QGraphicsItem | None = None):
        super().__init__(parent)
        self._graphview = weakref.ref(graphview)

    def paint(self, painter: QPainter, option: QStyleOption, widget=None):
        if self._graphview and self._graphview() and self._graphview()._delegate:
            self._graphview()._delegate.paintOutlet(painter, option, widget)
        else:
            super().paint(painter, option, widget)


class LinkWidgetWithDelegate(LinkWidget):
    def __init__(self, graphview: GraphView, parent: QGraphicsItem | None = None):
        super().__init__(parent)
        self._graphview = weakref.ref(graphview)

    def paint(self, painter: QPainter, option: QStyleOption, widget=None):
        if self._graphview and self._graphview() and self._graphview()._delegate:
            self._graphview()._delegate.paintLink(painter, option, widget)
        else:
            super().paint(painter, option, widget)


class CellWidgetWithDelegate(CellWidget):
    def __init__(self, graphview: GraphView, parent: QGraphicsItem | None = None):
        super().__init__(parent)
        self._graphview = weakref.ref(graphview)

    def paint(self, painter: QPainter, option: QStyleOption, widget=None):
        if self._graphview and self._graphview() and self._graphview()._delegate:
            self._graphview()._delegate.paintCell(painter, option, widget)
        else:
            super().paint(painter, option, widget)


class WidgetFactoryWithDelegate(QObject):
    portPositionChanged = Signal(QPersistentModelIndex)

    ## Widget Factory
    @override
    def createNodeWidget(self, parent_widget: QGraphicsScene, index: QModelIndex, graphview) -> 'NodeWidget':
        if not isinstance(parent_widget, QGraphicsScene):
            raise TypeError("Parent widget must be a QGraphicsScene")
        if not index.isValid():
            raise ValueError("Index must be valid")

        widget = NodeWidgetWithDelegate(graphview)
        parent_widget.addItem(widget)
        return widget

    @override
    def destroyNodeWidget(self, parent_widget: QGraphicsScene, widget: NodeWidgetWithDelegate):
        if not isinstance(parent_widget, QGraphicsScene):
            raise TypeError("Parent widget must be a QGraphicsScene")
        if not isinstance(widget, NodeWidgetWithDelegate):
            raise TypeError("Widget must be a NodeWidgetWithDelegate")

        parent_widget.removeItem(widget)

    @override
    def createInletWidget(self, parent_widget: NodeWidgetWithDelegate, index: QModelIndex, graphview) -> PortWidget:
        if not isinstance(parent_widget, NodeWidgetWithDelegate):
            raise TypeError("Parent widget must be a NodeWidget")
        if not index.isValid():
            raise ValueError("Index must be valid")

        widget = InletWidgetWithDelegate(graphview)
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
    
    @override
    def destroyInletWidget(self, parent_widget: NodeWidget, widget: PortWidget):
        if not isinstance(parent_widget, NodeWidget):
            raise TypeError("Parent widget must be a NodeWidget")
        if not isinstance(widget, PortWidget):
            raise TypeError("Widget must be an PortWidget")
        
        parent_widget.removeInlet(widget)
        # Schedule widget for deletion - this automatically disconnects all signals
        widget.deleteLater()
    
    @override
    def createOutletWidget(self, parent_widget: NodeWidget, index: QModelIndex, graphview) -> PortWidget:
        if not isinstance(parent_widget, NodeWidget):
            raise TypeError("Parent widget must be a NodeWidget")
        if not index.isValid():
            raise ValueError("Index must be valid")

        widget = OutletWidgetWithDelegate(graphview)
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
    
    @override
    def destroyOutletWidget(self, parent_widget: NodeWidget, widget: PortWidget):
        if not isinstance(parent_widget, NodeWidget):
            raise TypeError("Parent widget must be a NodeWidget")
        if not isinstance(widget, PortWidget):
            raise TypeError("Widget must be a PortWidget")

        parent_widget.removeOutlet(widget)
        # Schedule widget for deletion - this automatically disconnects all signals
        widget.deleteLater()
        
    @override
    def createLinkWidget(self, scene: QGraphicsScene, index: QModelIndex, graphview) -> LinkWidget:
        """Create a link widget. Links are added directly to the scene."""
        if not isinstance(scene, QGraphicsScene):
            raise TypeError("Scene must be a QGraphicsScene")
        if not index.isValid():
            raise ValueError("Index must be valid")

        link_widget = LinkWidgetWithDelegate(graphview)
        scene.addItem(link_widget)  # Links are added to the scene, not to the inlet widget
        return link_widget
    
    @override
    def destroyLinkWidget(self, scene: QGraphicsScene, widget: LinkWidget):
        if not isinstance(scene, QGraphicsScene):
            raise TypeError("Scene must be a QGraphicsScene")
        if not isinstance(widget, LinkWidget):
            raise TypeError("Widget must be a LinkWidget")
                
        scene.removeItem(widget)
        # Schedule widget for deletion to prevent memory leaks
        widget.deleteLater()

    @override
    def createCellWidget(self, parent_widget: NodeWidget|PortWidget|LinkWidget, index: QModelIndex, graphview) -> CellWidget:
        if not isinstance(parent_widget, (NodeWidget, PortWidget, LinkWidget)):
            raise TypeError("Parent widget must be a NodeWidget, PortWidget, or LinkWidget")
        if not index.isValid():
            raise ValueError("Index must be valid")

        cell = CellWidgetWithDelegate(graphview)
        parent_widget.insertCell(index.column(), cell)
        return cell

    @override
    def destroyCellWidget(self, parent_widget: NodeWidget|PortWidget|LinkWidget, widget: CellWidget):
        if not isinstance(parent_widget, (NodeWidget, PortWidget, LinkWidget)):
            raise TypeError("Parent widget must be a NodeWidget, PortWidget, or LinkWidget")
        if not isinstance(widget, CellWidget):
            raise TypeError("Widget must be a CellWidget")
        
        parent_widget.removeCell(widget)
        # Schedule widget for deletion - this automatically disconnects all signals
        widget.deleteLater()
