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
from ..managers import LinkingManager

from ..widgets import (
    NodeWidget, PortWidget, LinkWidget, CellWidget
)
class InletWidget(PortWidget):
    pass

class OutletWidget(PortWidget):
    pass

from ..delegates.graphview_delegate import GraphDelegate
from ..controllers.qitemmodel_graphcontroller import QItemModelGraphController
# from .factories.widget_factory import WidgetFactory
from ..factories.widgetfactory_using_delegate import WidgetFactoryUsingDelegate


class QItemModel_GraphView(QGraphicsView):
    def __init__(self, delegate:GraphDelegate|None=None, parent: QWidget | None = None):
        super().__init__(parent=parent)
        self._model:QAbstractItemModel | None = None
        self._model_connections: list[tuple[Signal, Slot]] = []
        self._selection:QItemSelectionModel | None = None
        self._selection_connections: list[tuple[Signal, Slot]] = []

        assert isinstance(delegate, GraphDelegate) or delegate is None, "Invalid delegate"
        self._delegate = delegate if delegate else GraphDelegate()
        self._controller = QItemModelGraphController(parent=self)
        self._controller_connections: list[tuple[Signal, Slot]] = []
        self._controller_connections = [
            (self._controller.nodesInserted,           self.handleNodesInserted),
            (self._controller.inletsInserted,          self.handleInletsInserted),
            (self._controller.outletsInserted,         self.handleOutletsInserted),
            (self._controller.linksInserted,           self.handleLinksInserted),

            (self._controller.nodesAboutToBeRemoved,   self.handleNodesRemoved),
            (self._controller.inletsAboutToBeRemoved,  self.handleInletsRemoved),
            (self._controller.outletsAboutToBeRemoved, self.handleOutletsRemoved),
            (self._controller.linksAboutToBeRemoved,   self.handleLinksRemoved),

            (self._controller.attributeDataChanged,        self.handleAttributeDataChanged),
        ]
        for signal, slot in self._controller_connections:
            signal.connect(slot)

        self._factory = WidgetFactoryUsingDelegate()
        self._factory.portPositionChanged.connect(self.handlePortPositionChanged)

        ## State of the graph view
        self._linking_tool = LinkingTool(self, self._controller)

        # Widget Manager
        self._widget_manager = PersistentWidgetIndexManager()
        self._cell_manager = PersistentWidgetIndexManager()

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
        
    def setModel(self, model:QAbstractItemModel):
        if self._model:
            for signal, slot in self._model_connections:
                signal.disconnect(slot)
        
        # if model:
        #     assert isinstance(model, QAbstractItemModel), "Model must be a subclass of QAbstractItemModel"

        #     self._model_connections = [
        #         (model.rowsInserted, self.handleRowsInserted),
        #         (model.rowsAboutToBeRemoved, self.handleRowsAboutToBeRemoved),
        #         (model.rowsRemoved, self.handleRowsRemoved),
        #         (model.dataChanged, self.handleDataChanged)
        #     ]

        #     for signal, slot in self._model_connections:
        #         signal.connect(slot)

        self._model = model
        self._controller.setModel(model)
        
        # populate initial scene
        ## clear
        scene = self.scene()
        assert scene
        scene.clear()
        self._widget_manager.clear()
        self._cell_manager.clear()

        if self._model.rowCount(QModelIndex()) > 0:
            self.handleRowsInserted(QModelIndex(), 0, self._model.rowCount(QModelIndex()) - 1)

    def model(self) -> QAbstractItemModel | None:
        return self._model
    
    ## Index lookup
    def rowAt(self, point:QPoint, filter_type:GraphItemType|None=None) -> Tuple[QModelIndex, GraphItemType]|None:
        all_widgets = set(self._widget_manager.widgets())
        for item in self.items(point):
            if item in all_widgets:
                index = self._widget_manager.getIndex(item)
                if filter_type is None:
                    return index, self._controller.itemType(index)
                else:
                    if self._controller.itemType(index) == filter_type:
                        return index, self._controller.itemType(index)
        return None

    def nodeAt(self, point:QPoint) -> QModelIndex|None:
        return self.rowAt(point, GraphItemType.NODE)
    
    def inletAt(self, point:QPoint) -> QModelIndex:
        return self.rowAt(point, GraphItemType.INLET)
    
    def outletAt(self, point:QPoint) -> QModelIndex:
        return self.rowAt(point, GraphItemType.OUTLET)
    
    def linkAt(self, point:QPoint) -> QModelIndex:
        return self.rowAt(point, GraphItemType.LINK)
    
    def attributeAt(self, point:QPoint) -> QModelIndex:
        """
        Find the index at the given position.
        point is in untransformed viewport coordinates, just like QMouseEvent::pos().
        """
        all_cells = set(self._cell_manager.widgets())
        for item in self.items(point):
            if item in all_cells:
                return self._cell_manager.getIndex(item)
        return QModelIndex()

    def handlePortPositionChanged(self, port_index:QPersistentModelIndex):
        """Reposition all links connected to the moved port widget."""
        

        link_indexes = self._controller.links(port_index)


        for link_index in link_indexes:
            if link_widget := self._widget_manager.getWidget(link_index):
                source_index = self._controller.linkSource(link_index)
                source_widget = self._widget_manager.getWidget(source_index)
                target_index = self._controller.linkTarget(link_index)
                target_widget = self._widget_manager.getWidget(target_index)
                if source_widget and target_widget:
                    self._update_link_position(link_widget, source_widget, target_widget)

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
            ...

        link_widget.update()

    ## Manage widgets lifecycle
    def addNodeWidgetForIndex(self, row_index:QPersistentModelIndex)->QGraphicsItem:
        assert row_index.column() == 0, "Can only add node widget for column 0"

        # widget management
        row_widget = self._factory.createNodeWidget(self.scene(), row_index, self)
        self._widget_manager.insertWidget(row_index, row_widget)

        # inlets and outlets
        for inlet_index in self._controller.inlets(row_index):
            self.addInletWidgetForIndex(inlet_index)
        for outlet_index in self._controller.outlets(row_index):
            self.addOutletWidgetForIndex(outlet_index)

        # Add cells for each column
        for attribute_index in self._controller.attributes(row_index):
            self.addCellWidgetForIndex(attribute_index)

        return row_widget

    def removeNodeWidgetForIndex(self, row_index:QPersistentModelIndex):
        ## Remove cells
        for attribute_index in reversed(self._controller.attributes(row_index)):
            self.removeCellWidgetForIndex(attribute_index)

        # inlets and outlets
        for inlet_index in self._controller.inlets(row_index):
            self.removeInletWidgetForIndex(inlet_index)
        for outlet_index in self._controller.outlets(row_index):
            self.removeOutletWidgetForIndex(outlet_index)

        # widget management
        row_widget = self._widget_manager.getWidget(row_index)
        self._factory.destroyNodeWidget(self.scene(), row_widget)
        self._widget_manager.removeWidget(row_index)

    def addInletWidgetForIndex(self, row_index:QPersistentModelIndex)->QGraphicsItem:
        assert row_index.column() == 0, "Can only add inlet widget for column 0"
        parent_node_widget = self._widget_manager.getWidget(row_index.parent())

        # widget factory
        row_widget = self._factory.createInletWidget(parent_node_widget, row_index, self)

        # widget management
        self._widget_manager.insertWidget(row_index, row_widget)

        # Add cells for each column
        for attribute_index in self._controller.attributes(row_index):
            self.addCellWidgetForIndex(attribute_index)

        return row_widget

    def removeInletWidgetForIndex(self, row_index:QPersistentModelIndex):
        ## Remove cells
        for col in range(self._model.columnCount(row_index.parent())):
            cell_index = self._model.index(row_index.row(), col, row_index.parent())
            self.removeCellWidgetForIndex(cell_index)

        # widget management
        row_widget = self._widget_manager.getWidget(row_index)
        parent_widget = self._widget_manager.getWidget(row_index.parent())
        self._factory.destroyInletWidget(parent_widget, row_widget)
        self._widget_manager.removeWidget(row_index)

    def addOutletWidgetForIndex(self, row_index:QPersistentModelIndex)->QGraphicsItem:
        parent_node_widget = self._widget_manager.getWidget(row_index.parent())
        assert isinstance(parent_node_widget, NodeWidget)
        # widget factory
        row_widget = self._factory.createOutletWidget(parent_node_widget, row_index, self)

        # widget management
        self._widget_manager.insertWidget(row_index, row_widget)

        # Add cells for each column
        for attribute_index in self._controller.attributes(row_index):
            self.addCellWidgetForIndex(attribute_index)

        return row_widget

    def removeOutletWidgetForIndex(self, row_index:QPersistentModelIndex):
        ## Remove cells
        for attribute_index in reversed(self._controller.attributes(row_index)):
            self.removeCellWidgetForIndex(attribute_index)

        # widget management
        row_widget = self._widget_manager.getWidget(row_index)
        parent_widget = self._widget_manager.getWidget(row_index.parent())
        self._factory.destroyOutletWidget(parent_widget, row_widget)
        self._widget_manager.removeWidget(row_index)

    def addLinkWidgetForIndex(self, link:QPersistentModelIndex)->QGraphicsItem:
        inlet_index = self._controller.linkTarget(link)  # ensure target is valid
        parent_inlet_widget = self._widget_manager.getWidget(inlet_index)
        assert isinstance(parent_inlet_widget, PortWidget)
        # widget factory
        link_widget = self._factory.createLinkWidget(self.scene(), link, self)

        # widget management
        self._widget_manager.insertWidget(link, link_widget)

        # link management
        source_index = self._controller.linkSource(link)
        source_widget = self._widget_manager.getWidget(source_index) if source_index is not None else None
        target_index = self._controller.linkTarget(link)
        target_widget = self._widget_manager.getWidget(target_index) if target_index is not None else None
        # self._link_manager.link(link_widget, source_widget, target_widget)
        self._update_link_position(link_widget, source_widget, target_widget)

        # Add cells for each column
        for attribute_index in self._controller.attributes(link):
            self.addCellWidgetForIndex(attribute_index)

        return link_widget
    
    def removeLinkWidgetForIndex(self, link_index:QModelIndex):
        ## Remove cells
        for attribute_index in reversed(self._controller.attributes(link_index)):
            self.removeCellWidgetForIndex(attribute_index)

        # widget management
        link_widget = self._widget_manager.getWidget(link_index)
        parent_widget = self._widget_manager.getWidget(link_index.parent())
        self._factory.destroyLinkWidget(self.scene(), link_widget)
        # self._link_manager.unlink(link_widget)
        self._widget_manager.removeWidget(link_index)

    def addCellWidgetForIndex(self, cell_index:QModelIndex)->QGraphicsItem:
        row_index = self._controller.attributeOwner(cell_index)
        row_widget = self._widget_manager.getWidget(row_index)
        cell_widget = self._factory.createCellWidget(row_widget, cell_index, self)
        self._cell_manager.insertWidget(cell_index, cell_widget)
        self._set_cell_data(cell_index, roles=[Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole])
        return cell_widget
    
    def removeCellWidgetForIndex(self, cell_index:QModelIndex):
        if cell_widget := self._cell_manager.getWidget(cell_index):
            row_index = self._controller.attributeOwner(cell_index)
            row_widget = self._widget_manager.getWidget(row_index)
            self._factory.destroyCellWidget(row_widget, cell_widget)
            self._cell_manager.removeWidget(cell_index)

    ## Handle model changes
    def handleNodesInserted(self, node_indexes:List[QPersistentModelIndex]):
        for node_index in node_indexes:
            self.addNodeWidgetForIndex(node_index)

    def handleNodesRemoved(self, node_indexes:List[QPersistentModelIndex]):
        for node_index in node_indexes:
            self.removeNodeWidgetForIndex(node_index)

    def handleInletsInserted(self, inlet_indexes:List[QPersistentModelIndex]):
        for inlet_index in inlet_indexes:
            self.addInletWidgetForIndex(inlet_index)

    def handleInletsRemoved(self, inlet_indexes:List[QPersistentModelIndex]):
        for inlet_index in inlet_indexes:
            self.removeInletWidgetForIndex(inlet_index)

    def handleOutletsInserted(self, outlet_indexes:List[QPersistentModelIndex]):
        for outlet_index in outlet_indexes:
            self.addOutletWidgetForIndex(outlet_index)

    def handleOutletsRemoved(self, outlet_indexes:List[QPersistentModelIndex]):
        for outlet_index in outlet_indexes:
            self.removeOutletWidgetForIndex(outlet_index)

    def handleLinksInserted(self, link_indexes:List[QPersistentModelIndex]):
        for link_index in link_indexes:
            self.addLinkWidgetForIndex(link_index)

    def handleLinksRemoved(self, link_indexes:List[QPersistentModelIndex]):
        for link_index in link_indexes:
            self.removeLinkWidgetForIndex(link_index)

    def handleAttributeDataChanged(self, attributes:List[QPersistentModelIndex], roles:List[int]):
        for attribute in attributes:
            self._set_cell_data(attribute, roles)

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
            
            assert self._model
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

        if Qt.ItemDataRole.DisplayRole in roles or Qt.ItemDataRole.DisplayRole in roles or roles == []:
            if cell_widget:= self._cell_manager.getWidget(index):
                text = index.data(Qt.ItemDataRole.DisplayRole)
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
        index = self.attributeAt(QPoint(int(event.position().x()), int(event.position().y())))

        if not index.isValid():
            idx = self._controller.addNode(QModelIndex())
            if widget := self._widget_manager.getWidget(idx):
                center = widget.boundingRect().center()
                widget.setPos(self.mapToScene(event.position().toPoint())-center)

            return
            
        def onEditingFinished(editor:QLineEdit, cell_widget:CellWidget, index:QModelIndex):
            self._delegate.setModelData(editor, self._model, index)
            editor.deleteLater()
            self._set_cell_data(index, roles=[Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole])

        if cell_widget := self._cell_manager.getWidget(index):
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

