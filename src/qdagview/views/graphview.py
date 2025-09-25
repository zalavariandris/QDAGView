##################
# The Graph View #
##################

  
#
# A Graph view that directly connects to QStandardItemModel
#

from __future__ import annotations

import logging

from qdagview.utils.qt import blockingSignals
logger = logging.getLogger(__name__)

from typing import *
from enum import Enum
from dataclasses import dataclass

from qtpy.QtGui import *
from qtpy.QtCore import *
from qtpy.QtWidgets import *

import networkx as nx

from ..core import GraphDataRole, GraphItemType, GraphMimeType, indexToPath, indexFromPath
from ..utils import group_consecutive_numbers
from ..utils import makeLineBetweenShapes, makeLineToShape, makeArrowShape, getShapeCenter
from ..utils import bfs

from .tools.linking_tool import LinkingTool

from .managers import BidictWidgetManager, PersistentWidgetManager
from .managers.linking_manager import LinkingManager
from .managers.cell_manager import CellManager

from .widgets import (
    NodeWidget, PortWidget, LinkWidget, CellWidget
)

class InletWidget(PortWidget):
    pass

class OutletWidget(PortWidget):
    pass

from .managers.selection_manager import GraphSelectionManager
from ..models import AbstractGraphModel
from ..models.abstract_graphmodel import GraphItemRef, NodeRef, InletRef, OutletRef, LinkRef, AttributeRef
from .delegates.graphview_delegate import GraphDelegate
# from .factories.widget_factory import WidgetFactory
from .factories.widget_factory_using_delegate import WidgetFactoryUsingDelegate


