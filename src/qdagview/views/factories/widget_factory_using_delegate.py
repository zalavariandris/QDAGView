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

if TYPE_CHECKING:
    from ...views.graphview import GraphView

def makeViewOption(option_graphics:QStyleOptionGraphicsItem, index:QModelIndex, widget=None):
    """
    Convert a QStyleOptionGraphicsItem + QModelIndex into a QStyleOptionViewItem.
    """
    assert isinstance(option_graphics, QStyleOptionGraphicsItem)
    assert isinstance(index, QModelIndex), f"Expected QModelIndex, got {type(index)}"
    opt = QStyleOptionViewItem()

    # Geometry
    opt.rect = option_graphics.rect

    # State flags (hovered, selected, enabled, etc.)
    opt.state = option_graphics.state

    # Palette
    if widget is not None:
        opt.palette = widget.palette()
        opt.font = widget.font()
    else:
        opt.palette = QApplication.palette()
        opt.font = QApplication.font()

    # Text & icon (from model data)
    opt.text = str(index.data(Qt.DisplayRole)) if index.isValid() else ""
    icon_data = index.data(Qt.DecorationRole) if index.isValid() else None
    opt.icon = icon_data if icon_data is not None else QIcon()

    # Alignment (from model or default)
    alignment = index.data(Qt.TextAlignmentRole)
    opt.displayAlignment = alignment if alignment is not None else Qt.AlignLeft | Qt.AlignVCenter

    # Check state (for checkboxes, if provided by model)
    check_state = index.data(Qt.CheckStateRole)
    if check_state is not None:
        opt.checkState = check_state
    else:
        opt.checkState = Qt.Unchecked

    # Features (optional: mark if it has checkboxes, etc.)
    # TODO: Set features based on model data if needed
    # opt.features = QStyleOptionViewItem.

    return opt

class NodeWidgetWithDelegate(NodeWidget):
    def __init__(self, graphview: GraphView, parent: QGraphicsItem | None = None):
        super().__init__(parent)
        self._graphview = weakref.ref(graphview)

    def paint(self, painter: QPainter, option: QStyleOption, widget=None):
        if graphview:=self._graphview():
            index = graphview._widget_manager.getIndex(self)
            if index is None:
                return # If index is None, the widget is being removed - skip painting
            opt = makeViewOption(option, index, graphview)
            graphview._delegate.paintNode(painter, opt, index)
        else:
            super().paint(painter, option, widget)


class InletWidgetWithDelegate(PortWidget):
    def __init__(self, graphview: GraphView, parent: QGraphicsItem | None = None):
        super().__init__(parent)
        self._graphview = weakref.ref(graphview)

    def paint(self, painter: QPainter, option: QStyleOption, widget=None):
        if graphview:=self._graphview():
            index = graphview._widget_manager.getIndex(self)
            if index is None:
                # TODO: revisit this logic. 
                # no painting should be invoked after it has been removed from the scene right?
                return # If index is None, the widget is being removed - skip painting
            opt = makeViewOption(option, index, graphview)
            graphview._delegate.paintInlet(painter, opt, index)
        else:
            super().paint(painter, option, widget)


class OutletWidgetWithDelegate(PortWidget):
    def __init__(self, graphview: GraphView, parent: QGraphicsItem | None = None):
        super().__init__(parent)
        self._graphview = weakref.ref(graphview)

    def paint(self, painter: QPainter, option: QStyleOption, widget=None):
        if graphview:=self._graphview():
            index = graphview._widget_manager.getIndex(self)
            if index is None:
                return # If index is None, the widget is being removed - skip painting
            opt = makeViewOption(option, index, graphview)
            graphview._delegate.paintInlet(painter, opt, index)
        else:
            super().paint(painter, option, widget)


class LinkWidgetWithDelegate(LinkWidget):
    def __init__(self, graphview: GraphView, parent: QGraphicsItem | None = None):
        super().__init__(parent)
        self._graphview = weakref.ref(graphview)

    def paint(self, painter: QPainter, option: QStyleOption, widget=None):
        if graphview:=self._graphview():
            index = graphview._widget_manager.getIndex(self)
            if index is None:
                return # If index is None, the widget is being removed - skip painting
            opt = makeViewOption(option, index, graphview)
            outlet = graphview._link_manager.getLinkSource(self)
            inlet = graphview._link_manager.getLinkTarget(self)
            # Set decoration alignment based on relative positions
            if outlet and inlet:
                dx = inlet.scenePos().x() - outlet.scenePos().x()
                dy = inlet.scenePos().y() - outlet.scenePos().y()
                if dx >= 0 and dy >= 0:  # Target is bottom-right
                    opt.decorationAlignment = Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight
                elif dx < 0 and dy >= 0:  # Target is bottom-left  
                    opt.decorationAlignment = Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft
                elif dx >= 0 and dy < 0:  # Target is top-right
                    opt.decorationAlignment = Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight
                else:  # Target is top-left
                    opt.decorationAlignment = Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft

            graphview._delegate.paintLink(painter, opt, index)
        
        else:
            super().paint(painter, option, widget)


class CellWidgetWithDelegate(CellWidget):
    def __init__(self, graphview: GraphView, parent: QGraphicsItem | None = None):
        super().__init__(parent)
        self._graphview = weakref.ref(graphview)

    def paint(self, painter: QPainter, option: QStyleOption, widget=None):
        if graphview:=self._graphview():
            index = graphview._cell_manager.getIndex(self)
            if index is not None:
                opt = makeViewOption(option, index, graphview)
                graphview._delegate.paintCell(painter, opt, index)
            # If index is None, the widget is being removed - skip painting
        else:
            super().paint(painter, option, widget)


class WidgetFactoryUsingDelegate(QObject):
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
            raise TypeError(f"Parent widget must be a NodeWidget, PortWidget, or LinkWidget, got {parent_widget}")
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
