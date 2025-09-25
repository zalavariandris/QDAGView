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

from ..tools.linking_tool import LinkingTool

from ..managers import PersistentWidgetIndexManager
from ..managers.linking_manager import LinkingManager
from ..managers.cell_manager import CellManager

from ..widgets import (
    NodeWidget, PortWidget, LinkWidget, CellWidget
)

class InletWidget(PortWidget):
    pass

class OutletWidget(PortWidget):
    pass

from ..models import AbstractGraphModel
from ..delegates.graphview_delegate import GraphDelegate
# from .factories.widget_factory import WidgetFactory
from ..factories.widgetfactory_using_delegate import WidgetFactoryUsingDelegate

class GraphModel_GraphView(QGraphicsView):
    def __init__(self, delegate:GraphDelegate|None=None, parent: QWidget | None = None):
        super().__init__(parent=parent)
        self._model: AbstractGraphModel | None = None
        self._model_connections: list[tuple[Signal, Slot]] = []
        self._selection:QItemSelectionModel | None = None
        self._selection_connections: list[tuple[Signal, Slot]] = []

        assert isinstance(delegate, GraphDelegate) or delegate is None, "Invalid delegate"
        self._delegate = delegate if delegate else GraphDelegate()
        
        self._factory = WidgetFactoryUsingDelegate()
        self._factory.portPositionChanged.connect(self.handlePortPositionChanged)

        ## State of the graph view
        self._linking_tool = LinkingTool(self, self._model)

        # Widget Manager
        self._widget_manager = PersistentWidgetIndexManager()
        self._cell_manager = CellManager()

        # Link management
        # self._link_manager = LinkingManager[LinkWidget, InletWidget, OutletWidget]()

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
                (model.nodesDataChanged, self.handleNodeDataChanged),
                (model.inletsInserted, self.handleInletsInserted),
                (model.inletsAboutToBeRemoved, self.handleInletsRemoved),
                (model.inletsDataChanged, self.handleInletsDataChanged),
                (model.outletsInserted, self.handleOutletsInserted),
                (model.outletsAboutToBeRemoved, self.handleOutletsRemoved),
                (model.outletsDataChanged, self.handleOutletsDataChanged),
                (model.linksInserted, self.handleLinksInserted),
                (model.linksAboutToBeRemoved, self.handleLinksRemoved),
                (model.linksDataChanged, self.handleLinkDataChanged)
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

    def model(self) -> QAbstractItemModel | None:
        return self._model
    
    ## Index lookup
    def rowAt(self, point:QPoint) -> QModelIndex:
        """
        Find the index at the given position.
        point is in untransformed viewport coordinates, just like QMouseEvent::pos().
        """

        all_widgets = set(self._widget_manager.widgets())
        for item in self.items(point):
            if item in all_widgets:
                # If the item is a widget, return its index
                return self._widget_manager.getIndex(item)
        return QModelIndex()
    
    def indexAt(self, point:QPoint) -> QModelIndex:
        """
        Find the index at the given position.
        point is in untransformed viewport coordinates, just like QMouseEvent::pos().
        """
        all_cells = set(self._cell_manager.cells())
        for item in self.items(point):
            if item in all_cells:
                # If the item is a cell, return its index
                return self._cell_manager.getIndex(item)
            
        # fallback to rowAt if no cell is found
        return self.rowAt(point)

    def handlePortPositionChanged(self, port_index:QPersistentModelIndex):
        """Reposition all links connected to the moved port widget."""
        print(f"handlePortPositionChanged: {indexToPath(port_index)}")

        link_indexes = []
        match self._model.itemType(port_index):
            case GraphItemType.INLET:
                link_indexes = self._model.inletLinks(port_index)
            case GraphItemType.OUTLET:
                link_indexes = self._model.outletLinks(port_index)
            case _:
                logger.warning(f"Port position changed for non-port item: {indexToPath(port_index)}")
                return
            
        print(f"  found {len(link_indexes)} links to update")
            
        for link_index in link_indexes:
            if not self._widget_manager.getWidget(link_index):
                continue

            # remove incomplete link
            source_outlet_index = self._model.linkSource(link_index)
            target_inlet_index = self._model.linkTarget(link_index)
            if not self._widget_manager.getWidget(source_outlet_index) or not self._widget_manager.getWidget(target_inlet_index):
                # link is incomplete
                # remove the widget for the link. the model is probably corrupted
                logger.info(f"Link {indexToPath(link_index)} is incomplete, removing it from the view")
                self.removeLinkWidgetForIndex(link_index)
                continue

            source_outlet_widget = self._widget_manager.getWidget(source_outlet_index)
            target_inlet_widget = self._widget_manager.getWidget(target_inlet_index)
            if not source_outlet_widget or not target_inlet_widget:
                # link is incomplete
                # no widgets for the link endpoints
                logger.info(f"Link {indexToPath(link_index)} has no widgets for its endpoints, removing it from the view")
                self.removeLinkWidgetForIndex(link_index)
                continue

            # ensure link widget exists
            link_widget = self._widget_manager.getWidget(link_index)
            if not link_widget:
                # link widget not found (should not happen)
                logger.info(f"Link {indexToPath(link_index)} has no widget, adding it back to the view")
                link_widget = self.addLinkWidgetForIndex(link_index)

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
    def addNodeWidgetForIndex(self, row_index:QPersistentModelIndex)->QGraphicsItem:
        # validate parameters
        assert row_index.column() == 0, "Can only add node widget for column 0"

        # avoid duplicates
        if self._widget_manager.getWidget(row_index):
            return self._widget_manager.getWidget(row_index)

        # widget management
        row_widget = self._factory.createNodeWidget(self.scene(), row_index, self)
        self._widget_manager.insertWidget(row_index, row_widget)

        # Add cells for each column
        self._addCellsForRow(row_index)

        return row_widget
    
    def removeNodeWidgetForIndex(self, row_index:QPersistentModelIndex):
        assert row_index.column() == 0, "Can only add node widget for column 0"

        # check if widget exists, if not, nothing to do
        if not self._widget_manager.getWidget(row_index):
            return

        ## First Remove cells
        self._removeCellsForRow(row_index)

        # widget management
        row_widget = self._widget_manager.getWidget(row_index)
        self._factory.destroyNodeWidget(self.scene(), row_widget)
        self._widget_manager.removeWidget(row_index, row_widget)

    def addInletWidgetForIndex(self, row_index:QPersistentModelIndex)->QGraphicsItem|None:
        """
        Add an inlet widget at the given index.
        The inlet must be a child of a node.
        """
        # validate parameters
        assert row_index.column() == 0, "Can only add inlet widget for column 0"

        # validate parent node widget
        parent_node_widget = self._widget_manager.getWidget(row_index.parent())
        if not parent_node_widget:
            return None
        assert isinstance(parent_node_widget, NodeWidget)

        # avoid duplicates
        if self._widget_manager.getWidget(row_index):
            return self._widget_manager.getWidget(row_index)

        # widget factory
        row_widget = self._factory.createInletWidget(parent_node_widget, row_index, self)

        # widget management
        self._widget_manager.insertWidget(row_index, row_widget)

        # Add cells for each column
        self._addCellsForRow(row_index)

        return row_widget

    def removeInletWidgetForIndex(self, row_index:QPersistentModelIndex):  
        # check if widget exists, if not, nothing to do
        if not self._widget_manager.getWidget(row_index):
            return

        ## Remove cells
        self._removeCellsForRow(row_index)

        # widget management
        row_widget = self._widget_manager.getWidget(row_index)
        parent_widget = self._widget_manager.getWidget(row_index.parent())
        self._factory.destroyInletWidget(parent_widget, row_widget)
        self._widget_manager.removeWidget(row_index, row_widget)

    def addOutletWidgetForIndex(self, row_index:QPersistentModelIndex)->QGraphicsItem|None:
        # validate parent node widget
        parent_node_widget = self._widget_manager.getWidget(row_index.parent())
        if not parent_node_widget:
            return None
        
        assert isinstance(parent_node_widget, NodeWidget)
        
        # avoid duplicates
        if self._widget_manager.getWidget(row_index):
            return self._widget_manager.getWidget(row_index)
        
        # widget factory
        row_widget = self._factory.createOutletWidget(parent_node_widget, row_index, self)

        # widget management
        self._widget_manager.insertWidget(row_index, row_widget)

        # Add cells for each column
        self._addCellsForRow(row_index)

        return row_widget

    def removeOutletWidgetForIndex(self, row_index:QPersistentModelIndex):
        # check if widget exists, if not, nothing to do
        if not self._widget_manager.getWidget(row_index):
            return
        
        ## Remove cells
        self._removeCellsForRow(row_index)

        # widget management
        row_widget = self._widget_manager.getWidget(row_index)
        parent_widget = self._widget_manager.getWidget(row_index.parent())
        self._factory.destroyOutletWidget(parent_widget, row_widget)
        self._widget_manager.removeWidget(row_index, row_widget)

    def addLinkWidgetForIndex(self, link:QPersistentModelIndex)->QGraphicsItem|None:
        """
        
        """
        # validate parent widgets
        inlet_index = self._model.linkTarget(link)  # ensure target is valid
        if not inlet_index or not inlet_index.isValid():
            return None
        target_node_index = self._model.inletNode(inlet_index)  # ensure inlet parent is valid
        if not target_node_index or not target_node_index.isValid():
            return None
        outlet_index = self._model.linkSource(link)  # ensure source is valid
        if not outlet_index or not outlet_index.isValid():
            return None
        source_node_index = self._model.outletNode(outlet_index)  # ensure outlet parent is valid
        if not source_node_index or not source_node_index.isValid():
            return None

        inlet_widget = self._widget_manager.getWidget(inlet_index)
        outlet_widget = self._widget_manager.getWidget(outlet_index)
        source_node_widget = self._widget_manager.getWidget(source_node_index)
        target_node_widget = self._widget_manager.getWidget(target_node_index)
        if not all([inlet_widget, outlet_widget, source_node_widget, target_node_widget]):
            logger.info(f"Cannot create link widget for link {indexToPath(link)}: missing widgets")
            return None

        # avoid duplicates
        if self._widget_manager.getWidget(link):
            return self._widget_manager.getWidget(link)

        # widget factory
        link_widget = self._factory.createLinkWidget(self.scene(), link, self)

        # widget management
        self._widget_manager.insertWidget(link, link_widget)

        # link management
        source_index = self._model.linkSource(link)
        source_widget = self._widget_manager.getWidget(source_index) if source_index is not None else None
        target_index = self._model.linkTarget(link)
        target_widget = self._widget_manager.getWidget(target_index) if target_index is not None else None
        # self._link_manager.link(link_widget, source_widget, target_widget)
        self._update_link_position(link_widget, source_widget, target_widget)

        self._addCellsForRow(link)

        return link_widget
    
    def removeLinkWidgetForIndex(self, link:QPersistentModelIndex):
        # check if widget exists, if not, nothing to do
        if not self._widget_manager.getWidget(link):
            return
        
        ## Remove cells
        self._removeCellsForRow(link)

        # widget management
        link_widget = self._widget_manager.getWidget(link)
        parent_widget = self._widget_manager.getWidget(link.parent())
        self._factory.destroyLinkWidget(self.scene(), link_widget)
        # self._link_manager.unlink(link_widget)
        self._widget_manager.removeWidget(link, link_widget)

    def addCellWidgetForIndex(self, cell_index:QPersistentModelIndex)->QGraphicsItem:
        # avoid duplicates
        if self._cell_manager.getCell(cell_index):
            return self._cell_manager.getCell(cell_index)
        
        row_widget = self._widget_manager.getWidget(cell_index.siblingAtColumn(0))
        cell_widget = self._factory.createCellWidget(row_widget, cell_index, self)
        self._cell_manager.insertCell(cell_index, cell_widget)
        self._set_cell_data(cell_index, roles=[Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole])
        return cell_widget
    
    def removeCellWidgetForIndex(self, cell_index:QPersistentModelIndex):
        # check if widget exists, if not, nothing to do
        if not self._cell_manager.getCell(cell_index):
            return
        
        if cell_widget := self._cell_manager.getCell(cell_index):
            row_widget = self._widget_manager.getWidget(cell_index.siblingAtColumn(0))
            self._factory.destroyCellWidget(row_widget, cell_widget)
            self._cell_manager.removeCell(cell_index)
    
    def _addCellsForRow(self, row_index:QPersistentModelIndex):
        """add cells for each attribute"""
        assert self._model is not None, "Model is not set"
        for key, value in range(self._model.attributes(row_index)):
            cell_id = (row_index, col)
            cell_index = self._model.index(row_index.row(), col, row_index.parent())
            self.addCellWidgetForIndex(cell_index)

    def _removeCellsForRow(self, row_index:QPersistentModelIndex):
        """remove cells for each attribute"""
        for col in range(self._model.columnCount(row_index.parent())):
            cell_index = self._model.index(row_index.row(), col, row_index.parent())
            self.removeCellWidgetForIndex(cell_index)

    ## Handle model changes
    def handleNodesInserted(self, node_indexes:List[QPersistentModelIndex]):
        # nodes
        for node_index in node_indexes:
            if not self._widget_manager.getWidget(node_index):
                self.addNodeWidgetForIndex(node_index)

        # inlets and outlets
        for node_index in node_indexes:
            for inlet_index in self._model.nodeInlets(node_index):
                if not self._widget_manager.getWidget(inlet_index):
                    self.addInletWidgetForIndex(inlet_index)
            for outlet_index in self._model.nodeOutlets(node_index):
                if not self._widget_manager.getWidget(outlet_index):
                    self.addOutletWidgetForIndex(outlet_index)

        # links
        for node_index in node_indexes:
            for inlet_index in self._model.nodeInlets(node_index):
                for link_index in self._model.inletLinks(inlet_index):
                    if not self._widget_manager.getWidget(link_index):
                        self.addLinkWidgetForIndex(link_index)
            for outlet_index in self._model.nodeOutlets(node_index):
                for link_index in self._model.outletLinks(outlet_index):
                    if not self._widget_manager.getWidget(link_index):
                        self.addLinkWidgetForIndex(link_index)

    def handleNodesRemoved(self, node_indexes:List[QPersistentModelIndex]):
        # links
        for node_index in node_indexes:
            for inlet_index in self._model.nodeInlets(node_index):
                for link_index in self._model.inletLinks(inlet_index):
                    if self._widget_manager.getWidget(link_index):
                        self.removeLinkWidgetForIndex(link_index)

            for outlet_index in self._model.nodeOutlets(node_index):
                for link_index in self._model.outletLinks(outlet_index):
                    if self._widget_manager.getWidget(link_index):
                        self.removeLinkWidgetForIndex(link_index)

        # inlets and outlets
        for node_index in node_indexes:
            for inlet_index in self._model.nodeInlets(node_index):
                if self._widget_manager.getWidget(inlet_index):
                    self.removeInletWidgetForIndex(inlet_index)
            for outlet_index in self._model.nodeOutlets(node_index):
                if self._widget_manager.getWidget(outlet_index):
                    self.removeOutletWidgetForIndex(outlet_index)
        #nodes
        for node_index in node_indexes:
            if self._widget_manager.getWidget(node_index):
                self.removeNodeWidgetForIndex(node_index)

    def handleInletsInserted(self, inlet_indexes:List[QPersistentModelIndex]):
        #inlets
        for inlet_index in inlet_indexes:
            if not self._widget_manager.getWidget(inlet_index):
                self.addInletWidgetForIndex(inlet_index)

        # links
        for inlet_index in inlet_indexes:
            for link_index in self._model.inletLinks(inlet_index):
                if not self._widget_manager.getWidget(link_index):
                    self.addLinkWidgetForIndex(link_index)

    def handleInletsRemoved(self, inlet_indexes:List[QPersistentModelIndex]):
        #links
        for inlet_index in inlet_indexes:
            for link_index in self._model.inletLinks(inlet_index):
                if self._widget_manager.getWidget(link_index):
                    self.removeLinkWidgetForIndex(link_index)

        # inlets
        for inlet_index in inlet_indexes:
            if self._widget_manager.getWidget(inlet_index):
                self.removeInletWidgetForIndex(inlet_index)

    def handleOutletsInserted(self, outlet_indexes:List[QPersistentModelIndex]):
        # outlets
        for outlet_index in outlet_indexes:
            if not self._widget_manager.getWidget(outlet_index):
                self.addOutletWidgetForIndex(outlet_index)

        # links
        for outlet_index in outlet_indexes:
            for link_index in self._model.outletLinks(outlet_index):
                if not self._widget_manager.getWidget(link_index):
                    self.addLinkWidgetForIndex(link_index)

    def handleOutletsRemoved(self, outlet_indexes:List[QPersistentModelIndex]):
        # links
        for outlet_index in outlet_indexes:
            for link_index in self._model.outletLinks(outlet_index):
                if self._widget_manager.getWidget(link_index):
                    self.removeLinkWidgetForIndex(link_index)
        # outlets
        for outlet_index in outlet_indexes:
            if self._widget_manager.getWidget(outlet_index):
                self.removeOutletWidgetForIndex(outlet_index)

    def handleLinksInserted(self, link_indexes:List[QPersistentModelIndex]):
        # links
        for link_index in link_indexes:
            if not self._widget_manager.getWidget(link_index):
                self.addLinkWidgetForIndex(link_index)

    def handleLinksRemoved(self, link_indexes:List[QPersistentModelIndex]):
        for link_index in link_indexes:
            if self._widget_manager.getWidget(link_index):
                self.removeLinkWidgetForIndex(link_index)

    def handleNodeDataChanged(self, top_left:QPersistentModelIndex, bottom_right:QPersistentModelIndex, roles:List[int]):
        for row in range(top_left.row(), bottom_right.row() + 1):
            index = top_left.sibling(row, top_left.column())
            self._set_cell_data(index, roles)

    def handleInletsDataChanged(self, top_left:QPersistentModelIndex, bottom_right:QPersistentModelIndex, roles:List[int]):
        for row in range(top_left.row(), bottom_right.row() + 1):
            index = top_left.sibling(row, top_left.column())
            self._set_cell_data(index, roles)

    def handleOutletsDataChanged(self, top_left:QPersistentModelIndex, bottom_right:QPersistentModelIndex, roles:List[int]):
        for row in range(top_left.row(), bottom_right.row() + 1):
            index = top_left.sibling(row, top_left.column())
            self._set_cell_data(index, roles)
    
    def handleLinkDataChanged(self, links, columns, roles:List[int]):
        for link in links:
            for col in columns:
                index = link.sibling(link.row(), col)
                self._set_cell_data(index, roles)

    # def handleRowsInserted(self, parent:QModelIndex, start:int, end:int):
    #     assert self._model, "Model must be set before handling rows inserted!"

    #     match self._controller.itemType(parent):
    #         case GraphItemType.SUBGRAPH | None:
    #             # Inserting nodes into the root or a subgraph
    #             for row in range(start, end + 1):
    #                 row_index = self._model.index(row, 0, parent)
    #                 self.addNodeWidgetForIndex(row_index)

    #         case GraphItemType.NODE:
    #             # Inserting inlets or outlets into a node
    #             for child_row in range(start, end + 1):
    #                 child_index = self._model.index(child_row, 0, parent)
    #                 match child_index.data(GraphDataRole.TypeRole):
    #                     case GraphItemType.OUTLET:
    #                         self.addOutletWidgetForIndex(child_index)
    #                     case _:
    #                         self.addInletWidgetForIndex(child_index)

    #         case GraphItemType.INLET:
    #             # Inserting links into an inlet
    #             for row in range(start, end + 1):
    #                 row_index = self._model.index(row, 0, parent)
    #                 self.addLinkWidgetForIndex(row_index)

    #         case GraphItemType.OUTLET:
    #             # outlets have no children
    #             pass

    #         case GraphItemType.LINK:
    #             # links have no children
    #             pass
    
    # def handleRowsAboutToBeRemoved(self, parent:QModelIndex, start:int, end:int):
    #     assert self._model, "Model must be set before handling rows removed!"

    #     match self._controller.itemType(parent):
    #         case GraphItemType.SUBGRAPH | None:
    #             # Removing nodes from the root or a subgraph
    #             for row in reversed(range(start, end + 1)):
    #                 row_index = self._model.index(row, 0, parent)
    #                 self.removeNodeWidgetForIndex(row_index)

    #         case GraphItemType.NODE:
    #             # Removing inlets or outlets from a node
    #             for child_row in reversed(range(start, end + 1)):
    #                 child_index = self._model.index(child_row, 0, parent)
    #                 match child_index.data(GraphDataRole.TypeRole):
    #                     case GraphItemType.OUTLET:
    #                         self.removeOutletWidgetForIndex(child_index)
    #                     case _:
    #                         self.removeInletWidgetForIndex(child_index)

    #         case GraphItemType.INLET:
    #             # Removing links from an inlet
    #             for row in reversed(range(start, end + 1)):
    #                 row_index = self._model.index(row, 0, parent)
    #                 self.removeLinkWidgetForIndex(row_index)

    #         case GraphItemType.OUTLET:
    #             # outlets have no children
    #             pass

    #         case GraphItemType.LINK:
    #             # links have no children
    #             pass

    # def handleRowsRemoved(self, parent:QModelIndex, start:int, end:int):
    #     ...
    
    # def handleDataChanged(self, top_left:QModelIndex, bottom_right:QModelIndex, roles:list):
    #     """
    #     Handle data changes in the model.
    #     This updates the widgets in the graph view.
    #     """
    #     assert self._model

    #     if GraphDataRole.SourceRole in roles or roles == []:
    #         # If the source role is changed, we need to update the link widget
    #         for row in range(top_left.row(), bottom_right.row() + 1):
    #             index = self._model.index(row, top_left.column(), top_left.parent())
    #             match self._controller.itemType(index):
    #                 case GraphItemType.LINK:
    #                     link_widget = cast(LinkWidget, self._widget_manager.getWidget(index))
    #                     if link_widget:
    #                         source_widget = self._widget_manager.getWidget(self._controller.linkSource(index))
    #                         target_widget = self._widget_manager.getWidget(self._controller.linkTarget(index))

    #                         self._link_manager.unlink(link_widget)
    #                         self._link_manager.link(link_widget, source_widget, target_widget)
    #                         self._update_link_position(link_widget, source_widget, target_widget)

    #     if GraphDataRole.TypeRole in roles or roles == []:
    #         # if an inlet or outlet type is changed, we need to update the widget
    #         for row in range(top_left.row(), bottom_right.row() + 1):
    #             index = self._model.index(row, top_left.column(), top_left.parent())
    #             if widget := self._widget_manager.getWidget(index):
    #                 ... # TODO replace Widget

    #     for row in range(top_left.row(), bottom_right.row() + 1):
    #         index = self._model.index(row, top_left.column(), top_left.parent())
    #         self._set_cell_data(index, roles=[Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole])

    # def handleColumnsInserted(self, parent: QModelIndex, start: int, end: int):
    #     # TODO: add cells
    #     raise NotImplementedError("Column insertion is not yet implemented in the graph view")

    # def handleColumnsAboutToBeRemoved(self, parent: QModelIndex, start: int, end: int):
        # TODO: remove cells
        # raise NotImplementedError("Column removal is not yet implemented in the graph view")

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

    # # Selection
    def setSelectionModel(self, selection: QItemSelectionModel):
        """
        Set the selection model for the graph view.
        This is used to synchronize the selection of nodes in the graph view
        with the selection model.
        """
        assert isinstance(selection, QItemSelectionModel), f"got: {selection}"
        assert self._model, "Model must be set before setting the selection model!"
        assert selection.model() == self._model, "Selection model must be for the same model as the graph view!"
        if self._selection:
            for signal, slot in self._selection_connections:
                signal.disconnect(slot)
            self._selection_connections = []
        
        if selection:
            self._selection_connections = [
                (selection.selectionChanged, self.handleSelectionChanged)
            ]
            for signal, slot in self._selection_connections:
                signal.connect(slot)

        self._selection = selection
        
        scene = self.scene()
        assert scene is not None
        scene.selectionChanged.connect(self.syncSelectionModel)

    def selectionModel(self) -> QItemSelectionModel | None:
        """
        Get the current selection model for the graph view.
        This is used to synchronize the selection of nodes in the graph view
        with the selection model.
        """
        return self._selection
    
    def syncSelectionModel(self):
        """update selection model from scene selection"""
        scene = self.scene()
        assert scene is not None
        if self._model and self._selection:
            # get currently selected widgets
            selected_widgets = scene.selectedItems()

            # map widgets to QModelIndexes
            selected_indexes = map(self._widget_manager.getIndex, selected_widgets)
            selected_indexes = filter(lambda idx: idx is not None and idx.isValid(), selected_indexes)
            
            assert self._model is not None
            def selectionFromIndexes(selected_indexes:Iterable[QModelIndex]) -> QItemSelection:
                """Create a QItemSelection from a list of selected indexes."""
                item_selection = QItemSelection()
                for index in selected_indexes:
                    if index.isValid():
                        item_selection.select(index, index)
                
                return item_selection

            # perform selection on model
            item_selection = selectionFromIndexes(selected_indexes)
            self._selection.select(item_selection, QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows)
            if len(item_selection.indexes()) > 0:
                last_selected_index = item_selection.indexes()[-1]
                self._selection.setCurrentIndex(
                    last_selected_index,
                    QItemSelectionModel.SelectionFlag.Current | QItemSelectionModel.SelectionFlag.Rows
                )
            else:
                self._selection.clearSelection()
                self._selection.setCurrentIndex(QModelIndex(), QItemSelectionModel.SelectionFlag.Current | QItemSelectionModel.SelectionFlag.Rows)

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
        index = self.rowAt(QPoint(int(pos.x()), int(pos.y())))
        assert index is not None, f"got: {index}"
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
            drop_target = self.rowAt(pos)  # Ensure the index is updated
            if not self._linking_tool.finishLinking(drop_target):
                # Handle failed linking
                logger.warning("WARNING: Linking failed!")
        else:
            super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event:QMouseEvent):
        index = self.indexAt(QPoint(int(event.position().x()), int(event.position().y())))

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
    

    # def dragEnterEvent(self, event)->None:
    #     if event.mimeData().hasFormat(GraphMimeType.InletData) or event.mimeData().hasFormat(GraphMimeType.OutletData):
    #         # Create a draft link if the mime data is for inlets or outlets
            
    #         event.acceptProposedAction()

    #     if event.mimeData().hasFormat(GraphMimeType.LinkHeadData) or event.mimeData().hasFormat(GraphMimeType.LinkTailData):
    #         # Create a draft link if the mime data is for link heads or tails
    #         event.acceptProposedAction()

    # def dragLeaveEvent(self, event):
    #     if self._draft_link:
    #         scene = self.scene()
    #         assert scene is not None
    #         scene.removeItem(self._draft_link)
    #         self._draft_link = None
    #     #self._cleanupDraftLink()  # Cleanup draft link if it exists
    #     # super().dragLeaveEvent(event)
    #     # self._cleanupDraftLink()

    # def dragMoveEvent(self, event)->None:
    #     """Handle drag move events to update draft link position"""
    #     pos = QPoint(int(event.position().x()), int(event.position().y())) # Ensure pos is in integer coordinates

    #     data = event.mimeData()
    #     payload = Payload.fromMimeData(data)
        
    #     self.updateLinking(payload, pos)
    #     return

    # def dropEvent(self, event: QDropEvent) -> None:
    #     pos = QPoint(int(event.position().x()), int(event.position().y())) # Ensure pos is in integer coordinates
    #     drop_target = self.rowAt(pos)  # Ensure the index is updated

    #     # TODO: check for drag action
    #     # match event.proposedAction():
    #     #     case Qt.DropAction.CopyAction:
    #     #         ...
    #     #     case Qt.DropAction.MoveAction:
    #     #         ...
    #     #     case Qt.DropAction.LinkAction:
    #     #         ...
    #     #     case Qt.DropAction.IgnoreAction:
    #     #         ...
        
    #     if self.finishLinking(event.mimeData(), drop_target):
    #         event.acceptProposedAction()
    #     else:
    #         event.ignore()

