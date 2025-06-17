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
from PySide6.QtGui import *
from PySide6.QtCore import *
from PySide6.QtWidgets import *

from collections import defaultdict
from bidict import bidict

from utils import group_consecutive_numbers
from utils.geo import makeLineBetweenShapes, makeLineToShape, makeArrowShape
# from pylive.utils.geo import makeLineBetweenShapes, makeLineToShape
# from pylive.utils.qt import distribute_items_horizontal
# from pylive.utils.unique import make_unique_name
# from pylive.utils.diff import diff_set

import logging
from enum import StrEnum, IntEnum
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


from core import GraphDataRole, GraphItemType, GraphMimeData
import networkx as nx

class GraphAdapter(QObject):
    nodeAdded = Signal(QPersistentModelIndex) # key
    nodeAboutToBeRemoved = Signal(QPersistentModelIndex) # key
    inletAdded = Signal(QPersistentModelIndex) # key
    inletAboutToBeRemoved = Signal(QPersistentModelIndex) # key
    outletAdded = Signal(QPersistentModelIndex) # key
    outletAboutToBeRemoved = Signal(QPersistentModelIndex) # key
    linkAdded = Signal(QPersistentModelIndex) # key
    linkAboutToBeRemoved = Signal(QPersistentModelIndex) # key
    nodeDataChanged = Signal(QPersistentModelIndex, int, list) # key, column, roles

    def __init__(self, parent:QObject|None = None ):
        super().__init__(parent)
        self._sourceModel:QAbstractItemModel | None = None
        self._graph = nx.MultiDiGraph()

    def setSourceModel(self, sourceModel:QAbstractItemModel| None):
        """
        Set the source model for the adapter.
        This is used to synchronize the adapter with the model.
        """
        assert sourceModel is None or isinstance(sourceModel, QAbstractItemModel), f"got: {sourceModel}, expected QAbstractItemModel or None"

        if self._sourceModel:
            for signal, slot in self._model_connections:
                signal.disconnect(slot)
            self._model_connections = []
 
        if sourceModel:
            self._model_connections = [
                (sourceModel.dataChanged, self.onDataChanged),
                (sourceModel.rowsInserted, self.onRowsInserted),
                (sourceModel.rowsAboutToBeRemoved, self.onRowsAboutToBeRemoved)
            ]
            for signal, slot in self._model_connections:
                signal.connect(slot)

        self._sourceModel = sourceModel

        # self.onRowsInserted(QModelIndex(), 0, self._sourceModel.rowCount() - 1)

    def sourceModel(self) -> QAbstractItemModel | None:
        """
        Get the current source model for the adapter.
        This is used to synchronize the adapter with the model.
        """
        return self._sourceModel
    
    def nodes(self, subgraph:QModelIndex|QPersistentModelIndex=QModelIndex()) -> List[QPersistentModelIndex]:
        """
        Get all nodes in the graph.
        This returns a list of QModelIndexes for the nodes in the graph.
        """
        if not self._sourceModel:
            return []
        return [QPersistentModelIndex(self._sourceModel.index(row, 0, subgraph)) for row in range(self._sourceModel.rowCount()) if self.itemType(row, QModelIndex()) == GraphItemType.NODE]

    def inlets(self, node:QModelIndex|QPersistentModelIndex=QModelIndex()) -> List[QPersistentModelIndex]:
        """
        Get all inlets in the graph.
        This returns a list of QModelIndexes for the outlets in the graph.
        """
        assert self._sourceModel, "Source model must be set before getting outlets"
        return [QPersistentModelIndex(self._sourceModel.index(row, 0, node)) for row in range(self._sourceModel.rowCount(node)) if self.itemType(row, node) == GraphItemType.INLET]

    def outlets(self, node:QModelIndex|QPersistentModelIndex=QModelIndex()) -> List[QPersistentModelIndex]:
        """
        Get all outlets in the graph.
        This returns a list of QModelIndexes for the outlets in the graph.
        """
        assert self._sourceModel, "Source model must be set before getting outlets"
        return [QPersistentModelIndex(self._sourceModel.index(row, 0, node)) for row in range(self._sourceModel.rowCount(node)) if self.itemType(row, node) == GraphItemType.OUTLET]
    
    def links(self, inlet:QModelIndex|QPersistentModelIndex=QModelIndex()) -> List[QPersistentModelIndex]:
        """
        Get all links in the graph.
        This returns a list of QModelIndexes for the links in the graph.
        """
        assert self._sourceModel, "Source model must be set before getting links"
        return [QPersistentModelIndex(self._sourceModel.index(row, 0, inlet)) for row in range(self._sourceModel.rowCount(inlet)) if self.itemType(row, inlet) == GraphItemType.LINK]
    
    def nodeDataCount(self, node:QModelIndex|QPersistentModelIndex=QModelIndex()) -> int:
        """
        Get the number of data items for a node in the graph.
        This returns the number of data items for the node at the specified index.
        """
        assert self._sourceModel, "Source model must be set before getting node data count"
        return self._sourceModel.rowCount(node)

    def nodeData(self, node:QModelIndex|QPersistentModelIndex=QModelIndex(), column:int=0, role:int=Qt.ItemDataRole.DisplayRole) -> Any:
        """
        Get the data for a node in the graph.
        This returns the data for the node at the specified column.
        """
        assert self._sourceModel, "Source model must be set before getting node data"
        index = self._sourceModel.index(node.row(), column, node.parent())
        return index.data(role)
    
    def inletData(self, inlet:QModelIndex|QPersistentModelIndex=QModelIndex(), column:int=0, role:int=Qt.ItemDataRole.DisplayRole) -> Any:
        """
        Get the data for an inlet in the graph.
        This returns the data for the inlet at the specified column.
        """
        assert self._sourceModel, "Source model must be set before getting inlet data"
        index = self._sourceModel.index(inlet.row(), column, inlet.parent())
        return index.data(Qt.ItemDataRole.DisplayRole)
    
    def outletData(self, outlet:QModelIndex|QPersistentModelIndex=QModelIndex(), column:int=0, role:int=Qt.ItemDataRole.DisplayRole) -> Any:
        """
        Get the data for an outlet in the graph.
        This returns the data for the outlet at the specified column.
        """
        assert self._sourceModel, "Source model must be set before getting outlet data"
        index = self._sourceModel.index(outlet.row(), column, outlet.parent())
        return index.data(Qt.ItemDataRole.DisplayRole)

    def linkData(self, link:QModelIndex|QPersistentModelIndex=QModelIndex(), column:int=0, role:int=Qt.ItemDataRole.DisplayRole) -> Any:
        """
        Get the data for a link in the graph.
        This returns the data for the link at the specified column.
        """
        assert self._sourceModel, "Source model must be set before getting link data"
        index = self._sourceModel.index(link.row(), column, link.parent())
        return index.data(Qt.ItemDataRole.DisplayRole)

    ## Helpers
    def itemType(self, row:int, parent:QModelIndex):
        index = self._sourceModel.index(row, 0, parent)
        row_kind = index.data(GraphDataRole.TypeRole)
        if not row_kind:
            row_kind = self._defaultItemType(row, parent)
        assert self._validateItemType(row, parent, row_kind), f"Invalid row kind {row_kind} for index {index}!"
        return row_kind
    
    def _defaultItemType(self, row:int, parent:QModelIndex) -> GraphItemType | None:
        """
        Determine the kind of row based on the index.
        This is used to determine whether to create a Node, Inlet, Outlet or Link widget.
        Args:
            index (QModelIndex): The index of the row.
        """
        index = self._sourceModel.index(row, 0, parent)
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
        index = self._sourceModel.index(row, 0, parent)
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

    def addNode(self, subgraph:QModelIndex|QPersistentModelIndex=QModelIndex()):
        ...

    def addInlet(self, node:QPersistentModelIndex):
        ...

    def addOutlet(self, node:QPersistentModelIndex):
        ...

    def addLink(self, outlet:QPersistentModelIndex, inlet:QPersistentModelIndex):
        ...

    def mapToSource(self, key:QPersistentModelIndex) -> QModelIndex:
        """
        Map a persistent model index to the source model index.
        This is used to get the original index from the persistent index.
        """
        assert self._sourceModel, "Source model must be set before mapping to source"
        return QModelIndex(key)
    
    def inletMimeData(self, inlet:QPersistentModelIndex)->QMimeData:
        """
        Create a QMimeData object for an inlet.
        This is used to provide data for drag-and-drop operations.
        """
        mime = QMimeData()

        # Convert index to path string
        path = []
        idx = inlet
        while idx.isValid():
            path.append(idx.row())
            idx = idx.parent()
        path = "/".join(map(str, reversed(path)))
        mime.setData(GraphMimeData.InletData, path.encode("utf-8"))
        return mime

    def outletMimeData(self, outlet:QPersistentModelIndex):
        """
        Create a QMimeData object for an inlet.
        This is used to provide data for drag-and-drop operations.
        """
        mime = QMimeData()

        # Convert index to path string
        path = []
        idx = outlet
        while idx.isValid():
            path.append(idx.row())
            idx = idx.parent()
        path = "/".join(map(str, reversed(path)))
        mime.setData(GraphMimeData.OutletData, path.encode("utf-8"))
        return mime
    
    ## Handle signals
    @Slot(QModelIndex, QModelIndex, int, int)
    def onRowsInserted(self, parent:QModelIndex, first:int, last:int):
        def children(index:QModelIndex):
            for row in range(self._sourceModel.rowCount(parent=index)):
                yield self._sourceModel.index(row, 0, index)

        queue:List[QModelIndex] = [self._sourceModel.index(row, 0, parent) for row in range(first, last + 1)]
        indexes = list()
        while queue:
            index = queue.pop(0)  # Remove from front for proper BFS
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
                    # self._add_node_widget(row, parent)
                    self.nodeAdded.emit(QPersistentModelIndex(index))
                case GraphItemType.INLET:
                    # self._add_inlet_widget(row, parent)
                    self.inletAdded.emit(QPersistentModelIndex(index))
                case GraphItemType.OUTLET:
                    # self._add_outlet_widget(row, parent)
                    self.outletAdded.emit(QPersistentModelIndex(index))
                case GraphItemType.LINK:
                    # self._add_link_widget(row, parent)
                    self.linkAdded.emit(QPersistentModelIndex(index))
                case _:
                    raise NotImplementedError(f"Row kind {row_kind} is not implemented!")
    
    @Slot(QModelIndex, QModelIndex, int, int)
    def onRowsAboutToBeRemoved(self, parent: QModelIndex, first: int, last: int):
        """
        Handle rows being removed from the model.
        This removes the corresponding widgets from the scene and cleans up internal mappings.
        Removal is done recursively from bottom up to ensure proper cleanup of widget hierarchies.
        """
        assert self._model

        def children(index:QModelIndex):
            for row in range(self._model.rowCount(parent=index)):
                yield self._model.index(row, 0, index)        # Breadth-first search

        root = [self._model.index(row, 0, parent) for row in range(first, last + 1)]

        queue:List[QModelIndex] = [*root]
        bfs_indexes = list()
        while queue:
            index = queue.pop(0)  # Remove from front for proper BFS
            bfs_indexes.append(index)
            for child in children(index):
                queue.append(child)

        # remove links first
        link_indexes = filter(lambda idx: self.itemType(idx.row(), idx.parent()) == GraphItemType.LINK, bfs_indexes)
        
        for index in link_indexes:
            self.linkAboutToBeRemoved.emit(QPersistentModelIndex(index))
            # self._remove_link_widget(index.row(), index.parent())

        # remove widgets reversed depth order
        non_link_indexes = filter(lambda idx: self.itemType(idx.row(), idx.parent()) != GraphItemType.LINK, reversed(bfs_indexes) )
        for index in non_link_indexes:
            row, parent = index.row(), index.parent()
            row_kind = self.itemType(row, parent)
            match row_kind:

                case None:
                    pass
                case GraphItemType.NODE:
                    # self._remove_node_widget(row, parent)
                    self.nodeAboutToBeRemoved.emit(QPersistentModelIndex(index))
                case GraphItemType.INLET:
                    # self._remove_inlet_widget(row, parent)
                    self.inletAboutToBeRemoved.emit(QPersistentModelIndex(index))
                case GraphItemType.OUTLET:
                    # self._remove_outlet_widget(row, parent)
                    self.outletAboutToBeRemoved.emit(QPersistentModelIndex(index))
                case _:
                    raise NotImplementedError(f"Row kind {row_kind} is not implemented!")

    @Slot(QModelIndex, QModelIndex, list)
    def onDataChanged(self, topLeft:QModelIndex , bottomRight:QModelIndex , roles=[]):
        assert self._model

        ## Update data cells
        for row in range(topLeft.row(), bottomRight.row()+1):
            index = topLeft.sibling(row, 0)
            if self.itemType(row, topLeft.parent()) == GraphItemType.NODE:
                # update node data
                for col in range(topLeft.column(), bottomRight.column()+1):
                    self.nodeDataChanged.emit(QPersistentModelIndex(index), col, roles)


        ## check if link source has changed
        if GraphDataRole.SourceRole in roles or roles == []:
            for row in range(topLeft.row(), bottomRight.row()+1):
                if self.itemType(row, topLeft.parent()) == GraphItemType.LINK:
                    persistent_link_index = QPersistentModelIndex(topLeft.siblingAtRow(row))
                    new_source_index = persistent_link_index.data(GraphDataRole.SourceRole)
                    previous_source_index = self._link_source[persistent_link_index]
                    if previous_source_index != new_source_index:
                        self.linkAboutToBeRemoved.emit(persistent_link_index)
                        self.linkAdded.emit(QPersistentModelIndex(persistent_link_index))
                        # """!link source has changed"""
                        # link_widget = self._row_widgets[persistent_link_index]
                        # target_index = persistent_link_index.parent()
                        # link_widget.link(
                        #     self._row_widgets[QPersistentModelIndex(new_source_index)],
                        #     self._row_widgets[QPersistentModelIndex(target_index)]
                        # )
                        # self._link_source[persistent_link_index] = new_source_index
                        # self._out_links[previous_source_index].remove(persistent_link_index)
                        # self._out_links[previous_source_index].append(new_source_index)
    

