from __future__ import annotations

import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

from typing import *

from qtpy.QtGui import *
from qtpy.QtCore import *
from qtpy.QtWidgets import *

from ...core import GraphDataRole, GraphItemType


class GraphController:
    """
    
    """
    def __init__(self, model:QAbstractItemModel|None = None):
        self._model = model

    def setModel(self, model:QAbstractItemModel):
        self._model = model

    def model(self) -> QAbstractItemModel | None:
        return self._model

    ## QUERY MODEL
    def linkSource(self, link_index:QModelIndex|QPersistentModelIndex) -> QModelIndex|None:
        """Return the (non-persistent) QModelIndex of the link source if present.

        Internally we store a QPersistentModelIndex to survive model changes.
        We convert it back to a QModelIndex for client code to keep backward compatibility.
        """
        stored = link_index.data(GraphDataRole.SourceRole)
        if stored is None:
            return None
        # Allow legacy storage of plain QModelIndex; migrate silently
        if isinstance(stored, QModelIndex):
            if not stored.isValid():
                return None
            return stored
        if isinstance(stored, QPersistentModelIndex):
            if not stored.isValid():
                return None
            return QModelIndex(stored)
        # Unexpected type – ignore gracefully
        logger.warning(f"Unexpected SourceRole payload type: {type(stored)}")
        return None
    
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
        elif item_type == GraphItemType.NODE:  # Fix: Add missing elif
            return index.parent() == QModelIndex()
        elif item_type == GraphItemType.INLET:
            return index.parent().isValid() and index.parent().parent() == QModelIndex()
        elif item_type == GraphItemType.OUTLET:
            return index.parent().isValid() and index.parent().parent() == QModelIndex()
        elif item_type == GraphItemType.LINK:
            return index.parent().isValid() and index.parent().parent().isValid() and index.parent().parent().parent() == QModelIndex()
        else:
            return False  # Explicit return for unhandled cases

    def canLink(self, source:QModelIndex, target:QModelIndex)->bool:
        """
        Check if linking is possible between the source and target indexes.
        """

        if source.parent() == target.parent():
            # Cannot link items in the same parent
            return False
        
        source_type = self.itemType(source)
        target_type = self.itemType(target)
        if  (source_type, target_type) == (GraphItemType.INLET, GraphItemType.OUTLET) or \
            (source_type, target_type) == (GraphItemType.OUTLET, GraphItemType.INLET):
            # Both source and target must be either inlet or outlet
            return True
        
        return False
    
    def inletCount(self, node:QModelIndex|QPersistentModelIndex) -> int:
        """
        Get the number of inlets for a given node.
        Args:
            node (QModelIndex): The index of the node.
        Returns:
            int: The number of inlets for the node.
        """
        assert self.itemType(node) == GraphItemType.NODE, "Node index must be of type NODE"
        inlet_count = 0
        for row in range(self._model.rowCount(node)):
            child_index = self._model.index(row, 0, node)
            if self.itemType(child_index) == GraphItemType.INLET:
                inlet_count += 1
        return inlet_count

    def outletCount(self, node:QModelIndex|QPersistentModelIndex) -> int:
        """
        Get the number of outlets for a given node.
        Args:
            node (QModelIndex): The index of the node.
        Returns:
            int: The number of outlets for the node.
        """
        assert self.itemType(node) == GraphItemType.NODE, "Node index must be of type NODE"
        outlet_count = 0
        for row in range(self._model.rowCount(node)):
            child_index = self._model.index(row, 0, node)
            if self.itemType(child_index) == GraphItemType.OUTLET:
                outlet_count += 1
        return outlet_count

    ## CREATE
    def addNode(self, subgraph:QModelIndex|QPersistentModelIndex=QModelIndex()):
        position = self._model.rowCount(subgraph)
        if self._model.insertRows(position, 1, subgraph):
            new_index = self._model.index(position, 0, subgraph)
            assert new_index.isValid(), "Created index is not valid"
            new_node_name = f"{'Node'}#{position + 1}"
            success = self._model.setData(new_index, new_node_name, Qt.ItemDataRole.DisplayRole)
            assert success, "Failed to set data for the new child item"
            return True
        return False

    def addInlet(self, node:QModelIndex|QPersistentModelIndex)->bool:
        assert node.isValid(), "Node index must be valid"
        assert self.itemType(node) == GraphItemType.NODE, "Node index must be of type NODE"
        
        # Make sure the parent has at least one column for children, otherwise the treeview won't show them
        if self._model.columnCount(node) == 0:
            self._model.insertColumns(0, 1, node)

        # Append child to the selected item using generic methods
        position = self._model.rowCount(node)
        if self._model.insertRows(position, 1, node):
            new_index = self._model.index(position, 0, node)
            assert new_index.isValid(), "Created index is not valid"
            new_inlet_name = f"{'in'}#{position + 1}"
            success = self._model.setData(new_index, new_inlet_name, Qt.ItemDataRole.DisplayRole)
            # by default node children are inlets. dont need to set GraphItemType.INLET explicitly
            assert success, "Failed to set data for the new child item"
            return True
        return False

    def addOutlet(self, model:QAbstractItemModel, node:QModelIndex|QPersistentModelIndex)->bool:
        assert node.isValid(), "Node index must be valid"
        assert self.itemType(node) == GraphItemType.NODE, "Node index must be of type NODE"
        
        if self._model.columnCount(node) == 0:
            # Make sure the parent has at least one column for children, otherwise the treeview won't show them
            self._model.insertColumns(0, 1, node)

        position = self._model.rowCount(node)
        if self._model.insertRows(position, 1, node):
            new_index = self._model.index(position, 0, node)
            assert new_index.isValid(), "Created index is not valid"
            new_outlet_name = f"{'out'}#{position + 1}"
            success = self._model.setData(new_index, new_outlet_name, Qt.ItemDataRole.DisplayRole)
            success = self._model.setData(new_index, GraphItemType.OUTLET, GraphDataRole.TypeRole)
            assert success, "Failed to set data for the new child item"
            return True
        return False

    def addLink(self, outlet:QModelIndex|QPersistentModelIndex, inlet:QModelIndex|QPersistentModelIndex)->bool:
        """Add a child item to the currently selected item."""
        assert self._model is not None, "Source model must be set before adding child items"
        assert outlet.isValid()
        assert self.itemType(outlet) == GraphItemType.OUTLET, "Outlet index must be of type OUTLET"
        assert inlet.isValid()
        assert self.itemType(inlet) == GraphItemType.INLET, "Inlet index must be of type INLET"

        # Add child to the selected item using generic methods
        position = self._model.rowCount(inlet)

        # Make sure the parent has at least one column for children, otherwise the treeview won't show them
        if self._model.columnCount(inlet) == 0:
            self._model.insertColumns(0, 1, inlet)
        
        if self._model.insertRows(position, 1, inlet):
            link_index = self._model.index(position, 0, inlet)
            new_link_name = f"{'Link'}#{position + 1}"
            persistent_outlet = outlet if isinstance(outlet, QPersistentModelIndex) else QPersistentModelIndex(outlet)
            if self._model.setData(link_index, persistent_outlet, role=GraphDataRole.SourceRole):
                self._model.setData(link_index, new_link_name, role=Qt.ItemDataRole.DisplayRole)
                return True
        return False

    ## UPDATE
    def setLinkSource(self, link:QModelIndex|QPersistentModelIndex, source:QModelIndex|QPersistentModelIndex):
        """
        Set the source of a link.
        This sets the source of the link at the specified index to the given source index.
        """
        assert self._model, "Source model must be set before setting a link source"
        assert link.isValid(), "Link index must be valid"
        assert source.isValid(), "Source index must be valid"
        persistent_source = source if isinstance(source, QPersistentModelIndex) else QPersistentModelIndex(source)
        self._model.setData(link, persistent_source, role=GraphDataRole.SourceRole)

    ## DELETE
    def removeNode(self, node:QModelIndex|QPersistentModelIndex)->bool:
        """
        Remove a node from the graph.
        This removes the node at the specified index from the model.
        """
        assert self._model, "Source model must be set before removing a node"
        assert node.isValid(), "Node index must be valid"
        return self._model.removeRows(node.row(), 1, node.parent())
    
    def removeLink(self, link:QModelIndex|QPersistentModelIndex)->bool:
        """
        Remove a link from the graph.
        This removes the link at the specified index from the model.
        """
        assert self._model, "Source model must be set before removing a link"
        assert link.isValid(), "Link index must be valid"
        return self._model.removeRows(link.row(), 1, link.parent())