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
from ..views.managers import LinkingManager

from .abstract_graphmodel import AbstractGraphModel

class QItemModelGraphModel(AbstractGraphModel):
    """
    Controller for a graph backed by a QAbstractItemModel.
    This class provides methods to interact with a graph structure stored in a QAbstractItemModel.
    """

    nodesInserted = Signal(list) # list of QPersistentModelIndex
    nodesAboutToBeRemoved = Signal(list) # list of QPersistentModelIndex
    nodesDataChanged = Signal(list, list, list) # list of QPersistentModelIndex, list of columns,  list of roles

    inletsInserted = Signal(list) # list of QPersistentModelIndex
    inletsAboutToBeRemoved = Signal(list) # list of QPersistentModelIndex
    inletsDataChanged = Signal(list, list, list) # list of QPersistentModelIndex, list of columns,  list of roles

    outletsInserted = Signal(list) # list of QPersistentModelIndex
    outletsAboutToBeRemoved = Signal(list) # list of QPersistentModelIndex
    outletsDataChanged = Signal(list, list, list) # list of QPersistentModelIndex, list of columns,  list of roles

    linksInserted = Signal(list) # list of QPersistentModelIndex
    linksAboutToBeRemoved = Signal(list) # list of QPersistentModelIndex
    linksDataChanged = Signal(list, list, list) # list of QPersistentModelIndex, list of columns,  list of roles

    def __init__(self, parent: QObject | None=None):
        super().__init__(parent)
        self._source_model: QAbstractItemModel | None = None
        self._model_connections: list[tuple[Signal, Slot]] = []
        self._link_manager = LinkingManager[QPersistentModelIndex, QPersistentModelIndex, QPersistentModelIndex]()

    def setSourceModel(self, model:QAbstractItemModel):
        self._source_model = model
    
        if self._source_model:
            for signal, slot in self._model_connections:
                signal.disconnect(slot)
        
        if model:
            assert isinstance(model, QAbstractItemModel), "Model must be a subclass of QAbstractItemModel"

            self._model_connections = [
                (model.rowsInserted, self.handleRowsInserted),
                (model.rowsAboutToBeInserted, self.handleRowsAboutToBeInserted),
                (model.rowsAboutToBeRemoved, self.handleRowsAboutToBeRemoved),
                (model.dataChanged, self.handleDataChanged)
            ]

            for signal, slot in self._model_connections:
                signal.connect(slot)

        self._source_model = model

        self._link_manager.clear()

    def sourceModel(self) -> QAbstractItemModel | None:
        return self._source_model

    ## Transformations
    def handleRowsAboutToBeInserted(self, parent:QModelIndex, start:int, end:int):
        pass

    def handleRowsInserted(self, parent:QModelIndex, start:int, end:int):
        assert self._source_model, "Model must be set before handling rows inserted!"

        match self.itemType(parent):
            case GraphItemType.SUBGRAPH | None:
                node_keys = [QPersistentModelIndex(self._source_model.index(row, 0, parent)) for row in range(start, end + 1)]
                if node_keys:
                    self.nodesInserted.emit(node_keys)
                
            case GraphItemType.NODE:
                inlet_keys = []
                outlet_keys = []
                for row in range(start, end + 1):
                    inlet_index = self._source_model.index(row, 0, parent)
                    match self.itemType(inlet_index):
                        case GraphItemType.OUTLET:
                            outlet_keys.append(QPersistentModelIndex(inlet_index))
                        case GraphItemType.INLET | None:
                            inlet_keys.append(QPersistentModelIndex(inlet_index))
                        case _:
                            raise ValueError(f"Invalid item type for child of NODE: {self.itemType(inlet_index)}")

                if inlet_keys:
                    self.inletsInserted.emit(inlet_keys)
                if outlet_keys:
                    self.outletsInserted.emit(outlet_keys)

            case GraphItemType.INLET:
                added_links: list[Tuple[QPersistentModelIndex, QPersistentModelIndex, QPersistentModelIndex]] = []

                for row in range(start, end + 1):
                    link_index = self._source_model.index(row, 0, parent)
                    persistent_link_index = QPersistentModelIndex(link_index)
                    persistent_source_index = self.linkSource(link_index)
                    persistent_target_index = self.linkTarget(link_index)

                    IsLinkComplete = persistent_source_index is not None and persistent_target_index is not None
                    if not IsLinkComplete:
                        # incomplete links will not be added to the graph.
                        # when they are completed (by setting the source role), they will be added then. #TODO: make a test for this
                        continue

                    assert isinstance(persistent_source_index, QPersistentModelIndex), f"Link source must be a valid persistent index, got: {persistent_source_index}"
                    assert isinstance(persistent_target_index, QPersistentModelIndex), f"Link target must be a valid persistent index, got: {persistent_target_index}"

                    added_links.append((persistent_link_index, persistent_source_index, persistent_target_index))
                
                if added_links:
                    for link_index, source_index, target_index in added_links:
                        assert isinstance(source_index, QPersistentModelIndex), f"Link source must be a valid persistent index, got: {source_index}"
                        assert isinstance(target_index, QPersistentModelIndex), f"Link target must be a valid persistent index, got: {target_index}"
                        assert isinstance(link_index, QPersistentModelIndex), f"Link must be a valid persistent index, got: {link_index}"
                        self._link_manager.link(link_index, source_index, target_index)
                    self.linksInserted.emit([link_index for link_index, _, _ in added_links])

    def handleRowsAboutToBeRemoved(self, parent:QModelIndex, start:int, end:int):
        assert self._source_model, "Model must be set before handling rows removed!"

        match self.itemType(parent):
            case GraphItemType.SUBGRAPH | None:
                removed_nodes = [QPersistentModelIndex(self._source_model.index(row, 0, parent)) for row in range(start, end + 1)]
                
                for node in removed_nodes:
                    connected_links = []
                    for inlet in self.inlets(node):
                        connected_links.extend(self._link_manager.getInletLinks(inlet))
                    for outlet in self.outlets(node):
                        connected_links.extend(self._link_manager.getOutletLinks(outlet))

                    if connected_links:
                        for link in sorted(connected_links, key=lambda idx: idx.row(), reverse=True):
                            self.removeLink(link)

                if removed_nodes:
                    self.nodesAboutToBeRemoved.emit(removed_nodes)
                
            case GraphItemType.NODE:
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

                if removed_inlets:
                    self.inletsAboutToBeRemoved.emit(removed_inlets)
                if removed_outlets:
                    self.outletsAboutToBeRemoved.emit(removed_outlets)

            case GraphItemType.INLET:
                removed_links = []
                for row in range(start, end + 1):
                    link_index = self._source_model.index(row, 0, parent)
                    persistent_link_index = QPersistentModelIndex(link_index)
                    removed_links.append(persistent_link_index)
            
                if removed_links:
                    self.linksAboutToBeRemoved.emit(removed_links)
                    for link in removed_links:
                        self._link_manager.unlink(link)

    def handleDataChanged(self, top_left:QModelIndex, bottom_right:QModelIndex, roles:List[int]=[]):
        assert self._source_model, "Model must be set before handling data changed!"
        if GraphDataRole.SourceRole in roles or roles == []:
            # If the source role is changed, we need to update the link widget
            removed_links:List[Tuple[QPersistentModelIndex, QPersistentModelIndex, QPersistentModelIndex]] = []
            added_links:List[Tuple[QPersistentModelIndex, QPersistentModelIndex, QPersistentModelIndex]] = []
            for row in range(top_left.row(), bottom_right.row() + 1):
                link_index = self._source_model.index(row, top_left.column(), top_left.parent())
                persistent_link_index = QPersistentModelIndex(link_index)

                old_persistent_source_index = self._link_manager.getLinkSource(persistent_link_index)
                old_persistent_target_index = self._link_manager.getLinkTarget(persistent_link_index)
                removed_links.append((persistent_link_index, old_persistent_source_index, old_persistent_target_index))
                # self.linksRemoved.emit(link_key, old_source_key, old_target_key)

                new_persistent_source_index = QPersistentModelIndex(self._source_model.data(link_index, GraphDataRole.SourceRole))
                new_persistent_target_index = QPersistentModelIndex(link_index.parent())
                added_links.append((persistent_link_index, new_persistent_source_index, new_persistent_target_index))

            for link_index, _, _ in removed_links:
                assert isinstance(link_index, QPersistentModelIndex), "Link must be a valid persistent index"
                self._link_manager.unlink(link_index)

            for persistent_link_index, persistent_source_index, persistent_target_index in added_links:
                assert isinstance(persistent_link_index, QPersistentModelIndex), "Link must be a valid persistent index"
                assert isinstance(persistent_source_index, QPersistentModelIndex), "Link source must be a valid persistent index"
                assert isinstance(persistent_target_index, QPersistentModelIndex), "Link target must be a valid persistent index"
                self._link_manager.link(persistent_link_index, persistent_source_index, persistent_target_index)
            
            self.linksAboutToBeRemoved.emit([link_index for link_index, _, _ in removed_links])
            self.linksInserted.emit([link_index for link_index, _, _ in added_links])

        if GraphDataRole.TypeRole in roles or roles == []:
            # if an inlet or outlet type is changed, we need to update the widget
            raise NotImplementedError("Changing item type is not supported yet.")

        # if display or edit role is changed, we need to update the label
        assert top_left.parent() == bottom_right.parent(), "DataChanged must be within the same parent"

        # collect attribute columns
        changed_columns = list(range(top_left.column(), bottom_right.column() + 1))

        match self.itemType(top_left.parent()):
            case GraphItemType.SUBGRAPH | None:
                changed_nodes = [QPersistentModelIndex(self._source_model.index(row, 0, top_left.parent())) for row in range(top_left.row(), bottom_right.row() + 1)]
                self.nodesDataChanged.emit(changed_nodes, changed_columns, roles)

            case GraphItemType.NODE:
                changed_inlets = []
                changed_outlets = []
                for row in range(top_left.row(), bottom_right.row() + 1):
                    index = self._source_model.index(row, 0, top_left.parent())
                    match self.itemType(index):
                        case GraphItemType.OUTLET:
                            changed_outlets.append(QPersistentModelIndex(index))
                        case GraphItemType.INLET | None:
                            changed_inlets.append(QPersistentModelIndex(index))
                        case _:
                            raise ValueError(f"Invalid item type for child of NODE: {self.itemType(index)}")
                if changed_inlets:
                    self.inletsDataChanged.emit(changed_inlets, changed_columns, roles)
                if changed_outlets:
                    self.outletsDataChanged.emit(changed_outlets, changed_columns, roles)

            case GraphItemType.INLET:
                changed_links = [QPersistentModelIndex(self._source_model.index(row, 0, top_left.parent())) for row in range(top_left.row(), bottom_right.row() + 1)]
                if changed_links:
                    self.linksDataChanged.emit(changed_links, changed_columns, roles)

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

    def data(self, item:QPersistentModelIndex, attribute:int)-> Any:
        index = self._source_model.index(item.row(), attribute, item.parent()) # get the index at column
        return self._source_model.data(index, role=Qt.ItemDataRole.DisplayRole)
    
    def setData(self, item:QPersistentModelIndex, value:Any, attribute:int)-> bool:
        index = self._source_model.index(item.row(), attribute, item.parent()) # get the index at column
        return self._source_model.setData(index, value, role=Qt.ItemDataRole.EditRole)

    def attributeCount(self, item:QPersistentModelIndex) -> int:
        return self._source_model.columnCount(item.parent())
    
    def attributes(self, item:QPersistentModelIndex) -> List[QPersistentModelIndex]:
        attrs = []
        for col in range(self.attributeCount(item)):
            index = self._source_model.index(item.row(), col, item.parent())
            attrs.append(QPersistentModelIndex(index))
        return attrs
    
    ## nodes
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
    
    def links(self) -> List[QPersistentModelIndex]:
        """Return a list of all link indexes in the model."""
        if self._source_model is None:
            return []
        
        links = []
        for node in self.nodes():
            for row in range(self._source_model.rowCount(node)):
                inlet_index = self._source_model.index(row, 0, node)
                if self.itemType(inlet_index) == GraphItemType.INLET:
                    for link_row in range(self._source_model.rowCount(inlet_index)):
                        link_index = self._source_model.index(link_row, 0, inlet_index)
                        if self.itemType(link_index) == GraphItemType.LINK:
                            links.append(QPersistentModelIndex(link_index))
        return links

    def nodeCount(self, subgraph:QModelIndex|None=None) -> int:
        return self._source_model.rowCount(subgraph if subgraph is not None else QModelIndex())

    def linkCount(self) -> int:
        return len(self._link_manager._link_source)

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
    
    def inletNode(self, inlet:QModelIndex|QPersistentModelIndex) -> QPersistentModelIndex|None:
        assert self.itemType(inlet) == GraphItemType.INLET, "Inlet index must be of type INLET"
        node_index = inlet.parent()
        if not node_index.isValid():
            return None
        assert self.itemType(node_index) == GraphItemType.NODE, "Parent of inlet must be of type NODE"
        return QPersistentModelIndex(node_index)
    
    def outletNode(self, outlet:QModelIndex|QPersistentModelIndex) -> QPersistentModelIndex|None:
        assert self.itemType(outlet) == GraphItemType.OUTLET, f"Outlet index must be of type OUTLET, got: {self.itemType(outlet)}"
        node_index = outlet.parent()
        if not node_index.isValid():
            return None
        assert self.itemType(node_index) == GraphItemType.NODE, f"Parent of outlet must be of type NODE, got: {self.itemType(node_index)}"
        return QPersistentModelIndex(node_index)
    
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

    def inLinks(self, inlet:QPersistentModelIndex) -> List[QPersistentModelIndex]:
        """
        Get a list of link indexes for a given inlet.
        Args:
            inlet (QModelIndex): The index of the inlet.
        Returns:
            List[QModelIndex]: A list of link indexes for the inlet.
        """
        assert self.itemType(inlet) == GraphItemType.INLET, "Inlet index must be of type INLET"
        links = []
        for row in range(self._source_model.rowCount(inlet)):
            child_index = self._source_model.index(row, 0, inlet)
            if self.itemType(child_index) == GraphItemType.LINK:
                links.append(child_index)
        return [QPersistentModelIndex(link) for link in links]

    def outLinks(self, outlet:QModelIndex|QPersistentModelIndex) -> List[QPersistentModelIndex]:
        """
        Get a list of link indexes for a given outlet.
        Args:
            outlet (QModelIndex): The index of the outlet.

        Returns:
            List[QModelIndex]: A list of link indexes for the outlet.
        """
        assert self.itemType(outlet) == GraphItemType.OUTLET, "Outlet index must be of type OUTLET"
        link_indexes = self._link_manager.getOutletLinks(QPersistentModelIndex(outlet))

        return [QPersistentModelIndex(link) for link in link_indexes]

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
            # new_node_name = f"{'Node'}#{position + 1}"
            # if not self._model.setData(new_index, new_node_name, Qt.ItemDataRole.DisplayRole):
            #     logger.warning(f"Failed to set data for new node: {new_node_name}")
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
                logger.warning(f"Failed to set 'name' data for new link: {new_link_name}")

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
        """
        assert self._source_model, "Source model must be set before removing a node"
        if not isinstance(node, (QModelIndex, QPersistentModelIndex)):
            logger.error(f"Node must be a QModelIndex or QPersistentModelIndex, got: {type(node)}")
            return False
        # remove links connected to the node
        # collect links
        links_connected = []
        for inlet in self.inlets(node):
            for link in self.inLinks(inlet):
                links_connected.append(QPersistentModelIndex(link))
        for outlet in self.outlets(node):
            for link in self.outLinks(outlet):
                links_connected.append(QPersistentModelIndex(link))

        for link in links_connected:
            self.removeLink(link)

        return self._source_model.removeRows(node.row(), 1, node.parent())
    
    def removeLink(self, link:QModelIndex|QPersistentModelIndex)->bool:
        """
        Remove a link from the graph.
        This removes the link at the specified index from the model.
        """
        assert self._source_model, "Source model must be set before removing a link"
        assert link.isValid(), "Link index must be valid"
        if self._source_model.removeRows(link.row(), 1, link.parent()):
            self._link_manager.unlink(QPersistentModelIndex(link))
            return True
        return False

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

                
                
