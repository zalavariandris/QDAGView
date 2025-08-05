#####################
# The Network Scene #
#####################

#
# A Graph view that directly connects to QStandardItemModel
#
from __future__ import annotations
import traceback

from enum import Enum
from typing import *
from qtpy.QtGui import *
from qtpy.QtCore import *
from qtpy.QtWidgets import *

from collections import defaultdict
from bidict import bidict

from utils import group_consecutive_numbers

from graphview_widgets import (
    BaseRowWidget, CellWidget, NodeWidget, InletWidget, OutletWidget, LinkWidget
)
from utils.geo import makeLineBetweenShapes, makeLineToShape, makeArrowShape, getShapeCenter
# from pylive.utils.geo import makeLineBetweenShapes, makeLineToShape
# from pylive.utils.qt import distribute_items_horizontal
# from pylive.utils.unique import make_unique_name
# from pylive.utils.diff import diff_set

import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


from core import GraphDataRole, GraphItemType, GraphMimeType
from utils import bfs
from graphdelegate import GraphDelegate
from dataclasses import dataclass


@dataclass
class Payload:
    index: QModelIndex | None
    kind: Literal['head', 'tail', 'inlet', 'outlet']


def indexFromPath(model, path:str) -> QModelIndex:
    """
    Parse a path string to a persistent model index.
    This is used to convert the path string back to a QModelIndex.
    """
    path = list(map(int, path.split("/")))

    idx = model.index(path[0], 0, QModelIndex())
    for row in path[1:]:
        idx = model.index(row, 0, idx)
    return idx

# Convert index to path string
def indexToPath(index:QModelIndex|QPersistentModelIndex) -> str:
    path = []
    idx = index
    while idx.isValid():
        path.append(idx.row())
        idx = idx.parent()
    return "/".join(map(str, reversed(path)))

    
def payloadFromMimeData(model, mime:QMimeData) -> Payload:
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

    index = indexFromPath(model, index_path)

    return Payload(index=index, kind=drag_source_type)


def payloadToMimeData(payload:Payload) -> QMimeData:
    """
    Convert the payload to mime data.
    This is used to initiate a drag-and-drop operation for linking.
    """
    mime = QMimeData()

    # mime type
    mime_type = payload.kind
        
    if mime_type is None:
        return None
    
    index_path = indexToPath(payload.index)
    print(f"Creating mime data for index: {payload.index}, path: {index_path}, type: {payload.kind}")
    mime.setData(payload.kind, index_path.encode("utf-8"))
    return mime
    