class GraphView(QGraphicsView):
    class State(Enum):
        IDLE = "IDLE"
        LINKING = "LINKING"
        
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent=parent)
        self.setAcceptDrops(True)
        self._adapter:GraphAdapter | None = None
        self._adapter_connections = []
        # self._selection: QItemSelectionModel | None = None
        # self._selection_connections = []

        # store model widget relations
        # map item index to widgets
        self._row_widgets: bidict[QPersistentModelIndex, BaseRowWidget] = bidict()
        self._cell_widgets: bidict[QPersistentModelIndex, CellWidget] = bidict()

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

    def setAdapter(self, adapter:GraphAdapter):
        if self._adapter_connections:
            for signal, slot in self._adapter_connections:
                signal.disconnect(slot)
            self._adapter_connections = []
            self._adapter.setSourceModel(None)
            self._adapter = None
        
        if adapter:
            assert isinstance(adapter, GraphAdapter), "Model must be a subclass of QAbstractItemModel"
            self._adapter = GraphAdapter(self)

            self._adapter_connections = [
                (self._adapter.nodeAdded, self._add_node_widget),
                (self._adapter.nodeAboutToBeRemoved, self._remove_node_widget),
                (self._adapter.inletAdded, self._add_inlet_widget),
                (self._adapter.inletAboutToBeRemoved, self._remove_inlet_widget),
                (self._adapter.outletAdded, self._add_outlet_widget),
                (self._adapter.outletAboutToBeRemoved, self._remove_outlet_widget),
                (self._adapter.linkAdded, self._add_link_widget),
                (self._adapter.linkAboutToBeRemoved, self._remove_link_widget),
                (self._adapter.nodeDataChanged, self._set_node_data)
            ]

            for signal, slot in self._adapter_connections:
                signal.connect(slot)
        self._adapter = adapter
        
        # populate initial scene
        ## clear
        self.scene().clear()
        self._row_widgets.clear()
        self._cell_widgets.clear()
        if self._adapter:
            for node in self._adapter.nodes():
                self._add_node_widget(node)
                for inlet in self._adapter.inlets(node):
                    self._add_inlet_widget(inlet)
                for outlet in self._adapter.outlets(node):
                    self._add_outlet_widget(outlet)

    def adapter(self) -> GraphAdapter | None:
        return self._adapter
    
    # # Selection
    def setSelectionModel(self, selection: QItemSelectionModel):
        """
        Set the selection model for the graph view.
        This is used to synchronize the selection of nodes in the graph view
        with the selection model.
        """
    #     assert isinstance(selection, QItemSelectionModel)
    #     assert self._model, "Model must be set before setting the selection model!"
    #     assert selection.model() == self._model, "Selection model must be for the same model as the graph view!"
    #     if self._selection:
    #         for signal, slot in self._selection_connections:
    #             signal.disconnect(slot)
    #         self._selection_connections = []
        
    #     if selection:
    #         self._selection_connections = [
    #             (selection.selectionChanged, self.onSelectionChanged)
    #         ]
    #         for signal, slot in self._selection_connections:
    #             signal.connect(slot)

    #     self._selection = selection
    # 
    #     scene.selectionChanged.connect(self.updateSelectionModel)

    # def selectionModel(self) -> QItemSelectionModel | None:
    #     """
    #     Get the current selection model for the graph view.
    #     This is used to synchronize the selection of nodes in the graph view
    #     with the selection model.
    #     """
    #     return self._selection
    
    # @Slot(QItemSelection, QItemSelection)
    # def onSelectionChanged(self, selected:QItemSelection, deselected:QItemSelection):
    #     """
    #     Handle selection changes in the selection model.
    #     This updates the selection in the graph view.
    #     """
    #     print(f"onSelectionChanged: {selected}, {deselected}")
    #     assert self._selection, "Selection model must be set before handling selection changes!"
    #     assert self._model, "Model must be set before handling selection changes!"

    #     scene = self.scene()
    #     scene.blockSignals(True)
    #     for index in deselected.indexes():
    #         widget = self._row_widgets[QPersistentModelIndex(index.siblingAtColumn(0))]
    #         widget.setSelected(False)
    #         # widget.update()

    #     for index in selected.indexes():
    #         widget = self._row_widgets[QPersistentModelIndex(index.siblingAtColumn(0))]
    #         widget.setSelected(True)
    #         # widget.update()
    #     scene.blockSignals(False)

    # def updateSelectionModel(self):
    #     """update selection model from scene selection"""
    #     if self._adapter and self._selection:
    #         # get currently selected widgets
    #         selected_widgets = self.scene().selectedItems()

    #         # map widgets to QModelIndexes
    #         selected_indexes = map(lambda widget: self._row_widgets.inverse.get(widget, None), selected_widgets)
    #         selected_indexes = filter(lambda idx: idx is not None and idx.isValid(), selected_indexes)

    #         # group indexes by parents
    #         indexes_by_parent = defaultdict(list)
    #         for index in selected_indexes:
    #             parent = index.parent()
    #             indexes_by_parent[parent].append(index)

    #         # create QItemSelection
    #         item_selection = QItemSelection()
    #         for parent, indexes in indexes_by_parent.items():
    #             all_rows = sorted(index.row() for index in indexes)
    #             ranges = group_consecutive_numbers(all_rows)

    #             for row_range in ranges:
    #                 top_left = self._model.index(row_range.start, 0, parent)
    #                 bottom_right = self._model.index(row_range.stop - 1, self._model.columnCount(parent) - 1, parent)
    #                 selection_range = QItemSelectionRange(top_left, bottom_right)
    #                 item_selection.append(selection_range)

    #         # perform selection on model
    #         self._selection.select(item_selection, QItemSelectionModel.SelectionFlag.ClearAndSelect)

    # Manage Widgets
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
            
    def _add_node_widget(self, index:QPersistentModelIndex):
        #add widget to view
        assert isinstance(index, QPersistentModelIndex), f"Index must be a QPersistentModelIndex, got: {index}"
        assert index.column()==0, "Index must be in the first column"
        widget = NodeWidget(graphview=self)
        self._row_widgets[index] = widget
        self._add_cell_widgets(index.row(), index.parent() )

        # attach to scene or parent widget
        if index.parent().isValid():
            raise NotImplementedError()
        else:
            self.scene().addItem(widget)
        return widget

    def _add_inlet_widget(self, index:QPersistentModelIndex):
        #add widget to view
        assert isinstance(index, QPersistentModelIndex), "Index must be a QPersistentModelIndex"
        assert index.column()==0, "Index must be in the first column"
        # add widget
        widget = InletWidget(graphview=self)

        self._row_widgets[index] = widget
        self._add_cell_widgets(index.row(), index.parent() )

        # attach to parent widget
        if index.parent().isValid():
            parent_widget = self._row_widgets[QPersistentModelIndex(index.parent())]
            if not isinstance(parent_widget, NodeWidget):
                raise ValueError("inlets must have a Node parent")
            parent_widget = cast(NodeWidget, parent_widget)
            parent_widget.addInlet(widget)
        else:
            raise NotImplementedError("root graph inlets are not yet implemented!")
        
        # update link geometry
        # def update_in_links(view=self, inlet_index:QModelIndex=index):
        #     for child_row in range(view._model.rowCount(inlet_index)):
        #         view.updateLinkGeometry(child_row, inlet_index)

        # widget.scenePositionChanged.connect(update_in_links)

        # return widget
        return widget
    
    def _add_outlet_widget(self, index:QPersistentModelIndex):
        #add widget to view
        assert isinstance(index, QPersistentModelIndex), "Index must be a QPersistentModelIndex"
        assert index.column()==0, "Index must be in the first column"
        widget = OutletWidget(graphview=self)
        self._row_widgets[index] = widget
        self._add_cell_widgets(index.row(), index.parent())
        self.scene().addItem(widget)


        # attach to parent widget
        if index.parent().isValid():
            parent_widget = self._row_widgets[QPersistentModelIndex(index.parent())]
            parent_widget = cast(NodeWidget, parent_widget)
            parent_widget.addOutlet(widget)

        # self._out_links[QPersistentModelIndex(outlet_index)] = []

        # update link geometry
        # def update_out_links(view=self, outlet_index:QModelIndex=outlet_index):
        #     for link_index in view._out_links[QPersistentModelIndex(outlet_index)]:
        #         view.updateLinkGeometry(link_index.row(), link_index.parent())

        # widget.scenePositionChanged.connect(update_out_links)

        return widget
    
    def _add_link_widget(self, index:QPersistentModelIndex):
        # add widget
        assert isinstance(index, QPersistentModelIndex), "Index must be a QPersistentModelIndex"
        assert index.column()==0, "Index must be in the first column"
        target_index = index.parent()
        
        link_widget = LinkWidget(graphview=self)
        self._row_widgets[index] = link_widget
        self._add_cell_widgets(index.row(), index.parent())
        self.scene().addItem(link_widget)

        # attach to parent widget
        # def get_target_index():
        
        target_index = index.parent()
        source_index = index.data(GraphDataRole.SourceRole)
        if not target_index.isValid():
            raise ValueError("Link's target is invalid")
        if not source_index.isValid():
            raise ValueError("link's source is invalid")
        
        source_outlet = self._row_widgets[QPersistentModelIndex(source_index)]
        target_inlet = self._row_widgets[QPersistentModelIndex(target_index)]
        link_widget.link(source_outlet, target_inlet)

        # print("parent not valid?", target_index.isValid())
        # if target_index.isValid():
        #     target_widget = self._row_widgets[QPersistentModelIndex(target_index)]
        #     target_widget = cast(InletWidget, target_widget)
        #     link_widget.setParentItem(target_widget)
        # else:
        #     raise ValueError("Link must have a parents")
        
        # # check for source outlets
        
        # if source_index.isValid():
        #     pass
        #     # if source_index is valid, it means this link is an outlet link
        #     # we need to update the link source
        #     # self._link_source[persistent_link_index] = QPersistentModelIndex(source_index)
        #     # self._out_links[QPersistentModelIndex(source_index)].append(persistent_link_index)

        return link_widget

    def _remove_cell_widgets(self, index:QPersistentModelIndex):
        """Remove all cell widgets associated with a row."""
        assert isinstance(index, QPersistentModelIndex), "Index must be a QPersistentModelIndex"
        assert index.column()==0, "Index must be in the first column"
        
          
        # Remove cell widgets for all columns of this row
        for col in range(self._model.columnCount(parent=index.parent())):
            cell_index = index.sibling(index.row(), col)
            persistent_cell_index = QPersistentModelIndex(cell_index)
            assert persistent_cell_index in self._cell_widgets
            cell_widget = self._cell_widgets[persistent_cell_index]
            row_widget = self._row_widgets[index]
            row_widget.removeCell(cell_widget)
            del self._cell_widgets[persistent_cell_index]

    def _remove_node_widget(self, index:QPersistentModelIndex):
        """Remove a node widget"""
        assert isinstance(index, QPersistentModelIndex), "Index must be a QPersistentModelIndex"
        assert index.column()==0, "Index must be in the first column"
        
        # Remove all cell widgets for this node
        self._remove_cell_widgets(index.row(), index.parent() )

        # remove widget from graphview
        widget = self._row_widgets[index]
        del self._row_widgets[index]
        
        # detach from scene or parent widget
        if index.parent().isValid():
            raise NotImplementedError()
        else:
            self.scene().removeItem(widget)
        
    def _remove_inlet_widget(self, index:QPersistentModelIndex):
        """Remove an inlet widget and its associated cell widgets."""
        assert isinstance(index, QPersistentModelIndex), "Index must be a QPersistentModelIndex"
        assert index.column()==0, "Index must be in the first column"
        # Remove all cell widgets for this inlet
        self._remove_cell_widgets(index.row(), index.parent() )
        
        # remove widget from graphview
        widget = self._row_widgets[index]
        del self._row_widgets[index]

        # detach widget from scene (or parent widget)
        if index.parent().isValid():
            parent_widget = self._row_widgets[QPersistentModelIndex(index.parent())]
            parent_widget = cast(NodeWidget, parent_widget)
            parent_widget.removeInlet(widget)
        else:
            raise NotImplementedError("support inlets attached to the root graph")

    def _remove_outlet_widget(self, index:QPersistentModelIndex):
        """Remove an outlet widget and its associated cell widgets."""
        assert isinstance(index, QPersistentModelIndex), "Index must be a QPersistentModelIndex"
        assert index.column()==0, "Index must be in the first column"
        # Remove all cell widgets for this outlet
        self._remove_cell_widgets(index.row(), index.parent())
        
        # remove widget from graphview
        widget = self._row_widgets[index]
        del self._row_widgets[index]
        
        # detach widget from scene (or parent widget)
        if index.parent().isValid():
            parent_widget = self._row_widgets[QPersistentModelIndex(index.parent())]
            parent_widget = cast(NodeWidget, parent_widget)
            parent_widget.removeOutlet(widget)
        else:
            raise NotImplementedError("support inlets attached to the root graph")
        
        # # update links
        # for persistent_link_index in self._out_links[persistent_outlet_index]:
        #     assert isinstance(persistent_link_index, QPersistentModelIndex)
        #     self.updateLinkGeometry(persistent_link_index.row(), persistent_link_index.parent())
        #     self._link_source[persistent_link_index].remove(persistent_outlet_index)
        # del self._out_links[persistent_outlet_index]
        
    def _remove_link_widget(self, index:QPersistentModelIndex):
        """Remove an inlet widget and its associated cell widgets."""
        assert isinstance(index, QPersistentModelIndex), "Index must be a QPersistentModelIndex"
        assert index.column()==0, "Index must be in the first column"
        widget = self._row_widgets[index]
        # detach widget from scene (or parent widget)
        link_widget = cast(LinkWidget, widget)
        
        # link_widget.deleteLater()  # Schedule for deletion
        # link_widget.setParentItem(None)
        # self.scene().removeItem(link_widget)

        # Remove all cell widgets for this inlet
        self._remove_cell_widgets(index.row(), index.parent())
        
        # remove widget from graphview
        
        assert isinstance(widget, LinkWidget), "Link widget must be of type LinkWidget"
        del self._row_widgets[index]

        # detach link source
        # persistent_link_index = QPersistentModelIndex(index)
        # if persistent_link_index in self._link_source:
        #     source_index = self._link_source[persistent_link_index]
        #     if source_index in self._out_links:
        #         self._out_links[source_index].remove(persistent_link_index)
        #     del self._link_source[persistent_link_index]

        self.scene().removeItem(link_widget)  # Remove from scene immediately

    def _set_node_data(self, index:QPersistentModelIndex, column:int, roles:list):
        """Set the data for a node widget."""
        assert isinstance(index, QPersistentModelIndex), "Index must be a QPersistentModelIndex"
        assert index.column() == 0, "Index must be in the first column"
        assert index in self._row_widgets, f"Index {index} not found in row widgets"

        widget = self._row_widgets[index]
        if not isinstance(widget, NodeWidget):
            raise ValueError(f"Widget for index {index} is not a NodeWidget")
        
        # update cell widgets

        cell_index = index.sibling(index.row(), column)
        widget = self._cell_widgets[QPersistentModelIndex(cell_index)]
        proxy = cast(QGraphicsProxyWidget, widget)
        label = proxy.widget()
        assert isinstance(label, QLabel)
        label.setText(cell_index.data(Qt.ItemDataRole.DisplayRole))


    # helper methods
    # def _defaultItemType(self, row:int, parent:QModelIndex) -> GraphItemType | None:
    #     """
    #     Determine the kind of row based on the index.
    #     This is used to determine whether to create a Node, Inlet, Outlet or Link widget.
    #     Args:
    #         index (QModelIndex): The index of the row.
    #     """
    #     index = self._model.index(row, 0, parent)
    #     if not index.isValid():
    #         return None
    #     elif index.parent() == QModelIndex():
    #         return GraphItemType.NODE
    #     elif index.parent().isValid() and index.parent().parent() == QModelIndex():
    #         return GraphItemType.INLET
    #     elif index.parent().isValid() and index.parent().parent().isValid() and index.parent().parent().parent() == QModelIndex():
    #         return GraphItemType.LINK
    #     else:
    #         raise ValueError(
    #             f"Invalid index: {index}. "
    #             "Index must be a valid QModelIndex with a valid parent."
    #         )
        
    # def _validateItemType(self, row:int, parent:QModelIndex, item_type: 'GraphItemType') -> bool:
    #     """
    #     Validate the row kind based on the index.
    #     This is used to ensure that the row kind matches the expected kind
    #     Args:   

    #         index (QModelIndex): The index of the row.
    #         row_kind (NodeType | None): The kind of row to validate.
    #     Returns:
    #         bool: True if the row kind is valid, False otherwise.
    #     """
    #     index = self._model.index(row, 0, parent)
    #     if not index.isValid():
    #         return False
    #     if item_type is None:
    #         return True  # No specific row kind, so always valid
    #     if item_type == GraphItemType.NODE:
    #         return index.parent() == QModelIndex()
    #     elif item_type == GraphItemType.INLET:
    #         return index.parent().isValid() and index.parent().parent() == QModelIndex()
    #     elif item_type == GraphItemType.OUTLET:
    #         return index.parent().isValid() and index.parent().parent() == QModelIndex()
    #     elif item_type == GraphItemType.LINK:
    #         return index.parent().isValid() and index.parent().parent().isValid() and index.parent().parent().parent() == QModelIndex()

    # def itemType(self, row:int, parent:QModelIndex):
    #     index = self._model.index(row, 0, parent)
    #     row_kind = index.data(GraphDataRole.TypeRole)
    #     if not row_kind:
    #         row_kind = self._defaultItemType(row, parent)
    #     assert self._validateItemType(row, parent, row_kind), f"Invalid row kind {row_kind} for index {index}!"
    #     return row_kind
    
    # Handle drag and drop
    def _pathFromIndex(self, index:QModelIndex) -> str:
        """Convert a QModelIndex to a path string. separated by '/'"""
        assert self._adapter, "Model must be set before converting index to path"
        assert index.isValid(), "Index must be valid"
        path = []
        while index.isValid():
            path.append(index.row())
            index = index.parent()

        path = reversed(path)
        path = map(str, path)
        path = "/".join(path)
        return path
    
    def _indexFromPath(self, path:str) -> QModelIndex:
        """Get the QModelIndex from a path.
        path is a '/'-separated string of row numbers.
        For example, "0/1/2" corresponds to the index at row 2 of the child of row 1 of the root node.
        """
        assert self._adapter, "Model must be set before converting path to index"
        assert isinstance(path, str), "Path must be a string"

        index = QModelIndex()
        rows = list(map(int, path.split("/")))
        for row in rows:
            index = self._adapter.index(row, 0, index)
        assert index.isValid(), "Index must be valid"
        return index

    def _createDraftLink(self):
        """Safely create draft link with state tracking"""
        assert self._draft_link is None
            
        self._draft_link = QGraphicsLineItem()
        self._draft_link.setPen(QPen(self.palette().text(), 1))
        self.scene().addItem(self._draft_link)

    def updateDraftLink(self, source:QGraphicsItem|QPointF, target:QGraphicsItem|QPointF):
        """Update the draft link to connect source and target items"""
        assert self._draft_link, "Draft link must be created before updating"
        line = makeLineBetweenShapes(source, target)
        self._draft_link.setLine(line)
 
    def _cleanupDraftLink(self):
        """Safely cleanup draft link"""
        assert self._draft_link
        self.scene().removeItem(self._draft_link)
        self._draft_link = None

    def dragEnterEvent(self, event)->None:
        print("GraphScene DragEnterEvent", event.mimeData().formats())
        super().dragEnterEvent(event)  # Let the scene handle the event normally, which will forward to widgets
        if not event.isAccepted():
            event.acceptProposedAction()
        # event.acceptProposedAction()
    
    def dragMoveEvent(self, event)->None:
        print("dragMoveEvent", event.mimeData().formats())
        super().dragMoveEvent(event) # sLet the scene handle the event normally, which will forward to widgets
        if event.isAccepted():
            return

        if event.mimeData().hasFormat(GraphMimeData.InletData):
            path = event.mimeData().data(GraphMimeData.InletData).toStdString()
            index = self._indexFromPath(path)
            widget = self._row_widgets[QPersistentModelIndex(index)]

            self.updateDraftLink(self.mapToScene(event.position().toPoint()), widget)
            event.acceptProposedAction()

        if event.mimeData().hasFormat(GraphMimeData.OutletData):
            path = event.mimeData().data(GraphMimeData.OutletData).toStdString()
            index = self._indexFromPath(path)
            widget = self._row_widgets[QPersistentModelIndex(index)]

            line = self.updateDraftLink(widget, self.mapToScene(event.position().toPoint()))
            event.acceptProposedAction()

        if event.mimeData().hasFormat(GraphMimeData.LinkTailData):
            print("GraphScene DragMoveEvent LinkTailData", event.mimeData().formats())
            link_path = event.mimeData().data(GraphMimeData.LinkTailData).toStdString()
            link_index = self._indexFromPath(link_path)
            target_index = link_index.parent()

            target_widget = self._row_widgets[QPersistentModelIndex(target_index)]
            mouse_scene_pos = self.mapToScene(event.position().toPoint())
            line = makeLineBetweenShapes(mouse_scene_pos, target_widget)
            
            link_widget = self._row_widgets[QPersistentModelIndex(link_index)]
            line = QLineF(link_widget.mapFromScene(line.p1()), link_widget.mapFromScene(line.p2()))
            link_widget.setLine(line)
            event.acceptProposedAction()

        if event.mimeData().hasFormat(GraphMimeData.LinkHeadData):
            print("GraphScene DragMoveEvent LinkHeadData", event.mimeData().formats())
            link_path = event.mimeData().data(GraphMimeData.LinkHeadData).toStdString()
            link_index = self._indexFromPath(link_path)
            source_index = link_index.data(GraphDataRole.SourceRole)

            source_widget = self._row_widgets[QPersistentModelIndex(source_index)]
            mouse_scene_pos = self.mapToScene(event.position().toPoint())
            line = makeLineBetweenShapes(source_widget, mouse_scene_pos)
            
            link_widget = self._row_widgets[QPersistentModelIndex(link_index)]
            line = QLineF(link_widget.mapFromScene(line.p1()), link_widget.mapFromScene(line.p2()))

            link_widget.setLine(line)
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        print("GraphScene DropEvent", event.mimeData().formats())
        super().dropEvent(event)

        if event.mimeData().hasFormat(GraphMimeData.LinkTailData):
            assert self._model
            link_path = event.mimeData().data(GraphMimeData.LinkTailData).toStdString()
            link_index = self._indexFromPath(link_path)
            if not link_index.isValid():
                print("Link index is not valid, cannot drop link tail")
                return

            if not self._model.data(link_index, GraphDataRole.TypeRole) == GraphItemType.LINK:
                print("Link index must be of type LINK")

            if not link_index.parent().isValid():
                print("Link index must have a parent")
                return

            if not self._model.removeRows(link_index.row(), 1, link_index.parent()):
                print("Failed to remove link row from model")
            return

        if event.mimeData().hasFormat(GraphMimeData.LinkHeadData):
            assert self._model
            link_path = event.mimeData().data(GraphMimeData.LinkHeadData).toStdString()
            link_index = self._indexFromPath(link_path)
            if not link_index.isValid():
                print("Link index is not valid, cannot drop link tail")
                return

            if not self._model.data(link_index, GraphDataRole.TypeRole) == GraphItemType.LINK:
                print("Link index must be of type LINK")

            if not link_index.parent().isValid():
                print("Link index must have a parent")
                return
            
            if not self._model.removeRows(link_index.row(), 1, link_index.parent()):
                print("Failed to remove link row from model")
            return
        
    def dragLeaveEvent(self, event):
        print("GraphScene DragLeaveEvent")
        super().dragLeaveEvent(event)
        self._cleanupDraftLink()


