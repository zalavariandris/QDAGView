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

        ## State of the graph view
        self._state = GraphView.State.IDLE
        self._draft_link: QGraphicsLineItem | None = None
        self._payload: QModelIndex = QModelIndex()  # This will hold the index of the item being dragged or linked
        self._link_end: Literal['head', 'tail'] | None = None  # This will hold the end of the link being dragged

        # store model widget relations
        self._widgets: bidict[QPersistentModelIndex, BaseRowWidget] = bidict()
        self._cells: bidict[QPersistentModelIndex, CellWidget] = bidict()
        

        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setCacheMode(QGraphicsView.CacheModeFlag.CacheNone)
        self.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        scene = QGraphicsScene()
        scene.setSceneRect(QRectF(-9999, -9999, 9999 * 2, 9999 * 2))
        self.setScene(scene)
        self.setAcceptDrops(True)
        self._delegate = delegate if delegate else GraphDelegate()
    
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
                        parent_widget.addOutlet(widget)
                    case InletWidget():
                        parent_widget.addInlet(widget)
                    case _:
                        ...

            case InletWidget():
                match widget:
                    case LinkWidget():
                        widget.setParentItem(parent_widget)
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
                    case InletWidget():
                        parent_widget.removeInlet(widget)
                    case _:
                        widget.setParentItem(None)
                        scene.removeItem(widget)
            case InletWidget():
                match widget:
                    case LinkWidget():
                        widget.unlink()
                        widget.setParentItem(parent_widget)
                        scene.removeItem(widget)
                    case _:
                        widget.setParentItem(None)
                        scene.removeItem(widget)
            case _:
                raise ValueError(f"Unknown parent widget type: {type(parent_widget)}")

    def onRowsInserted(self, parent:QModelIndex, start:int, end:int):
        assert self._model, "Model must be set before handling rows inserted!"

        # def _make_child_widgets_recursive(parent_widget:QGraphicsItem|QGraphicsScene, parent:QModelIndex, start:int, end:int):
        #     """
        #     Create widgets for the given range of rows in the model.
        #     This is used to populate the graph view with nodes, inlets, outlets and links.
        #     """

        #     for row in range(start, end + 1):
        #         index = self._model.index(row, 0, parent)
        #         if not index.isValid():
        #             logger.warning(f"Invalid index at row {row} for parent {parent}")
        #             continue
                
        #         widget = self.createWidget(parent_widget, index)
        #         persistent_index = QPersistentModelIndex(index)
        #         assert persistent_index not in self._widgets, f"Widget for index {index} already exists in _widgets"
        #         self._widgets[persistent_index] = widget
        #         self._set_widget_data(index, 0)

        #         row_count = self._model.rowCount(index)
        #         if row_count > 0:
        #             _make_child_widgets_recursive(
        #                 parent_widget=widget, 
        #                 parent=index, 
        #                 start=0, 
        #                 end=row_count - 1
        #             )

        # parent_widget = self.widgetFromIndex(parent) if parent.isValid() else self.scene()
        # _make_child_widgets_recursive(
        #     parent_widget=parent_widget, 
        #     parent=parent, 
        #     start=start, 
        #     end=end
        # )

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
                    self._set_widget_data(cell_index.row(), col, cell_index.parent())

        make_child_widgets_bfs(parent, start, end)

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
                if widget := self.rowWidgetFromIndex(index):
                    if isinstance(widget, LinkWidget):
                        widget.link(
                            self.rowWidgetFromIndex(self._delegate.linkSource(index)),
                            widget._target
                        )
        
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
        scene.selectionChanged.connect(self.updateSelectionModel)

    def selectionModel(self) -> QItemSelectionModel | None:
        """
        Get the current selection model for the graph view.
        This is used to synchronize the selection of nodes in the graph view
        with the selection model.
        """
        return self._selection
    
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

    def updateSelectionModel(self):
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

    def _set_widget_data(self, row:int, column:int, parent:QModelIndex|QPersistentModelIndex, roles:list=[]):
        """Set the data for a node widget."""
        index = self._model.index(row, column, parent)
        assert index.isValid(), "Index must be valid"

        if cell_widget:= self.cellFromIndex(index):
            cell_widget.setDisplayText(index.data(Qt.ItemDataRole.DisplayRole))

    ## Linking
    def canLink(self, source:QModelIndex, target:QModelIndex)->bool:
        """
        Check if linking is possible between the source and target indexes.
        This is used to determine if a drag-and-drop operation can be initiated.
        """
        if not self._model:
            # No model set, cannot link
            return False

        if source.parent() == target.parent():
            # Cannot link items in the same parent
            return False
        
        source_type = self._delegate.itemType(source)
        target_type = self._delegate.itemType(target)
 
        if  (source_type, target_type) == (GraphItemType.INLET, GraphItemType.OUTLET) or \
            (source_type, target_type) == (GraphItemType.OUTLET, GraphItemType.INLET):
            # Both source and target must be either inlet or outlet
            return True
        
        return False

    def startLinking(self, index:QModelIndex|QPersistentModelIndex, end:Literal['head', 'tail']='tail')->bool:
        """
        Start linking from the given index.
        This is used to initiate a drag-and-drop operation for linking.
        return True if the drag operation was started, False otherwise.
        """

        index_type = self._delegate.itemType(index)
        if index_type not in (GraphItemType.INLET, GraphItemType.OUTLET, GraphItemType.LINK):
            # Only inlets, outlets and links can be dragged
            return False
        
        if index_type in (GraphItemType.OUTLET, GraphItemType.INLET):
            # create a draft link line
            if not self._draft_link:
                self._draft_link = QGraphicsLineItem()
                self._draft_link.setPen(QPen(self.palette().text(), 1))
                self.scene().addItem(self._draft_link)
        
        mime = self._createMimeData(index, end=end)
        if mime is None:
            return False
        
        drag = QDrag(self)
        drag.setMimeData(mime)

        # Execute drag
        try:
            action = drag.exec(Qt.DropAction.LinkAction)
        except Exception as err:
            traceback.print_exc()
        return True

    def updateLinking(self, data:QMimeData, pos:QPoint):
        """
        Update the linking position
        """
        pos = QPoint(int(pos.x()), int(pos.y())) # defense against passing QPointF
        
        # Determine the source and target types
        target_index = self.rowAt(pos)  # Ensure the index is updated
        drop_target_type = self._delegate.itemType(target_index)

        drag_source_type:Literal['inlet', 'outlet', 'head', 'tail']
        if data.hasFormat(GraphMimeType.OutletData):
            drag_source_type = "outlet"
        elif data.hasFormat(GraphMimeType.InletData):
            drag_source_type = "inlet"
        elif data.hasFormat(GraphMimeType.LinkTailData):
            drag_source_type = "tail"
        elif data.hasFormat(GraphMimeType.LinkHeadData):
            drag_source_type = "head"

        # find the relevant widgets
        outlet_widget, inlet_widget, link_widget = None, None, None
        match drag_source_type, drop_target_type:
            case 'outlet', GraphItemType.INLET:
                outlet_widget = self.rowWidgetFromIndex( self._parseMimeData(data) )
                inlet_widget = self.rowWidgetFromIndex(target_index)
                link_widget = self._draft_link

            case 'inlet', GraphItemType.OUTLET:
                # inlet dragged over outlet
                outlet_widget = self.rowWidgetFromIndex(target_index)
                inlet_widget = self.rowWidgetFromIndex( self._parseMimeData(data) )
                link_widget = self._draft_link

            case 'outlet', _:
                # outlet dragged over empty space
                outlet_widget = self.rowWidgetFromIndex( self._parseMimeData(data) )
                link_widget = self._draft_link

            case 'inlet', _:
                # inlet dragged over empty space
                inlet_widget = self.rowWidgetFromIndex( self._parseMimeData(data) )
                link_widget = self._draft_link

            case 'head', GraphItemType.INLET:
                # link head dragged over inlet
                link_index = self._parseMimeData(data)
                outlet_widget = self.rowWidgetFromIndex( self._delegate.linkSource(link_index) )
                inlet_widget = self.rowWidgetFromIndex(target_index)
                link_widget = self.rowWidgetFromIndex(link_index)

            case 'tail', GraphItemType.OUTLET:
                # link tail dragged over outlet
                link_index = self._parseMimeData(data)
                outlet_widget = self.rowWidgetFromIndex(target_index)
                inlet_widget = self.rowWidgetFromIndex( self._delegate.linkTarget(link_index) )
                link_widget = self.rowWidgetFromIndex(link_index)

            case 'head', _:
                # link head dragged over empty space
                link_index = self._parseMimeData(data)
                outlet_widget = self.rowWidgetFromIndex( self._delegate.linkSource(link_index) )
                link_widget = self.rowWidgetFromIndex(link_index)

            case 'tail', _:
                # link tail dragged over empty space
                link_index = self._parseMimeData(data)
                inlet_widget = self.rowWidgetFromIndex( self._delegate.linkTarget(link_index) )
                link_widget = self.rowWidgetFromIndex(link_index)

            case _:
                # No valid drag source or drop target, do nothing
                return

        if outlet_widget and inlet_widget:
            line = makeLineBetweenShapes(outlet_widget, inlet_widget)
            line = QLineF(link_widget.mapFromScene(line.p1()), link_widget.mapFromScene(line.p2()))
        elif outlet_widget:
            line = makeLineBetweenShapes(outlet_widget, self.mapToScene(pos))
            line = QLineF(link_widget.mapFromScene(line.p1()), link_widget.mapFromScene(line.p2()))
        elif inlet_widget:
            line = makeLineBetweenShapes(self.mapToScene(pos), inlet_widget)
            line = QLineF(link_widget.mapFromScene(line.p1()), link_widget.mapFromScene(line.p2()))

        link_widget.setLine(line)

    def finishLinking(self, data:QMimeData, target_index:QModelIndex)->bool:
        """
        Finish linking operation.
        """
        
        # Determine the drop target type
        drop_target_type = self._delegate.itemType(target_index)

        # Determine the drag source type based on the mime data
        drag_source_type:Literal['inlet', 'outlet', 'head', 'tail']
        if data.hasFormat(GraphMimeType.OutletData):
            drag_source_type = "outlet"
        elif data.hasFormat(GraphMimeType.InletData):
            drag_source_type = "inlet"
        elif data.hasFormat(GraphMimeType.LinkTailData):
            drag_source_type = "tail"
        elif data.hasFormat(GraphMimeType.LinkHeadData):
            drag_source_type = "head"

        # Perform the linking based on the drag source and drop target types
        # return True if the linking was successful, False otherwise
        success = False
        match drag_source_type, drop_target_type:
            case "outlet", GraphItemType.INLET:
                # outlet dropped on inlet
                outlet_index = self._parseMimeData(data)
                assert outlet_index.isValid(), "Outlet index must be valid"
                inlet_index = target_index
                self._delegate.addLink(self._model, outlet_index, inlet_index)
                success = True

            case "inlet", GraphItemType.OUTLET:
                # inlet dropped on outlet
                inlet_index = self._parseMimeData(data)
                assert inlet_index.isValid(), "Inlet index must be valid"
                outlet_index = target_index
                self._delegate.addLink(self._model, outlet_index, inlet_index)
                success = True

            case "head", GraphItemType.INLET:
                # link head dropped on inlet
                link_index = self._parseMimeData(data)
                new_inlet_index = target_index
                current_outlet_index = self._delegate.linkSource(link_index)
                self._delegate.removeLink(self._model, link_index)
                self._delegate.addLink(self._model, current_outlet_index, new_inlet_index)
                success = True

            case "tail", GraphItemType.OUTLET:
                # link tail dropped on outlet
                link_index = self._parseMimeData(data)
                new_outlet_index = target_index
                current_inlet_index = self._delegate.linkTarget(link_index)
                self._delegate.removeLink(self._model, link_index)
                self._delegate.addLink(self._model, new_outlet_index, current_inlet_index)
                sucess = True
            
            case 'tail', _:
                # tail dropped on empty space
                link_index = self._parseMimeData(data)
                link_source = self._delegate.linkSource(link_index)
                link_target = self._delegate.linkTarget(link_index)
                IsLinked = link_source and link_source.isValid() and link_target and link_target.isValid()
                if IsLinked:
                    self._delegate.removeLink(self._model, link_index)
                    sucsess = True

            case 'head', _:
                # head dropped on empty space
                link_index = self._parseMimeData(data)
                assert link_index.isValid(), "Link index must be valid"
                IsLinked = self._delegate.linkSource(link_index).isValid() and self._delegate.linkTarget(link_index).isValid()
                if IsLinked:
                    self._delegate.removeLink(self._model, link_index)
                    sucsess =  True

        # cleanup DraftLink
        if self._draft_link:
            self.scene().removeItem(self._draft_link)
            self._draft_link = None

        return success

    def cancelLinking(self):
        """
        Cancel the linking operation.
        This is used to remove the draft link and reset the state.
        """
        if self._draft_link:
            scene = self.scene()
            assert scene is not None
            scene.removeItem(self._draft_link)
            self._draft_link = None

    ## Handle drag and drop    
    def _parseMimeData(self, mime:QMimeData) -> QModelIndex | None:
        """
        Parse the mime data to get the original index.
        This is used to get the original index from the mime data.
        """
        def parseIndexPath(path:str) -> QModelIndex:
            """
            Parse a path string to a persistent model index.
            This is used to convert the path string back to a QModelIndex.
            """
            path = list(map(int, path.split("/")))

            idx = self._model.index(path[0], 0, QModelIndex())
            for row in path[1:]:
                idx = self._model.index(row, 0, idx)
            return idx
        
        if mime.hasFormat(GraphMimeType.InletData):
            # Inlet data
            index_path = mime.data(GraphMimeType.InletData).data().decode("utf-8")

        elif mime.hasFormat(GraphMimeType.OutletData):
            # Outlet data
            index_path = mime.data(GraphMimeType.OutletData).data().decode("utf-8")

        elif mime.hasFormat(GraphMimeType.LinkTailData):
            # Link tail data
            index_path = mime.data(GraphMimeType.LinkTailData).data().decode("utf-8")

        elif mime.hasFormat(GraphMimeType.LinkHeadData):
            # Link head data
            index_path = mime.data(GraphMimeType.LinkHeadData).data().decode("utf-8")
        else:
            # No valid mime type found
            return None

        index = parseIndexPath(index_path)
        return index

    def _createMimeData(self, index, end:Literal['head', 'tail']='tail')-> QMimeData | None:
        mime = QMimeData()

        # Convert index to path string
        def indexToPath(index:QModelIndex|QPersistentModelIndex) -> str:
            path = []
            idx = index
            while idx.isValid():
                path.append(idx.row())
                idx = idx.parent()
            return "/".join(map(str, reversed(path)))

        def indexToMimeType(index:QModelIndex|QPersistentModelIndex) -> GraphMimeType:
            """
            Convert the index to a mime type based on the item type.
            This is used to determine the mime type for drag-and-drop operations.
            """
            item_type = self._delegate.itemType(index)
            match item_type:
                case GraphItemType.INLET:
                    return GraphMimeType.InletData
                case GraphItemType.OUTLET:
                    return GraphMimeType.OutletData
                case GraphItemType.LINK:
                    if end == 'head':
                        return GraphMimeType.LinkHeadData
                    else:
                        return GraphMimeType.LinkTailData
                case _:
                    raise ValueError(f"Unknown item type: {item_type}")
 
        # mime type
        mime_type = indexToMimeType(index)
            
        if mime_type is None:
            return None
        
        index_path = indexToPath(index)
        print(f"Creating mime data for index: {index}, path: {index_path}, type: {mime_type}")
        mime.setData(mime_type, index_path.encode("utf-8"))
        return mime
    
    def _canDropMimeData(self, data:QMimeData, action:Qt.DropAction, drop_target:QModelIndex|QPersistentModelIndex) -> bool:
        """
        Check if the mime data can be dropped on the graph view.
        This is used to determine if the drag-and-drop operation is valid.
        """
        drop_target_type = self._delegate.itemType(drop_target)

        if data.hasFormat(GraphMimeType.OutletData):
            return True
        
        elif data.hasFormat(GraphMimeType.InletData):
            return True
        
        elif data.hasFormat(GraphMimeType.LinkTailData):
            return True
        
        elif data.hasFormat(GraphMimeType.LinkHeadData):
            return True
        
        return False

    def _dropMimeData(self, data:QMimeData, action:Qt.DropAction, drop_target:QModelIndex|QPersistentModelIndex) -> bool:
        drop_target = QModelIndex(drop_target)
        return self.finishLinking(data, drop_target)

    ## Handle mouse events
    def mousePressEvent(self, event):
        """
        By default start linking from the item under the mouse cursor.
        if starting a link is not possible, fallback to the QGraphicsView behavior.
        """

        if self._state == GraphView.State.IDLE:
            pos = event.position()
            index = self.rowAt(QPoint(int(pos.x()), int(pos.y())))  # Ensure the index is updated
            assert index

            match self._delegate.itemType(index):
                case GraphItemType.INLET | GraphItemType.OUTLET:
                    if self.startLinking(index):
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
    
                    if self.startLinking(index, end=link_end):
                        return
                    
        super().mousePressEvent(event)
    
    def mouseDoubleClickEvent(self, event:QMouseEvent):
        index = self.rowAt(QPoint(int(event.position().x()), int(event.position().y())))

        if not index.isValid():
            return super().mouseDoubleClickEvent(event)
                
        def onEditingFinished(editor:QLineEdit, cell_widget:CellWidget, index:QModelIndex):
            self._delegate.setModelData(editor, self._model, index)
            cell_widget.setEditorWidget(None)  # Clear the editor widget
            editor.deleteLater()
            self._set_widget_data(index.row(), index.column(), index.parent())


        if cell_widget := self.cellFromIndex(index):
            editor = self._delegate.createEditor(self, None, index)
            assert editor.parent() is None, "Editor must not have a parent"
            cell_widget.setEditorWidget(editor)  # Clear any existing editor widget
            editor.setText(index.data(Qt.ItemDataRole.EditRole))
            editor.setFocus(Qt.FocusReason.MouseFocusReason)
            editor.editingFinished.connect(lambda editor = editor, cell_widget=cell_widget, index=index: onEditingFinished(editor, cell_widget, index) )
       
    ## Handle drag and drop events
    def dragEnterEvent(self, event)->None:
        if event.mimeData().hasFormat(GraphMimeType.InletData) or event.mimeData().hasFormat(GraphMimeType.OutletData):
            # Create a draft link if the mime data is for inlets or outlets
            
            event.acceptProposedAction()

        if event.mimeData().hasFormat(GraphMimeType.LinkHeadData) or event.mimeData().hasFormat(GraphMimeType.LinkTailData):
            # Create a draft link if the mime data is for link heads or tails
            event.acceptProposedAction()

    def dragMoveEvent(self, event)->None:
        """Handle drag move events to update draft link position"""
        pos = event.position()
        pos = QPoint(int(pos.x()), int(pos.y()))  # Ensure pos is an integer QPoint
        self.updateLinking(event.mimeData(), pos)
        return
            
    def dropEvent(self, event: QDropEvent) -> None:
        pos = event.position()
        drop_target = self.rowAt(QPoint(int(pos.x()), int(pos.y())))  # Ensure the index is updated

        # TODO: check for drag action
        # match event.proposedAction():
        #     case Qt.DropAction.CopyAction:
        #         ...
        #     case Qt.DropAction.MoveAction:
        #         ...
        #     case Qt.DropAction.LinkAction:
        #         ...
        #     case Qt.DropAction.IgnoreAction:
        #         ...
        
        if self.finishLinking(event.mimeData(), drop_target):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self._cleanupDraftLink()  # Cleanup draft link if it exists
        # super().dragLeaveEvent(event)
        # self._cleanupDraftLink()


