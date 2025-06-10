#####################
# The Network Scene #
#####################

#
# A Graph view that directly connects to QStandardItemModel
#
import traceback

from enum import Enum
from typing import *
from PySide6.QtGui import *
from PySide6.QtCore import *
from PySide6.QtWidgets import *

from collections import defaultdict
from bidict import bidict

from utils import group_consecutive_numbers
from utils.geo import makeLineBetweenShapes, makeLineToShape
# from pylive.utils.geo import makeLineBetweenShapes, makeLineToShape
# from pylive.utils.qt import distribute_items_horizontal
# from pylive.utils.unique import make_unique_name
# from pylive.utils.diff import diff_set

import logging
from enum import StrEnum, IntEnum
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


from core import GraphDataRole, GraphItemType, GraphMimeData


class GraphView(QGraphicsView):
    class State(Enum):
        IDLE = "IDLE"
        LINKING = "LINKING"
        
    nodesLinked = Signal(QModelIndex, QModelIndex, str, str)
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent=parent)
        self.setAcceptDrops(True)
        self._model:QAbstractItemModel | None = None
        self._selection: QItemSelectionModel | None = None
        self._model_connections = []
        self._selection_connections = []

        # store model widget relations
        # map item index to widgets
        self._row_widgets: bidict[QPersistentModelIndex, BaseRowWidget] = bidict()
        self._cell_widgets: bidict[QPersistentModelIndex, CellWidget] = bidict()

        self._link_source: dict[QPersistentModelIndex, QPersistentModelIndex] = defaultdict(list)
        self._out_links: dict[QPersistentModelIndex, List[QPersistentModelIndex]] = defaultdict(list)
        
        # self._link_widgets: bidict[tuple[QPersistentModelIndex, QPersistentModelIndex], LinkItem] = bidict()
        self._draft_link: QGraphicsLineItem | None = None
        self._state = GraphView.State.IDLE
        self.setupUI()
        self.setAcceptDrops(True)

    def indexFromWidget(self, widget:QGraphicsItem) -> QModelIndex:
        """
        Get the index of the widget in the model.
        This is used to identify the outlet in the model.
        """
        return QModelIndex(self._row_widgets.inverse[widget])
    
    def widgetFromIndex(self, index:QModelIndex) -> QGraphicsItem:
        """
        Get the widget from the index.
        This is used to identify the outlet in the model.
        """
        return self._row_widgets[QPersistentModelIndex(index)]

    def _createDraftLink(self):
        """Safely create draft link with state tracking"""
        assert self._draft_link is None
            
        self._draft_link = QGraphicsLineItem()
        self._draft_link.setPen(QPen(self.palette().text(), 1))
        self.scene().addItem(self._draft_link)
 
    def _cleanupDraftLink(self):
        """Safely cleanup draft link"""
        assert self._draft_link
        self.scene().removeItem(self._draft_link)
        self._draft_link = None

    def dragEnterEvent(self, event)->None:
        print("GraphScene DragEnterEvent", event.mimeData().formats())
        super().dragEnterEvent(event)  # Let the scene handle the event normally, which will forward to widgets
        self._createDraftLink()
        if not event.isAccepted():
            event.acceptProposedAction()
        # event.acceptProposedAction()
    
    def dragMoveEvent(self, event)->None:
        
        print("dragMoveEvent", event.mimeData().formats())
        super().dragMoveEvent(event) # sLet the scene handle the event normally, which will forward to widgets
        if event.isAccepted():
            return

        if event.mimeData().hasFormat(GraphMimeData.OutletData):
            pass
            # source_node, outlet = event.mimeData().data(GraphMimeData.OutletData).toStdString().split("/")
            # source_item = self._node_widgets[source_node]._outlet_widgets[outlet]
            # if self._draft_link:
            #     line = self._draft_link.line()
            #     mouse_scene_pos = self.mapToScene(event.position().toPoint())
            #     line = makeLineBetweenShapes(source_item, mouse_scene_pos)
            #     self._draft_link.setLine(line)


        if event.mimeData().hasFormat(GraphMimeData.InletData):
            node_row, inlet_row = event.mimeData().data(GraphMimeData.InletData).toStdString().split("/")
            node_index = self._model.index(int(node_row), 0, QModelIndex())
            inlet_index = self._model.index(int(inlet_row), 0, node_index)
            target_item = self._row_widgets[QPersistentModelIndex(inlet_index)]
            if self._draft_link:
                line = self._draft_link.line()
                mouse_scene_pos = self.mapToScene(event.position().toPoint())
                line = makeLineBetweenShapes(mouse_scene_pos, target_item)
                self._draft_link.setLine(line)

        if event.mimeData().hasFormat(GraphMimeData.LinkSourceData):
            pass
            # link_key = event.mimeData().data(GraphMimeData.LinkSourceData).toStdString().split("/")
            # source, target, outlet, inlet = link_key
            # source_item = self._node_widgets[source]._outlet_widgets[outlet]
            # target_item = self._node_widgets[target]._inlet_widgets[inlet]

            # if self._draft_link:
            #     line = self._draft_link.line()
            #     mouse_scene_pos = self.mapToScene(event.position().toPoint())
            #     line = makeLineBetweenShapes(source_item, mouse_scene_pos)
            #     self._draft_link.setLine(line)
            #     event.acceptProposedAction() # Todo: accept delete action

        if event.mimeData().hasFormat(GraphMimeData.LinkTargetData):
            pass
            # link_key = event.mimeData().data(GraphMimeData.LinkTargetData).toStdString().split("/")
            # source, target, outlet, inlet = link_key
            # source_item = self._node_widgets[source]._outlet_widgets[outlet]
            # target_item = self._node_widgets[target]._inlet_widgets[inlet]

            # if self._draft_link:
            #     line = self._draft_link.line()
            #     mouse_scene_pos = self.mapToScene(event.position().toPoint())
            #     line = makeLineBetweenShapes(mouse_scene_pos, target_item)
            #     self._draft_link.setLine(line)
            #     event.acceptProposedAction() # Todo: accept delete action

    def dropEvent(self, event: QDropEvent) -> None:
        super().dropEvent(event)
        print("GraphScene DropEvent", event.mimeData().formats())
        self._cleanupDraftLink()
    #     # if event.isAccepted():
    #     #     return

    #     if event.mimeData().hasFormat(GraphMimeData.LinkSourceData):
    #         assert self._model
    #         link_key = event.mimeData().data(GraphMimeData.LinkSourceData).toStdString().split("/")
    #         source, target, outlet, inlet = link_key
    #         self._model.unlinkNodes(source, target, outlet, inlet)

    #     if event.mimeData().hasFormat(GraphMimeData.LinkTargetData):
    #         assert self._model
    #         link_key = event.mimeData().data(GraphMimeData.LinkTargetData).toStdString().split("/")
    #         source, target, outlet, inlet = link_key
    #         self._model.unlinkNodes(source, target, outlet, inlet)

    def dragLeaveEvent(self, event):
        print("GraphScene DragLeaveEvent")
        super().dragLeaveEvent(event)
        self._cleanupDraftLink()

    def setupUI(self):
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setCacheMode(QGraphicsView.CacheModeFlag.CacheNone)
        self.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        scene = QGraphicsScene()
        scene.setSceneRect(QRectF(-9999, -9999, 9999 * 2, 9999 * 2))
        self.setScene(scene)
        # layout = QVBoxLayout()
        # self.setLayout(layout)

        scene.selectionChanged.connect(self.updateSelectionModel)

    def updateSelectionModel(self):
        if self._model and self._selection:
            # get currently selected widgets
            selected_widgets = self.scene().selectedItems()

            # map widgets to QModelIndexes
            selected_indexes = map(lambda widget: self._row_widgets.inverse.get(widget, None), selected_widgets)
            selected_indexes = filter(lambda idx: idx is not None and idx.isValid(), selected_indexes)

            # group indexes by parents
            indexes_by_parent = defaultdict(list)
            for index in selected_indexes:
                parent = index.parent()
                indexes_by_parent[parent].append(index)

            # create QItemSelection
            item_selection = QItemSelection()
            for parent, indexes in indexes_by_parent.items():
                all_rows = sorted(index.row() for index in indexes)
                ranges = group_consecutive_numbers(all_rows)

                for row_range in ranges:
                    top_left = self._model.index(row_range.start, 0, parent)
                    bottom_right = self._model.index(row_range.stop - 1, self._model.columnCount(parent) - 1, parent)
                    selection_range = QItemSelectionRange(top_left, bottom_right)
                    item_selection.append(selection_range)

            # perform selection on model
            self._selection.select(item_selection, QItemSelectionModel.SelectionFlag.ClearAndSelect)

    @Slot(QItemSelection, QItemSelection)
    def onSelectionChanged(self, selected:QItemSelection, deselected:QItemSelection):
        """
        Handle selection changes in the selection model.
        This updates the selection in the graph view.
        """
        print(f"onSelectionChanged: {selected}, {deselected}")
        assert self._selection, "Selection model must be set before handling selection changes!"
        assert self._model, "Model must be set before handling selection changes!"

        scene = self.scene()
        scene.blockSignals(True)
        for index in deselected.indexes():
            widget = self._row_widgets[QPersistentModelIndex(index.siblingAtColumn(0))]
            widget.setSelected(False)
            # widget.update()

        for index in selected.indexes():
            widget = self._row_widgets[QPersistentModelIndex(index.siblingAtColumn(0))]
            widget.setSelected(True)
            # widget.update()
        scene.blockSignals(False)

    def setModel(self, model:QAbstractItemModel):
        if self._model:
            for signal, slot in self._model_connections:
                signal.disconnect(slot)
            self._model_connections = []

        assert isinstance(model, QAbstractItemModel)
 
        if model:
            self._model_connections = [
                (model.dataChanged, self.onDataChanged),
                (model.rowsInserted, self.onRowsInserted),
                (model.rowsAboutToBeRemoved, self.onRowsAboutToBeRemoved)
            ]
            for signal, slot in self._model_connections:
                signal.connect(slot)

        self._model = model

        # populate initial scene
        ## clear
        self.scene().clear()
        self._row_widgets.clear()
        self._cell_widgets.clear()
        self._out_links.clear()
        self.addRowWidgets(QModelIndex())

    def onWidgetPositionChanged(self, widget:QGraphicsItem):
        """handle widget position change, and update connected links"""
        if index := self._row_widgets.inverse.get(widget, None):
            # incoming links
            for child_row in range(self._model.rowCount(index)):
                if self.itemType(child_row, index) == GraphItemType.LINK:
                    self.updateLinkGeometry(child_row, index)

            # outgoing links
            if links:=self._out_links.get(index):
                for link_index in links:
                    self.updateLinkGeometry(link_index.row(), link_index.parent())

    def updateLinkGeometry(self, row:int, parent:QModelIndex):
        """update link widget position associated with the qmodelindex"""
        print("update link geometry")
        link_index = self._model.index(row, 0, parent)
        source = self._model.data(link_index, GraphDataRole.SourceRole)
        target = link_index.parent()

        if link_widget:=self._row_widgets.get(QPersistentModelIndex(link_index)):
            source_widget = self._row_widgets.get(QPersistentModelIndex(source))
            target_widget = self._row_widgets.get(QPersistentModelIndex(target))
            link_widget = cast(LinkWidget, link_widget)
            link_widget.updateLine(source_widget, target_widget)

    def model(self) -> QAbstractItemModel | None:
        return self._model
    
    def setSelectionModel(self, selection: QItemSelectionModel):
        """
        Set the selection model for the graph view.
        This is used to synchronize the selection of nodes in the graph view
        with the selection model.
        """
        assert isinstance(selection, QItemSelectionModel)
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

    def selectionModel(self) -> QItemSelectionModel | None:
        """
        Get the current selection model for the graph view.
        This is used to synchronize the selection of nodes in the graph view
        with the selection model.
        """
        return self._selection
    
    def addRowWidgets(self, *root:QModelIndex):
        # first pass: Breadth-first search: collect each row recursively
        def children(index:QModelIndex):
            for row in range(self._model.rowCount(parent=index)):
                yield self._model.index(row, 0, index) 

        queue:List[QModelIndex] = [*root]
        indexes = list()
        while queue:
            index = queue.pop()
            indexes.append(index)
            for child in children(index):
                queue.append(child)

        # second pass: create nodes and inlets hiearchy
        for index in indexes:
            if not index.isValid():
                continue
            row, parent = index.row(), index.parent()
            row_kind = self.itemType(row, parent)
            match row_kind:
                case GraphItemType.NODE:
                    self._add_node_widget(row, parent)
                case GraphItemType.INLET:
                    self._add_inlet_widget(row, parent)
                case GraphItemType.OUTLET:
                    self._add_outlet_widget(row, parent)
                case GraphItemType.LINK:
                    pass
                case _:
                    raise NotImplementedError(f"Row kind {row_kind} is not implemented!")
        
        # third pass: create the links
        for index in indexes:
            if not index.isValid():
                continue
            row, parent = index.row(), index.parent()
            row_kind = self.itemType(row, parent)
            match row_kind:
                case None:
                    pass
                case GraphItemType.NODE:
                    pass
                case GraphItemType.INLET:
                    pass
                case GraphItemType.OUTLET:
                    pass
                case GraphItemType.LINK:
                    
                    link_index = QPersistentModelIndex(self._model.index(row, 0, parent))
                    source_index = link_index.data(GraphDataRole.SourceRole)
                    self._out_links[source_index].append(link_index)
                    self._link_source[link_index] = source_index
                    self._add_link_widget(row, parent)
                    self.updateLinkGeometry(link_index.row(), link_index.parent())
                case _:
                    raise NotImplementedError(f"Row kind {row_kind} is not implemented!")

    def removeRowWidgets(self, *root:QModelIndex):
        # first pass: collect each row recursively
        def children(index:QModelIndex):
            for row in range(self._model.rowCount(parent=index)):
                yield self._model.index(row, 0, index) 

        # Breadth-first search
        queue:List[QModelIndex] = [*root]
        bfs_indexes = list()
        while queue:
            index = queue.pop()
            bfs_indexes.append(index)
            for child in children(index):
                queue.append(child)

        # remove links first
        for index in filter(lambda idx: self.itemType(idx.row(), idx.parent()) == GraphItemType.LINK, bfs_indexes):
            self._remove_link_widget(index.row(), index.parent())

        # remove widgets reversed depth order
        for index in filter(lambda idx: self.itemType(idx.row(), idx.parent()) != GraphItemType.LINK, reversed(bfs_indexes) ):
            row, parent = index.row(), index.parent()
            row_kind = self.itemType(row, parent)
            match row_kind:

                case None:
                    pass
                case GraphItemType.NODE:
                    self._remove_node_widget(row, parent)
                case GraphItemType.INLET:
                    self._remove_inlet_widget(row, parent)
                case GraphItemType.OUTLET:
                    self._remove_outlet_widget(row, parent)
                case _:
                    raise NotImplementedError(f"Row kind {row_kind} is not implemented!")
        
    ## populate
    def _add_cell_widgets(self, row:int, parent: QModelIndex): 
        """Add all cell widgets associated with a row."""       
        # create labels from row cells
        for col in range(self._model.columnCount(parent=parent)):
            cell_index = self._model.index(row, col, parent)
            text = cell_index.data(Qt.ItemDataRole.DisplayRole)
            cell_widget = CellWidget()
            cell_widget.setText(f"{text}")
            self._cell_widgets[QPersistentModelIndex(cell_index)] = cell_widget

            row_widget = self._row_widgets[QPersistentModelIndex(self._model.index(row, 0, parent))]
            row_widget.addCell(cell_widget)
            
    def _add_node_widget(self, row: int, parent:QModelIndex):
        #add widget to view
        index = self._model.index(row, 0, parent)
        widget = NodeWidget(graphview=self)
        self._row_widgets[QPersistentModelIndex(index)] = widget
        self._add_cell_widgets(row, parent)

        # attach to scene or parent widget
        if parent.isValid():
            raise NotImplementedError()
        else:
            self.scene().addItem(widget)
        return widget

    def _add_inlet_widget(self, row:int, parent:QModelIndex):
        # add widget
        index = self._model.index(row, 0, parent)
        widget = InletWidget(graphview=self)

        self._row_widgets[QPersistentModelIndex(index)] = widget
        self._add_cell_widgets(row, parent)

        # attach to parent widget
        if parent.isValid():
            parent_widget = self._row_widgets[QPersistentModelIndex(parent)]
            if not isinstance(parent_widget, NodeWidget):
                raise ValueError("inlets must have a Node parent")
            parent_widget = cast(NodeWidget, parent_widget)
            parent_widget.addInlet(widget)
        else:
            raise NotImplementedError("root graph inlets are not yet implemented!")
        
        # update link geometry
        def update_in_links(view=self, inlet_index:QModelIndex=index):
            for child_row in range(view._model.rowCount(inlet_index)):
                view.updateLinkGeometry(child_row, inlet_index)

        widget.scenePositionChanged.connect(update_in_links)

        # return widget
        return widget
    
    def _add_outlet_widget(self, row, parent: QModelIndex):
        # add widget
        outlet_index = self._model.index(row, 0, parent)
        widget = OutletWidget(graphview=self)
        self._row_widgets[QPersistentModelIndex(outlet_index)] = widget
        self._add_cell_widgets(row, parent)
        self.scene().addItem(widget)


        # attach to parent widget
        parent = outlet_index.parent()
        if parent.isValid():
            parent_widget = self._row_widgets[QPersistentModelIndex(parent)]
            parent_widget = cast(NodeWidget, parent_widget)
            parent_widget.addOutlet(widget)

        self._out_links[QPersistentModelIndex(outlet_index)] = []

        # update link geometry
        def update_out_links(view=self, outlet_index:QModelIndex=outlet_index):
            for link_index in view._out_links[QPersistentModelIndex(outlet_index)]:
                view.updateLinkGeometry(link_index.row(), link_index.parent())

        widget.scenePositionChanged.connect(update_out_links)

        return widget
    
    def _add_link_widget(self, row:int, parent: QModelIndex):
        # add widget
        persistent_link_index = QPersistentModelIndex(self._model.index(row, 0, parent))
        widget = LinkWidget(graphview=self)
        self._row_widgets[persistent_link_index] = widget
        self._out_links[persistent_link_index] = []
        self._link_source[persistent_link_index] = None
        self._add_cell_widgets(row, parent)
        self.scene().addItem(widget)

        # attach to parent widget
        parent = persistent_link_index.parent()
        print("parent not valid?", parent.isValid())
        if parent.isValid():
            parent_widget = self._row_widgets[QPersistentModelIndex(parent)]
            parent_widget = cast(InletWidget, parent_widget)
            widget.setParentItem(parent_widget)
        else:
            raise ValueError("Link must have a parents")
        
        # check for source outlets
        source_index = persistent_link_index.data(GraphDataRole.SourceRole)
        if source_index.isValid():
            # if source_index is valid, it means this link is an outlet link
            # we need to update the link source
            self._link_source[persistent_link_index] = QPersistentModelIndex(source_index)
            self._out_links[QPersistentModelIndex(source_index)].append(persistent_link_index)

        return widget

    def _remove_cell_widgets(self, row:int, parent: QModelIndex):
        """Remove all cell widgets associated with a row."""
          
        # Remove cell widgets for all columns of this row
        for col in range(self._model.columnCount(parent=parent)):
            cell_index = self._model.index(row, col, parent)
            persistent_cell_index = QPersistentModelIndex(cell_index)
            assert persistent_cell_index in self._cell_widgets
            cell_widget = self._cell_widgets[persistent_cell_index]
            row_widget = self._row_widgets[QPersistentModelIndex(self._model.index(row, 0, parent))]
            row_widget.removeCell(cell_widget)
            del self._cell_widgets[persistent_cell_index]

    def _remove_node_widget(self, row: int, parent: QModelIndex):
        """Remove a node widget"""
        # Remove all cell widgets for this node
        self._remove_cell_widgets(row, parent)

        # remove widget from graphview
        index = self._model.index(row, 0, parent)
        widget = self._row_widgets[QPersistentModelIndex(index)]
        del self._row_widgets[QPersistentModelIndex(index)]
        
        # detach from scene or parent widget
        if parent.isValid():
            raise NotImplementedError()
        else:
            self.scene().removeItem(widget)
        
    def _remove_inlet_widget(self, row:int, parent:QModelIndex):
        """Remove an inlet widget and its associated cell widgets."""
        # Remove all cell widgets for this inlet
        self._remove_cell_widgets(row, parent)
        
        # remove widget from graphview
        index = self._model.index(row, 0, parent)
        widget = self._row_widgets[QPersistentModelIndex(index)]
        del self._row_widgets[QPersistentModelIndex(index)]

        # detach widget from scene (or parent widget)
        if parent.isValid():
            parent_widget = self._row_widgets[QPersistentModelIndex(parent)]
            parent_widget = cast(NodeWidget, parent_widget)
            parent_widget.removeInlet(widget)
        else:
            raise NotImplementedError("support inlets attached to the root graph")

    def _remove_outlet_widget(self, row:int, parent: QModelIndex):
        """Remove an outlet widget and its associated cell widgets."""
        # Remove all cell widgets for this outlet
        self._remove_cell_widgets(row, parent)
        
        # remove widget from graphview
        persistent_outlet_index = QPersistentModelIndex(self._model.index(row, 0, parent))
        widget = self._row_widgets[persistent_outlet_index]
        del self._row_widgets[persistent_outlet_index]
        

        # detach widget from scene (or parent widget)
        if parent.isValid():
            parent_widget = self._row_widgets[QPersistentModelIndex(parent)]
            parent_widget = cast(NodeWidget, parent_widget)
            parent_widget.removeOutlet(widget)
        else:
            raise NotImplementedError("support inlets attached to the root graph")
        
        # update links
        for persistent_link_index in self._out_links[persistent_outlet_index]:
            assert isinstance(persistent_link_index, QPersistentModelIndex)
            self.updateLinkGeometry(persistent_link_index.row(), persistent_link_index.parent())
            self._link_source[persistent_link_index].remove(persistent_outlet_index)
        del self._out_links[persistent_outlet_index]
        
    def _remove_link_widget(self, row:int, parent: QModelIndex):
        """Remove an inlet widget and its associated cell widgets."""
        # Remove all cell widgets for this inlet
        self._remove_cell_widgets(row, parent)
        
        # remove widget from graphview
        index = self._model.index(row, 0, parent)
        widget = self._row_widgets[QPersistentModelIndex(index)]
        del self._row_widgets[QPersistentModelIndex(index)]

        # detach link source
        persistent_link_index = QPersistentModelIndex(index)
        if persistent_link_index in self._link_source:
            source_index = self._link_source[persistent_link_index]
            if source_index in self._out_links:
                self._out_links[source_index].remove(persistent_link_index)
            del self._link_source[persistent_link_index]

        # detach widget from scene (or parent widget)
        if parent.isValid():
            parent_widget = self._row_widgets[QPersistentModelIndex(parent)]
            parent_widget = cast(InletWidget, parent_widget)
            parent_widget.setParentItem(None)
            self.scene().removeItem(widget)
        else:
            raise ValueError()

    def _defaultItemType(self, row:int, parent:QModelIndex) -> GraphItemType | None:
        """
        Determine the kind of row based on the index.
        This is used to determine whether to create a Node, Inlet, Outlet or Link widget.
        Args:
            index (QModelIndex): The index of the row.
        """
        index = self._model.index(row, 0, parent)
        if not index.isValid():
            return None
        elif index.parent() == QModelIndex():
            return GraphItemType.NODE
        elif index.parent().isValid() and index.parent().parent() == QModelIndex():
            return GraphItemType.INLET
        elif index.parent().isValid() and index.parent().parent().isValid() and index.parent().parent().parent() == QModelIndex():
            return GraphItemType.LINK
        else:
            raise ValueError(
                f"Invalid index: {index}. "
                "Index must be a valid QModelIndex with a valid parent."
            )
        
    def _validateItemType(self, row:int, parent:QModelIndex, item_type: 'GraphItemType') -> bool:
        """
        Validate the row kind based on the index.
        This is used to ensure that the row kind matches the expected kind
        Args:   

            index (QModelIndex): The index of the row.
            row_kind (NodeType | None): The kind of row to validate.
        Returns:
            bool: True if the row kind is valid, False otherwise.
        """
        index = self._model.index(row, 0, parent)
        if not index.isValid():
            return False
        if item_type is None:
            return True  # No specific row kind, so always valid
        if item_type == GraphItemType.NODE:
            return index.parent() == QModelIndex()
        elif item_type == GraphItemType.INLET:
            return index.parent().isValid() and index.parent().parent() == QModelIndex()
        elif item_type == GraphItemType.OUTLET:
            return index.parent().isValid() and index.parent().parent() == QModelIndex()
        elif item_type == GraphItemType.LINK:
            return index.parent().isValid() and index.parent().parent().isValid() and index.parent().parent().parent() == QModelIndex()

    def itemType(self, row:int, parent:QModelIndex):
        index = self._model.index(row, 0, parent)
        row_kind = index.data(GraphDataRole.TypeRole)
        if not row_kind:
            row_kind = self._defaultItemType(row, parent)
        assert self._validateItemType(row, parent, row_kind), f"Invalid row kind {row_kind} for index {index}!"
        return row_kind
    
    @Slot(QModelIndex, QModelIndex, int, int)
    def onRowsInserted(self, parent:QModelIndex, first:int, last:int):
        assert self._model

        # populate the new rows
        self.addRowWidgets(*[self._model.index(row, 0, parent) for row in range(first, last + 1)])

    @Slot(QModelIndex, QModelIndex, int, int)
    def onRowsAboutToBeRemoved(self, parent: QModelIndex, first: int, last: int):
        """
        Handle rows being removed from the model.
        This removes the corresponding widgets from the scene and cleans up internal mappings.
        Removal is done recursively from bottom up to ensure proper cleanup of widget hierarchies.
        """
        assert self._model

        self.removeRowWidgets(*[self._model.index(row, 0, parent) for row in range(first, last + 1)])

        # # Remove rows in reverse order to handle siblings properly
        # for row in reversed(range(first, last + 1)):
        #     # index = self._model.index(row, 0, parent=parent)
        #     self._remove_row_recursive(row, parent)

    @Slot(QModelIndex, QModelIndex, list)
    def onDataChanged(self, topLeft:QModelIndex , bottomRight:QModelIndex , roles=[]):
        assert self._model

        ## Update data cells
        for row in range(topLeft.row(), bottomRight.row()+1):
            for col in range(topLeft.column(), bottomRight.column()+1):  
                cell_index = topLeft.sibling(row, col)
                widget = self._cell_widgets[QPersistentModelIndex(cell_index)]
                proxy = cast(QGraphicsProxyWidget, widget)
                label = proxy.widget()
                assert isinstance(label, QLabel)
                label.setText(cell_index.data(Qt.ItemDataRole.DisplayRole))

        ## check if link source has changed
        if GraphDataRole.SourceRole in roles or roles == []:
            for row in range(topLeft.row(), bottomRight.row()+1):
                if self.itemType(row, topLeft.parent()) == GraphItemType.LINK:
                    persistent_link_index = QPersistentModelIndex(topLeft.siblingAtRow(row))
                    new_source_index = persistent_link_index.data(GraphDataRole.SourceRole)
                    previous_source_index = self._link_source[persistent_link_index]
                    if previous_source_index != new_source_index:
                        """!link source has changed"""
                        self._link_source[persistent_link_index] = new_source_index
                        self._out_links[previous_source_index].remove(persistent_link_index)
                        self._out_links[previous_source_index].append(new_source_index)


