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
    
    def linkSource(self, link:QModelIndex|QPersistentModelIndex=QModelIndex()) -> QPersistentModelIndex:
        """
        Get the source of a link in the graph.
        This returns the QModelIndex of the source of the link at the specified index.
        """
        assert self._sourceModel, "Source model must be set before getting link source"
        index = self._sourceModel.index(link.row(), 0, link.parent())
        return QPersistentModelIndex(index.data(GraphDataRole.SourceRole))
    
    def linkTarget(self, link:QModelIndex|QPersistentModelIndex=QModelIndex()) -> QPersistentModelIndex:
        """
        Get the target of a link in the graph.
        This returns the QModelIndex of the target of the link at the specified index.
        """
        assert self._sourceModel, "Source model must be set before getting link target"
        index = self._sourceModel.index(link.row(), 0, link.parent())
        return QPersistentModelIndex(index.parent())

    def nodeDataCount(self, node:QModelIndex|QPersistentModelIndex=QModelIndex()) -> int:
        """
        Get the number of data items for a node in the graph.
        This returns the number of data items for the node at the specified index.
        """
        assert self._sourceModel, "Source model must be set before getting node data count"
        return self._sourceModel.rowCount(node)

    def nodeData(self, node:QModelIndex|QPersistentModelIndex=QModelIndex(), role:int=Qt.ItemDataRole.DisplayRole) -> Any:
        """
        Get the data for a node in the graph.
        This returns the data for the node at the specified column.
        """
        assert self._sourceModel, "Source model must be set before getting node data"
        index = self._sourceModel.index(node.row(), node.parent())
        return index.data(role)
    
    def inletData(self, inlet:QModelIndex|QPersistentModelIndex=QModelIndex(), role:int=Qt.ItemDataRole.DisplayRole) -> Any:
        """
        Get the data for an inlet in the graph.
        This returns the data for the inlet at the specified column.
        """
        assert self._sourceModel, "Source model must be set before getting inlet data"
        index = self._sourceModel.index(inlet.row(), 0, inlet.parent())
        return index.data(Qt.ItemDataRole.DisplayRole)
    
    def outletData(self, outlet:QModelIndex|QPersistentModelIndex=QModelIndex(), role:int=Qt.ItemDataRole.DisplayRole) -> Any:
        """
        Get the data for an outlet in the graph.
        This returns the data for the outlet at the specified column.
        """
        assert self._sourceModel, "Source model must be set before getting outlet data"
        index = self._sourceModel.index(outlet.row(), column, outlet.parent())
        return index.data(Qt.ItemDataRole.DisplayRole)

    def linkData(self, link:QModelIndex|QPersistentModelIndex=QModelIndex(), role:int=Qt.ItemDataRole.DisplayRole) -> Any:
        """
        Get the data for a link in the graph.
        This returns the data for the link at the specified column.
        """
        assert self._sourceModel, "Source model must be set before getting link data"
        index = self._sourceModel.index(link.row(), 0, link.parent())
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
            return GraphItemType.SUBGRAPH
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

        if item_type is None:
            return True  # No specific row kind, so always valid
        elif item_type == GraphItemType.SUBGRAPH:
            return not index.isValid()
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
        assert self._sourceModel, "Source model must be set before adding a link"
        assert isinstance(outlet, QPersistentModelIndex), "Outlet must be a QPersistentModelIndex, got: {outlet}"
        assert isinstance(inlet, QPersistentModelIndex), f"Inlet must be a QPersistentModelIndex, got: {inlet}"
        assert outlet.isValid(), "Outlet index must be valid"
        assert inlet.isValid(), "Inlet index must be valid"
        self._sourceModel.createLink(
            source=outlet,
            target=inlet
        )

    def removeLink(self, link:QPersistentModelIndex):
        """
        Remove a link from the graph.
        This removes the link at the specified index from the model.
        """
        assert self._sourceModel, "Source model must be set before removing a link"
        assert isinstance(link, QPersistentModelIndex), f"Link must be a QPersistentModelIndex, got: {link}"
        assert link.isValid(), "Link index must be valid"
        self._sourceModel.removeRows(link.row(), 1, link.parent())

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

    def decodeInletMimeData(self, mime:QMimeData) -> QPersistentModelIndex:
        """
        Decode a QMimeData object to a persistent model index.
        This is used to get the original index from the mime data.
        """
        if not mime.hasFormat(GraphMimeData.InletData):
            return QPersistentModelIndex()
        
        path = mime.data(GraphMimeData.InletData).data().decode("utf-8")
        path = list(map(int, path.split("/")))

        idx = self._sourceModel.index(path[0], 0, QModelIndex())
        for row in path[1:]:
            idx = self._sourceModel.index(row, 0, idx)
        return QPersistentModelIndex(idx)
    
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
    
    def decodeOutletMimeData(self, mime:QMimeData) -> QPersistentModelIndex:
        """
        Decode a QMimeData object to a persistent model index.
        This is used to get the original index from the mime data.
        """
        if not mime.hasFormat(GraphMimeData.OutletData):
            return QPersistentModelIndex()
        
        path = mime.data(GraphMimeData.OutletData).data().decode("utf-8")
        path = list(map(int, path.split("/")))

        idx = self._sourceModel.index(path[0], 0, QModelIndex())
        for row in path[1:]:
            idx = self._sourceModel.index(row, 0, idx)
        return QPersistentModelIndex(idx)
    
    def linkTailMimeData(self, link:QPersistentModelIndex) -> QMimeData:
        """
        Create a QMimeData object for a link source.
        This is used to provide data for drag-and-drop operations.
        """
        mime = QMimeData()

        # Convert index to path string
        path = []
        idx = link
        while idx.isValid():
            path.append(idx.row())
            idx = idx.parent()
        path = "/".join(map(str, reversed(path)))
        mime.setData(GraphMimeData.LinkTailData, path.encode("utf-8"))
        return mime
    
    def decodeLinkTailMimeData(self, mime:QMimeData) -> QPersistentModelIndex:
        """
        Decode a QMimeData object to a persistent model index.
        This is used to get the original index from the mime data.
        """
        if not mime.hasFormat(GraphMimeData.LinkTailData):
            return QPersistentModelIndex()
        
        path = mime.data(GraphMimeData.LinkTailData).data().decode("utf-8")
        path = list(map(int, path.split("/")))

        idx = self._sourceModel.index(path[0], 0, QModelIndex())
        for row in path[1:]:
            idx = self._sourceModel.index(row, 0, idx)
        return QPersistentModelIndex(idx)
    
    def linkHeadMimeData(self, link:QPersistentModelIndex) -> QMimeData:
        """
        Create a QMimeData object for a link head.
        This is used to provide data for drag-and-drop operations.
        """
        mime = QMimeData()

        # Convert index to path string
        path = []
        idx = link
        while idx.isValid():
            path.append(idx.row())
            idx = idx.parent()
        path = "/".join(map(str, reversed(path)))
        mime.setData(GraphMimeData.LinkHeadData, path.encode("utf-8"))
        return mime

    def decodeLinkHeadMimeData(self, mime:QMimeData) -> QPersistentModelIndex:
        """
        Decode a QMimeData object to a persistent model index.
        This is used to get the original index from the mime data.
        """
        if not mime.hasFormat(GraphMimeData.LinkHeadData):
            return QPersistentModelIndex()
        
        path = mime.data(GraphMimeData.LinkHeadData).data().decode("utf-8")
        path = list(map(int, path.split("/")))

        idx = self._sourceModel.index(path[0], 0, QModelIndex())
        for row in path[1:]:
            idx = self._sourceModel.index(row, 0, idx)
        return QPersistentModelIndex(idx)
    
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
                    self.nodeAdded.emit(QPersistentModelIndex(index))
                case GraphItemType.INLET:
                    self.inletAdded.emit(QPersistentModelIndex(index))
                case GraphItemType.OUTLET:
                    self.outletAdded.emit(QPersistentModelIndex(index))
                case GraphItemType.LINK:
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
        assert self._sourceModel

        def children(index:QModelIndex):
            for row in range(self._sourceModel.rowCount(parent=index)):
                yield self._sourceModel.index(row, 0, index)        # Breadth-first search

        root = [self._sourceModel.index(row, 0, parent) for row in range(first, last + 1)]

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
        # if GraphDataRole.SourceRole in roles or roles == []:
        #     for row in range(topLeft.row(), bottomRight.row()+1):
        #         if self.itemType(row, topLeft.parent()) == GraphItemType.LINK:
        #             persistent_link_index = QPersistentModelIndex(topLeft.siblingAtRow(row))
        #             new_source_index = persistent_link_index.data(GraphDataRole.SourceRole)
        #             previous_source_index = self._link_source[persistent_link_index]
        #             if previous_source_index != new_source_index:
        #                 self.linkAboutToBeRemoved.emit(persistent_link_index)
        #                 self.linkAdded.emit(QPersistentModelIndex(persistent_link_index))

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
    
    def canDropMimeData(self, data:QMimeData, action:Qt.DropAction, drop_target:QPersistentModelIndex) -> bool:
        """
        Check if the mime data can be dropped on the graph view.
        This is used to determine if the drag-and-drop operation is valid.
        """
        drop_target_type = self.itemType(drop_target.row(), drop_target.parent())
        if data.hasFormat(GraphMimeData.OutletData):
            return True
        
        elif data.hasFormat(GraphMimeData.InletData):
            return True
        
        elif data.hasFormat(GraphMimeData.LinkTailData):
            return True
        
        elif data.hasFormat(GraphMimeData.LinkHeadData):
            return True
        
        return False

    def dropMimeData(self, data:QMimeData, action:Qt.DropAction, drop_target:QPersistentModelIndex) -> bool:
        if data.hasFormat(GraphMimeData.OutletData):
            # outlet dropped
            outlet_index = self.decodeOutletMimeData(data)
            assert outlet_index.isValid(), "Outlet index must be valid"
            if drop_target.data(GraphDataRole.TypeRole) == GraphItemType.INLET:
                # ... on inlet
                inlet_index = drop_target
                self.addLink(outlet_index, inlet_index)
                return True

        if data.hasFormat(GraphMimeData.InletData):
            # inlet dropped
            inlet_index = self.decodeInletMimeData(data)
            assert inlet_index.isValid(), "Inlet index must be valid"
            if drop_target.data(GraphDataRole.TypeRole) == GraphItemType.OUTLET:
                # ... on outlet
                outlet_index = drop_target
                self.addLink(outlet_index, inlet_index)
                return True
            
        if data.hasFormat(GraphMimeData.LinkTailData):
            # link tail dropped
            link_index = self.decodeLinkTailMimeData(data)
            assert link_index.isValid(), "Link index must be valid"
            if drop_target.data(GraphDataRole.TypeRole) == GraphItemType.INLET:
                # ... on inlet
                inlet_index = drop_target
                self.removeLink(link_index)
                self.addLink(link_index, inlet_index)
                return True
            else:
                self.removeLink(link_index)
                return True
            
        if data.hasFormat(GraphMimeData.LinkHeadData):
            # link head dropped
            link_index = self.decodeLinkHeadMimeData(data)
            assert link_index.isValid(), "Link index must be valid"
            if drop_target.data(GraphDataRole.TypeRole) == GraphItemType.OUTLET:
                # ... on outlet
                outlet_index = drop_target
                self.removeLink(link_index)
                self.addLink(outlet_index, link_index)
                return True
            else:
                self.removeLink(link_index)
                return True
    
        return False


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
        self._node_widgets: bidict[QPersistentModelIndex, NodeWidget] = bidict()
        self._inlet_widgets: bidict[QPersistentModelIndex, InletWidget] = bidict()
        self._outlet_widgets: bidict[QPersistentModelIndex, OutletWidget] = bidict()
        self._link_widgets: bidict[QPersistentModelIndex, LinkWidget] = bidict()
        self._cell_widgets: bidict[QPersistentModelIndex, CellWidget] = bidict()

        self._draft_link: QGraphicsLineItem | None = None
        self._state = GraphView.State.IDLE
        self.setupUI()
        self.setAcceptDrops(True)

    def nodeFromWidget(self, widget:NodeWidget) -> QPersistentModelIndex:
        """
        Get the index of the node widget in the model.
        This is used to identify the node in the model.
        """
        return QPersistentModelIndex(self._node_widgets.inverse[widget])
    
    def widgetFromNode(self, index:QModelIndex) -> NodeWidget:
        """
        Get the widget from the index.
        This is used to identify the node in the model.
        """
        return self._node_widgets[QPersistentModelIndex(index)]
    
    def inletFromWidget(self, widget:InletWidget) -> QPersistentModelIndex:
        """
        Get the index of the inlet widget in the model.
        This is used to identify the inlet in the model.
        """
        return QPersistentModelIndex(self._inlet_widgets.inverse[widget])
    
    def widgetFromInlet(self, index:QModelIndex) -> InletWidget:
        """
        Get the widget from the index.
        This is used to identify the inlet in the model.
        """
        return self._inlet_widgets[QPersistentModelIndex(index)]
    
    def outletFromWidget(self, widget:OutletWidget) -> QPersistentModelIndex:
        """
        Get the index of the outlet widget in the model.
        This is used to identify the outlet in the model.
        """
        return QPersistentModelIndex(self._outlet_widgets.inverse[widget])
    
    def widgetFromOutlet(self, index:QModelIndex) -> OutletWidget:
        """
        Get the widget from the index.
        This is used to identify the outlet in the model.
        """
        return self._outlet_widgets[QPersistentModelIndex(index)]
    
    def linkFromWidget(self, widget:LinkWidget) -> QPersistentModelIndex:
        """
        Get the index of the link widget in the model.
        This is used to identify the link in the model.
        """
        return QPersistentModelIndex(self._link_widgets.inverse[widget])
    
    def widgetFromLink(self, index:QModelIndex) -> LinkWidget:
        """
        Get the widget from the index.
        This is used to identify the link in the model.
        """
        return self._link_widgets[QPersistentModelIndex(index)]

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


            self._adapter_connections = [
                (adapter.nodeAdded, self._add_node_widget),
                (adapter.nodeAboutToBeRemoved, self._remove_node_widget),
                (adapter.inletAdded, self._add_inlet_widget),
                (adapter.inletAboutToBeRemoved, self._remove_inlet_widget),
                (adapter.outletAdded, self._add_outlet_widget),
                (adapter.outletAboutToBeRemoved, self._remove_outlet_widget),
                (adapter.linkAdded, self._add_link_widget),
                (adapter.linkAboutToBeRemoved, self._remove_link_widget),
                (adapter.nodeDataChanged, self._set_node_data)
            ]

            for signal, slot in self._adapter_connections:
                signal.connect(slot)
        self._adapter = adapter
        
        # populate initial scene
        ## clear
        self.scene().clear()
        self._node_widgets.clear()
        self._inlet_widgets.clear()
        self._outlet_widgets.clear()
        self._link_widgets.clear()
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
    def _add_node_widget(self, index:QPersistentModelIndex):
        #add widget to view
        assert isinstance(index, QPersistentModelIndex), f"Index must be a QPersistentModelIndex, got: {index}"
        assert index.column()==0, "Index must be in the first column"
        widget = NodeWidget(graphview=self)
        self._node_widgets[index] = widget

        title_widget = CellWidget()
        title_widget.setText(index.data(Qt.ItemDataRole.DisplayRole))
        widget.addCell(title_widget)

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

        self._inlet_widgets[index] = widget
        title_widget = CellWidget()
        title_widget.setText(index.data(Qt.ItemDataRole.DisplayRole))
        widget.addCell(title_widget)

        # attach to parent widget
        if index.parent().isValid():
            parent_widget = self._node_widgets[QPersistentModelIndex(index.parent())]
            if not isinstance(parent_widget, NodeWidget):
                raise ValueError("inlets must have a Node parent")
            parent_widget = cast(NodeWidget, parent_widget)
            parent_widget.addInlet(widget)
        else:
            raise NotImplementedError("root graph inlets are not yet implemented!")
        
        return widget
    
    def _add_outlet_widget(self, index:QPersistentModelIndex):
        """add widget to view"""
        assert isinstance(index, QPersistentModelIndex), "Index must be a QPersistentModelIndex"
        assert index.column()==0, "Index must be in the first column"
        widget = OutletWidget(graphview=self)
        self._outlet_widgets[index] = widget
        title_widget = CellWidget()
        title_widget.setText(index.data(Qt.ItemDataRole.DisplayRole))
        widget.addCell(title_widget)
        self.scene().addItem(widget)


        # attach to parent widget
        if index.parent().isValid():
            parent_widget = self._node_widgets[QPersistentModelIndex(index.parent())]
            parent_widget = cast(NodeWidget, parent_widget)
            parent_widget.addOutlet(widget)

        return widget
    
    def _add_link_widget(self, index:QPersistentModelIndex):
        # add widget
        assert isinstance(index, QPersistentModelIndex), "Index must be a QPersistentModelIndex"
        assert index.column()==0, "Index must be in the first column"
        target_index = index.parent()
        
        link_widget = LinkWidget(graphview=self)
        self._link_widgets[index] = link_widget
        title_widget = CellWidget()
        title_widget.setText(index.data(Qt.ItemDataRole.DisplayRole))
        link_widget.addCell(title_widget)
        self.scene().addItem(link_widget)

        # attach to parent widget
        # def get_target_index():
        
        target_index = index.parent()
        source_index = index.data(GraphDataRole.SourceRole)
        if not target_index.isValid():
            raise ValueError("Link's target is invalid")
        if not source_index.isValid():
            raise ValueError("link's source is invalid")
        
        source_outlet = self._outlet_widgets[QPersistentModelIndex(source_index)]
        target_inlet = self._inlet_widgets[QPersistentModelIndex(target_index)]
        link_widget.link(source_outlet, target_inlet)

        return link_widget

    def _remove_node_widget(self, index:QPersistentModelIndex):
        """Remove a node widget"""
        assert isinstance(index, QPersistentModelIndex), "Index must be a QPersistentModelIndex"
        assert index.column()==0, "Index must be in the first column"
        
        # Remove all cell widgets for this node
        self._remove_cell_widgets(index.row(), index.parent() )

        # remove widget from graphview
        widget = self._node_widgets[index]
        del self._node_widgets[index]
        
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
        widget = self._inlet_widgets[index]
        del self._inlet_widgets[index]

        # detach widget from scene (or parent widget)
        if index.parent().isValid():
            parent_widget = self._node_widgets[QPersistentModelIndex(index.parent())]
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
        widget = self._outlet_widgets[index]
        del self._outlet_widgets[index]
        
        # detach widget from scene (or parent widget)
        if index.parent().isValid():
            parent_widget = self._node_widgets[QPersistentModelIndex(index.parent())]
            parent_widget = cast(NodeWidget, parent_widget)
            parent_widget.removeOutlet(widget)
        else:
            raise NotImplementedError("support inlets attached to the root graph")
        
    def _remove_link_widget(self, index:QPersistentModelIndex):
        """Remove an inlet widget and its associated cell widgets."""
        assert isinstance(index, QPersistentModelIndex), "Index must be a QPersistentModelIndex"
        assert index.column()==0, "Index must be in the first column"
        widget = self._link_widgets[index]
        # detach widget from scene (or parent widget)
        link_widget = cast(LinkWidget, widget)
        
        # link_widget.deleteLater()  # Schedule for deletion
        # link_widget.setParentItem(None)
        # self.scene().removeItem(link_widget)

        # Remove all cell widgets for this inlet
        self._remove_cell_widgets(index.row(), index.parent())
        
        # remove widget from graphview
        
        assert isinstance(widget, LinkWidget), "Link widget must be of type LinkWidget"
        del self._link_widgets[index]

        self.scene().removeItem(link_widget)  # Remove from scene immediately

    def _set_node_data(self, index:QPersistentModelIndex, column:int, roles:list):
        """Set the data for a node widget."""
        assert isinstance(index, QPersistentModelIndex), "Index must be a QPersistentModelIndex"
        assert index.column() == 0, "Index must be in the first column"
        assert index in self._node_widgets, f"Index {index} not found in row widgets"

        widget = self._node_widgets[index]
        if not isinstance(widget, NodeWidget):
            raise ValueError(f"Widget for index {index} is not a NodeWidget")
        
        # update cell widgets

        cell_index = index.sibling(index.row(), column)
        widget = self._cell_widgets[QPersistentModelIndex(cell_index)]
        proxy = cast(QGraphicsProxyWidget, widget)
        label = proxy.widget()
        assert isinstance(label, QLabel)
        label.setText(cell_index.data(Qt.ItemDataRole.DisplayRole))

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
        if self._draft_link is None:
            return
        
        self.scene().removeItem(self._draft_link)
        self._draft_link = None

    def dragEnterEvent(self, event)->None:
        print("GraphScene DragEnterEvent", event.mimeData().formats())
        if event.mimeData().hasFormat(GraphMimeData.InletData) or event.mimeData().hasFormat(GraphMimeData.OutletData):
            # Create a draft link if the mime data is for inlets or outlets
            self._createDraftLink()
            event.acceptProposedAction()
        if event.mimeData().hasFormat(GraphMimeData.LinkHeadData) or event.mimeData().hasFormat(GraphMimeData.LinkTailData):
            # Create a draft link if the mime data is for link heads or tails
            event.acceptProposedAction()

    def dragMoveEvent(self, event)->None:
        """Handle drag move events to update draft link position"""
        print("GraphScene DragMoveEvent", event.mimeData().formats())
        if event.mimeData().hasFormat(GraphMimeData.OutletData):
            # Outlet dragged
            outlet_index = self._adapter.decodeOutletMimeData(event.mimeData())
            assert outlet_index.isValid(), "Outlet index must be valid"
            outlet_widget = self._outlet_widgets[outlet_index]
            if inlet_index:=self.inletAt(event.position().toPoint()):
                # ...over inlet
                if self._adapter.canDropMimeData(event.mimeData(), event.dropAction(), inlet_index):
                    inlet_widget = self._inlet_widgets[inlet_index]
                    self.updateDraftLink(source=outlet_widget, target=inlet_widget)
                    event.acceptProposedAction()
                    return
            else:
                # ...over empty space
                self.updateDraftLink(source=outlet_widget, target=self.mapToScene(event.position().toPoint()))
                event.acceptProposedAction() 
                return
        
        if event.mimeData().hasFormat(GraphMimeData.InletData):
            # inlet dragged
            inlet_index = self._adapter.decodeInletMimeData(event.mimeData())
            assert inlet_index.isValid(), "Inlet index must be valid"
            inlet_widget = self._inlet_widgets[inlet_index]
            if outlet_index:= self.outletAt(event.position().toPoint()):
                # ... over outlet
                if self._adapter.canDropMimeData(event.mimeData(), event.dropAction(), outlet_index):
                    outlet_widget = self._outlet_widgets[outlet_index]
                    self.updateDraftLink(source=outlet_widget, target=inlet_widget)
                    event.acceptProposedAction()
                    return
            else:
                # ... over empty space
                self.updateDraftLink(source=self.mapToScene(event.position().toPoint()), target=inlet_widget)
                event.acceptProposedAction() 
                return
        
        if event.mimeData().hasFormat(GraphMimeData.LinkHeadData):
            # link head dragged
            print("GraphScene DragMoveEvent: Link Head")
            link_index = self._adapter.decodeLinkHeadMimeData(event.mimeData())
            assert link_index.isValid(), "Link index must be valid"
            link_widget = self._link_widgets[QPersistentModelIndex(link_index)]
            if inlet_index := self.inletAt(event.position().toPoint()):
                # ...over inlet
                inlet_widget = self._inlet_widgets[inlet_index]
                link_widget.setLine(makeLineBetweenShapes(link_widget._source, inlet_widget))
                event.acceptProposedAction()
                return
            else:
                # ... over empty space
                link_widget.setLine(makeLineBetweenShapes(link_widget._source, self.mapToScene(event.position().toPoint())))
                event.acceptProposedAction()
                return

        if event.mimeData().hasFormat(GraphMimeData.LinkTailData):
            # link tail dragged
            link_index = self._adapter.decodeLinkTailMimeData(event.mimeData())
            assert link_index.isValid(), "Link index must be valid"
            link_widget = self._link_widgets[QPersistentModelIndex(link_index)]
            if outlet_index := self.outletAt(event.position().toPoint()):
                # ...over outlet
                outlet_widget = self._outlet_widgets[outlet_index]
                link_widget.setLine(makeLineBetweenShapes(outlet_widget, link_widget._target))
                event.acceptProposedAction()
                return
            else:
                # ... over empty space
                link_widget.setLine(makeLineBetweenShapes(self.mapToScene(event.position().toPoint()), link_widget._target))
                event.acceptProposedAction()
                return
            
    def dropEvent(self, event: QDropEvent) -> None:
        print("GraphScene DropEvent", event.mimeData().formats())
        drop_target = self.indexAt(event.position().toPoint())
        if self._adapter.dropMimeData(event.mimeData(), event.dropAction(), drop_target):
            event.acceptProposedAction()
        else:
            event.ignore()

        if event.mimeData().hasFormat(GraphMimeData.LinkHeadData):
            link_index = self._adapter.decodeLinkHeadMimeData(event.mimeData())
            link_widget = self._link_widgets[QPersistentModelIndex(link_index)]
            link_widget.updateLine()  # Ensure the link line is updated after drop

        if event.mimeData().hasFormat(GraphMimeData.LinkTailData):
            link_index = self._adapter.decodeLinkTailMimeData(event.mimeData())
            link_widget = self._link_widgets[QPersistentModelIndex(link_index)]
            link_widget.updateLine()  # Ensure the link line is updated after drop

        self._cleanupDraftLink()

    def dragLeaveEvent(self, event):
        print("GraphScene DragLeaveEvent")
        self._cleanupDraftLink()  # Cleanup draft link if it exists
        # super().dragLeaveEvent(event)
        # self._cleanupDraftLink()

    def outletAt(self, pos:QPointF) -> QPersistentModelIndex|None:
        """
        Find the outlet at the given position.
        This is used to determine if a drag operation is valid.
        """
        for item in self.items(pos):
            if item in self._outlet_widgets.values():
                index = self._outlet_widgets.inverse[item]
                return QPersistentModelIndex(index)

        return None
    
    def inletAt(self, pos:QPointF) -> QPersistentModelIndex|None:
        for item in self.items(pos):
            if item in self._inlet_widgets.values():
                index = self._inlet_widgets.inverse[item]
                return QPersistentModelIndex(index)

        return None
    
    def indexAt(self, pos:QPointF) -> QPersistentModelIndex:
        """
        Find the index at the given position.
        This is used to determine if a drag operation is valid.
        """
        for item in self.items(pos):
            if item in self._node_widgets.values():
                index = self._node_widgets.inverse[item]
                return QPersistentModelIndex(index)
            elif item in self._inlet_widgets.values():
                index = self._inlet_widgets.inverse[item]
                return QPersistentModelIndex(index)
            elif item in self._outlet_widgets.values():
                index = self._outlet_widgets.inverse[item]
                return QPersistentModelIndex(index)
            elif item in self._link_widgets.values():
                index = self._link_widgets.inverse[item]
                return QPersistentModelIndex(index)

        return QPersistentModelIndex()




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

    def mousePressEvent(self, event:QGraphicsSceneMouseEvent) -> None:
        assert self._view
        # Setup new drag
        index = self._view._inlet_widgets.inverse[self]
        
        assert index.isValid(), "Outlet index must be valid"
        mime = self._view._adapter.inletMimeData(index)
        drag = QDrag(self._view)
        drag.setMimeData(mime)

        # Execute drag
        try:
            # self._view._createDraftLink()
            action = drag.exec(Qt.DropAction.CopyAction)
            # self._view._cleanupDraftLink()
        except Exception as err:
            traceback.print_exc()
        return super().mousePressEvent(event)
    
    # def dragEnterEvent(self, event: QGraphicsSceneDragDropEvent) -> None:
    #     event.setAccepted(True)
    #     if event.mimeData().hasFormat(GraphMimeData.OutletData):
    #         event.acceptProposedAction()

    # def dragMoveEvent(self, event: QGraphicsSceneDragDropEvent) -> None:
    #     if event.mimeData().hasFormat(GraphMimeData.OutletData):
    #         assert self._view
    #         assert self._view._adapter

    #         mime = event.mimeData()
    #         outlet_index = self._view._adapter.decodeOutletMimeData(mime)
    #         assert outlet_index.isValid(), "Inlet index must be valid"
    #         outlet_widget = self._view.widgetFromIndex(outlet_index)
    #         assert isinstance(outlet_widget, OutletWidget)
    #         self._view.updateDraftLink(outlet_widget, self)
    #         event.acceptProposedAction()
    #     else:
    #         event.ignore()
    
    # def dropEvent(self, event: QGraphicsSceneDragDropEvent) -> None:
    #     assert self._view
    #     assert self._view._adapter
    #     if self._view._adapter.dropMimeData(event.mimeData(), event.proposedAction(), self._view.indexFromWidget(self)):
    #         event.acceptProposedAction()

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
        outlet_index = self._view._outlet_widgets.inverse[self]
        
        assert outlet_index.isValid(), "Outlet index must be valid"
        mime = self._view._adapter.outletMimeData(outlet_index)
        drag = QDrag(self._view)
        drag.setMimeData(mime)

        # Execute drag
        try:
            # self._view._createDraftLink()
            action = drag.exec(Qt.DropAction.CopyAction)
            # self._view._cleanupDraftLink()
        except Exception as err:
            traceback.print_exc()
        return super().mousePressEvent(event)

    # def dragEnterEvent(self, event: QGraphicsSceneDragDropEvent) -> None:
    #     event.setAccepted(True)
    #     if event.mimeData().hasFormat(GraphMimeData.InletData):
    #         event.acceptProposedAction()

    # def dragMoveEvent(self, event: QGraphicsSceneDragDropEvent) -> None:
    #     if event.mimeData().hasFormat(GraphMimeData.InletData):
    #         assert self._view
    #         assert self._view._adapter

    #         mime = event.mimeData()
    #         inlet_index = self._view._adapter.decodeInletMimeData(mime)
    #         assert inlet_index.isValid(), "Inlet index must be valid"
    #         inlet_widget = self._view.widgetFromIndex(inlet_index)
    #         assert isinstance(inlet_widget, InletWidget)
    #         self._view.updateDraftLink(self, inlet_widget)
    #         event.acceptProposedAction()
    #     else:
    #         event.ignore()

    #     return super().dragMoveEvent(event)
    
    # def dropEvent(self, event: QGraphicsSceneDragDropEvent) -> None:
    #     assert self._view
    #     assert self._view._adapter
    #     if self._view._adapter.dropMimeData(event.mimeData(), event.proposedAction(), self._view.indexFromWidget(self)):
    #         event.acceptProposedAction()



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
        self.setAcceptHoverEvents(True)

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
        stroker.setWidth(4)
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
        tail_distance = (event.pos() - self.line().p1()).manhattanLength()
        head_distance = (event.pos() - self.line().p2()).manhattanLength()
        if tail_distance < head_distance:
            assert self._view
            # Setup new drag
            index = self._view._link_widgets.inverse[self]

            
            assert index.isValid(), "Link index must be valid"
            mime = self._view._adapter.linkTailMimeData(index)
            drag = QDrag(self._view)
            drag.setMimeData(mime)

            # Execute drag
            try:

                action = drag.exec(Qt.DropAction.CopyAction)
            except Exception as err:
                traceback.print_exc()
            return super().mousePressEvent(event)
        else:
            assert self._view
            # Setup new drag
            index = self._view._link_widgets.inverse[self]
            
            assert index.isValid(), "Link index must be valid"
            mime = self._view._adapter.linkHeadMimeData(index)
            drag = QDrag(self._view)
            drag.setMimeData(mime)

            # Execute drag
            try:
                action:Qt.DropAction = drag.exec(Qt.DropAction.CopyAction)
                match action:
                    case Qt.DropAction.CopyAction:
                        print("Link drag action: Copy")
                    case Qt.DropAction.MoveAction:
                        print("Link drag action: Move")
                    case Qt.DropAction.LinkAction:
                        print("Link drag action: Link")
                    case Qt.DropAction.IgnoreAction:
                        ...
                    case Qt.DropAction.TargetMoveAction:
                        print("Link drag action: Target Move")
                    case _:
                        print("Link drag action: Unknown action", action)
            except Exception as err:
                traceback.print_exc()
            return super().mousePressEvent(event)
        #     mime = QMimeData()
        #     link_index = self._view._row_widgets.inverse[self]
        #     assert link_index.isValid(), "Link index must be valid"
        #     link_path = self._view._pathFromIndex(link_index)
        #     mime.setData(GraphMimeData.LinkTailData, link_path.encode("utf-8"))
        #     drag = QDrag(self._view)
        #     drag.setMimeData(mime)
            
        #     # Execute drag
        #     try:
        #         action = drag.exec(Qt.DropAction.TargetMoveAction)
        #         print("Link drag action:", action)
        #     except Exception as err:
        #         traceback.print_exc()
        # else:
        #     # Setup new drag
        #     mime = QMimeData()
        #     link_index = self._view._row_widgets.inverse[self]
        #     assert link_index.isValid(), "Link index must be valid"
        #     link_path = self._view._pathFromIndex(link_index)
        #     mime.setData(GraphMimeData.LinkHeadData, link_path.encode("utf-8"))
        #     drag = QDrag(self._view)
        #     drag.setMimeData(mime)
            
        #     # Execute drag
        #     try:
        #         action = drag.exec(Qt.DropAction.TargetMoveAction)
        #     except Exception as err:
        #         traceback.print_exc()