class CellWidget(QGraphicsProxyWidget):
    def __init__(self, parent: QGraphicsItem | None = None):
        super().__init__(parent=parent)
        self._label = QLabel("")
        # self._label.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._label.setStyleSheet("background: orange;")
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # self._label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setWidget(self._label)
        # self.setAutoFillBackground(False)
        
        # Make CellWidget transparent to drag events so parent can handle them
        # self.setAcceptDrops(False)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)

    def setEditorWidget(self, editor: QWidget | None):
        if editor is None:
            editor = self._label
        else:
            # Ensure the editor is not parented elsewhere
            if editor.parent() is not None:
                editor.setParent(None)
        self.setWidget(editor)

    def displayText(self):
        label = self.widget()  # Ensure the widget is created
        return label.text() if label else ""

    def setDisplayText(self, text:str):
        label = self.widget()  # Ensure the widget is created
        label.setText(text)


class BaseRowWidget(QGraphicsWidget):
    def __init__(self, parent: QGraphicsItem | None = None):
        super().__init__(parent=parent)
        # create layout
        layout = QGraphicsLinearLayout(Qt.Orientation.Vertical)
        self.setLayout(layout)
        layout.updateGeometry()        
        
    def insertCell(self, pos:int, cell:CellWidget):
        a = list()
        layout = cast(QGraphicsLinearLayout, self.layout())
        layout.insertItem(pos, cell)

    def removeCell(self, cell:CellWidget):
        layout = cast(QGraphicsLinearLayout, self.layout())
        layout.removeItem(cell)