class CellWidget(QGraphicsProxyWidget):
    def __init__(self, parent: QGraphicsItem | None = None):
        super().__init__(parent=parent)
        self._label = QLabel("")
        self._label.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self._label.setStyleSheet("background: yellow;")
        self.setWidget(self._label)
        self.setAutoFillBackground(False)

    def text(self):
        return self._label.text()

    def setText(self, text:str):
        self._label.setText(text)



class BaseRowWidget(QGraphicsWidget):
    scenePositionChanged = Signal()
    def __init__(self, graphview:'GraphView', parent: QGraphicsItem | None = None):
        super().__init__(parent=parent)
        self._graphview = graphview
        layout = QGraphicsLinearLayout(Qt.Orientation.Vertical)
        self.setLayout(layout)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsScenePositionChanges, True)

    def addCell(self, cell:CellWidget):
        layout = cast(QGraphicsLinearLayout, self.layout())
        layout.addItem(cell)

    def removeCell(self, cell:CellWidget):
        layout = cast(QGraphicsLinearLayout, self.layout())
        layout.removeItem(cell)

    def itemChange(self, change, value):
        match change:
            case QGraphicsItem.GraphicsItemChange.ItemScenePositionHasChanged:
                self.scenePositionChanged.emit()
                    
        return super().itemChange(change, value)


