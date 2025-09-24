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

import networkx as nx


NodeType = Tuple[Literal['N'], str] # (type, node_id)
InletType = Tuple[Literal['I'], NodeType, str]
OutletType = Tuple[Literal['O'], NodeType, str]
LinkType = Tuple[Literal['L'], OutletType, InletType]
AttributeType = Tuple[Literal['A'], NodeType|InletType|OutletType|LinkType, str]

from ..utils import make_unique_name, listify

from .abstract_graphmodel import AbstractGraphModel

class NXGraphModel(AbstractGraphModel[None, NodeType, InletType, OutletType, LinkType]):
    """
    Controller for a graph backed by a NetworkX graph.
    This class provides methods to interact with a graph structure stored in a NetworkX graph.
    """

    nodesInserted = Signal(list) # list of NodeType
    nodesAboutToBeRemoved = Signal(list) # list of NodeType
    # nodesDataChanged = Signal(list, list, list) # list of NodeType, list of columns,  list of roles

    inletsInserted = Signal(list) # list of QPersistentModelIndex
    inletsAboutToBeRemoved = Signal(list) # list of QPersistentModelIndex
    # inletsDataChanged = Signal(list, list, list) # list of QPersistentModelIndex, list of columns,  list of roles

    outletsInserted = Signal(list) # list of QPersistentModelIndex
    outletsAboutToBeRemoved = Signal(list) # list of QPersistentModelIndex
    # outletsDataChanged = Signal(list, list, list) # list of QPersistentModelIndex, list of columns,  list of roles

    linksInserted = Signal(list) # list of QPersistentModelIndex
    linksAboutToBeRemoved = Signal(list) # list of QPersistentModelIndex
    # linksDataChanged = Signal(list, list, list) # list of QPersistentModelIndex, list of columns,  list of roles

    attributesInserted = Signal(list) # list of AttributeT
    attributesAboutToBeRemoved = Signal(list) # list of AttributeT
    attributeDataChanged = Signal(list) # list of AttributeT

    def data(self, attribute:AttributeType, role:int=Qt.ItemDataRole.DisplayRole) -> Any:
        kind, item, attribute_name = attribute
        match kind:
            case 'N':
                data = self.graph.nodes[item]
                return data.get(attribute_name, None)
            case 'I':
                data = self.graph.nodes[item]
                data.get('inlet_attributes')
            case 'O':
                ...
            case 'L':
                data = self.graph.links[item]
                return data.get(attribute_name, None)
            case _:
                return None 

    def setData(self, attribute:AttributeType, value:Any, role:int=Qt.ItemDataRole.DisplayRole):
        kind, item, attribute_name = attribute
        match kind:
            case 'N':
                data = self.graph.nodes[item]
                return data.get(attribute_name, None)
            case 'I':
                data = self.graph.nodes[item]
                data.get('inlet_attributes')
            case 'O':
                ...
            case 'L':
                data = self.graph.links[item]
                return data.get(attribute_name, None)
            case _:
                return None 

    def __init__(self, parent: QObject | None=None):
        super().__init__(parent)
        self.graph = nx.MultiDiGraph()
        self._link_manager = LinkingManager[QPersistentModelIndex, QPersistentModelIndex, QPersistentModelIndex]()

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
    
    ## QUERY MODEL
    def itemType(self, item:NodeType|InletType|OutletType|LinkType)-> GraphItemType | None:
        kind = item[0]
        match kind:
            case 'N':
                return GraphItemType.NODE
            case 'I':
                return GraphItemType.INLET
            case 'O':
                return GraphItemType.OUTLET
            case 'L':
                return GraphItemType.LINK
            case _:
                logger.warning(f"Unknown item type: {kind}")
                return None
    
    def nodeCount(self, subgraph:QModelIndex|None=None) -> int:
        if subgraph is not None:
            raise NotImplementedError("Subgraphs are not supported yet.")
        return len(self.graph.nodes)

    def linkCount(self) -> int:
        return len(self.graph.edges)

    def inletCount(self, node:NodeType) -> int:
        """
        Get the number of inlets for a given node.
        Args:
            node (QModelIndex): The index of the node.
        Returns:
            int: The number of inlets for the node.
        """
        inlets = self.graph.nodes[node].get('inlets', [])
        return len(inlets)

    def outletCount(self, node:NodeType) -> int:
        outlets = self.graph.nodes[node].get('outlets', [])
        return len(outlets)
    
    @listify
    def nodes(self, subgraph:QModelIndex|None=None) -> Generator[NodeType, None, None]:
        """Return a list of all node indexes in the model."""
        if subgraph is not None:
            raise NotImplementedError("Subgraphs are not supported yet.")
        for n, data in self.graph.nodes(data=True):
            yield 'N', n, data.get('expression', '')
    
    @listify
    def links(self) -> Generator[LinkType, None, None]:
        """Return a list of all link indexes in the model."""
        for source_node_name, target_node_name, ports, data in self.graph.edges(keys=True, data=True):
            outlet_name, inlet_name = ports
            source_node:NodeType = ('N', source_node_name)
            outlet:OutletType = ('O', source_node, outlet_name)
            target_node:NodeType = ('N', target_node_name)
            inlet:InletType = ('I', target_node, inlet_name)

            link:LinkType = 'L', outlet, inlet
            yield link

    @listify
    def nodeInlets(self, node:NodeType) -> Generator[InletType, None, None]:
        for inlet_name in self.graph.nodes[node].get('inlets', []):
            inlet:InletType = 'I', node, inlet_name
            yield inlet

    @listify
    def nodeOutlets(self, node:NodeType) -> Generator[OutletType, None, None]:
        for outlet_name in self.graph.nodes[node].get('outlets', []):
            outlet:OutletType = 'O', node, outlet_name
            yield outlet

    @listify
    def inletLinks(self, inlet:InletType) -> Generator[LinkType, None, None]:
        _, target_node, inlet_name = inlet
        for source_node_name, _, port_names in self.graph.in_edges(target_node, keys=True):
            if port_names[1] != inlet_name:
                continue # skip if link is not for this inlet

            # get outlet info
            source_node:NodeType = ("N", source_node_name)
            outlet_name = port_names[0]
            outlet:OutletType = ("O", source_node, outlet_name)

            yield "L", outlet, inlet

    @listify
    def outletLinks(self, outlet:QModelIndex|QPersistentModelIndex) -> Generator[LinkType, None, None]:
        _, source_node, outlet_name = outlet
        for _, target_node_name, port_names in self.graph.in_edges(source_node, keys=True):
            if port_names[0] != outlet_name:
                continue # skip if link is not for this outlet

            # get outlet info
            target_node:NodeType = ("N", target_node_name)
            inlet:InletType = ("I", target_node, port_names[1])

            yield "L", outlet, inlet

    def inletNode(self, inlet:InletType) -> NodeType:
        _, node, name = inlet
        return node
    
    def outletNode(self, outlet:OutletType) -> NodeType:
        _, node, name = outlet
        return node

    def linkSource(self, link:LinkType) -> OutletType|None:
        _, outlet, inlet = link
        return outlet
    
    def linkTarget(self, link:LinkType) -> OutletType|None:
        _, outlet, inlet = link
        return inlet

    ## CREATE
    def addNode(self, subgraph:object|None=None)->NodeType|None:
        if subgraph is not None:
            raise NotImplementedError("Subgraphs are not supported yet.")
        
        node_name = make_unique_name("node", existing_names=self.graph.nodes)   
        self.graph.add_node(node_name)

        node:NodeType = ('N', node_name, '')
        self.nodesInserted.emit([node])
        return node

    def addInlet(self, node:NodeType)->InletType|None:
        _, node_id = node
        if node not in self.graph.nodes:
            logger.error(f"Node {node} does not exist in the graph.")
            return None

        inlets:list[str] = self.graph.nodes[node].setdefault('inlets', [])
        inlet_name = make_unique_name("in", existing_names=inlets)
        inlets.append(inlet_name)

        inlet = ('I', node, inlet_name)
        self.inletsInserted.emit([inlet])
        return inlet

    def addOutlet(self, node:NodeType)->OutletType|None:
        _, node_id = node
        if node not in self.graph.nodes:
            logger.error(f"Node {node} does not exist in the graph.")
            return None

        outlets:list[str] = self.graph.nodes[node].setdefault('outlets', [])
        outlet_name = make_unique_name("out", existing_names=outlets)
        outlets.append(outlet_name)

        outlet = ('O', node, outlet_name)
        self.outletsInserted.emit([outlet])
        return outlet

    def addLink(self, outlet:OutletType, inlet:InletType)->LinkType|None:
        _, source_node, outlet_name = outlet
        _, target_node, inlet_name = inlet

        if source_node not in self.graph.nodes:
            logger.error(f"Source node {source_node} does not exist in the graph.")
            return None
        if target_node not in self.graph.nodes:
            logger.error(f"Target node {target_node} does not exist in the graph.")
            return None

        if outlet_name not in self.graph.nodes[source_node].get('outlets', []):
            logger.error(f"Outlet {outlet_name} does not exist in node {source_node}.")
            return None
        if inlet_name not in self.graph.nodes[target_node].get('inlets', []):
            logger.error(f"Inlet {inlet_name} does not exist in node {target_node}.")
            return None

        # add edge to graph
        key = (outlet_name, inlet_name)
        self.graph.add_edge(source_node, target_node, key=key)

        link:LinkType = 'L', outlet, inlet
        self.linksInserted.emit([link])
        return link

    ## DELETE
    def removeNode(self, node:NodeType)->bool:
        if node not in self.graph.nodes:
            logger.error(f"Node {node} does not exist in the graph.")
            return False
        self.nodesAboutToBeRemoved.emit([node])
        self.graph.remove_node(node)
        return True
    
    def removeInlet(self, inlet:InletType)->bool:
        _, node, inlet_name = inlet
        if node not in self.graph.nodes:
            logger.error(f"Node {node} does not exist in the graph.")
            return False
        
        inlets:list[str] = self.graph.nodes[node].get('inlets', [])
        if inlet_name not in inlets:
            logger.error(f"Inlet {inlet} does not exist in the graph.")
            return False
        
        # remove all links connected to this inlet
        links_to_remove = [link for link in self.inletLinks(inlet)]
        for link in links_to_remove:
            self.removeLink(link)
        
        self.inletsAboutToBeRemoved.emit([inlet])
        inlets.remove(inlet_name)

        return True
    
    def removeOutlet(self, outlet:OutletType)->bool:
        _, node, outlet_name = outlet
        if node not in self.graph.nodes:
            logger.error(f"Node {node} does not exist in the graph.")
            return False
        
        outlets:list[str] = self.graph.nodes[node].get('outlets', [])
        if outlet_name not in outlets:
            logger.error(f"Outlet {outlet} does not exist in the graph.")
            return False
        
        # remove all links connected to this outlet
        links_to_remove = [link for link in self.outletLinks(outlet)]
        for link in links_to_remove:
            self.removeLink(link)
        
        self.outletsAboutToBeRemoved.emit([outlet])
        outlets.remove(outlet_name)

        return True
    
    def removeLink(self, link:LinkType)->bool:
        if link not in self.graph.edges(keys=True):
            logger.error(f"Link {link} does not exist in the graph.")
            return False
        source_node, target_node, ports = link
        self.linksAboutToBeRemoved.emit([link])
        self.graph.remove_edge(source_node, target_node, key=ports)
        return True

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
        assert self._model, "Source model must be set before removing an item"

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
                if not self._model.removeRows(start_row, count, parent):
                    success = False
                    logger.warning(f"Failed to remove rows {start_row}-{start_row + count - 1} from parent {parent}")
        
        return success

                
                