class PortWidget(BaseRowWidget):
    def __init__(self, parent: QGraphicsItem | None = None):
        super().__init__(parent=parent)
        self._links:List[LinkWidget] = []
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsScenePositionChanges, True)

    def itemChange(self, change, value):
        match change:
            case QGraphicsItem.GraphicsItemChange.ItemScenePositionHasChanged:
                for link in self._links:
                    link.updateLine()
                    
        return super().itemChange(change, value)

    def paint(self, painter, option, /, widget = ...):
        painter.setBrush(self.palette().alternateBase())
        painter.drawRect(option.rect)


class InletWidget(PortWidget):
    def __init__(self, parent: QGraphicsItem | None = None):
        super().__init__(parent=parent)
        self.setAcceptDrops(True)

    def paint(self, painter:QPainter, option, /, widget:QWidget|None = None):
        painter.setBrush(QColor("lightblue"))
        painter.drawRect(option.rect)
    

class OutletWidget(PortWidget):
    def __init__(self, parent: QGraphicsItem | None = None):
        super().__init__(parent=parent)
        self.setAcceptDrops(True)

    def paint(self, painter, option, /, widget:QWidget|None = None):
        painter.setBrush(QColor("purple"))
        painter.drawRect(option.rect)


class NodeWidget(BaseRowWidget):
    def __init__(self, parent: QGraphicsItem | None = None):
        super().__init__(parent=parent)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)

    def addInlet(self, inlet:InletWidget):
        layout = cast(QGraphicsLinearLayout, self.layout())
        layout.addItem(inlet)

    def removeInlet(self, inlet:InletWidget):
        layout = cast(QGraphicsLinearLayout, self.layout())
        layout.removeItem(inlet)

    def addOutlet(self, outlet:OutletWidget):
        layout = cast(QGraphicsLinearLayout, self.layout())
        layout.addItem(outlet)

    def removeOutlet(self, outlet:OutletWidget):
        layout = cast(QGraphicsLinearLayout, self.layout())
        layout.removeItem(outlet)

    def paint(self, painter: QPainter, option: QStyleOption, widget=None):
        rect = option.rect       
        painter.setBrush(self.palette().alternateBase())
        if self.isSelected():
            painter.setBrush(self.palette().highlight())
        painter.drawRoundedRect(rect, 6, 6)

        