class CellWidget(QGraphicsProxyWidget):
    def __init__(self, parent: QGraphicsItem | None = None):
        super().__init__(parent=parent)
        self._label = QLabel("")
        self._label.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._label.setStyleSheet("background: orange;")
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setWidget(self._label)
        self.setAutoFillBackground(False)
        
        # Make CellWidget transparent to drag events so parent can handle them
        self.setAcceptDrops(False)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)

    def text(self):
        return self._label.text()

    def setText(self, text:str):
        self._label.setText(text)
    
    # def dragEnterEvent(self, event: QGraphicsSceneDragDropEvent) -> None:
    #     # Ignore drag events and let parent handle them
    #     event.ignore()
    
    # def dragMoveEvent(self, event: QGraphicsSceneDragDropEvent) -> None:
    #     # Ignore drag events and let parent handle them
    #     event.ignore()
    
    # def dropEvent(self, event: QGraphicsSceneDragDropEvent) -> None:
    #     # Ignore drop events and let parent handle them
    #     event.ignore()


class BaseRowWidget(QGraphicsWidget):
    def __init__(self, graphview:'GraphView', parent: QGraphicsItem | None = None):
        super().__init__(parent=parent)
        self._view = graphview
        layout = QGraphicsLinearLayout(Qt.Orientation.Vertical)
        self.setLayout(layout)
        

    def addCell(self, cell:CellWidget):
        layout = cast(QGraphicsLinearLayout, self.layout())
        layout.addItem(cell)

    def removeCell(self, cell:CellWidget):
        layout = cast(QGraphicsLinearLayout, self.layout())
        layout.removeItem(cell)


