from __future__ import annotations

import logging
from collections import defaultdict
from itertools import groupby
from operator import attrgetter


logger = logging.getLogger(__name__)

from typing import *

from qtpy.QtGui import *
from qtpy.QtCore import *
from qtpy.QtWidgets import *

from ..core import GraphDataRole, GraphItemType
from ..managers import LinkingManager


class GraphController_for_QTreeModel(QObject):
    """
    Controller for a graph backed by a QAbstractItemModel.
    This class provides methods to interact with a graph structure stored in a QAbstractItemModel.
    Items are represented by a tree structure in the model:
    - Graph (root)
        - Nodes
            - Inlets
                - Links (child of Inlet)
            - Outlets
    """

    nodesInserted =   Signal(list) # list of QPersistentModelIndex
    inletsInserted =  Signal(list) # list of QPersistentModelIndex
    outletsInserted = Signal(list) # list of QPersistentModelIndex
    linksInserted =   Signal(list) # list of QPersistentModelIndex

    nodesAboutToBeRemoved =   Signal(list) # list of QPersistentModelIndex
    inletsAboutToBeRemoved =  Signal(list) # list of QPersistentModelIndex
    outletsAboutToBeRemoved = Signal(list) # list of QPersistentModelIndex
    linksAboutToBeRemoved =   Signal(list) # list of QPersistentModelIndex

    nodesRemoved =   Signal(list) # list of QPersistentModelIndex
    inletsRemoved =  Signal(list) # list of QPersistentModelIndex
    outletsRemoved = Signal(list) # list of QPersistentModelIndex
    linksRemoved =   Signal(list) # list of QPersistentModelIndex

    attributesDataChanged = Signal(list, list) # list of QPersistentModelIndex, list of roles

    def __init__(self, parent: QObject | None=None):
        super().__init__(parent)
        self._source_model: QAbstractItemModel | None = None
        self._source_model_connections: list[tuple[Signal, Slot]] = []
        self._link_manager = LinkingManager[QPersistentModelIndex, QPersistentModelIndex, QPersistentModelIndex]()

    def setSourceModel(self, source_model:QAbstractItemModel):
        self._source_model = source_model
    
        if self._source_model:
            for signal, slot in self._source_model_connections:
                signal.disconnect(slot)
        
        if source_model:
            assert isinstance(source_model, QAbstractItemModel), "Model must be a subclass of QAbstractItemModel"

            self._source_model_connections = [
                (source_model.rowsInserted, self.handleRowsInserted),
                (source_model.rowsAboutToBeRemoved, self.handleRowsAboutToBeRemoved),
                (source_model.rowsRemoved, self.handleRowsRemoved),
                (source_model.dataChanged, self.handleDataChanged)
            ]

            for signal, slot in self._source_model_connections:
                signal.connect(slot)

        self._source_model = source_model
        self._link_manager.clear()

        if self._source_model:
            self.handleRowsInserted(QModelIndex(), 0, self._source_model.rowCount() - 1)

    def sourceModel(self) -> QAbstractItemModel | None:
        return self._source_model

    ## Transformations
    def handleRowsInserted(self, parent:QModelIndex, start:int, end:int):
        assert self._source_model, "Model must be set before handling rows inserted!"

        match self.itemType(parent):
            case GraphItemType.SUBGRAPH | None:
                node_refs = [QPersistentModelIndex(self._source_model.index(row, 0, parent)) for row in range(start, end + 1)]
                if node_refs:
                    self.nodesInserted.emit(node_refs)
                
            case GraphItemType.NODE:
                inlet_refs = []
                outlet_refs = []
                for row in range(start, end + 1):
                    inlet_index = self._source_model.index(row, 0, parent)
                    match self.itemType(inlet_index):
                        case GraphItemType.OUTLET:
                            outlet_refs.append(QPersistentModelIndex(inlet_index))
                        case GraphItemType.INLET | None:
                            inlet_refs.append(QPersistentModelIndex(inlet_index))
                        case _:
                            raise ValueError(f"Invalid item type for child of NODE: {self.itemType(inlet_index)}")

                if inlet_refs:
                    self.inletsInserted.emit(inlet_refs)
                if outlet_refs:
                    self.outletsInserted.emit(outlet_refs)

            case GraphItemType.INLET:
                added_links: list[QPersistentModelIndex] = []

                for row in range(start, end + 1):
                    link_index = self._source_model.index(row, 0, parent)
                    persistent_link_index = QPersistentModelIndex(link_index)
                    link_source_index = self.linkSource(link_index)
                    source_key = QPersistentModelIndex(link_source_index) if link_source_index else None
                    target_key = QPersistentModelIndex(self.linkTarget(link_index)) if self.linkTarget(link_index) else None

                    added_links.append((persistent_link_index, source_key, target_key))
                
                if added_links:
                    for link_index, source_index, target_index in added_links:
                        self._link_manager.link(link_index, source_index, target_index)
                    self.linksInserted.emit([link_index for link_index, _, _ in added_links])

    def handleRowsAboutToBeRemoved(self, parent:QModelIndex, start:int, end:int):
        """Map QAbstractItemModel.rowsAboutToBeRemoved to graph signals.

        This method handles cleanup of connected links when nodes or ports are removed.
        """
        assert self._source_model, "Model must be set before handling rows removed!"

        match self.itemType(parent):
            case GraphItemType.SUBGRAPH | None:
                # collect nodes to be removed
                removed_nodes = [QPersistentModelIndex(self._source_model.index(row, 0, parent)) for row in range(start, end + 1)]
                
                # clean up connected links first
                all_connected_links = []
                for node in removed_nodes:
                    for inlet in self.inlets(node):
                        all_connected_links.extend(self._link_manager.getInletLinks(inlet))
                    for outlet in self.outlets(node):
                        all_connected_links.extend(self._link_manager.getOutletLinks(outlet))

                if all_connected_links:
                    for link in all_connected_links:
                        if link.isValid():
                            self._source_model.removeRows(link.row(), 1, link.parent())

                # emit signals for nodes about to be removed
                if removed_nodes:
                    self.nodesAboutToBeRemoved.emit(removed_nodes)
                
            case GraphItemType.NODE:
                # collect inlets and outlets to be removed
                removed_inlets = []
                removed_outlets = []
                for row in range(start, end + 1):
                    port_index = self._source_model.index(row, 0, parent)
                    match self.itemType(port_index):
                        case GraphItemType.OUTLET:
                            removed_outlets.append(QPersistentModelIndex(port_index))
                        case GraphItemType.INLET | None:
                            removed_inlets.append(QPersistentModelIndex(port_index))
                        case _:
                            raise ValueError(f"Invalid item type for child of NODE: {self.itemType(port_index)}")

                # clean up connected links first
                all_connected_links = []
                for inlet in removed_inlets:
                    all_connected_links.extend(self._link_manager.getInletLinks(inlet))
                for outlet in removed_outlets:
                    all_connected_links.extend(self._link_manager.getOutletLinks(outlet))
                
                if all_connected_links:
                    self.linksAboutToBeRemoved.emit(all_connected_links)
                    for link in all_connected_links:
                        if link.isValid():
                            self._source_model.removeRows(link.row(), 1, link.parent())

                # emit signals for nodes about to be removed
                if removed_inlets:
                    self.inletsAboutToBeRemoved.emit(removed_inlets)
                if removed_outlets:
                    self.outletsAboutToBeRemoved.emit(removed_outlets)

            case GraphItemType.INLET:
                # collect links to be removed
                removed_links = []
                for row in range(start, end + 1):
                    link_index = self._source_model.index(row, 0, parent)
                    persistent_link_index = QPersistentModelIndex(link_index)
                    removed_links.append(persistent_link_index)
            
                # emit signals for links about to be removed 
                if removed_links:
                    self.linksAboutToBeRemoved.emit(removed_links)
                    for link in removed_links:
                        self._link_manager.unlink(link)

    def handleRowsRemoved(self, parent:QModelIndex, start:int, end:int):
        assert self._source_model, "Model must be set before handling rows removed!"
        # This method is connected to rowsRemoved signal but currently has no implementation.
        # All cleanup logic is handled in handleRowsAboutToBeRemoved (before removal).
        # This method could be used for post-removal cleanup if needed in the future.
        pass

    def handleDataChanged(self, top_left:QModelIndex, bottom_right:QModelIndex, roles:List[int]=[]):
        """
        Map QAbstractItemModel.dataChanged to graph signals.
        """
        assert self._source_model, "Model must be set before handling data changed!"

        if GraphDataRole.TypeRole in roles or roles == []:
            # if an inlet or outlet type is changed, we need to update the widget
            raise NotImplementedError("Changing item type is not supported yet.")

        # collect attribute columns
        parent_index = top_left.parent().siblingAtColumn(0)
        parent_type = self.itemType(parent_index)
        match parent_type:
            case GraphItemType.SUBGRAPH | None:
                # node attributes changed
                for node_row in range(top_left.row(), bottom_right.row() + 1):
                    changed_node_attributes = []
                    for column in range(top_left.column(), bottom_right.column() + 1):
                        attribute_index = self._source_model.index(node_row, column, top_left.parent())
                        changed_node_attributes.append(attribute_index)

                    if changed_node_attributes:
                        self.attributesDataChanged.emit([QPersistentModelIndex(attr) for attr in changed_node_attributes], roles)

            case GraphItemType.NODE:
                # port attributes changed
                for port_row in range(top_left.row(), bottom_right.row() + 1):
                    port_index = self._source_model.index(port_row, 0, top_left.parent())

                    match self.itemType(port_index):
                        case GraphItemType.OUTLET:
                            for outlet_row in range(top_left.row(), bottom_right.row() + 1):
                                changed_attributes = []
                                for column in range(top_left.column(), bottom_right.column() + 1):
                                    attribute_index = self._source_model.index(outlet_row, column, top_left.parent())
                                    changed_attributes.append(QPersistentModelIndex(attribute_index))
                                if changed_attributes:
                                    self.attributesDataChanged.emit(changed_attributes, roles)

                        case GraphItemType.INLET | None:
                            for inlet_row in range(top_left.row(), bottom_right.row() + 1):
                                changed_attributes = []
                                for column in range(top_left.column(), bottom_right.column() + 1):
                                    attribute_index = self._source_model.index(inlet_row, column, top_left.parent())
                                    changed_attributes.append(QPersistentModelIndex(attribute_index))
                                if changed_attributes:
                                    self.attributesDataChanged.emit(changed_attributes, roles)

                        case _:
                            raise ValueError(f"Invalid item type for child of NODE: {self.itemType(port_index)}") 

            case GraphItemType.INLET:
                # link attributes changed
                if GraphDataRole.SourceRole in roles or roles == []:
                    # If the source role is changed, we need to update the link widget
                    removed_links:List[Tuple[QPersistentModelIndex, QPersistentModelIndex, QPersistentModelIndex]] = []
                    added_links:List[Tuple[QPersistentModelIndex, QPersistentModelIndex, QPersistentModelIndex]] = []
                    for node_row in range(top_left.row(), bottom_right.row() + 1):
                        link_index = self._source_model.index(node_row, top_left.column(), top_left.parent())
                        link_key = QPersistentModelIndex(link_index)

                        old_source_key = self._link_manager.getLinkSource(link_key)
                        old_target_key = self._link_manager.getLinkTarget(link_key)
                        self._link_manager.unlink(link_key)
                        removed_links.append((link_key, old_source_key, old_target_key))
                        # self.linksRemoved.emit(link_key, old_source_key, old_target_key)

                        new_source_key = QPersistentModelIndex(self._source_model.data(link_index, GraphDataRole.SourceRole))
                        new_target_key = QPersistentModelIndex(link_index.parent())
                        self._link_manager.link(link_key, new_source_key, new_target_key)
                        added_links.append((link_key, new_source_key, new_target_key))
                    
                    self.linksAboutToBeRemoved.emit([link_index for link_index, _, _ in removed_links])
                    self.linksInserted.emit([link_index for link_index, _, _ in added_links])
                else:
                    for link_row in range(top_left.row(), bottom_right.row() + 1):
                        changed_link_attributes = []
                        for column in range(top_left.column(), bottom_right.column() + 1):
                            attribute_index = self._source_model.index(link_row, column, top_left.parent())
                            changed_link_attributes.append(attribute_index)

                        if changed_link_attributes:
                            self.attributesDataChanged.emit([QPersistentModelIndex(attr) for attr in changed_link_attributes], roles)

    ## QUERY MODEL
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

    def nodesCount(self, subgraph:QModelIndex|None=None) -> int:
        return self._source_model.rowCount(subgraph if subgraph is not None else QModelIndex())

    def linkCount(self, port:QModelIndex|QPersistentModelIndex=None) -> int:
        if port is None:
            return len(self._link_manager._link_source)
        
        elif self.itemType(port) == GraphItemType.INLET:
            return len(self._link_manager.getInletLinks(port))
        
        elif self.itemType(port) == GraphItemType.OUTLET:
            return len(self._link_manager.getOutletLinks(port))
        else:
            return 0

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
        for row in range(self._source_model.rowCount(node)):
            child_index = self._source_model.index(row, 0, node)
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
        for row in range(self._source_model.rowCount(node)):
            child_index = self._source_model.index(row, 0, node)
            if self.itemType(child_index) == GraphItemType.OUTLET:
                outlet_count += 1
        return outlet_count
    
    def attributes(self, index:QModelIndex|QPersistentModelIndex) -> List[QPersistentModelIndex]:
        """Return a list of attribute indexes for the given item."""
        if self._source_model is None:
            return []
        
        attribute_indexes = []
        for col in range(self._source_model.columnCount(index.parent())):
            attribute_index = self._source_model.index(index.row(), col, index.parent())
            assert attribute_index.isValid(), "Attribute index must be valid"
            attribute_indexes.append(attribute_index)

        return [QPersistentModelIndex(attr) for attr in attribute_indexes]

    ## Data
    def attributeData(self, attribute:QModelIndex|QPersistentModelIndex, role:int=Qt.ItemDataRole.DisplayRole) -> Any:
        assert attribute.isValid(), "Attribute index must be valid"
        return attribute.data(role)
    
    def setAttributeData(self, attribute:QModelIndex|QPersistentModelIndex, value:Any, role:int=Qt.ItemDataRole.EditRole) -> bool:
        assert attribute.isValid(), "Attribute index must be valid"
        return self._source_model.setData(attribute, value, role)

    ### item relationships
    def nodes(self, subgraph:QModelIndex|None=None) -> List[QModelIndex]:
        """Return a list of all node indexes in the model."""
        if self._source_model is None:
            return []
        
        nodes = []
        for row in range(self._source_model.rowCount()):
            index = self._source_model.index(row, 0, subgraph if subgraph is not None else QModelIndex())
            if self.itemType(index) == GraphItemType.NODE:
                nodes.append(index)
        return nodes
    
    def inlets(self, node:QModelIndex|QPersistentModelIndex) -> List[QPersistentModelIndex]:
        """
        Get a list of inlet indexes for a given node.
        Args:
            node (QModelIndex): The index of the node.
        Returns:
            List[QModelIndex]: A list of inlet indexes for the node.
        """
        assert self.itemType(node) == GraphItemType.NODE, "Node index must be of type NODE"
        inlets = []
        for row in range(self._source_model.rowCount(node)):
            child_index = self._source_model.index(row, 0, node)
            if self.itemType(child_index) == GraphItemType.INLET:
                inlets.append(child_index)
        return [QPersistentModelIndex(inlet) for inlet in inlets]

    def outlets(self, node:QPersistentModelIndex) -> List[QPersistentModelIndex]:
        """
        Get a list of outlet indexes for a given node.
        Args:
            node (QModelIndex): The index of the node.
        Returns:
            List[QModelIndex]: A list of outlet indexes for the node.
        """
        assert self.itemType(node) == GraphItemType.NODE, "Node index must be of type NODE"
        outlets = []
        for row in range(self._source_model.rowCount(node)):
            child_index = self._source_model.index(row, 0, node)
            if self.itemType(child_index) == GraphItemType.OUTLET:
                outlets.append(child_index)
        return [QPersistentModelIndex(outlet) for outlet in outlets]

    def links(self, port:QModelIndex|QPersistentModelIndex=None) -> List[QPersistentModelIndex]:
        """Return a list links indexes in the model.
        
        Parameters
        ----------

        port (QModelIndex|QPersistentModelIndex, optional): 
            The port index to filter links.
            If port is None, return all links in the model.
            If port is an inlet or outlet, return all links connected to that port.
        """
        if self._source_model is None:
            return []
        
        if port is None:
            links = []
            for node in self.nodes():
                for row in range(self._source_model.rowCount(node)):
                    inlet_index = self._source_model.index(row, 0, node)
                    if self.itemType(inlet_index) == GraphItemType.INLET:
                        for link_row in range(self._source_model.rowCount(inlet_index)):
                            link_index = self._source_model.index(link_row, 0, inlet_index)
                            if self.itemType(link_index) == GraphItemType.LINK:
                                links.append(link_index)
            return [QPersistentModelIndex(link) for link in links]

        elif self.itemType(port) == GraphItemType.INLET:
            inlet = port
            links = []
            for row in range(self._source_model.rowCount(inlet)):
                child_index = self._source_model.index(row, 0, inlet)
                if self.itemType(child_index) == GraphItemType.LINK:
                    links.append(child_index)
            return [QPersistentModelIndex(link) for link in links]
        elif self.itemType(port) == GraphItemType.OUTLET:
            # For outlets, use the link manager since links are stored as children of inlets, not outlets
            outlet = port
            return self._link_manager.getOutletLinks(QPersistentModelIndex(outlet))
        return links

    def inletNode(self, inlet:QModelIndex|QPersistentModelIndex) -> QPersistentModelIndex|None:
        assert self.itemType(inlet) == GraphItemType.INLET, "Inlet index must be of type INLET"
        node_index = inlet.parent()
        if not node_index.isValid():
            return None
        assert self.itemType(node_index) == GraphItemType.NODE, "Parent of inlet must be of type NODE"
        return QPersistentModelIndex(node_index)
    
    def outletNode(self, outlet:QModelIndex|QPersistentModelIndex) -> QPersistentModelIndex|None:
        assert self.itemType(outlet) == GraphItemType.OUTLET, "Outlet index must be of type OUTLET"
        node_index = outlet.parent()
        if not node_index.isValid():
            return None
        assert self.itemType(node_index) == GraphItemType.NODE, "Parent of outlet must be of type NODE"
        return QPersistentModelIndex(node_index)

    def linkSource(self, link_index:QPersistentModelIndex) -> QPersistentModelIndex|None:
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
            return QPersistentModelIndex(stored)
        if isinstance(stored, QPersistentModelIndex):
            if not stored.isValid():
                return None
            return QPersistentModelIndex(stored)
        # Unexpected type – ignore gracefully
        logger.warning(f"Unexpected SourceRole payload type: {type(stored)}")
        return None
    
    def linkTarget(self, link_index:QPersistentModelIndex) -> QPersistentModelIndex:
        assert link_index.isValid(), "Link index must be valid"
        target_index = link_index.parent()
        assert target_index.isValid(), "Target index must be valid"
        return QPersistentModelIndex(target_index)

    def attributeOwner(self, attribute:QModelIndex|QPersistentModelIndex) -> QPersistentModelIndex|None:
        assert attribute.isValid(), "Attribute index must be valid"
        index = self._source_model.index(attribute.row(), 0, attribute.parent())
        assert index.isValid(), "Owner index must be valid"
        return QPersistentModelIndex(index)

    # behaviour TODO: move to delegate
    def canLink(self, source:QPersistentModelIndex, target:QPersistentModelIndex)->bool:
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
    
    ## CREATE
    def addNode(self, subgraph:QModelIndex|QPersistentModelIndex=QModelIndex())->QPersistentModelIndex|None:
        position = self._source_model.rowCount(subgraph)
        if self._source_model.insertRows(position, 1, subgraph):
            new_index = self._source_model.index(position, 0, subgraph)
            assert new_index.isValid(), "Created index is not valid"
            return QPersistentModelIndex(new_index)
        return None

    def addInlet(self, node:QModelIndex|QPersistentModelIndex)->QPersistentModelIndex|None:
        assert node.isValid(), "Node index must be valid"
        assert self.itemType(node) == GraphItemType.NODE, "Node index must be of type NODE"
        
        # Make sure the parent has at least one column for children, otherwise the treeview won't show them
        if self._source_model.columnCount(node) == 0:
            self._source_model.insertColumns(0, 1, node)

        # Append child to the selected item using generic methods
        position = self._source_model.rowCount(node)
        if self._source_model.insertRows(position, 1, node):
            new_index = self._source_model.index(position, 0, node)
            assert new_index.isValid(), "Created index is not valid"
            new_inlet_name = f"{'in'}#{position + 1}"
            success = self._source_model.setData(new_index, new_inlet_name, Qt.ItemDataRole.DisplayRole)
            # by default node children are inlets. dont need to set GraphItemType.INLET explicitly
            assert success, "Failed to set data for the new child item"
            return QPersistentModelIndex(new_index)
        return None

    def addOutlet(self, model:QAbstractItemModel, node:QModelIndex|QPersistentModelIndex)->QPersistentModelIndex|None:
        assert node.isValid(), "Node index must be valid"
        assert self.itemType(node) == GraphItemType.NODE, "Node index must be of type NODE"
        
        if self._source_model.columnCount(node) == 0:
            # Make sure the parent has at least one column for children, otherwise the treeview won't show them
            self._source_model.insertColumns(0, 1, node)

        position = self._source_model.rowCount(node)
        if self._source_model.insertRows(position, 1, node):
            new_index = self._source_model.index(position, 0, node)
            assert new_index.isValid(), "Created index is not valid"
            new_outlet_name = f"{'out'}#{position + 1}"
            success = self._source_model.setData(new_index, new_outlet_name, Qt.ItemDataRole.DisplayRole)
            success = self._source_model.setData(new_index, GraphItemType.OUTLET, GraphDataRole.TypeRole)
            assert success, "Failed to set data for the new child item"
            return QPersistentModelIndex(new_index)
        return None

    def addLink(self, outlet:QModelIndex|QPersistentModelIndex, inlet:QModelIndex|QPersistentModelIndex)->QPersistentModelIndex|None:
        """Add a child item to the currently selected item."""
        assert self._source_model is not None, "Source model must be set before adding child items"
        assert isinstance(outlet, (QModelIndex, QPersistentModelIndex)), f"outlet must be a QModelIndex got: {outlet}"
        assert outlet.isValid(), "Outlet must be a valid"
        assert self.itemType(outlet) == GraphItemType.OUTLET, "Outlet index must be of type OUTLET"
        assert isinstance(inlet, (QModelIndex, QPersistentModelIndex)), f"inlet must be a QModelIndex got: {inlet}"
        assert inlet.isValid(), "Inlet must be a valid"
        assert self.itemType(inlet) == GraphItemType.INLET, "Inlet index must be of type INLET"

        # Add child to the selected item using generic methods
        position = self._source_model.rowCount(inlet)

        # Make sure the parent has at least one column for children, otherwise the treeview won't show them
        if self._source_model.columnCount(inlet) == 0:
            self._source_model.insertColumns(0, 1, inlet)
        
        if self._source_model.insertRows(position, 1, inlet):
            link_index = self._source_model.index(position, 0, inlet)
            new_link_name = f"{'Link'}#{position + 1}"
            persistent_outlet = outlet if isinstance(outlet, QPersistentModelIndex) else QPersistentModelIndex(outlet)
            if not self._source_model.setData(link_index, persistent_outlet, role=GraphDataRole.SourceRole):
                logger.warning(f"Failed to set source for new link: {persistent_outlet}")

            if not self._source_model.setData(link_index, new_link_name, role=Qt.ItemDataRole.DisplayRole):
                logger.warning(f"Failed to set data for new link: {new_link_name}")

            return QPersistentModelIndex(link_index)
            
        return None

    ## UPDATE
    def setLinkSource(self, link:QModelIndex|QPersistentModelIndex, source:QModelIndex|QPersistentModelIndex)->bool:
        """
        Set the source of a link.
        This sets the source of the link at the specified index to the given source index.
        """
        assert self._source_model, "Source model must be set before setting a link source"
        assert link.isValid(), "Link index must be valid"
        assert source.isValid(), "Source index must be valid"
        persistent_source = source if isinstance(source, QPersistentModelIndex) else QPersistentModelIndex(source)
        return self._source_model.setData(link, persistent_source, role=GraphDataRole.SourceRole)

    ## DELETE
    def removeNode(self, node:QModelIndex|QPersistentModelIndex)->bool:
        """
        Remove a node from the graph.
        This removes the node at the specified index from the model.
        Note: Connected links are automatically removed by handleRowsAboutToBeRemoved.
        """
        assert self._source_model, "Source model must be set before removing a node"
        if not isinstance(node, (QModelIndex, QPersistentModelIndex)):
            logger.error(f"Node must be a QModelIndex or QPersistentModelIndex, got: {type(node)}")
            return False
        
        # Simply remove the node - handleRowsAboutToBeRemoved will handle connected links
        return self._source_model.removeRows(node.row(), 1, node.parent())
    
    def removeLink(self, link:QModelIndex|QPersistentModelIndex)->bool:
        """
        Remove a link from the graph.
        This removes the link at the specified index from the model.
        Note: The _link_manager.unlink() is handled automatically in handleRowsAboutToBeRemoved.
        """
        assert self._source_model, "Source model must be set before removing a link"
        assert link.isValid(), "Link index must be valid"
        return self._source_model.removeRows(link.row(), 1, link.parent())

    def batchRemove(self, indexes: List[QModelIndex|QPersistentModelIndex])->bool:
        """
        Batch remove multiple items from the graph.
        
        This method efficiently removes multiple items by:
        1. Filtering out descendants to avoid double-deletion
        2. Grouping by parent and consolidating adjacent rows into ranges
        3. Removing in reverse order to prevent index shifting
        
        Args:
            indexes: List of model indexes to remove
            
        Returns:
            bool: True if all removals succeeded, False if any failed
        """
        assert self._source_model, "Source model must be set before removing an item"

        if not indexes:
            return True  # Nothing to remove, trivially succeed
        
        # force all to column 0, filter valid indexes, and create set for efficient operations
        normalized_indexes = [idx.siblingAtColumn(0) for idx in indexes]

        # fail removal if any nonexistent indexes are provided
        if any(not idx.isValid() for idx in normalized_indexes):
            return False
        
        
        # remove duplicates using set (faster than dict.fromkeys for this use case)
        indexes_set = set(normalized_indexes)
        indexes = list(indexes_set)  # Convert back to list, order doesn't matter for our algorithm

        # filter out descendants using set operations for efficiency
        def has_ancestor_in_set(index, index_set):
            current = index.parent()
            while current.isValid():
                if current in index_set:
                    return True
                current = current.parent()
            return False
        
        indexes = {idx for idx in indexes if not has_ancestor_in_set(idx, indexes_set)}

        # Early exit if nothing left to remove after filtering
        if not indexes:
            return True

        # group by parent using defaultdict
        rows_by_parents = defaultdict(list)
        for index in indexes:
            rows_by_parents[index.parent()].append(index.row())

        # consolidate adjacent rows into ranges using groupby
        def sequence_to_ranges(rows: List[int]) -> List[Tuple[int, int]]:
            """Convert list of row numbers into (start, count) ranges for consecutive rows.
            
            Example: [1, 2, 3, 7, 8, 10] → [(1, 3), (7, 2), (10, 1)]
            """
            if not rows:
                return []
                
            rows = sorted(rows)
            ranges = []
            for _, group_items in groupby(enumerate(rows), lambda x: x[1] - x[0]):
                group = list(group_items)
                start = group[0][1]
                count = len(group)
                ranges.append((start, count))
            return ranges
        
        ranges_by_parents = {parent: sequence_to_ranges(rows) for parent, rows in rows_by_parents.items()}
        
        # Sort parents by depth (deepest first) to ensure children are removed before parents
        def get_depth(index: QModelIndex) -> int:
            """Calculate the depth of an index in the tree (root = 0)"""
            depth = 0
            current = index
            while current.isValid():
                depth += 1
                current = current.parent()
            return depth
        
        sorted_parents = sorted(ranges_by_parents.keys(), key=get_depth, reverse=True)
        
        # Remove rows in reverse order to avoid index shifting issues
        success = True
        for parent in sorted_parents:
            ranges = ranges_by_parents[parent]
            # Sort ranges by starting row in descending order
            ranges.sort(key=lambda r: r[0], reverse=True)
            
            for start_row, count in ranges:
                if not self._source_model.removeRows(start_row, count, parent):
                    success = False
                    logger.warning(f"Failed to remove rows {start_row}-{start_row + count - 1} from parent {parent}")
        
        return success

                
                
