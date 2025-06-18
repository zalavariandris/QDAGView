from typing import *
from PySide6.QtGui import *
from PySide6.QtCore import *
from PySide6.QtWidgets import *

from core import GraphDataRole, GraphItemType, GraphMimeData

class GraphAdapter(QObject):
    """
    A proxyModel that adapts a QAbstractItemModel to a graph view.
    """
    ## Model Signals
    nodeAdded = Signal(QPersistentModelIndex) # key
    nodeAboutToBeRemoved = Signal(QPersistentModelIndex) # key
    inletAdded = Signal(QPersistentModelIndex) # key
    inletAboutToBeRemoved = Signal(QPersistentModelIndex) # key
    outletAdded = Signal(QPersistentModelIndex) # key
    outletAboutToBeRemoved = Signal(QPersistentModelIndex) # key
    linkAdded = Signal(QPersistentModelIndex) # key
    linkAboutToBeRemoved = Signal(QPersistentModelIndex) # key
    dataChanged = Signal(QPersistentModelIndex, int, list) # key, column, roles

    def __init__(self, parent:QObject|None = None ):
        super().__init__(parent)
        self._sourceModel:QAbstractItemModel | None = None
        self._source_model_connections:List[Tuple[Signal, Callable]] = []
        
    def setSourceModel(self, sourceModel:QAbstractItemModel| None):
        """
        Set the source model for the adapter.
        This is used to synchronize the adapter with the model.
        """
        assert sourceModel is None or isinstance(sourceModel, QAbstractItemModel), f"got: {sourceModel}, expected QAbstractItemModel or None"

        if self._sourceModel:
            for signal, slot in self._source_model_connections:
                signal.disconnect(slot)
            self._source_model_connections = []
 
        if sourceModel:
            self._source_model_connections = [
                (sourceModel.dataChanged, self.onDataChanged),
                (sourceModel.rowsInserted, self.onRowsInserted),
                (sourceModel.rowsAboutToBeRemoved, self.onRowsAboutToBeRemoved)
            ]
            for signal, slot in self._source_model_connections:
                signal.connect(slot)

        self._sourceModel = sourceModel

        # self.onRowsInserted(QModelIndex(), 0, self._sourceModel.rowCount() - 1)

    def sourceModel(self) -> QAbstractItemModel | None:
        """
        Get the current source model for the adapter.
        This is used to synchronize the adapter with the model.
        """
        return self._sourceModel
    
    def nodes(self, subgraph:QModelIndex|QPersistentModelIndex=QModelIndex()) -> Iterable[QPersistentModelIndex]:
        """
        Get all nodes in the graph.
        This returns a list of QModelIndexes for the nodes in the graph.
        """
        if not self._sourceModel:
            return []
        
        for row in range(self._sourceModel.rowCount()):
            index = QPersistentModelIndex(self._sourceModel.index(row, 0, subgraph))
            if self.itemType(index) == GraphItemType.NODE:
                yield index

    def inlets(self, node:QModelIndex|QPersistentModelIndex=QModelIndex()) -> Iterable[QPersistentModelIndex]:
        """
        Get all inlets in the graph.
        This returns a list of QModelIndexes for the outlets in the graph.
        """
        assert self._sourceModel, "Source model must be set before getting outlets"
        for row in range(self._sourceModel.rowCount()):
            index = QPersistentModelIndex(self._sourceModel.index(row, 0, node))
            if self.itemType(index) == GraphItemType.INLET:
                yield index

    def outlets(self, node:QModelIndex|QPersistentModelIndex=QModelIndex()) -> Iterable[QPersistentModelIndex]:
        """
        Get all outlets in the graph.
        This returns a list of QModelIndexes for the outlets in the graph.
        """
        assert self._sourceModel, "Source model must be set before getting outlets"
        for row in range(self._sourceModel.rowCount()):
            index = QPersistentModelIndex(self._sourceModel.index(row, 0, node))
            if self.itemType(index) == GraphItemType.OUTLET:
                yield index
    
    def inLinks(self, inlet:QModelIndex|QPersistentModelIndex=QModelIndex()) -> Iterable[QPersistentModelIndex]:
        """
        Get all links in the graph.
        This returns a list of QModelIndexes for the links in the graph.
        """
        assert self._sourceModel, "Source model must be set before getting links"
        for row in range(self._sourceModel.rowCount(inlet)):
            index = QPersistentModelIndex(self._sourceModel.index(row, 0, inlet))
            if self.itemType(index) == GraphItemType.LINK:
                yield index

    def outLinks(self, outlet:QModelIndex|QPersistentModelIndex=QModelIndex()) -> Iterable[QPersistentModelIndex]:
        """
        Get all links in the graph.
        This returns a list of QModelIndexes for the links in the graph.
        """
        ...

    def linkSource(self, link:QModelIndex|QPersistentModelIndex=QModelIndex()) -> QPersistentModelIndex:
        """
        Get the source of a link in the graph.
        This returns the QModelIndex of the source of the link at the specified index.
        """
        assert self._sourceModel, "Source model must be set before getting link source"
        source_index = link.data(GraphDataRole.SourceRole)
        if source_index is not None:
            return QPersistentModelIndex(source_index)
        else:
            return QPersistentModelIndex()
    
    def linkTarget(self, link:QModelIndex|QPersistentModelIndex=QModelIndex()) -> QPersistentModelIndex:
        """
        Get the target of a link in the graph.
        This returns the QModelIndex of the target of the link at the specified index.
        """
        assert self._sourceModel, "Source model must be set before getting link target"
        target_index = link.parent()
        if target_index.isValid():
            return QPersistentModelIndex(target_index)
        else:
            return QPersistentModelIndex()

    def data(self, index:QModelIndex|QPersistentModelIndex=QModelIndex(), role:int=Qt.ItemDataRole.DisplayRole) -> Any:
        """
        Get the data for a node in the graph.
        This returns the data for the node at the specified column.
        """
        assert self._sourceModel, "Source model must be set before getting node data"
        return index.data(role)
    
    ## Helpers
    def itemType(self, index:QPersistentModelIndex):
        row_kind = index.data(GraphDataRole.TypeRole)
        if not row_kind:
            row_kind = self._defaultItemType(index)
        assert self._validateItemType(index, row_kind), f"Invalid row kind {row_kind} for index {index}!"
        return row_kind
    
    def _defaultItemType(self, index:QPersistentModelIndex) -> GraphItemType | None:
        """
        Determine the kind of row based on the index.
        This is used to determine whether to create a Node, Inlet, Outlet or Link widget.
        Args:
            index (QModelIndex): The index of the row.
        """
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
        
    def _validateItemType(self, index:QPersistentModelIndex, item_type: 'GraphItemType') -> bool:
        """
        Validate the row kind based on the index.
        This is used to ensure that the row kind matches the expected kind
        Args:   

            index (QModelIndex): The index of the row.
            row_kind (NodeType | None): The kind of row to validate.
        Returns:
            bool: True if the row kind is valid, False otherwise.
        """

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
        row = self._sourceModel.rowCount(subgraph)
        self._sourceModel.insertRows(row, 1, subgraph) 

    def addInlet(self, node:QPersistentModelIndex)->bool:
        self._sourceModel.addInlet(node)

    def addOutlet(self, node:QPersistentModelIndex)->bool:
        assert node.isValid(), "Node index must be valid"
        assert self.itemType(node) == GraphItemType.NODE, "Node index must be of type NODE"
        
        if self._sourceModel.columnCount(node) == 0:
            # Make sure the parent has at least one column for children, otherwise the treeview won't show them
            self._sourceModel.insertColumns(0, 1, node)

        position = self._sourceModel.rowCount(node)
        if self._sourceModel.insertRows(position, 1, node):
            new_index = self._sourceModel.index(position, 0, node)
            assert new_index.isValid(), "Created index is not valid"
            success = self._sourceModel.setData(new_index, f"{'Child Item' if node.isValid() else 'Item'} {row + 1}", Qt.ItemDataRole.DisplayRole)
            assert success, "Failed to set data for the new child item"
            return True
        return False

    def addLink(self, outlet:QPersistentModelIndex, inlet:QPersistentModelIndex):
        """Add a child item to the currently selected item."""
        assert self._sourceModel is not None, "Source model must be set before adding child items"
        assert isinstance(outlet, QPersistentModelIndex), f"Outlet must be a QPersistentModelIndex, got: {outlet}"
        assert outlet.isValid()
        assert self.itemType(outlet) == GraphItemType.OUTLET, "Outlet index must be of type OUTLET"
        assert isinstance(inlet, QPersistentModelIndex), f"Inlet must be a QPersistentModelIndex, got: {inlet}"
        assert inlet.isValid()
        assert self.itemType(inlet) == GraphItemType.INLET, "Inlet index must be of type INLET"

            
        # Add child to the selected item using generic methods
        if self._sourceModel.columnCount(inlet) == 0:
            # Make sure the parent has at least one column for children, otherwise the treeview won't show them
            self._sourceModel.insertColumns(0, 1, inlet)
        position = self._sourceModel.rowCount(inlet)
        if self._sourceModel.insertRows(position, 1, inlet):
            index = self._sourceModel.index(position, 0, inlet)
            self._sourceModel.setData(index, f"Child Item {position + 1}", role=Qt.ItemDataRole.DisplayRole)
            self._sourceModel.setData(index, QPersistentModelIndex(outlet), role=GraphDataRole.SourceRole)

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
        assert link.isValid(), "Link index must be valid"
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
            row_kind = self.itemType(index)
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
        link_indexes = filter(lambda idx: self.itemType(idx) == GraphItemType.LINK, bfs_indexes)
        
        for index in link_indexes:
            self.linkAboutToBeRemoved.emit(QPersistentModelIndex(index))
            # self._remove_link_widget(index.row(), index.parent())

        # remove widgets reversed depth order
        non_link_indexes = filter(lambda idx: self.itemType(idx) != GraphItemType.LINK, reversed(bfs_indexes) )
        for index in non_link_indexes:
            row_kind = self.itemType(index)
            match row_kind:

                case None:
                    pass
                case GraphItemType.NODE:
                    self.nodeAboutToBeRemoved.emit(QPersistentModelIndex(index))
                case GraphItemType.INLET:
                    self.inletAboutToBeRemoved.emit(QPersistentModelIndex(index))
                case GraphItemType.OUTLET:
                    self.outletAboutToBeRemoved.emit(QPersistentModelIndex(index))
                case _:
                    raise NotImplementedError(f"Row kind {row_kind} is not implemented!")

    @Slot(QModelIndex, QModelIndex, list)
    def onDataChanged(self, topLeft:QModelIndex , bottomRight:QModelIndex , roles=[]):
        assert self._sourceModel

        ## Update data cells
        for row in range(topLeft.row(), bottomRight.row()+1):
            index = topLeft.sibling(row, 0)

            for col in range(topLeft.column(), bottomRight.column()+1):
                self.dataChanged.emit(QPersistentModelIndex(index), col, roles)


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

    ## Handle drag and drop
    def canDropMimeData(self, data:QMimeData, action:Qt.DropAction, drop_target:QPersistentModelIndex) -> bool:
        """
        Check if the mime data can be dropped on the graph view.
        This is used to determine if the drag-and-drop operation is valid.
        """
        drop_target_type = self.itemType(drop_target)
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
        
        drop_target_type = self.itemType(drop_target)
        if data.hasFormat(GraphMimeData.OutletData):
            # outlet dropped
            outlet_index = self.decodeOutletMimeData(data)
            assert outlet_index.isValid(), "Outlet index must be valid"
              # Ensure drop target is valid
            if drop_target_type == GraphItemType.INLET:
                # ... on inlet
                inlet_index = drop_target
                self.addLink(outlet_index, inlet_index)
                return True

        if data.hasFormat(GraphMimeData.InletData):
            # inlet dropped
            inlet_index = self.decodeInletMimeData(data)
            assert inlet_index.isValid(), "Inlet index must be valid"
            if drop_target_type == GraphItemType.OUTLET:
                # ... on outlet
                outlet_index = drop_target
                self.addLink(outlet_index, inlet_index)
                return True
            
        if data.hasFormat(GraphMimeData.LinkTailData):
            # link tail dropped
            link_index = self.decodeLinkTailMimeData(data)
            assert link_index.isValid(), "Link index must be valid"
            if drop_target_type == GraphItemType.INLET:
                # ... on inlet
                inlet_index = drop_target
                self.removeLink(link_index)
                self.addLink(link_index, inlet_index)
                return True
            else:
                # ... on empty space
                IsLinked = self.linkSource(link_index).isValid() and self.linkTarget().isValid()
                if IsLinked:
                    self.removeLink(link_index)
                    return True
                return True
            
        if data.hasFormat(GraphMimeData.LinkHeadData):
            # link head dropped
            link_index = self.decodeLinkHeadMimeData(data)
            assert link_index.isValid(), "Link index must be valid"
            if drop_target_type == GraphItemType.OUTLET:
                # ... on outlet
                outlet_index = drop_target
                self.removeLink(link_index)
                self.addLink(outlet_index, link_index)
                return True
            else:
                # ... on empty space
                IsLinked = self.linkSource(link_index).isValid() and self.linkTarget().isValid()
                if IsLinked:
                    self.removeLink(link_index)
                    return True
                return True
    
        return False
    