class GraphView2(QGraphicsView):
    def __init__(self, delegate:GraphDelegate|None=None, parent: QWidget | None = None):
        super().__init__(parent=parent)
        self._model: AbstractGraphModel | None = None
        self._model_connections: list[tuple[Signal, Slot]] = []
        self._selection: QItemSelectionModel | None = None
        self._selection_connections: list[tuple[Signal, Slot]] = []

        assert isinstance(delegate, GraphDelegate) or delegate is None, "Invalid delegate"
        self._delegate = delegate if delegate else GraphDelegate()
        
        self._factory = WidgetFactoryUsingDelegate()
        self._factory.portPositionChanged.connect(self.handlePortPositionChanged)

        ## UI Tools
        self._linking_tool = LinkingTool(self)

        ## Selection Model
        self._selection_manager = GraphSelectionManager(self)

        # Widget Managers
        self._widget_manager = BidictWidgetManager()
        self._cell_manager = CellManager()

        # setup the view
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setAcceptDrops(True)

        self.setCacheMode(QGraphicsView.CacheModeFlag.CacheNone)
        self.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        # create a scene
        scene = QGraphicsScene()
        scene.setSceneRect(QRectF(-9999, -9999, 9999 * 2, 9999 * 2))
        self.setScene(scene)
        
    def setModel(self, model:AbstractGraphModel|None):
        if self._model:
            # disconnect previous controller
            for signal, slot in self._model_connections:
                signal.disconnect(slot)
            self._model_connections.clear()
            self._model = None

        if model:
            self._model_connections = [
                (model.nodesInserted, self.handleNodesInserted),
                (model.nodesAboutToBeRemoved, self.handleNodesRemoved),

                (model.inletsInserted, self.handleInletsInserted),
                (model.inletsAboutToBeRemoved, self.handleInletsRemoved),

                (model.outletsInserted, self.handleOutletsInserted),
                (model.outletsAboutToBeRemoved, self.handleOutletsRemoved),

                (model.linksInserted, self.handleLinksInserted),
                (model.linksAboutToBeRemoved, self.handleLinksRemoved),
                (model.dataChanged, self.handleDataChanged)
            ]

            for signal, slot in self._model_connections:
                signal.connect(slot)

        self._model = model
        
        # populate initial scene
        ## clear
        scene = self.scene()
        assert scene
        scene.clear()
        self._widget_manager.clear()
        # self._link_manager.clear()
        self._cell_manager.clear()

        if self._model.nodeCount() > 0:
            self.handleNodesInserted(self._model.nodes())

    def model(self) -> AbstractGraphModel | None:
        return self._model
    
    ## Model Referece lookup
    def refAt(self, point:QPoint) -> GraphItemRef|None:
        """
        Find the ref at the given position.
        point is in untransformed viewport coordinates, just like QMouseEvent::pos().
        """

        all_widgets = set(self._widget_manager.widgets())
        for item in self.items(point):
            if item in all_widgets:
                # If the item is a widget, return its ref
                return self._widget_manager.getKey(item)
        return None
    
    def attributeAt(self, point:QPoint) -> tuple[GraphItemRef, str]|None:
        """
        Find the ref at the given position.
        point is in untransformed viewport coordinates, just like QMouseEvent::pos().
        """
        all_cells = set(self._cell_manager.cells())
        for item in self.items(point):
            if item in all_cells:
                # If the item is a cell, return its ref
                return self._cell_manager.getIndex(item)
            
        return None

    def handlePortPositionChanged(self, port_ref:OutletRef|InletRef):
        """Reposition all links connected to the moved port widget."""
        print(f"handlePortPositionChanged: {port_ref}")

        link_refs = []
        match self._model.itemType(port_ref):
            case GraphItemType.INLET:
                link_refs = self._model.inLinks(port_ref)
            case GraphItemType.OUTLET:
                link_refs = self._model.outLinks(port_ref)
            case _:
                logger.warning(f"Port position changed for non-port item: {indexToPath(port_ref)}")
                return
            
        print(f"  found {len(link_refs)} links to update")
            
        for link_ref in link_refs:
            if not self._widget_manager.getWidget(link_ref):
                continue

            # remove incomplete link
            source_outlet_ref = self._model.linkSource(link_ref)
            target_inlet_ref = self._model.linkTarget(link_ref)
            if not self._widget_manager.getWidget(source_outlet_ref) or not self._widget_manager.getWidget(target_inlet_ref):
                # link is incomplete
                # remove the widget for the link. the model is probably corrupted
                logger.info(f"Link {link_ref} is incomplete, removing it from the view")
                self.removeLinkWidgetForRef(link_ref)
                continue

            source_outlet_widget = self._widget_manager.getWidget(source_outlet_ref)
            target_inlet_widget = self._widget_manager.getWidget(target_inlet_ref)
            if not source_outlet_widget or not target_inlet_widget:
                # link is incomplete
                # no widgets for the link endpoints
                logger.info(f"Link {link_ref} has no widgets for its endpoints, removing it from the view")
                self.removeLinkWidgetForRef(link_ref)
                continue

            # ensure link widget exists
            link_widget = self._widget_manager.getWidget(link_ref)
            if not link_widget:
                # link widget not found (should not happen)
                logger.info(f"Link {link_ref} has no widget, adding it back to the view")
                link_widget = self.addLinkWidgetForRef(link_ref)

            # actually update the link position
            assert isinstance(link_widget, LinkWidget)
            self._update_link_position(link_widget, source_outlet_widget, target_inlet_widget)

    def _update_link_position(self, link_widget:LinkWidget, source_widget:QGraphicsItem|None=None, target_widget:QGraphicsItem|None=None):
        # Compute the link geometry in the link widget's local coordinates.
        if source_widget and target_widget:
            line = makeLineBetweenShapes(source_widget, target_widget)
            line = QLineF(link_widget.mapFromScene(line.p1()), link_widget.mapFromScene(line.p2()))
            link_widget.setLine(line)

        elif source_widget:
            source_center = getShapeCenter(source_widget)
            source_size = source_widget.boundingRect().size()
            origin = QPointF(source_center.x() - source_size.width()/2, source_center.y() - source_size.height()/2)+QPointF(24,24)
            line = makeLineToShape(origin, source_widget)
            line = QLineF(link_widget.mapFromScene(line.p1()), link_widget.mapFromScene(line.p2()))
            line = QLineF(line.p2(), line.p1())  # Reverse the line direction
            link_widget.setLine(line)

        elif target_widget:
            target_center = getShapeCenter(target_widget)
            target_size = target_widget.boundingRect().size()
            origin = QPointF(target_center.x() - target_size.width()/2, target_center.y() - target_size.height()/2)-QPointF(24,24)
            line = makeLineToShape(origin, target_widget)
            line = QLineF(link_widget.mapFromScene(line.p1()), link_widget.mapFromScene(line.p2()))
            link_widget.setLine(line)
        else:
            logger.warning("Cannot update link position: no source or target widget")

        link_widget.update()

    ## Manage widgets lifecycle
    def addNodeWidgetForRef(self, node_ref:NodeRef)->QGraphicsItem:
        # validate parameters

        # avoid duplicates
        if self._widget_manager.getWidget(node_ref):
            return self._widget_manager.getWidget(node_ref)

        # widget management
        row_widget = self._factory.createNodeWidget(self.scene(), node_ref, self)
        self._widget_manager.insertWidget(node_ref, row_widget)

        # Add cells for each column
        self._addCellsForRow(node_ref)

        return row_widget
    
    def removeNodeWidgetForRef(self, node_ref:NodeRef):
        assert node_ref.column() == 0, "Can only add node widget for column 0"

        # check if widget exists, if not, nothing to do
        if not self._widget_manager.getWidget(node_ref):
            return

        ## First Remove cells
        self._removeCellsForRow(node_ref)

        # widget management
        row_widget = self._widget_manager.getWidget(node_ref)
        self._factory.destroyNodeWidget(self.scene(), row_widget)
        self._widget_manager.removeWidget(node_ref, row_widget)

    def addInletWidgetForRef(self, inlet_ref:InletRef)->QGraphicsItem|None:
        """
        Add an inlet widget for the given ref.
        """
        # validate parent node widget
        parent_node_widget = self._widget_manager.getWidget(inlet_ref.parent())
        if not parent_node_widget:
            return None
        assert isinstance(parent_node_widget, NodeWidget)

        # avoid duplicates
        if self._widget_manager.getWidget(inlet_ref):
            return self._widget_manager.getWidget(inlet_ref)

        # widget factory
        row_widget = self._factory.createInletWidget(parent_node_widget, inlet_ref, self)

        # widget management
        self._widget_manager.insertWidget(inlet_ref, row_widget)

        # Add cells for each column
        self._addCellsForRow(inlet_ref)

        return row_widget

    def removeInletWidgetForRef(self, inlet_ref:InletRef):  
        assert self._model
        # check if widget exists, if not, nothing to do
        if not self._widget_manager.getWidget(inlet_ref):
            return

        ## Remove cells
        self._removeCellsForRow(inlet_ref)

        # widget management
        row_widget = self._widget_manager.getWidget(inlet_ref)
        
        parent_node_ref = self._model.inletNode(inlet_ref)
        parent_node_widget = self._widget_manager.getWidget(parent_node_ref)
        self._factory.destroyInletWidget(parent_node_widget, row_widget)
        self._widget_manager.removeWidget(inlet_ref, row_widget)

    def addOutletWidgetForRef(self, outlet_ref:OutletRef)->QGraphicsItem|None:
        # validate parent node widget
        parent_node_ref = self._model.outletNode(outlet_ref)
        parent_node_widget = self._widget_manager.getWidget(parent_node_ref)
        if not parent_node_widget:
            return None
        
        assert isinstance(parent_node_widget, NodeWidget)
        
        # avoid duplicates
        if self._widget_manager.getWidget(outlet_ref):
            return self._widget_manager.getWidget(outlet_ref)
        
        # widget factory
        row_widget = self._factory.createOutletWidget(parent_node_widget, outlet_ref, self)

        # widget management
        self._widget_manager.insertWidget(outlet_ref, row_widget)

        # Add cells for each column
        self._addCellsForRow(outlet_ref)

        return row_widget

    def removeOutletWidgetForRef(self, outlet_ref:OutletRef):
        # check if widget exists, if not, nothing to do
        if not self._widget_manager.getWidget(outlet_ref):
            return
        
        ## Remove cells
        self._removeCellsForRow(outlet_ref)

        # widget management
        outlet_widget = self._widget_manager.getWidget(outlet_ref)
        parent_node_ref = self._model.outletNode(outlet_ref)
        parent_widget = self._widget_manager.getWidget(parent_node_ref)
        self._factory.destroyOutletWidget(parent_widget, outlet_widget)
        self._widget_manager.removeWidget(outlet_ref, outlet_widget)

    def addLinkWidgetForRef(self, link_ref:LinkRef)->QGraphicsItem|None:
        """
        
        """
        # validate parent widgets
        inlet_ref = self._model.linkTarget(link_ref)  # ensure target is valid
        if not inlet_ref or not inlet_ref.isValid():
            return None
        target_node_ref = self._model.inletNode(inlet_ref)  # ensure inlet parent is valid
        if not target_node_ref or not target_node_ref.isValid():
            return None
        outlet_ref = self._model.linkSource(link_ref)  # ensure source is valid
        if not outlet_ref or not outlet_ref.isValid():
            return None
        source_node_ref = self._model.outletNode(outlet_ref)  # ensure outlet parent is valid
        if not source_node_ref or not source_node_ref.isValid():
            return None

        inlet_widget = self._widget_manager.getWidget(inlet_ref)
        outlet_widget = self._widget_manager.getWidget(outlet_ref)
        source_node_widget = self._widget_manager.getWidget(source_node_ref)
        target_node_widget = self._widget_manager.getWidget(target_node_ref)
        if not all([inlet_widget, outlet_widget, source_node_widget, target_node_widget]):
            logger.info(f"Cannot create link widget for link {link_ref}: missing widgets")
            return None

        # avoid duplicates
        if self._widget_manager.getWidget(link_ref):
            return self._widget_manager.getWidget(link_ref)

        # widget factory
        link_widget = self._factory.createLinkWidget(self.scene(), link_ref, self)

        # widget management
        self._widget_manager.insertWidget(link_ref, link_widget)

        # link management
        source_ref = self._model.linkSource(link_ref)
        source_widget = self._widget_manager.getWidget(source_ref) if source_ref is not None else None
        target_ref = self._model.linkTarget(link_ref)
        target_widget = self._widget_manager.getWidget(target_ref) if target_ref is not None else None
        # self._link_manager.link(link_widget, source_widget, target_widget)
        self._update_link_position(link_widget, source_widget, target_widget)

        self._addCellsForRow(link_ref)

        return link_widget
    
    def removeLinkWidgetForRef(self, link_ref:LinkRef):
        # check if widget exists, if not, nothing to do
        if not self._widget_manager.getWidget(link_ref):
            return
        
        ## Remove cells
        self._removeCellsForRow(link_ref)

        # widget management
        link_widget = self._widget_manager.getWidget(link_ref)
        self._factory.destroyLinkWidget(self.scene(), link_widget)
        # self._link_manager.unlink(link_widget)
        self._widget_manager.removeWidget(link_ref, link_widget)

    def addCellWidgetForRef(self, attr_ref:Tuple[GraphItemRef, str])->QGraphicsItem:
        # avoid duplicates
        if self._cell_manager.getCell(attr_ref):
            return self._cell_manager.getCell(attr_ref)
        
        
        row_widget = self._widget_manager.getWidget(attr_ref[0]) # TODO: revisit attribute references
        cell_widget = self._factory.createCellWidget(row_widget, attr_ref, self)
        self._cell_manager.insertCell(attr_ref, cell_widget)
        self._set_cell_data(attr_ref, roles=[Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole])
        return cell_widget
    
    def removeCellWidgetForRef(self, attr_ref:Tuple[GraphItemRef, str]):
        # check if widget exists, if not, nothing to do
        if not self._cell_manager.getCell(attr_ref):
            return
        
        if cell_widget := self._cell_manager.getCell(attr_ref):
            row_widget = self._widget_manager.getWidget(attr_ref[0])  # TODO: revisit attribute references
            self._factory.destroyCellWidget(row_widget, cell_widget)
            self._cell_manager.removeCell(attr_ref)
    
    def _addCellsForRow(self, item_ref:GraphItemRef):
        """add cells for each attribute"""
        assert self._model is not None, "Model is not set"
        match self._model.itemType(item_ref):
            case GraphItemType.NODE:
                for attr_name in self._model.nodeAttributes(item_ref):
                    self.addCellWidgetForRef(item_ref, attr_name)

            case GraphItemType.INLET:
                for attr_name in self._model.inletAttributes(item_ref):
                    self.addCellWidgetForRef(item_ref, attr_name)

            case GraphItemType.OUTLET:
                for attr_name in self._model.outletAttributes(item_ref):
                    self.addCellWidgetForRef(item_ref, attr_name)

            case GraphItemType.LINK:
                for attr_name in self._model.linkAttributes(item_ref):
                    self.addCellWidgetForRef(item_ref, attr_name)

    def _removeCellsForRow(self, item_ref:GraphItemRef):
        """remove cells for each attribute"""
        assert self._model is not None, "Model is not set"
        match self._model.itemType(item_ref):
            case GraphItemType.NODE:
                for attr_name in range(self._model.nodeAttributes(item_ref)):
                    self.removeCellWidgetForRef(item_ref, attr_name)

            case GraphItemType.INLET:
                for attr_name in range(self._model.inletAttributes(item_ref)):
                    self.removeCellWidgetForRef(item_ref, attr_name)

            case GraphItemType.OUTLET:
                for attr_name in range(self._model.outletAttributes(item_ref)):
                    self.removeCellWidgetForRef(item_ref, attr_name)

            case GraphItemType.LINK:
                for attr_name in range(self._model.linkAttributes(item_ref)):
                    self.removeCellWidgetForRef(item_ref, attr_name)

    ## Handle model changes
    def handleNodesInserted(self, node_refs:List[NodeRef]):
        # nodes
        for node_ref in node_refs:
            if not self._widget_manager.getWidget(node_ref):
                self.addNodeWidgetForRef(node_ref)

        # child inlets and outlets
        for node_ref in node_refs:
            self.handleInletsInserted(self._model.inlets(node_ref))
            self.handleOutletsInserted(self._model.outlets(node_ref))

    def handleNodesRemoved(self, node_refs:List[NodeRef]):
        # child inlets and outlets
        for node_ref in node_refs:
            self.handleInletsRemoved(self._model.inlets(node_ref))
            self.handleOutletsInserted(self._model.outlets(node_ref))

        #nodes
        for node_ref in node_refs:
            if self._widget_manager.getWidget(node_ref):
                self.removeNodeWidgetForRef(node_ref)

    def handleInletsInserted(self, inlet_refs:List[InletRef]):
        #inlets
        for inlet_ref in inlet_refs:
            if not self._widget_manager.getWidget(inlet_ref):
                self.addInletWidgetForRef(inlet_ref)

        # child links
        for inlet_ref in inlet_refs:
            self.handleLinksInserted(self._model.inLinks(inlet_ref))

    def handleInletsRemoved(self, inlet_refs:List[InletRef]):
        # child links
        for inlet_ref in inlet_refs:
            self.handleLinksRemoved(self._model.inLinks(inlet_ref))

        # inlets
        for inlet_ref in inlet_refs:
            if self._widget_manager.getWidget(inlet_ref):
                self.removeInletWidgetForRef(inlet_ref)

    def handleOutletsInserted(self, outlet_refs:List[OutletRef]):
        # outlets
        for outlet_ref in outlet_refs:
            if not self._widget_manager.getWidget(outlet_ref):
                self.addOutletWidgetForRef(outlet_ref)

        # child links
        for outlet_ref in outlet_refs:
            self.handleLinksInserted(self._model.inLinks(outlet_ref))

    def handleOutletsRemoved(self, outlet_refs:List[OutletRef]):
        # child links
        for outlet_ref in outlet_refs:
            self.handleLinksRemoved(self._model.outLinks(outlet_ref))

        # outlets
        for outlet_ref in outlet_refs:
            if self._widget_manager.getWidget(outlet_ref):
                self.removeOutletWidgetForRef(outlet_ref)

    def handleLinksInserted(self, link_refs:List[LinkRef]):
        for link_ref in link_refs:
            if not self._widget_manager.getWidget(link_ref):
                self.addLinkWidgetForRef(link_ref)

    def handleLinksRemoved(self, link_refs:List[LinkRef]):
        for link_ref in link_refs:
            if self._widget_manager.getWidget(link_ref):
                self.removeLinkWidgetForRef(link_ref)

    # handle data changes
    def handleNodeDataChanged(self, attributes:List[AttributeRef], roles:List[int]):
        for attr in attributes:
            self._set_cell_data(attr, roles)


    ## Selection handling   
    @Slot(QItemSelection, QItemSelection)
    def handleSelectionChanged(self, selected:QItemSelection, deselected:QItemSelection):
        """
        Handle selection changes in the selection model.
        This updates the selection in the graph view.
        """
        assert self._selection, "Selection model must be set before handling selection changes!"
        assert self._model, "Model must be set before handling selection changes!"
        assert self._selection.model() == self._model, "Selection model must be for the same model as the graph view!"
        if not selected or not deselected:
            return
        scene = self.scene()
        assert scene is not None

        with blockingSignals(scene):           
            selected_indexes = sorted([idx for idx in selected.indexes()], 
                                    key= lambda idx: idx.row(), 
                                    reverse= True)
            
            deselected_indexes = sorted([idx for idx in deselected.indexes()], 
                                        key= lambda idx: idx.row(), 
                                        reverse= True)
            
            for index in deselected_indexes:
                if index.isValid() and index.column() == 0:
                    if widget:=self._widget_manager.getWidget(index):
                        if widget.scene() and widget.isSelected():
                            widget.setSelected(False)

            for index in selected_indexes:
                if index.isValid() and index.column() == 0:
                    if widget:=self._widget_manager.getWidget(index):
                        if widget.scene() and not widget.isSelected():
                            widget.setSelected(True)

    ##
    def _set_cell_data(self, index:QModelIndex|QPersistentModelIndex, roles:list=[]):
        """Set the data for a cell widget."""
        assert index.isValid(), "Index must be valid"
        assert self._model, "Model must be set before setting cell data!"
        if Qt.ItemDataRole.DisplayRole in roles or Qt.ItemDataRole.DisplayRole in roles or roles == []:
            if cell_widget:= self._cell_manager.getCell(index):
                text = self._model.data(index, Qt.ItemDataRole.DisplayRole)
                cell_widget.setText(text)

    ## Handle mouse events
    def mousePressEvent(self, event):
        """
        By default start linking from the item under the mouse cursor.
        if starting a link is not possible, fallback to the QGraphicsView behavior.
        """

        if self._linking_tool.isActive():
            # If we are already linking, cancel the linking operation
            self._linking_tool.cancelLinking()
            return

        # get the index at the mouse position
        pos = event.position()
        if index := self.refAt(QPoint(int(pos.x()), int(pos.y()))):
            # map the position to scene coordinates
            scene_pos = self.mapToScene(event.position().toPoint())

            # If we can start linking, do so
            if self._linking_tool.startLinking(index, scene_pos):
                return
            else:
                # Fallback to default behavior
                super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._linking_tool.isActive():
            pos = QPoint(int(event.position().x()), int(event.position().y())) # Ensure pos is in integer coordinates
            self._linking_tool.updateLinking(pos)
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._linking_tool.isActive():
            pos = QPoint(int(event.position().x()), int(event.position().y())) # Ensure pos is in integer coordinates
            drop_target = self.refAt(pos)  # Ensure the index is updated
            if not self._linking_tool.finishLinking(drop_target):
                # Handle failed linking
                logger.warning("WARNING: Linking failed!")
        else:
            super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event:QMouseEvent):
        index = self.attributeAt(QPoint(int(event.position().x()), int(event.position().y())))

        if not index.isValid():
            idx = self._model.addNode(QModelIndex())
            if widget := self._widget_manager.getWidget(idx):
                center = widget.boundingRect().center()
                widget.setPos(self.mapToScene(event.position().toPoint())-center)

            return
            
        def onEditingFinished(editor:QLineEdit, cell_widget:CellWidget, index:QModelIndex):
            self._delegate.setModelData(editor, self._model, index)
            editor.deleteLater()
            self._set_cell_data(index, roles=[Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole])

        if cell_widget := self._cell_manager.getCell(index):
            option = QStyleOptionViewItem()
            scene_rect = cell_widget.mapRectToScene(cell_widget.boundingRect())
            view_poly:QPolygon = self.mapFromScene(scene_rect)
            rect = view_poly.boundingRect()
            option.rect = rect
            option.state = QStyle.StateFlag.State_Enabled | QStyle.StateFlag.State_Active
            
            editor = self._delegate.createEditor(self, option, index)
            if editor:
                # Ensure the editor is properly positioned and shown
                editor.setParent(self)
                editor.setGeometry(rect)
                self._delegate.setEditorData(editor, index)
                editor.show()  # Explicitly show the editor
                editor.setFocus(Qt.FocusReason.MouseFocusReason)
                editor.editingFinished.connect(lambda editor=editor, cell_widget=cell_widget, index=index: onEditingFinished(editor, cell_widget, index))
    