class PortWidget(BaseRowWidget):
    def __init__(self, graphview:'GraphView', parent: QGraphicsItem | None = None):
        super().__init__(graphview, parent=parent)
        # self.setGeometry(-14,0,14,14)
        
        self.setLayout(QGraphicsLinearLayout(Qt.Orientation.Horizontal, self))

    def paint(self, painter, option, /, widget = ...):
        painter.setBrush(self.palette().alternateBase())
        painter.drawRect(option.rect)


class InletWidget(PortWidget):
    def mousePressEvent(self, event):
        # Setup new drag
        graphview = self._graphview
        # assert isinstance(graphview, 'GraphView'), "Inlet must be in a GraphView"
        node_widget = self.parentItem()
        assert isinstance(node_widget, NodeWidget), "Inlet must be a child of NodeWidget"
        inlet_index = graphview._row_widgets.inverse[self]
        node_index = inlet_index.parent()
        assert node_index.isValid(), "Inlet must have a valid parent node index"
        node_index.data(GraphDataRole.TypeRole) == GraphItemType.NODE, "Inlet must have a valid parent node of type NODE"
        mime = QMimeData()
        mime.setData(GraphMimeData.InletData, f"{node_index.row()}/{inlet_index.row()}".encode("utf-8"))
        drag = QDrag(graphview)
        drag.setMimeData(mime)

        # Create visual feedback
        # graphview._createDraftLink()

        # Execute drag
        try:
            action = drag.exec(Qt.DropAction.CopyAction)
        except Exception as err:
            traceback.print_exc()
        finally:
            pass
            # graphview._cleanupDraftLink()
        return super().mousePressEvent(event)