class PortWidget(BaseRowWidget):
    def __init__(self, graphview:'GraphView', parent: QGraphicsItem | None = None):
        super().__init__(graphview, parent=parent)
        self._links:List[LinkWidget] = []
        # self.setGeometry(-14,0,14,14)
        
        self.setLayout(QGraphicsLinearLayout(Qt.Orientation.Horizontal, self))
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
    def __init__(self, graphview:'GraphView', parent: QGraphicsItem | None = None):
        super().__init__(graphview, parent=parent)
        self.setAcceptDrops(True)

    def paint(self, painter, option, /, widget:QWidget|None = None):
        painter.setBrush("lightblue")
        painter.drawRect(option.rect)

    def mousePressEvent(self, event:QGraphicsSceneMouseEvent)->None:
        # Setup new drag
        inlet_index = self._view._row_widgets.inverse[self]
        inlet_path = self._view._pathFromIndex(inlet_index)
        mime = QMimeData()
        mime.setData(GraphMimeData.InletData, inlet_path.encode("utf-8"))
        
        drag = QDrag(self._view)
        drag.setMimeData(mime)

        # Execute drag
        try:
            self._view._createDraftLink()
            action = drag.exec(Qt.DropAction.CopyAction)
            self._view._cleanupDraftLink()
        except Exception as err:
            traceback.print_exc()

        return super().mousePressEvent(event)
    
    def dragEnterEvent(self, event: QGraphicsSceneDragDropEvent) -> None:
        print("INLET: drag enter event", event.mimeData().formats())
        event.setAccepted(True)
        if event.mimeData().hasFormat(GraphMimeData.OutletData):
            event.acceptProposedAction()

    def dragMoveEvent(self, event: QGraphicsSceneDragDropEvent) -> None:
        print("Inlet: drag move event", event.mimeData().formats())
        if event.mimeData().hasFormat(GraphMimeData.OutletData):
            assert self._view
            assert self._view._model
            # parse the target inlet path
            outlet_path = event.mimeData().data(GraphMimeData.OutletData).toStdString()

            outlet_index = self._view._indexFromPath(outlet_path)
            assert outlet_index.isValid(), "Inlet index must be valid"
            
            outlet_widget = self._view._row_widgets[QPersistentModelIndex(outlet_index)]
            assert isinstance(outlet_widget, OutletWidget)

            self._view.updateDraftLink(outlet_widget, self)
            event.acceptProposedAction()

            
        if event.mimeData().hasFormat(GraphMimeData.LinkTailData):
            print("INLET: drag move event link source", event.mimeData().formats())
            assert self._view
            assert self._view._model
            link_path = event.mimeData().data(GraphMimeData.LinkTailData).toStdString()
            link_index = self.indexFromPath(link_path)
            target_index = link_index.parent()

            target_widget = self._row_widgets[QPersistentModelIndex(target_index)]
            mouse_scene_pos = self.mapToScene(event.position().toPoint())
            line = makeLineBetweenShapes(mouse_scene_pos, target_widget)
            
            link_widget = self._row_widgets[QPersistentModelIndex(link_index)]
            line = QLineF(link_widget.mapFromScene(line.p1()), link_widget.mapFromScene(line.p2()))
            link_widget.setLine(line)

        return super().dragMoveEvent(event)
    
    def dropEvent(self, event: QGraphicsSceneDragDropEvent) -> None:
        assert self._view
        assert self._view._model
        print("INLET: drop event", event.mimeData().formats())
        if event.mimeData().hasFormat(GraphMimeData.OutletData):

            outlet_path = event.mimeData().data(GraphMimeData.OutletData).toStdString()
            outlet_index = self._view._indexFromPath(outlet_path)

            # get the source outlet index, the index corresponding to this widget
            inlet_index = self._view.indexFromWidget(self)

            self._view._model.createLink(
                source=outlet_index,
                target=inlet_index
            )

            # self._graphview._model.linkNodes(cast(NodeItem, self.parentItem()).key, target_node, self.key, inlet)
            event.acceptProposedAction()
            return

        return super().dragMoveEvent(event)


