##################
# The Graph View #
##################

  
#
# A Graph view that directly connects to QStandardItemModel
#

from __future__ import annotations

import logging
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

from .managers import PersistentWidgetManager
from .managers.linking_manager import LinkingManager
from .managers.cell_manager import CellManager

from .widgets import (
    NodeWidget, PortWidget, LinkWidget, CellWidget
)
from .delegates.graphview_delegate import GraphDelegate
from ..controllers.qitemmodel_graphcontroller import QItemModelGraphController
# from .factories.widget_factory import WidgetFactory
from .factories.widget_factory_using_delegate import WidgetFactoryUsingDelegate



class GraphView(QGraphicsView):
    def __init__(self, delegate:GraphDelegate|None=None, parent: QWidget | None = None):
        super().__init__(parent=parent)
        self._model:QAbstractItemModel | None = None
        self._model_connections: list[tuple[Signal, Slot]] = []
        self._selection:QItemSelectionModel | None = None
        self._selection_connections: list[tuple[Signal, Slot]] = []

        assert isinstance(delegate, GraphDelegate) or delegate is None, "Invalid delegate"
        self._delegate = delegate if delegate else GraphDelegate()
        self._controller = QItemModelGraphController()
        self._factory = WidgetFactoryUsingDelegate()
        self._factory.portPositionChanged.connect(self.handlePortPositionChanged)

        ## State of the graph view
        self._linking_tool = LinkingTool(self)

        # Widget Manager
        self._widget_manager = PersistentWidgetManager()
        self._cell_manager = CellManager()

        # Link management
        self._link_manager = LinkingManager()

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
        if self._model_connections:
            for signal, slot in self._model_connections:
                signal.disconnect(slot)
        
        if model:
            assert isinstance(model, QAbstractItemModel), "Model must be a subclass of QAbstractItemModel"

            self._model_connections = [
                (model.rowsInserted, self.handleRowsInserted),
                (model.rowsAboutToBeRemoved, self.handleRowsAboutToBeRemoved),
                (model.rowsRemoved, self.handleRowsRemoved),
                (model.dataChanged, self.handleDataChanged)
            ]

            for signal, slot in self._model_connections:
                signal.connect(slot)

        self._model = model
        self._controller.setModel(model)
        
        # populate initial scene
        ## clear
        scene = self.scene()
        assert scene
        scene.clear()
        self._widget_manager.clear()
        self._link_manager.clear()
        self._cell_manager.clear()

        if self._model.rowCount(QModelIndex()) > 0:
            self.handleRowsInserted(QModelIndex(), 0, self._model.rowCount(QModelIndex()) - 1)

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

    def handlePortPositionChanged(self, index:QPersistentModelIndex):
        """Reposition all links connected to the moved port widget."""
        widget = self._widget_manager.getWidget(index)

        link_widgets: list[LinkWidget] = []
        link_widgets.extend(self._link_manager.getOutletLinks(widget))
        link_widgets.extend(self._link_manager.getInletLinks(widget))


        for link_widget in link_widgets:
            source_widget = self._link_manager.getLinkSource(link_widget)
            target_widget = self._link_manager.getLinkTarget(link_widget)
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
    @Slot(QModelIndex, int, int)
    def handleRowsInserted(self, parent:QModelIndex, start:int, end:int):
        assert self._model, "Model must be set before handling rows inserted!"

        # get index trees in BFS order
        def get_children(index:QModelIndex) -> Iterable[QModelIndex]:
            if not isinstance(index, QModelIndex):
                raise TypeError(f"Expected QModelIndex, got {type(index)}")
            model = index.model()
            for row in range(model.rowCount(index)):
                child_index = model.index(row, 0, index)
                yield child_index
            return []
        
        sorted_indexes:List[QModelIndex] = list(bfs(
            *[self._model.index(row, 0, parent) for row in range(start, end + 1)], 
            children=get_children, 
            reverse=False
        ))

        ## Add widgets for each index
        for row_index in sorted_indexes:
            # Widget Factory
            parent_widget = self._widget_manager.getWidget(row_index.parent()) if row_index.parent().isValid() else self.scene()
            match self._controller.itemType(row_index):
                case GraphItemType.SUBGRAPH:
                    raise NotImplementedError("Subgraphs are not yet supported in the graph view")
                    
                case GraphItemType.NODE:
                    # widget factory
                    row_widget = self._factory.createNodeWidget(self.scene(), row_index, self)

                    # widget management
                    self._widget_manager.insertWidget(row_index, row_widget)

                case GraphItemType.INLET:
                    assert isinstance(parent_widget, NodeWidget)
                    # widget factory
                    row_widget = self._factory.createInletWidget(parent_widget, row_index, self)

                    # widget management
                    self._widget_manager.insertWidget(row_index, row_widget)
                    
                case GraphItemType.OUTLET:
                    assert isinstance(parent_widget, NodeWidget)
                    # widget factory
                    row_widget = self._factory.createOutletWidget(parent_widget, row_index, self)
    

                    # widget management
                    self._widget_manager.insertWidget(row_index, row_widget)

                case GraphItemType.LINK:
                    assert isinstance(parent_widget, PortWidget)
                    # widget factory
                    row_widget = self._factory.createLinkWidget(self.scene(), row_index, self)

                    # widget management
                    self._widget_manager.insertWidget(row_index, row_widget)

                    # link management
                    source_index = self._controller.linkSource(row_index)
                    source_widget = self._widget_manager.getWidget(source_index) if source_index is not None else None
                    target_index = self._controller.linkTarget(row_index)
                    target_widget = self._widget_manager.getWidget(target_index) if target_index is not None else None
                    self._link_manager.link(row_widget, source_widget, target_widget)
                    self._update_link_position(row_widget, source_widget, target_widget)
                case _:
                    raise ValueError(f"Unknown item type: {self._controller.itemType(row_widget)}")


            # Add cells for each column
            for col in range(self._model.columnCount(row_index.parent())):
                cell_index = self._model.index(row_index.row(), col, row_index.parent())
                cell_widget = self._factory.createCellWidget(row_widget, cell_index, self)
                self._cell_manager.insertCell(cell_index, cell_widget)
                self._set_cell_data(cell_index, roles=[Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole])

    def handleColumnsInserted(self, parent: QModelIndex, start: int, end: int):
        # TODO: add cells
        raise NotImplementedError("Column insertion is not yet implemented in the graph view")

    def handleColumnsAboutToBeRemoved(self, parent: QModelIndex, start: int, end: int):
        # TODO: remove cells
        raise NotImplementedError("Column removal is not yet implemented in the graph view")

    @Slot(QModelIndex, int, int)
    def handleRowsAboutToBeRemoved(self, parent:QModelIndex, start:int, end:int):
        assert self._model, "Model must be set before handling rows removed!"

        # get index trees in BFS order
        def get_children(index:QModelIndex) -> Iterable[QModelIndex]:
            if not index.isValid():
                return []
            model = index.model()
            for row in range(model.rowCount(index)):
                child_index = model.index(row, 0, index)
                yield child_index

            return []
        
        sorted_indexes:List[QModelIndex] = list(bfs(
            *[self._model.index(row, 0, parent) for row in range(start, end + 1)], 
            children=get_children, 
            reverse=True
        ))
        
        ## Remove widgets for each index
        scene = self.scene()
        assert scene is not None
        scene.blockSignals(True)
        for row_index in sorted_indexes:
            row_widget = self._widget_manager.getWidget(row_index)
            if row_widget is None:
                logger.warning(f"Row widget not found for index: {indexToPath(row_index)}")
                # Already removed, skip
                continue

            # Remove all cells associated with this widget
            for col in range(self._model.columnCount(row_index.parent())):
                cell_index = self._model.index(row_index.row(), col, row_index.parent())
                if cell_widget := self._cell_manager.getCell(cell_index):
                    self._factory.destroyCellWidget(row_widget, cell_widget)
                    self._cell_manager.removeCell(cell_index)

            # Remove the row widget from the scene
            if row_index.parent().isValid():
                parent_widget = self._widget_manager.getWidget(row_index.parent())
            else:
                parent_widget = scene

            ## widget factory
            match self._controller.itemType(row_index):
                case GraphItemType.SUBGRAPH:
                    raise NotImplementedError("Subgraphs are not yet supported in the graph view")
                case GraphItemType.NODE:
                    self._factory.destroyNodeWidget(scene, row_widget)
                    self._widget_manager.removeWidget(row_index, row_widget)
                case GraphItemType.INLET:
                    self._factory.destroyInletWidget(parent_widget, row_widget)
                    self._widget_manager.removeWidget(row_index, row_widget)
                case GraphItemType.OUTLET:
                    self._factory.destroyOutletWidget(parent_widget, row_widget)
                    self._widget_manager.removeWidget(row_index, row_widget)
                case GraphItemType.LINK:
                    self._factory.destroyLinkWidget(scene, row_widget)
                    self._link_manager.unlink(row_widget)
                    self._widget_manager.removeWidget(row_index, row_widget)

                case _:
                    raise ValueError(f"Unknown widget type: {type(row_widget)}")

            # widget management
            

        scene.blockSignals(False)

    @Slot(QModelIndex, int, int)
    def handleRowsRemoved(self, parent:QModelIndex, start:int, end:int):
        ...
    
    def handleDataChanged(self, top_left:QModelIndex, bottom_right:QModelIndex, roles:list):
        """
        Handle data changes in the model.
        This updates the widgets in the graph view.
        """
        assert self._model

        if GraphDataRole.SourceRole in roles or roles == []:
            # If the source role is changed, we need to update the link widget
            for row in range(top_left.row(), bottom_right.row() + 1):
                index = self._model.index(row, top_left.column(), top_left.parent())
                match self._controller.itemType(index):
                    case GraphItemType.LINK:
                        link_widget = cast(LinkWidget, self._widget_manager.getWidget(index))
                        if link_widget:
                            source_widget = self._widget_manager.getWidget(self._controller.linkSource(index))
                            target_widget = self._widget_manager.getWidget(self._controller.linkTarget(index))

                            self._link_manager.unlink(link_widget)
                            self._link_manager.link(link_widget, source_widget, target_widget)
                            self._update_link_position(link_widget, source_widget, target_widget)

        if GraphDataRole.TypeRole in roles or roles == []:
            # if an inlet or outlet type is changed, we need to update the widget
            for row in range(top_left.row(), bottom_right.row() + 1):
                index = self._model.index(row, top_left.column(), top_left.parent())
                if widget := self._widget_manager.getWidget(index):
                    ... # TODO replace Widget

        for row in range(top_left.row(), bottom_right.row() + 1):
            index = self._model.index(row, top_left.column(), top_left.parent())
            self._set_cell_data(index, roles=[Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole])

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
        scene.blockSignals(True)
        
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
        
        scene.blockSignals(False)

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
            if cell_widget:= self._cell_manager.getCell(index):
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
        index = self.indexAt(QPoint(int(event.position().x()), int(event.position().y())))

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
    
    ## Export to NetworkX
    def toNetworkX(self)-> nx.MultiDiGraph:
        G = nx.MultiDiGraph()
        port_to_node: dict[QGraphicsItem, NodeWidget] = {}
        all_widgets = list(self._widget_manager.widgets())

        for widget in all_widgets:
            # collect nodes and ports
            if isinstance(widget, NodeWidget):
                node_widget = cast(NodeWidget, widget)
                node_name = widget.cells()[0].text()
                expression_text = widget.cells()[1].text()
                assert node_name not in G.nodes, f"Duplicate node name: {node_name}"
                inlet_names = []
                for inlet_widget in node_widget.inlets():
                    inlet_name = inlet_widget.cells()[0].text()
                    inlet_names.append(inlet_name)
                    port_to_node[inlet_widget] = node_widget

                for outlet_widget in node_widget.outlets():
                    port_to_node[outlet_widget] = node_widget

                assert node_name not in G.nodes, f"Duplicate node name: {node_name}"
                G.add_node(node_name, inlets=inlet_names, expression=expression_text)
                
            # collect links
            elif isinstance(widget, LinkWidget):
                source_outlet = self._link_manager.getLinkSource(widget)
                target_inlet = self._link_manager.getLinkTarget(widget)
                assert source_outlet is not None and target_inlet is not None, "Link source and target must be valid"
                source_node_widget = port_to_node[source_outlet]
                target_node_widget = port_to_node[target_inlet]
                G.add_edge(
                    source_node_widget.cells()[0].text(), 
                    target_node_widget.cells()[0].text(), 
                    target_inlet.cells()[0].text()
                )
        return G

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