class OutletWidget(PortWidget):
    def __init__(self, graphview:'GraphView', parent: QGraphicsItem | None = None):
        super().__init__(graphview, parent=parent)
        self._view = graphview
        self.setAcceptDrops(True)

    def paint(self, painter, option, /, widget:QWidget|None = None):
        painter.setBrush("purple")
        painter.drawRect(option.rect)

    def dragEnterEvent(self, event: QGraphicsSceneDragDropEvent) -> None:
        print("OUTLET: drag enter event", event.mimeData().formats())
        

        event.setAccepted(True)
        if event.mimeData().hasFormat(GraphMimeData.InletData):
            event.acceptProposedAction() # Todo: set accepted action
            return

        if event.mimeData().hasFormat(GraphMimeData.LinkTargetData):
            event.acceptProposedAction()
            return

    def dragMoveEvent(self, event: QGraphicsSceneDragDropEvent) -> None:
        print("OUTLET: drag move event", event.mimeData().formats())
        if event.mimeData().hasFormat(GraphMimeData.InletData):
            assert self._view
            assert self._view._model
            target_path = event.mimeData().data(GraphMimeData.InletData).toStdString()
            node_row, inlet_row = target_path.split("/")
            node_index = self._view._model.index(int(node_row), 0, QModelIndex())
            inlet_index = self._view._model.index(int(inlet_row), 0, node_index)
            
            inlet_widget = self._view._row_widgets[QPersistentModelIndex(inlet_index)]
            assert isinstance(inlet_widget, InletWidget), "Inlet must be a child of InletWidget"
            if self._view._draft_link:
                line = self._view._draft_link.line()
                line = makeLineBetweenShapes(self, inlet_widget)
                self._view._draft_link.setLine(line)
                event.acceptProposedAction()
                return

        if event.mimeData().hasFormat(GraphMimeData.LinkTargetData):
            assert self._view
            link_key = event.mimeData().data(GraphMimeData.LinkTargetData).toStdString().split("/")
            source, target, outlet, inlet = link_key
            source_item = self._view._node_widgets[source]._inlet_widgets[outlet]
            if self._view._draft_link:
                line = self._view._draft_link.line()
                line = makeLineBetweenShapes(source_item, self)
                self._view._draft_link.setLine(line)
                event.acceptProposedAction()
                return

        return super().dragMoveEvent(event)
    
    def dropEvent(self, event: QGraphicsSceneDragDropEvent) -> None:
        print("OUTLET: drop event", event.mimeData().formats())
        if event.mimeData().hasFormat(GraphMimeData.InletData):
            assert self._view
            assert self._view._model
            inlet_path = event.mimeData().data(GraphMimeData.InletData).toStdString()
            target_node_row, target_inlet_row = inlet_path.split("/")
            target_node_index = self._view._model.index(int(target_node_row), 0, QModelIndex())
            target_inlet_index = self._view._model.index(int(target_inlet_row), 0, target_node_index)

            # get the source outlet index, the index corresponding to this widget
            source_outlet_index = self._view.indexFromWidget(self)

            self._view._model.createLink(
                source_outlet_index,
                target_inlet_index
            )

            # self._view._model.linkNodes(cast(NodeItem, self.parentItem()).key, target_node, self.key, inlet)
            event.acceptProposedAction()
            return

        if event.mimeData().hasFormat(GraphMimeData.LinkTargetData):
            assert self._view
            assert self._view._model
            link_key = event.mimeData().data(GraphMimeData.LinkTargetData).toStdString().split("/")
            source, target, outlet, inlet = link_key
            # unlink current
            self._view._model.unlinkNodes(source, target, outlet, inlet)

            # link source with new target
            self._view._model.linkNodes(source, cast(NodeItem, self.parentItem()).key, outlet, self.key)
            event.acceptProposedAction()
            return

        return super().dragMoveEvent(event)


