##################
# The Graph View #
##################

  
#
# A Graph view that directly connects to QStandardItemModel
#

from __future__ import annotations

import logging
logging.basicConfig(level=logging.DEBUG)
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

from .managers import WidgetManager
from .managers.link_manager import LinkManager
from .managers.cell_manager import CellManager

from .widgets import (
    NodeWidget, PortWidget, LinkWidget, CellWidget
)
from .graphview_delegate import GraphDelegate
from .controllers.graph_controller import GraphController
from .widget_factory import WidgetFactory


@dataclass
class Payload:
    index: QModelIndex | None
    kind: Literal['head', 'tail', 'inlet', 'outlet']

    @staticmethod
    def fromMimeData(model, mime:QMimeData) -> Payload | None:
        """
        Parse the payload from the mime data.
        This is used to determine the source and target of the link being dragged.
        """
        drag_source_type:Literal['inlet', 'outlet', 'head', 'tail']
        if mime.hasFormat(GraphMimeType.LinkTailData):
            drag_source_type = "tail"
        elif mime.hasFormat(GraphMimeType.LinkHeadData):
            drag_source_type = "head"
        elif mime.hasFormat(GraphMimeType.OutletData):
            drag_source_type = "outlet"
        elif mime.hasFormat(GraphMimeType.InletData):
            drag_source_type = "inlet"


        if mime.hasFormat(GraphMimeType.InletData):
            index_path = mime.data(GraphMimeType.InletData).data().decode("utf-8")

        elif mime.hasFormat(GraphMimeType.OutletData):
            index_path = mime.data(GraphMimeType.OutletData).data().decode("utf-8")

        elif mime.hasFormat(GraphMimeType.LinkTailData):
            index_path = mime.data(GraphMimeType.LinkTailData).data().decode("utf-8")

        elif mime.hasFormat(GraphMimeType.LinkHeadData):
            index_path = mime.data(GraphMimeType.LinkHeadData).data().decode("utf-8")
        else:
            # No valid mime type found
            return None

        index = indexFromPath(model, list(map(int, index_path.split("/"))))

        return Payload(index=index, kind=drag_source_type)
    
    def toMimeData(self) -> QMimeData:
        """
        Convert the payload to mime data.
        This is used to initiate a drag-and-drop operation for linking.
        """
        mime = QMimeData()

        # mime type
        mime_type = self.kind
            
        if mime_type is None:
            return None
        
        index_path = "/".join(map(str, indexToPath(self.index)))
        logger.debug(f"Creating mime data for index: {self.index}, path: {index_path}, type: {self.kind}")
        mime.setData(self.kind, index_path.encode("utf-8"))
        return mime