class LinkWidget(BaseRowWidget):
    def __init__(self, parent: QGraphicsItem | None = None):
        super().__init__(parent=parent)
        # self.setZValue(-1)  # Ensure links are drawn below nodes
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self._line = QLineF(0, 0, 100, 100)
        self._label = QLabel("Link")
        self._data_column = QGraphicsWidget(parent=self)
        self._data_column.setLayout(QGraphicsLinearLayout(Qt.Orientation.Vertical))

        self._source: QGraphicsItem | None = None
        self._target: QGraphicsItem | None = None
        self.setAcceptHoverEvents(True)

    def line(self)->QLineF:
        """Get the line of the link widget."""
        return self._line
    
    def setLine(self, line:QLineF):
        """Set the line of the link widget."""
        
        self.prepareGeometryChange()
        self._line = line

        self._data_column.layout().setGeometry(
            QRectF(self._line.p1(), self._line.p2())
            .adjusted(-5, -5, 5, 5)
            .normalized()
        )

        self.update()

    def boundingRect(self):
        _ = QRectF(self._line.p1(), self._line.p2())
        _ = _.normalized()
        _ = _.adjusted(-5,-5,5,5)
        return _
    
    def shape(self)->QPainterPath:
        path = QPainterPath()
        path.moveTo(self._line.p1())
        path.lineTo(self._line.p2())
        stroker = QPainterPathStroker()
        stroker.setWidth(4)
        return stroker.createStroke(path)
    
    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget=None):

        if self.isSelected():
            painter.setBrush(self.palette().accent())
        elif option.state & QStyle.StateFlag.State_MouseOver:
            painter.setBrush(Qt.red)
        else:
            painter.setBrush(self.palette().text())
        painter.setPen(Qt.PenStyle.NoPen)
        arrow = makeArrowShape(self._line, 2)
        painter.drawPath(arrow)

    def link(self, source:QGraphicsItem|None, target:QGraphicsItem|None):
        """Link this widget to a source and target item."""
        self.unlink()  # Unlink any existing connections
        self._source = source
        self._target = target
        if source:
            source._links.append(self)
        if target:
            target._links.append(self)
        self.updateLine()
        self.update()

    def unlink(self):
        """Unlink this widget from its source and target items."""
        if self._source:
            self._source._links.remove(self)
            self._source = None
        if self._target:
            self._target._links.remove(self)
            self._target = None
        self.updateLine()
        self.update()

    def updateLine(self):
        if self._source and self._target:
            line = makeLineBetweenShapes(self._source, self._target)
            line = QLineF(self.mapFromScene(line.p1()), self.mapFromScene(line.p2()))
            self.setLine(line)

        elif self._source:
            source_center = getShapeCenter(self._source)
            source_size = self._source.boundingRect().size()
            origin = QPointF(source_center.x() - source_size.width()/2, source_center.y() - source_size.height()/2)+QPointF(24,24)
            line = makeLineToShape(origin, self._source)
            line = QLineF(self.mapFromScene(line.p1()), self.mapFromScene(line.p2()))
            line = QLineF(line.p2(), line.p1())  # Reverse the line direction
            self.setLine(line)

        elif self._target:
            target_center = getShapeCenter(self._target)
            target_size = self._target.boundingRect().size()
            origin = QPointF(target_center.x() - target_size.width()/2, target_center.y() - target_size.height()/2)-QPointF(24,24)
            line = makeLineToShape(origin, self._target)
            line = QLineF(self.mapFromScene(line.p1()), self.mapFromScene(line.p2()))
            self.setLine(line)
        else:
            ...