class NodeWidget(BaseRowWidget):
    def __init__(self, graphview:'GraphView', parent: QGraphicsItem | None = None):
        super().__init__(graphview, parent=parent)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        layout = QGraphicsLinearLayout(Qt.Orientation.Vertical)
        self.setLayout(layout)

    def addInlet(self, inlet:InletWidget):
        layout = cast(QGraphicsLinearLayout, self.layout())
        layout.addItem(inlet)

    def removeInlet(self, inlet:InletWidget):
        layout = cast(QGraphicsLinearLayout, self.layout())
        layout.removeItem(inlet)

    def addOutlet(self, outlet:OutletWidget):
        layout = cast(QGraphicsLinearLayout, self.layout())
        layout.addItem(outlet)

    def removeOutlet(self, outlet:InletWidget):
        layout = cast(QGraphicsLinearLayout, self.layout())
        layout.removeItem(outlet)

    def addCell(self, cell):
        return super().addCell(cell)

    def paint(self, painter: QPainter, option: QStyleOption, widget=None):
        rect = option.rect       
        painter.setBrush(self.palette().alternateBase())
        if self.isSelected():
            painter.setBrush(self.palette().highlight())
        painter.drawRoundedRect(rect, 6, 6)


class LinkWidget(BaseRowWidget):
    def __init__(self, graphview:'GraphView', parent: QGraphicsItem | None = None):
        super().__init__(graphview, parent=parent)
        # self.setZValue(-1)  # Ensure links are drawn below nodes
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self._line = QLineF(0, 0, 100, 100)
        self._label = QLabel("Link")
        self._data_column = QGraphicsWidget(parent=self)
        self._data_column.setLayout(QGraphicsLinearLayout(Qt.Orientation.Vertical))

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
        stroker.setWidth(2)
        return stroker.createStroke(path)
    
    def addCell(self, cell:CellWidget):
        layout = cast(QGraphicsLinearLayout, self._data_column.layout())
        layout.addItem(cell)

    def removeCell(self, cell:CellWidget):
        layout = cast(QGraphicsLinearLayout, self._data_column.layout())
        layout.addItem(cell)

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget=None):
        if self.isSelected():
            painter.setBrush(self.palette().accent())
        else:
            painter.setBrush(self.palette().text())
        painter.setPen(Qt.PenStyle.NoPen)
        print("paint")
        shape = self.shape()
        painter.drawPath(shape)

    def updateLine(self, source:QGraphicsItem|None, target:QGraphicsItem|None):
        print("updateLine: {source}->{target}")
        self.prepareGeometryChange()
        if source and target:
            self._line = makeLineBetweenShapes(source, target)
            self._line.translate(-self.scenePos().x(), -self.scenePos().y())
        elif source:
            source_pos = source.scenePos()-self.scenePos()
            self._line = QLineF(source_pos, source_pos+QPointF(100,100))
        elif target:
            target_pos = target.scenePos()-self.scenePos()
            self._line = QLineF(target_pos-QPointF(100,100), target_pos)
        else:
            ...

        self._data_column.layout().setGeometry(
            QRectF(self._line.p1(), self._line.p2())
            .adjusted(-5, -5, 5, 5)
            .normalized()
        )

        self.update()
