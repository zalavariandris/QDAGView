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

import networkx as nx

from ..core import GraphDataRole, GraphItemType
from ..views.managers import LinkingManager
from ..utils import make_unique_name, listify

from .abstract_graphmodel import AbstractGraphModel


# Local identifiers - string names unique within their scope
NodeName: TypeAlias = str      # unique within the graph.
InletName: TypeAlias = str     # unique within a node
OutletName: TypeAlias = str    # unique within a node
AttributeName: TypeAlias = str # unique within an item

# Global references - structured identifiers unique within the whole graph
NodeRef = Tuple[Literal['N'], NodeName] 
InletRef = Tuple[Literal['I'], NodeRef, InletName]
OutletRef = Tuple[Literal['O'], NodeRef, OutletName]
LinkRef = Tuple[Literal['L'], OutletRef, InletRef]


class NXGraphModel(AbstractGraphModel[NodeRef, InletRef, OutletRef, LinkRef]):
    """Controller for a graph backed by a NetworkX graph.

    This class provides methods to interact with a graph structure stored in a NetworkX graph.
    """

    ## CREATE
    def addNode(self, name:NodeName|None=None)->NodeRef|None:
        node_name = make_unique_name("node", existing_names=self.graph.nodes)   
        self.graph.add_node(node_name)
        self.graph.nodes[node_name] = {
            'inlets': defaultdict(dict),  # TODO? support for reordering inlets?
            'outlets': defaultdict(dict),
            'attributes': {},
        }
        node = self.createIndexForNode(node_name)
        self.nodesInserted.emit([node])
        return node

    def addInlet(self, node:NodeRef, name:InletName|None=None)->InletRef|None:
        """Add a new inlet to the specified node.
        
        node: NodeRef
            The node to which the inlet will be added.
        name: InletName|None
            The name of the new inlet.
            Name must be unique within the node. If None, a unique name will be generated.
        """
        _, node_name = node
        if node_name not in self.graph.nodes:
            logger.error(f"Node {node_name} does not exist in the graph.")
            return None

        inlets:list[str] = self.graph.nodes[node_name].setdefault('inlets', [])
        if not name:
            name = make_unique_name("in", existing_names=inlets)
        if name in inlets:
            logger.error(f"Cannot add inlet '{name}': inlet name already exists in node '{node_name}'. Inlet names must be unique per node.")
            return None
        
        inlets.append(name)
        inlet = self.createIndexForInlet(name, node)
        self.inletsInserted.emit([inlet])
        return inlet

    def addOutlet(self, node:NodeRef, name:str|None=None)->OutletRef|None:
        _, node_name = node
        if node not in self.graph.nodes:
            logger.error(f"Node {node} does not exist in the graph.")
            return None

        outlets:list[str] = self.graph.nodes[node].setdefault('outlets', [])
        if not name:
            name = make_unique_name("out", existing_names=outlets)
        if name in outlets:
            logger.error(f"Cannot add outlet '{name}': outlet name already exists in node '{node_name}'. Outlet names must be unique per node.")
            return None
        outlets.append(name)

        outlet = self.createIndexForOutlet(name, node)
        self.outletsInserted.emit([outlet])
        return outlet

    def addLink(self, outlet:OutletRef, inlet:InletRef)->LinkRef|None:
        """Add an edge from outlet to inlet.

        Parameters
        ----------
        outlet : OutletType
            The outlet from which the link originates.
        inlet : InletType
            The inlet to which the link connects.

        Returns
        -------
        The link index if the link was added, None otherwise.
        """

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
        if self.graph.has_edge(source_node, target_node, key):
            logger.error(f"Link from outlet {outlet} to inlet {inlet} already exists.")
            return None
        
        self.graph.add_edge(source_node, target_node, key)

        link:LinkRef = self.createIndexForLink(outlet, inlet)
        self.linksInserted.emit([link])
        return link

    # DATA
    def setNodeData(self, node: NodeRef, attribute: AttributeName, value: Any, role: int = Qt.ItemDataRole.DisplayRole) -> bool:
        _, node_name = node
        try:
            self.graph.nodes[node_name]["attributes"][attribute] = value
            return True
        except KeyError:
            return False
        
    def setInletData(self, inlet: InletRef, attribute: AttributeName, value: Any, role: int = Qt.ItemDataRole.DisplayRole) -> bool:
        _, node, inlet_name = inlet
        _, node_name = node
        # get inlet data
        try:
            self.graph.nodes[node_name]["inlets"][inlet_name][attribute] = value
            return True
        except KeyError:
            return False
        
    def setOutletData(self, outlet: OutletRef, attribute: AttributeName, value: Any, role: int = Qt.ItemDataRole.DisplayRole) -> bool:
        _, node, outlet_name = outlet
        _, node_name = node
        # get outlet data
        try:
            self.graph.nodes[node_name]["outlets"][outlet_name][attribute] = value
            return True
        except KeyError:
            return False
        
    def setLinkData(self, link: LinkRef, attribute: AttributeName, value: Any, role: int = Qt.ItemDataRole.DisplayRole) -> bool:
        _, outlet, inlet = link
        ports = (outlet_name, inlet_name)
        _, source_node, outlet_name = self.outletNode(outlet)
        _, target_node, inlet_name = self.inletNode(inlet)
        edge = (source_node, target_node, ports)
        # get edge data
        data = self.graph.edges[edge]
        if attribute not in data:
            return False
        data[attribute] = value
        return True
        
    def nodeData(self, node: NodeRef, attribute: AttributeName, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        _, node_name = node
        try:
            return self.graph.nodes[node_name]["attributes"][attribute]
        except KeyError as err:
            logger.error(f"Error getting node data for {node}, attribute '{attribute}': {err}")
            return None

    def inletData(self, inlet: InletRef, attribute: AttributeName, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        _, node, inlet_name = inlet
        _, node_name = node
        # get inlet data
        try:
            return self.graph.nodes[node_name]["inlets"][inlet_name][attribute]
        except KeyError as err:
            logger.error(f"Error getting inlet data for {inlet}, attribute '{attribute}': {err}")
            return None
    
    def outletData(self, outlet: OutletRef, attribute: AttributeName, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        _, node, outlet_name = outlet
        _, node_name = node
        # get outlet data
        try:
            return self.graph.nodes[node_name]["outlets"][outlet_name][attribute]
        except KeyError as err:
            logger.error(f"Error getting outlet data for {outlet}, attribute '{attribute}': {err}")
            return None

    def linkData(self, link: LinkRef, attribute: AttributeName, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        _, outlet, inlet = link
        ports = (outlet_name, inlet_name)
        _, source_node, outlet_name = self.outletNode(outlet)
        _, target_node, inlet_name = self.inletNode(inlet)
        edge = (source_node, target_node, ports)

        # get edge data
        try:
            return self.graph.edges[edge][attribute]
        except KeyError as err:
            logger.error(f"Error getting link data for {link}, attribute '{attribute}': {err}")
            return None

    def __init__(self, parent: QObject | None=None):
        super().__init__(parent)
        self.graph = nx.MultiDiGraph()
        self._link_manager = LinkingManager[QPersistentModelIndex, QPersistentModelIndex, QPersistentModelIndex]()

    # index creation
    def createIndexForNode(self, name:NodeName)->NodeRef:
        node:NodeRef = ('N', name)
        return node
    
    def createIndexForInlet(self, name:InletName, node:NodeRef)->InletRef:
        inlet:InletRef = ('I', node, name)
        return inlet
    
    def createIndexForOutlet(self, name:OutletName, node:NodeRef)->OutletRef:
        outlet:OutletRef = ('O', node, name)
        return outlet
    
    def createIndexForLink(self, outlet:OutletRef, inlet:InletRef)->LinkRef:
        link:LinkRef = ('L', outlet, inlet)
        return link

    def getNodeName(self, node:NodeRef)->NodeName:
        _, name = node
        return name
    
    def getInletName(self, inlet:InletRef)->InletName:
        _, _, name = inlet
        return name
    
    def getOutletName(self, outlet:OutletRef)->OutletName:
        _, _, name = outlet
        return name

    ## QUERY MODEL
    def itemType(self, item:NodeRef|InletRef|OutletRef|LinkRef)-> GraphItemType | None:
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
    
    def nodeCount(self) -> int:
        return len(self.graph.nodes)

    def linkCount(self) -> int:
        return len(self.graph.edges)

    def inletCount(self, node:NodeRef) -> int:
        """
        Get the number of inlets for a given node.
        Args:
            node (QModelIndex): The index of the node.
        Returns:
            int: The number of inlets for the node.
        """
        inlets = self.graph.nodes[node].get('inlets', [])
        return len(inlets)

    def outletCount(self, node:NodeRef) -> int:
        outlets = self.graph.nodes[node].get('outlets', [])
        return len(outlets)
    
    @listify
    def nodes(self) -> Generator[NodeRef, None, None]:
        """Return a list of all node indexes in the model."""        
        for n, data in self.graph.nodes(data=True):
            yield self.createIndexForNode(n)
    
    @listify
    def links(self) -> Generator[LinkRef, None, None]:
        """Return a list of all link indexes in the model."""
        for source_node_name, target_node_name, ports in self.graph.edges(keys=True):
            outlet_name, inlet_name = ports
            source_node:NodeRef = self.createIndexForNode(source_node_name)
            outlet:OutletRef = self.createIndexForOutlet(outlet_name, source_node)
            target_node:NodeRef = self.createIndexForNode(target_node_name)
            inlet:InletRef = self.createIndexForInlet(inlet_name, target_node)

            yield self.createIndexForLink(outlet, inlet)

    @listify
    def nodeInlets(self, node:NodeRef) -> Generator[InletRef, None, None]:
        for inlet_name in self.graph.nodes[node].get('inlets', []):
            yield self.createIndexForInlet(inlet_name, node)

    @listify
    def nodeOutlets(self, node:NodeRef) -> Generator[OutletRef, None, None]:
        for outlet_name in self.graph.nodes[node].get('outlets', []):
            yield self.createIndexForOutlet(outlet_name, node)

    @listify
    def inletLinks(self, inlet:InletRef) -> Generator[LinkRef, None, None]:
        _, target_node, inlet_name = inlet
        target_node_name = self.getNodeName(target_node)
        _, target_node_name = target_node
        for source_node_name, _, port_names in self.graph.in_edges(target_node_name, keys=True):
            if port_names[1] != inlet_name:
                continue # skip if link is not for this inlet

            # get outlet info
            source_node:NodeRef = ("N", source_node_name)
            outlet_name = port_names[0]
            outlet:OutletRef = ("O", source_node, outlet_name)

            yield self.createIndexForLink(outlet, inlet)

    @listify
    def outletLinks(self, outlet:QModelIndex|QPersistentModelIndex) -> Generator[LinkRef, None, None]:
        _, source_node, outlet_name = outlet
        source_node_name = self.getNodeName(source_node)
        for _, target_node_name, port_names in self.graph.out_edges(source_node_name, keys=True):
            if port_names[0] != outlet_name:
                continue # skip if link is not for this outlet

            # get outlet info
            target_node:NodeRef = ("N", target_node_name)
            inlet:InletRef = ("I", target_node, port_names[1])

            yield self.createIndexForLink(outlet, inlet)

    def inletNode(self, inlet:InletRef) -> NodeRef:
        _, node, name = inlet
        return node
    
    def outletNode(self, outlet:OutletRef) -> NodeRef:
        _, node, name = outlet
        return node

    def linkSource(self, link:LinkRef) -> OutletRef|None:
        _, outlet, inlet = link
        return outlet
    
    def linkTarget(self, link:LinkRef) -> OutletRef|None:
        _, outlet, inlet = link
        return inlet

    ## DELETE
    def removeNode(self, node:NodeRef)->bool:
        if node not in self.graph.nodes:
            logger.error(f"Node {node} does not exist in the graph.")
            return False
        
        self.nodesAboutToBeRemoved.emit([node])
        self.graph.remove_node(node)
        return True
    
    def removeInlet(self, inlet:InletRef)->bool:
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
    
    def removeOutlet(self, outlet:OutletRef)->bool:
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
    
    def removeLink(self, link:LinkRef)->bool:
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

                
                