class OutletWidget(PortWidget):
    def __init__(self, graphview:'GraphView', parent: QGraphicsItem | None = None):
        super().__init__(graphview, parent=parent)
        self.setAcceptDrops(True)

    def paint(self, painter, option, /, widget:QWidget|None = None):
        painter.setBrush("purple")
        painter.drawRect(option.rect)

    def mousePressEvent(self, event:QGraphicsSceneMouseEvent) -> None:
        assert self._view
        # Setup new drag
        outlet_index = self._view._row_widgets.inverse[self]
        assert outlet_index.isValid(), "Outlet index must be valid"
        outlet_path = self._view._pathFromIndex(outlet_index)
        mime = QMimeData()
        mime.setData(GraphMimeData.OutletData, outlet_path.encode("utf-8"))
        drag = QDrag(self._view)
        drag.setMimeData(mime)

        # Execute drag
        try:
            self._view._createDraftLink()
            action = drag.exec(Qt.DropAction.CopyAction)
            self._view._cleanupDraftLink()
        except Exception as err:
            traceback.print_exc()
        return super().mousePressEvent(event)

    def dragEnterEvent(self, event: QGraphicsSceneDragDropEvent) -> None:
        print("OUTLET: drag enter event", event.mimeData().formats())
        event.setAccepted(True)
        if event.mimeData().hasFormat(GraphMimeData.InletData):
            event.acceptProposedAction() # Todo: set accepted action
            return

        if event.mimeData().hasFormat(GraphMimeData.LinkHeadData):
            event.acceptProposedAction()
            return

    def dragMoveEvent(self, event: QGraphicsSceneDragDropEvent) -> None:
        print("OUTLET: drag move event", event.mimeData().formats())
        if event.mimeData().hasFormat(GraphMimeData.InletData):
            assert self._view
            assert self._view._model
            # parse the target inlet path
            inlet_path = event.mimeData().data(GraphMimeData.InletData).toStdString()

            inlet_index = self._view._indexFromPath(inlet_path)
            assert inlet_index.isValid(), "Inlet index must be valid"
            
            inlet_widget = self._view._row_widgets[QPersistentModelIndex(inlet_index)]
            assert isinstance(inlet_widget, InletWidget), "Inlet must be a child of InletWidget"
            self._view.updateDraftLink(self, inlet_widget)
            event.acceptProposedAction()
            return
            
        if event.mimeData().hasFormat(GraphMimeData.LinkHeadData):
            assert self._view
            assert self._view._model
            # parse the target inlet path
            link_path = event.mimeData().data(GraphMimeData.LinkHeadData).toStdString()

            link_index = self._view._indexFromPath(link_path)
            assert link_index.isValid(), "Link target index must be valid"
            
            link_widget = self._view._row_widgets[QPersistentModelIndex(link_index)]
            assert isinstance(link_widget, LinkWidget), "Link target must be a child of LinkWidget"
            source_index = self._link_source[QPersistentModelIndex(link_index)]
            source_widget = self._view._row_widgets[source_index]
            line = makeLineBetweenShapes(source_widget, self)
            link_widget.setLine(line)
            return

        return super().dragMoveEvent(event)
    
    def dropEvent(self, event: QGraphicsSceneDragDropEvent) -> None:
        print("OUTLET: drop event", event.mimeData().formats())
        if event.mimeData().hasFormat(GraphMimeData.InletData):
            assert self._view
            assert self._view._model
            inlet_path = event.mimeData().data(GraphMimeData.InletData).toStdString()
            target_inlet_index = self._view._indexFromPath(inlet_path)

            # get the source outlet index, the index corresponding to this widget
            source_outlet_index = self._view.indexFromWidget(self)

            self._view._model.createLink(
                source_outlet_index,
                target_inlet_index
            )

            # self._graphview._model.linkNodes(cast(NodeItem, self.parentItem()).key, target_node, self.key, inlet)
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
    
    def removeCell(self, cell):
        return super().removeCell(cell)

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

        self._source: QGraphicsItem | None = None
        self._target: QGraphicsItem | None = None

    def boundingRect(self):
        _ = QRectF(self._line.p1(), self._line.p2())
        _ = _.normalized()
        _ = _.adjusted(-5,-5,5,5)
        return _
    
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
        arrow = makeArrowShape(self._line, 2)
        painter.drawPath(arrow)

    def link(self, source:QGraphicsItem|None, target:QGraphicsItem|None):
        """Link this widget to a source and target item."""
        self.unlink()  # Unlink any existing connections
        self._source = source
        self._target = target
        source._links.append(self)
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
            source_pos = self._source.scenePos()-self.scenePos()
            line = QLineF(source_pos, source_pos+QPointF(100,100))
            line = QLineF(self.mapFromScene(line.p1()), self.mapFromScene(line.p2()))
            self.setLine(line)
        elif self._target:
            target_pos = self._target.scenePos()-self.scenePos()
            line = QLineF(target_pos-QPointF(100,100), target_pos)
            line = QLineF(self.mapFromScene(line.p1()), self.mapFromScene(line.p2()))
            self.setLine(line)
        else:
            ...

    def mousePressEvent(self, event:QGraphicsSceneMouseEvent) -> None:
        assert self._view
        source_distance = (event.pos() - self.line().p1()).manhattanLength()
        target_distance = (event.pos() - self.line().p2()).manhattanLength()
        if source_distance < target_distance:
            mime = QMimeData()
            link_index = self._view._row_widgets.inverse[self]
            assert link_index.isValid(), "Link index must be valid"
            link_path = self._view._pathFromIndex(link_index)
            mime.setData(GraphMimeData.LinkTailData, link_path.encode("utf-8"))
            drag = QDrag(self._view)
            drag.setMimeData(mime)
            
            # Execute drag
            try:
                action = drag.exec(Qt.DropAction.TargetMoveAction)
                print("Link drag action:", action)
            except Exception as err:
                traceback.print_exc()
        else:
            # Setup new drag
            mime = QMimeData()
            link_index = self._view._row_widgets.inverse[self]
            assert link_index.isValid(), "Link index must be valid"
            link_path = self._view._pathFromIndex(link_index)
            mime.setData(GraphMimeData.LinkHeadData, link_path.encode("utf-8"))
            drag = QDrag(self._view)
            drag.setMimeData(mime)
            
            # Execute drag
            try:
                action = drag.exec(Qt.DropAction.TargetMoveAction)
            except Exception as err:
                traceback.print_exc()