class GraphView(QGraphicsView):
    class State(Enum):
        IDLE = "IDLE"
        LINKING = "LINKING"

    def __init__(self, delegate:GraphDelegate|None=None, parent: QWidget | None = None):
        super().__init__(parent=parent)
        self._model:QAbstractItemModel | None = None
        self._model_connections = []
        self._selection:QItemSelectionModel | None = None
        self._selection_connections = []

        self._delegate = delegate if delegate else GraphDelegate()

        ## State of the graph view
        self._state = GraphView.State.IDLE
        self._draft_link: QGraphicsLineItem | None = None
        self._linking_payload: QModelIndex = QModelIndex()  # This will hold the index of the item being dragged or linked
        self._link_end: Literal['head', 'tail'] | None = None  # This will hold the end of the link being dragged

        # store model widget relations
        self._widgets: bidict[QPersistentModelIndex, BaseRowWidget] = bidict()
        self._cells: bidict[QPersistentModelIndex, CellWidget] = bidict()
        
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
                (model.rowsInserted, self.onRowsInserted),
                (model.rowsAboutToBeRemoved, self.onRowsAboutToBeRemoved),
                (model.rowsRemoved, self.onRowsRemoved),
                (model.dataChanged, self.onDataChanged)
            ]

            for signal, slot in self._model_connections:
                signal.connect(slot)
        self._model = model
        
        # populate initial scene
        ## clear
        scene = self.scene()
        assert scene
        scene.clear()
        self._widgets.clear()
        self._cells.clear()
        if self._model.rowCount(QModelIndex()) > 0:
            self.onRowsInserted(QModelIndex(), 0, self._model.rowCount(QModelIndex()) - 1)

    def model(self) -> QAbstractItemModel | None:
        return self._model
    
    def indexFromRowWidget(self, widget:QGraphicsItem) -> QModelIndex:
        """
        Get the index of the node widget in the model.
        This is used to identify the node in the model.
        """
        idx = self._widgets.inverse[widget]
        return QModelIndex(idx)
    
    def rowWidgetFromIndex(self, index:QModelIndex|QPersistentModelIndex) -> BaseRowWidget|None:
        """
        Get the widget from the index.
        This is used to identify the node in the model.
        Returns None if the widget does not exist for the given index.
        """
        idx = QPersistentModelIndex(index)
        return self._widgets.get(idx, None)
    
    def indexFromCell(self, cell:CellWidget) -> QModelIndex:
        """
        Get the index of the cell widget in the model.
        This is used to identify the cell in the model.
        """
        idx = self._cells.inverse[cell]
        return QModelIndex(idx)
    
    def cellFromIndex(self, index:QModelIndex|QPersistentModelIndex) -> CellWidget|None:
        idx = QPersistentModelIndex(index)
        return self._cells.get(idx, None)

    def rowAt(self, point:QPoint) -> QModelIndex:
        """
        Find the index at the given position.
        point is in untransformed viewport coordinates, just like QMouseEvent::pos().
        """

        all_widgets = set(self._widgets.values())
        for item in self.items(point):
            if item in all_widgets:
                # If the item is a widget, return its index
                return self.indexFromRowWidget(item)
        return QModelIndex()
    
    def indexAt(self, point:QPoint) -> QModelIndex:
        """
        Find the index at the given position.
        point is in untransformed viewport coordinates, just like QMouseEvent::pos().
        """
        all_cells = set(self._cells.values())
        for item in self.items(point):
            if item in all_cells:
                # If the item is a cell, return its index
                return self.indexFromCell(item)
            
        # fallback to rowAt if no cell is found
        return self.rowAt(point)

    def createRowWidget(self, parent_widget:QGraphicsItem|QGraphicsScene, index:QModelIndex|QPersistentModelIndex) -> BaseRowWidget:
        # create the widget
        match self._delegate.itemType(index):
            case GraphItemType.SUBGRAPH:
                raise NotImplementedError("Subgraphs are not yet supported in the graph view")
            case GraphItemType.NODE:
                widget = NodeWidget()
            case GraphItemType.INLET:
                widget = InletWidget()
            case GraphItemType.OUTLET:
                widget =  OutletWidget()
            case GraphItemType.LINK:
                widget = LinkWidget()
            case _:
                raise ValueError(f"Unknown item type: {self._delegate.itemType(index)}")
        
        # add the widget to the scene or parent widget
        match parent_widget:
            case QGraphicsScene():
                # attach to scene
                parent_widget.addItem(widget)

            case NodeWidget():
                match widget:
                    case OutletWidget():
                        node_index = index.parent()
                        pos = self._delegate.outletCount(node_index)
                        parent_widget.insertOutlet(pos, widget)
                        # widget.scenePositionChanged.connect(self.onPortScenePositionChanged)

                    case InletWidget():
                        node_index = index.parent()
                        pos = self._delegate.inletCount(node_index)
                        parent_widget.insertInlet(pos, widget)
                        # widget.scenePositionChanged.connect(self.onPortScenePositionChanged)
                    case _:
                        ...

            case InletWidget():
                match widget:
                    case LinkWidget():
                        widget.setParentItem(parent_widget)
                        # source_widget = self.rowWidgetFromIndex(self._delegate.linkSource(index))
                        # target_widget = self.rowWidgetFromIndex(self._delegate.linkTarget(index))
                        # if source_widget:
                        #     self._outlinks[source_widget].append(widget)
                        # if target_widget:
                        #     self._inlinks[target_widget].append(widget)

                        source_index = self._delegate.linkSource(index)
                        source_widget = self.rowWidgetFromIndex(source_index) if source_index is not None else None
                        target_index = self._delegate.linkTarget(index)
                        target_widget = self.rowWidgetFromIndex(target_index)
                        widget.link(source_widget, target_widget)
            case _:
                raise ValueError(f"Unknown parent widget type: {type(parent_widget)}")
            
        return widget

    def destroyRowWidget(self, widget:QGraphicsItem, index:QModelIndex|QPersistentModelIndex):
        scene = widget.scene()
        assert scene is not None
        parent_widget = widget.parentItem()
        match parent_widget:
            case None:
                # attach to scene
                scene.removeItem(widget)

            case NodeWidget():
                match widget:
                    case OutletWidget():
                        parent_widget.removeOutlet(widget)
                        widget.scenePositionChanged.disconnect(self.onPortScenePositionChanged)
                    case InletWidget():
                        parent_widget.removeInlet(widget)
                        widget.scenePositionChanged.disconnect(self.onPortScenePositionChanged)
                    case _:
                        widget.setParentItem(None)
                        scene.removeItem(widget)

            case InletWidget():
                match widget:
                    case LinkWidget():
                        # widget.unlink()
                        widget.setParentItem(parent_widget)
                        scene.removeItem(widget)
                        source_widget = self.rowWidgetFromIndex(self._delegate.linkSource(index))
                        target_widget = self.rowWidgetFromIndex(self._delegate.linkTarget(index))
                        # if source_widget:
                        #     self._outlinks[source_widget].remove(widget)
                        # if target_widget:
                        #     self._inlinks[target_widget].remove(widget)
                    case _:
                        widget.setParentItem(None)
                        scene.removeItem(widget)
            case _:
                raise ValueError(f"Unknown parent widget type: {type(parent_widget)}")

    # def _update_link_position(self, link_index:QModelIndex|QPersistentModelIndex, source_widget:QGraphicsItem|None=None, target_widget:QGraphicsItem|None=None):
    #     link_widget = cast(LinkWidget, self.rowWidgetFromIndex(link_index))

    #     print("update link position for index:", link_index, source_widget, target_widget)
    #     if source_widget and target_widget:
    #         line = makeLineBetweenShapes(source_widget, target_widget)
    #         line = QLineF(
    #             QPointF(link_widget.mapFromScene(line.p1())), 
    #             QPointF(link_widget.mapFromScene(line.p2()))
    #         )
    #         link_widget.setLine(line)
    #     elif source_widget:
    #         ...
    #     elif target_widget:
    #         ...
    #     else:
    #         ...

    # def onPortScenePositionChanged(self):
    #     # Update the position of the port widget
    #     widget = self.sender()
    #     port_index = self.indexFromRowWidget(widget)

    #     links = []
    #     match self._delegate.itemType(port_index):
    #         case GraphItemType.OUTLET:
    #             print("Updating outlet position for index:", port_index)
    #             # Update links connected to this outlet
    #             links = self._outlinks[port_index]

    #         case GraphItemType.INLET:
    #             print("Updating inlet position for index:", port_index)
    #             links = self._inlinks[port_index]

    #     for link_index in links:
    #         link_widget = cast(LinkWidget, self.rowWidgetFromIndex(link_index))
    #         if link_widget:
    #             source_widget = self.rowWidgetFromIndex(self._delegate.linkSource(link_index))
    #             target_widget = self.rowWidgetFromIndex(self._delegate.linkTarget(link_index))
    #             self._update_link_position(link_index, source_widget, target_widget)

    @Slot(QModelIndex, int, int)
    def onRowsInserted(self, parent:QModelIndex, start:int, end:int):
        assert self._model, "Model must be set before handling rows inserted!"

        def make_child_widgets_bfs(parent:QModelIndex, start:int, end:int):
            def get_children(index:QModelIndex) -> Iterable[QModelIndex]:
                if not isinstance(index, QModelIndex):
                    raise TypeError(f"Expected QModelIndex, got {type(index)}")
                model = index.model()
                for row in range(model.rowCount(index)):
                    child_index = model.index(row, 0, index)
                    yield child_index
                return []
            
            sorted_indexes = bfs(
                *[self._model.index(row, 0, parent) for row in range(start, end + 1)], 
                children=get_children, 
                reverse=False
            )

            for row_index in sorted_indexes:
                # create the row widget
                parent_widget = self.rowWidgetFromIndex(row_index.parent()) if row_index.parent().isValid() else self.scene()
                row_widget = self.createRowWidget(parent_widget, row_index)
                assert isinstance(row_widget, BaseRowWidget), f"Widget must be a subclass of BaseRowWidget, got {type(row_widget)}"
                
                # Store the widget in the _widgets dictionary
                self._widgets[QPersistentModelIndex(row_index)] = row_widget

                # add cells to the row widget
                for col in range(self._model.columnCount(row_index.parent())):
                    cell_index = self._model.index(row_index.row(), col, row_index.parent())
                    cell = CellWidget()
                    self._cells[QPersistentModelIndex(cell_index)] = cell
                    row_widget.insertCell(col, cell)

                    # Set data for each column
                    self._set_cell_data (cell_index.row(), col, cell_index.parent())

        make_child_widgets_bfs(parent, start, end)

    def onColumnsInserted(self, parent: QModelIndex, start: int, end: int):
        # TODO: add cells
        raise NotImplementedError("Column insertion is not yet implemented in the graph view")

    def onColumnsAboutToBeRemoved(self, parent: QModelIndex, start: int, end: int):
        # TODO: remove cells
        raise NotImplementedError("Column removal is not yet implemented in the graph view")

    @Slot(QModelIndex, int, int)
    def onRowsAboutToBeRemoved(self, parent:QModelIndex, start:int, end:int):
        assert self._model, "Model must be set before handling rows removed!"

        def get_children(index:QModelIndex) -> Iterable[QModelIndex]:
            if not index.isValid():
                return []
            model = index.model()
            for row in range(model.rowCount(index)):
                child_index = model.index(row, 0, index)
                yield child_index

            return []
        
        sorted_indexes = bfs(
            *[self._model.index(row, 0, parent) for row in range(start, end + 1)], 
            children=get_children, 
            reverse=True
        )
        
        scene = self.scene()
        assert scene is not None
        scene.blockSignals(True)
        for row_index in sorted_indexes:
            row_widget = self.rowWidgetFromIndex(row_index)
            if row_widget is None:
                # Already removed, skip
                continue

            # Remove all cells associated with this widget
            for col in range(self._model.columnCount(row_index.parent())):
                cell_index = self._model.index(row_index.row(), col, row_index.parent())
                if cell_widget := self.cellFromIndex(cell_index):
                    row_widget.removeCell(cell_widget)
                    del self._cells[QPersistentModelIndex(cell_index)]

            # Remove the row widget from the scene
            self.destroyRowWidget(row_widget, row_index)

            # Clean up orphaned widgets and cells to avoid memory leaks
            del self._widgets[QPersistentModelIndex(row_index)]
                
        scene.blockSignals(False)

    @Slot(QModelIndex, int, int)
    def onRowsRemoved(self, parent:QModelIndex, start:int, end:int):
        ...
    
    def onDataChanged(self, top_left:QModelIndex, bottom_right:QModelIndex, roles:list):
        """
        Handle data changes in the model.
        This updates the widgets in the graph view.
        """
        assert self._model

        if GraphDataRole.SourceRole in roles or roles == []:
            # If the source role is changed, we need to update the link widget
            for row in range(top_left.row(), bottom_right.row() + 1):
                index = self._model.index(row, top_left.column(), top_left.parent())
                match self._delegate.itemType(index):
                    case GraphItemType.LINK:
                        link_widget = cast(LinkWidget, self.rowWidgetFromIndex(index))
                        if link_widget:
                            link_widget.unlink()
                            source_widget = self.rowWidgetFromIndex(self._delegate.linkSource(index))
                            target_widget = self.rowWidgetFromIndex(self._delegate.linkTarget(index))
                            link_widget.link(source_widget, target_widget)

        if GraphDataRole.TypeRole in roles or roles == []:
            # if an inlet or outlet type is changed, we need to update the widget
            for row in range(top_left.row(), bottom_right.row() + 1):
                index = self._model.index(row, top_left.column(), top_left.parent())
                if widget := self.rowWidgetFromIndex(index):
                    ... # TODO replace Widget

        for row in range(top_left.row(), bottom_right.row() + 1):
            index = self._model.index(row, top_left.column(), top_left.parent())
            print("Updating widget data for index:", index)
            if cell_widget := self.cellFromIndex(index):
                cell_widget.setDisplayText(index.data(Qt.ItemDataRole.DisplayRole))

    @Slot(QItemSelection, QItemSelection)
    def onSelectionChanged(self, selected:QItemSelection, deselected:QItemSelection):
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
                if widget:=self.rowWidgetFromIndex(index):
                    if widget.scene() and widget.isSelected():
                        widget.setSelected(False)

        for index in selected_indexes:
            if index.isValid() and index.column() == 0:
                if widget:=self.rowWidgetFromIndex(index):
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
                (selection.selectionChanged, self.onSelectionChanged)
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
    
    # # 
    def syncSelectionModel(self):
        """update selection model from scene selection"""
        scene = self.scene()
        assert scene is not None
        if self._model and self._selection:
            # get currently selected widgets
            selected_widgets = scene.selectedItems()

            # map widgets to QModelIndexes
            selected_indexes = map(self.indexFromRowWidget, selected_widgets)
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

    def _set_cell_data(self, row:int, column:int, parent:QModelIndex|QPersistentModelIndex, roles:list=[]):
        """Set the data for a node widget."""
        index = self._model.index(row, column, parent)
        assert index.isValid(), "Index must be valid"

        if cell_widget:= self.cellFromIndex(index):
            cell_widget.setDisplayText(index.data(Qt.ItemDataRole.DisplayRole))

    ## Linking
    def startLinking(self, payload:Payload)->bool:
        """
        Start linking from the given index.
        This is used to initiate a drag-and-drop operation for linking.
        return True if the drag operation was started, False otherwise.
        """

        if self._state != GraphView.State.IDLE:
            # Already in linking state, cannot start linking
            return False

        index_type = self._delegate.itemType(payload.index)
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
        
        # mime = payloadToMimeData(payload)
        # if mime is None:
        #     return False
        
        # drag = QDrag(self)
        # drag.setMimeData(mime)

        # # Execute drag
        # try:
        #     action = drag.exec(Qt.DropAction.LinkAction)
        # except Exception as err:
        #     traceback.print_exc()
        # return True

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
        drop_target_type = self._delegate.itemType(target_index)
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
                inlet_index = self._delegate.linkTarget(link_index)

            case 'head', GraphItemType.INLET:
                # link head dragged over inlet
                link_index = payload.index
                outlet_index = self._delegate.linkSource(link_index)
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
                outlet_index = self._delegate.linkSource(link_index)
                inlet_index = None

            case 'tail', _:
                # link tail dragged over empty space
                link_index = payload.index
                outlet_index = None
                inlet_index = self._delegate.linkTarget(link_index)

            case _:
                # No valid drag source or drop target, do nothing
                return None


        link_widget = self.rowWidgetFromIndex(link_index) if link_index else self._draft_link

        if outlet_index and inlet_index and self._delegate.canLink(outlet_index, inlet_index):
            outlet_widget = self.rowWidgetFromIndex(outlet_index)
            inlet_widget = self.rowWidgetFromIndex(inlet_index)
            line = makeLineBetweenShapes(outlet_widget, inlet_widget)
            line = QLineF(link_widget.mapFromScene(line.p1()), link_widget.mapFromScene(line.p2()))

        elif outlet_index:
            outlet_widget = self.rowWidgetFromIndex(outlet_index)
            line = makeLineBetweenShapes(outlet_widget, self.mapToScene(pos))
            line = QLineF(link_widget.mapFromScene(line.p1()), link_widget.mapFromScene(line.p2()))

        elif inlet_index:
            inlet_widget = self.rowWidgetFromIndex(inlet_index)
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
        drop_target_type = self._delegate.itemType(target_index)

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
                self._delegate.addLink(self._model, outlet_index, inlet_index)
                success = True

            case "inlet", GraphItemType.OUTLET:
                # inlet dropped on outlet
                inlet_index = payload.index
                assert inlet_index.isValid(), "Inlet index must be valid"
                outlet_index = target_index
                self._delegate.addLink(self._model, outlet_index, inlet_index)
                success = True

            case "head", GraphItemType.INLET:
                # link head dropped on inlet
                link_index = payload.index
                new_inlet_index = target_index
                current_outlet_index = self._delegate.linkSource(link_index)
                self._delegate.removeLink(self._model, link_index)
                self._delegate.addLink(self._model, current_outlet_index, new_inlet_index)
                success = True

            case "tail", GraphItemType.OUTLET:
                # link tail dropped on outlet
                link_index = payload.index
                new_outlet_index = target_index
                current_inlet_index = self._delegate.linkTarget(link_index)
                self._delegate.removeLink(self._model, link_index)
                self._delegate.addLink(self._model, new_outlet_index, current_inlet_index)
                sucess = True
            
            case 'tail', _:
                # tail dropped on empty space
                link_index = payload.index
                link_source = self._delegate.linkSource(link_index)
                link_target = self._delegate.linkTarget(link_index)
                IsLinked = link_source and link_source.isValid() and link_target and link_target.isValid()
                if IsLinked:
                    self._delegate.removeLink(self._model, link_index)
                    sucsess = True

            case 'head', _:
                # head dropped on empty space
                link_index = payload.index
                assert link_index.isValid(), "Link index must be valid"
                IsLinked = self._delegate.linkSource(link_index).isValid() and self._delegate.linkTarget(link_index).isValid()
                if IsLinked:
                    self._delegate.removeLink(self._model, link_index)
                    sucsess =  True

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

            if self._delegate.itemType(self._linking_payload.index) == GraphItemType.LINK:
                link_widget = cast(LinkWidget, self.rowWidgetFromIndex(self._linking_payload.index))
                assert link_widget is not None, "Link widget must not be None"
                link_widget.updateLine()

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
            assert index

            match self._delegate.itemType(index):
                case GraphItemType.INLET:
                    if self.startLinking(Payload(index, 'inlet')):
                        return
                case GraphItemType.OUTLET:
                    if self.startLinking(Payload(index, 'outlet')):
                        return

                case GraphItemType.LINK:
                    # If the item is a link, determine which end to drag
                    def getClosestLinkEnd(link_index:QModelIndex, scene_pos:QPointF) -> Literal['head', 'tail']:
                        source_index = self._delegate.linkSource(link_index)
                        target_index = self._delegate.linkTarget(link_index)
                        if source_index and source_index.isValid() and target_index and target_index.isValid():
                            link_widget = cast(LinkWidget, self.rowWidgetFromIndex(link_index))
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
            self.finishLinking(self._linking_payload, drop_target)
            
        else:
            super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event:QMouseEvent):
        index = self.indexAt(QPoint(int(event.position().x()), int(event.position().y())))

        if not index.isValid():
            self._delegate.addNode(self._model, QModelIndex())
            # self._model.insertRows(0, 1, QModelIndex())
            return
            # return super().mouseDoubleClickEvent(event)
                
        def onEditingFinished(editor:QLineEdit, cell_widget:CellWidget, index:QModelIndex):
            self._delegate.setModelData(editor, self._model, index)
            cell_widget.setEditorWidget(None)  # Clear the editor widget
            editor.deleteLater()
            self._set_cell_data(index.row(), index.column(), index.parent())

        if cell_widget := self.cellFromIndex(index):
            editor = self._delegate.createEditor(self, None, index)
            assert editor.parent() is None, "Editor must not have a parent"
            cell_widget.setEditorWidget(editor)  # Clear any existing editor widget
            editor.setText(index.data(Qt.ItemDataRole.EditRole))
            editor.setFocus(Qt.FocusReason.MouseFocusReason)
            editor.editingFinished.connect(lambda editor = editor, cell_widget=cell_widget, index=index: onEditingFinished(editor, cell_widget, index) )
    
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
    #     payload = payloadFromMimeData(data)
        
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

