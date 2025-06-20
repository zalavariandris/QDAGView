from typing import *
from qtpy.QtGui import *
from qtpy.QtCore import *
from qtpy.QtWidgets import *
from core import GraphDataRole, GraphItemType

class GraphDelegate(QObject):
    """
    Delegate for the GraphView.
    This is used to handle events and interactions with the graph view.
    """
    def __init__(self):
        super().__init__()

    def linkSource(self, link_index:QModelIndex|QPersistentModelIndex) -> QModelIndex|None:
        source_index = link_index.data(GraphDataRole.SourceRole)
        assert source_index is None or source_index.isValid(), "Source index must be valid or None"
        return QModelIndex(source_index)
    
    def linkTarget(self, link_index:QModelIndex|QPersistentModelIndex) -> QModelIndex:
        assert link_index.isValid(), "Link index must be valid"
        target_index = link_index.parent()
        assert target_index.isValid(), "Target index must be valid"
        return target_index
    
    def itemType(self, index:QModelIndex|QPersistentModelIndex)-> GraphItemType | None:
        row_kind = index.data(GraphDataRole.TypeRole)
        if not row_kind:
            row_kind = self._defaultItemType(index)
        assert self._validateItemType(index, row_kind), f"Invalid row kind {row_kind} for index {index}!"
        return row_kind
    
    def _defaultItemType(self, index:QModelIndex|QPersistentModelIndex) -> GraphItemType | None:
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
        
    def _validateItemType(self, index:QModelIndex|QPersistentModelIndex, item_type: 'GraphItemType') -> bool:
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

    ## CREATE
    def addNode(self, model:QAbstractItemModel, subgraph:QModelIndex|QPersistentModelIndex=QModelIndex()):
        row = model.rowCount(subgraph)
        model.insertRows(row, 1, subgraph) 

    def addInlet(self, model:QAbstractItemModel, node:QModelIndex|QPersistentModelIndex)->bool:
        assert node.isValid(), "Node index must be valid"
        assert self.itemType(node) == GraphItemType.NODE, "Node index must be of type NODE"
        
        if model.columnCount(node) == 0:
            # Make sure the parent has at least one column for children, otherwise the treeview won't show them
            model.insertColumns(0, 1, node)

        position = model.rowCount(node)
        if model.insertRows(position, 1, node):
            new_index = model.index(position, 0, node)
            assert new_index.isValid(), "Created index is not valid"
            success = model.setData(new_index, f"{'Child Item' if node.isValid() else 'Item'} {position + 1}", Qt.ItemDataRole.DisplayRole)
            assert success, "Failed to set data for the new child item"
            return True
        return False

    def addOutlet(self, model:QAbstractItemModel, node:QModelIndex|QPersistentModelIndex)->bool:
        assert node.isValid(), "Node index must be valid"
        assert self.itemType(node) == GraphItemType.NODE, "Node index must be of type NODE"
        
        if model.columnCount(node) == 0:
            # Make sure the parent has at least one column for children, otherwise the treeview won't show them
            model.insertColumns(0, 1, node)

        position = model.rowCount(node)
        if model.insertRows(position, 1, node):
            new_index = model.index(position, 0, node)
            assert new_index.isValid(), "Created index is not valid"
            success = model.setData(new_index, f"{'Child Item' if node.isValid() else 'Item'} {position + 1}", Qt.ItemDataRole.DisplayRole)
            success = model.setData(new_index, GraphItemType.OUTLET, GraphDataRole.TypeRole)
            assert success, "Failed to set data for the new child item"
            return True
        return False

    def addLink(self, model:QAbstractItemModel, outlet:QModelIndex|QPersistentModelIndex, inlet:QModelIndex|QPersistentModelIndex):
        """Add a child item to the currently selected item."""
        assert model is not None, "Source model must be set before adding child items"
        assert outlet.isValid()
        assert self.itemType(outlet) == GraphItemType.OUTLET, "Outlet index must be of type OUTLET"
        assert inlet.isValid()
        assert self.itemType(inlet) == GraphItemType.INLET, "Inlet index must be of type INLET"

        # Add child to the selected item using generic methods
        position = model.rowCount(inlet)
        model.beginInsertRows(inlet, position, position)
        model.blockSignals(True)
        if model.columnCount(inlet) == 0:
            # Make sure the parent has at least one column for children, otherwise the treeview won't show them
            model.insertColumns(0, 1, inlet)
        

        if model.insertRows(position, 1, inlet):
            link_index = model.index(position, 0, inlet)
            model.setData(link_index, f"Child Item {position + 1}", role=Qt.ItemDataRole.DisplayRole)
            model.setData(link_index, outlet, role=GraphDataRole.SourceRole)
        model.blockSignals(False)
        model.endInsertRows()
        
    ## DELETE
    def removeLink(self, model:QAbstractItemModel, link:QModelIndex|QPersistentModelIndex):
        """
        Remove a link from the graph.
        This removes the link at the specified index from the model.
        """
        assert model, "Source model must be set before removing a link"
        assert link.isValid(), "Link index must be valid"
        model.removeRows(link.row(), 1, link.parent())