class GraphView(QGraphicsView):
    class State(Enum):
        IDLE = "IDLE"
        LINKING = "LINKING"

    def __init__(self, delegate:GraphDelegate|None=None, parent: QWidget | None = None):
        super().__init__(parent=parent)
        self._model:QAbstractItemModel | None = None
        self._model_connections: list[tuple[Signal, Slot]] = []
        self._selection:QItemSelectionModel | None = None
        self._selection_connections: list[tuple[Signal, Slot]] = []

        assert isinstance(delegate, GraphDelegate) or delegate is None, "Invalid delegate"
        self._delegate = delegate if delegate else GraphDelegate()
        self._controller = GraphController()
        self._factory = WidgetFactory()
        self._factory.portPositionChanged.connect(self.handlePortPositionChanged)

        ## State of the graph view
        self._state = GraphView.State.IDLE
        self._draft_link: QGraphicsLineItem | None = None
        self._linking_payload: QModelIndex = QModelIndex()  # This will hold the index of the item being dragged or linked
        self._link_end: Literal['head', 'tail'] | None = None  # This will hold the end of the link being dragged

        # Widget Manager
        self._widget_manager = WidgetManager()
        self._cell_manager = CellManager()

        # Link management
        self._link_manager = LinkManager()

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
                    row_widget = self._factory.createNodeWidget(parent_widget, row_index)
                case GraphItemType.INLET:
                    assert isinstance(parent_widget, NodeWidget)
                    row_widget = self._factory.createInletWidget(parent_widget, row_index)
                    
                case GraphItemType.OUTLET:
                    assert isinstance(parent_widget, NodeWidget)
                    row_widget = self._factory.createOutletWidget(parent_widget, row_index)
                case GraphItemType.LINK:
                    # Links are added to the scene, not to the inlet widget
                    row_widget = self._factory.createLinkWidget(self.scene(), row_index)
                    # link management
                    source_index = self._controller.linkSource(row_index)
                    source_widget = self._widget_manager.getWidget(source_index) if source_index is not None else None
                    target_index = self._controller.linkTarget(row_index)
                    target_widget = self._widget_manager.getWidget(target_index) if target_index is not None else None
                    self._link_manager.link(row_widget, source_widget, target_widget)
                    self._update_link_position(row_widget, source_widget, target_widget)
                case _:
                    raise ValueError(f"Unknown item type: {self._controller.itemType(row_widget)}")

            # widget management
            self._widget_manager.insertWidget(row_index, row_widget)
            
            # Add cells for each column
            for col in range(self._model.columnCount(row_index.parent())):
                cell_index = self._model.index(row_index.row(), col, row_index.parent())
                cell_widget = self._factory.createCellWidget(row_widget, cell_index)
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

    ## Interactions Controller eg.: linking
    def startLinking(self, payload:Payload)->bool:
        """
        Start linking from the given index.
        This is used to initiate a drag-and-drop operation for linking.
        return True if the drag operation was started, False otherwise.
        """

        if self._state != GraphView.State.IDLE:
            # Already in linking state, cannot start linking
            return False

        index_type = self._controller.itemType(payload.index)
        if index_type not in (GraphItemType.INLET, GraphItemType.OUTLET, GraphItemType.LINK):
            # Only inlets, outlets and links can be dragged
            return False
        
        if index_type in (GraphItemType.OUTLET, GraphItemType.INLET):
            # create a draft link line
            if not self._draft_link:
                self._draft_link = LinkWidget()
                self.scene().addItem(self._draft_link)

        self._state = GraphView.State.LINKING
        self._linking_payload = payload        

        return True

    def updateLinking(self, payload:Payload, pos:QPoint):
        """
        Update the linking position
        """
        if self._state != GraphView.State.LINKING:
            # Not in linking state, cannot update linking
            return
        
        pos = QPoint(int(pos.x()), int(pos.y())) # defense against passing QPointF
        
        # Determine the source and target types
        target_index = self.rowAt(pos)  # Ensure the index is updated
        drop_target_type = self._controller.itemType(target_index)
        drag_source_type = payload.kind

        # find relevant indexes
        outlet_index, inlet_index, link_index = None, None, None
        match drag_source_type, drop_target_type:
            case 'outlet', GraphItemType.INLET:
                link_index = None
                outlet_index = payload.index
                inlet_index = target_index

            case 'inlet', GraphItemType.OUTLET:
                # inlet dragged over outlet
                link_index = None
                outlet_index = target_index
                inlet_index = payload.index

            case 'tail', GraphItemType.OUTLET:
                # link tail dragged over outlet
                link_index = payload.index
                outlet_index = target_index
                inlet_index = self._controller.linkTarget(link_index)

            case 'head', GraphItemType.INLET:
                # link head dragged over inlet
                link_index = payload.index
                outlet_index = self._controller.linkSource(link_index)
                inlet_index = target_index

            case 'outlet', _:
                # outlet dragged over empty space
                link_index = None
                outlet_index = payload.index
                inlet_index = None  

            case 'inlet', _:
                # inlet dragged over empty space
                link_index = None
                outlet_index = None
                inlet_index = payload.index
                
            case 'head', _:
                # link head dragged over empty space
                link_index = payload.index
                outlet_index = self._controller.linkSource(link_index)
                inlet_index = None

            case 'tail', _:
                # link tail dragged over empty space
                link_index = payload.index
                outlet_index = None
                inlet_index = self._controller.linkTarget(link_index)

            case _:
                # No valid drag source or drop target, do nothing
                return None


        link_widget = self._widget_manager.getWidget(link_index) if link_index else self._draft_link

        if outlet_index and inlet_index and self._controller.canLink(outlet_index, inlet_index):
            outlet_widget = self._widget_manager.getWidget(outlet_index)
            inlet_widget = self._widget_manager.getWidget(inlet_index)
            line = makeLineBetweenShapes(outlet_widget, inlet_widget)
            line = QLineF(link_widget.mapFromScene(line.p1()), link_widget.mapFromScene(line.p2()))

        elif outlet_index:
            outlet_widget = self._widget_manager.getWidget(outlet_index)
            line = makeLineBetweenShapes(outlet_widget, self.mapToScene(pos))
            line = QLineF(link_widget.mapFromScene(line.p1()), link_widget.mapFromScene(line.p2()))

        elif inlet_index:
            inlet_widget = self._widget_manager.getWidget(inlet_index)
            line = makeLineBetweenShapes(self.mapToScene(pos), inlet_widget)
            line = QLineF(link_widget.mapFromScene(line.p1()), link_widget.mapFromScene(line.p2()))

        link_widget.setLine(line)

    def finishLinking(self, payload:Payload, target_index:QModelIndex)->bool:
        """
        Finish linking operation.
        """

        if self._state != GraphView.State.LINKING:
            # Not in linking state, cannot finish linking
            return False
        
        # Determine the drop target type
        drop_target_type = self._controller.itemType(target_index)

        # Determine the drag source type based on the mime data
        drag_source_type:Literal['inlet', 'outlet', 'head', 'tail'] = payload.kind

        # Perform the linking based on the drag source and drop target types
        # return True if the linking was successful, False otherwise
        success = False
        match drag_source_type, drop_target_type:
            case "outlet", GraphItemType.INLET:
                # outlet dropped on inlet
                outlet_index = payload.index
                assert outlet_index.isValid(), "Outlet index must be valid"
                inlet_index = target_index
                if self._controller.addLink(outlet_index, inlet_index):
                    success = True

            case "inlet", GraphItemType.OUTLET:
                # inlet dropped on outlet
                inlet_index = payload.index
                assert inlet_index.isValid(), "Inlet index must be valid"
                outlet_index = target_index
                if self._controller.addLink(outlet_index, inlet_index):
                    success = True

            case "head", GraphItemType.INLET:
                # link head dropped on inlet
                link_index = payload.index
                new_inlet_index = target_index
                current_outlet_index = self._controller.linkSource(link_index)
                if self._controller.removeLink(link_index):
                    if self._controller.addLink(current_outlet_index, new_inlet_index):
                        success = True

            case "tail", GraphItemType.OUTLET:
                # link tail dropped on outlet
                link_index = payload.index
                new_outlet_index = target_index
                current_inlet_index = self._controller.linkTarget(link_index)
                if self._controller.removeLink(link_index):
                    if self._controller.addLink(new_outlet_index, current_inlet_index):
                        success = True

            case 'tail', _:
                # tail dropped on empty space
                link_index = payload.index
                assert link_index.isValid(), "Link index must be valid"
                link_source = self._controller.linkSource(link_index)
                link_target = self._controller.linkTarget(link_index)
                IsLinked = link_source and link_source.isValid() and link_target and link_target.isValid()
                if IsLinked:
                    if self._controller.removeLink(link_index):
                        success = True

            case 'head', _:
                # head dropped on empty space
                link_index = payload.index
                assert link_index.isValid(), "Link index must be valid"
                link_source = self._controller.linkSource(link_index)
                link_target = self._controller.linkTarget(link_index)
                IsLinked = link_source and link_source.isValid() and link_target and link_target.isValid()
                if IsLinked:
                    if self._controller.removeLink(link_index):
                        success = True

        # cleanup DraftLink
        if self._draft_link:
            self.scene().removeItem(self._draft_link)
            self._draft_link = None

        self._state = GraphView.State.IDLE
        return success

    def cancelLinking(self):
        """
        Cancel the linking operation.
        This is used to remove the draft link and reset the state.
        """
        if self._state == GraphView.State.LINKING:

            if self._controller.itemType(self._linking_payload.index) == GraphItemType.LINK:
                link_widget = cast(LinkWidget, self._widget_manager.getWidget(self._linking_payload.index))
                assert link_widget is not None, "Link widget must not be None"
                source_widget = self._link_manager.getLinkSource(link_widget)
                target_widget = self._link_manager.getLinkTarget(link_widget)
                self._update_link_position(link_widget, source_widget, target_widget)

            else:
                assert self._draft_link is not None, "Draft link must not be None"
                if self._draft_link:
                    self.scene().removeItem(self._draft_link)
                    self._draft_link = None

            # Reset state
            self._state = GraphView.State.IDLE
            self._linking_payload = None

    ## Handle mouse events
    def mousePressEvent(self, event):
        """
        By default start linking from the item under the mouse cursor.
        if starting a link is not possible, fallback to the QGraphicsView behavior.
        """

        self.setCursor(Qt.CursorShape.DragLinkCursor)  # Reset cursor to default
        if self._state == GraphView.State.LINKING:
            # If we are already linking, cancel the linking operation
            self.cancelLinking()
            return
        
        if self._state == GraphView.State.IDLE:
            pos = event.position()
            index = self.rowAt(QPoint(int(pos.x()), int(pos.y())))  # Ensure the index is updated
            assert index is not None, f"got: {index}"

            match self._controller.itemType(index):
                case GraphItemType.INLET:
                    if self.startLinking(Payload(index, 'inlet')):
                        return
                case GraphItemType.OUTLET:
                    if self.startLinking(Payload(index, 'outlet')):
                        return

                case GraphItemType.LINK:
                    # If the item is a link, determine which end to drag
                    def getClosestLinkEnd(link_index:QModelIndex, scene_pos:QPointF) -> Literal['head', 'tail']:
                        source_index = self._controller.linkSource(link_index)
                        target_index = self._controller.linkTarget(link_index)
                        if source_index and source_index.isValid() and target_index and target_index.isValid():
                            link_widget = cast(LinkWidget, self._widget_manager.getWidget(link_index))
                            local_pos = link_widget.mapFromScene(scene_pos)  # Ensure scene_pos is in the correct coordinate system
                            tail_distance = (local_pos-link_widget.line().p1()).manhattanLength()
                            head_distance = (local_pos-link_widget.line().p2()).manhattanLength()

                            if head_distance < tail_distance:
                                return 'head'  # Drag the head if closer to the mouse position
                            else:
                                return 'tail'
                            
                        elif source_index and source_index.isValid():
                            return 'head'
                        
                        elif target_index and target_index.isValid():
                            return 'tail'
                        
                        else:
                            return 'tail'
                    
                    scene_pos = self.mapToScene(event.position().toPoint())
                    link_end = getClosestLinkEnd(index, scene_pos)
    
                    if self.startLinking(Payload(index, kind=link_end)):
                        return
                    
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._state == self.State.LINKING:
            pos = QPoint(int(event.position().x()), int(event.position().y())) # Ensure pos is in integer coordinates
            self.updateLinking(self._linking_payload, pos)
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self.unsetCursor()
        if self._state == self.State.LINKING:
            
            pos = QPoint(int(event.position().x()), int(event.position().y())) # Ensure pos is in integer coordinates
            drop_target = self.rowAt(pos)  # Ensure the index is updated
            if not self.finishLinking(self._linking_payload, drop_target):
                # Handle failed linking
                logger.warning("WARNING: Linking failed!")
                pass

        else:
            super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event:QMouseEvent):
        index = self.indexAt(QPoint(int(event.position().x()), int(event.position().y())))

        if not index.isValid():
            self._controller.addNode(self._model, QModelIndex())
            # self._model.insertRows(0, 1, QModelIndex())
            return
            # return super().mouseDoubleClickEvent(event)
                
        def onEditingFinished(editor:QLineEdit, cell_widget:CellWidget, index:QModelIndex):
            self._delegate.setModelData(editor, self._model, index)
            cell_widget.setEditorWidget(None)  # Clear the editor widget
            editor.deleteLater()
            self._set_cell_data(index, roles=[Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole])

        if cell_widget := self._cell_manager.getCell(index):
            editor = self._delegate.createEditor(self, None, index)
            assert editor.parent() is None, "Editor must not have a parent"
            cell_widget.setEditorWidget(editor)  # Clear any existing editor widget
            editor.setText(index.data(Qt.ItemDataRole.EditRole))
            editor.setFocus(Qt.FocusReason.MouseFocusReason)
            editor.editingFinished.connect(lambda editor = editor, cell_widget=cell_widget, index=index: onEditingFinished(editor, cell_widget, index) )
    
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
                source_outlet = self._link_source[widget]
                target_inlet = self._link_target[widget]
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

