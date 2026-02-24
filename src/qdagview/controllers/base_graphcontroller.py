from __future__ import annotations

import logging
from collections import defaultdict
from itertools import groupby
from operator import attrgetter


logger = logging.getLogger(__name__)

from typing import *

from qtpy.QtGui import *
from qtpy.QtCore import *


from ..core.base_types import GraphT, NodeT, LinkT, PortT
from qdagview.core import GraphDataRole, GraphItemType


from abc import ABC, abstractmethod, ABCMeta

# 1. Create a combined metaclass
class CombinedMeta(type(QObject), ABCMeta):
    pass

class BaseGraphController(QObject, ABC, Generic[GraphT, NodeT, LinkT, PortT], metaclass=CombinedMeta):
    """
    all nodes, links, and ports must be a uniquely identifiable.
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

    ## QUERY MODEL
    @abstractmethod
    def itemType(self, index: QModelIndex) -> GraphItemType:
        """
        Return the type of the item at the given index.
        This is used by the graph view to determine how to render the item.
        """
        ...

    def addNode(self, subgraph:GraphT|None)->NodeT:
        """
        Add a new node to the graph.
        If subgraph is specified, add the node to the given subgraph.
        Returns the _NodeId_ of the newly added node.
        """
        raise NotImplementedError("addNode() method must be implemented by subclass")

    def removeNode(self, node:NodeT)->bool:
        """
        Remove a node from the graph.
        This removes the node at the specified index from the model.
        Note: The view will automatically remove connected links.
        """
        raise NotImplementedError("removeNode() method must be implemented by subclass")

    @abstractmethod
    def nodes(self, subgraph:GraphT|None=None) -> List[NodeT]:
        """Return a list of all _NodeIds_ in the model."""
        ...

    def nodeCount(self, subgraph:GraphT|None=None) -> int:
        """Return the number of nodes in the model."""
        return len(self.nodes(subgraph))
    
    def addInlet(self, node:NodeT)->PortT:
        """Add a new inlet to the given node. Returns the _InletId_ of the newly added inlet."""
        raise NotImplementedError("addInlet() method must be implemented by subclass")

    def removeInlet(self, inlet:PortT)->bool:
        """
        Remove an inlet from the graph.
        This removes the inlet at the specified index from the model.
        Note: The view will automatically remove connected links.
        """
        raise NotImplementedError("removeInlet() method must be implemented by subclass")

    @abstractmethod
    def inletNode(self, inlet:PortT) -> NodeT:
        """Return the node index that the given inlet belongs to.
        If the inlet is invalid or not an inlet, return None. TODO: """
        ...
    
    @abstractmethod
    def inlets(self, node:NodeT) -> List[PortT]:
        """
        Get a list of inlet indexes for a given node.
        Args:
            node (NodeT): The index of the node.
        Returns:
            List[PortT]: A list of inlet indexes for the node.
        """
        ...

    def inletCount(self, node) -> int:
        """
        Get the number of inlets for a given node.
        Args:
            node (QModelIndex): The index of the node.
        Returns:
            int: The number of inlets for the node.
        """
        return len(self.inlets(node))
    
    def addOutlet(self, node:NodeT)->PortT:
        """Add a new outlet to the given node. Returns the _OutletId_ of the newly added outlet.
        when subclasses implement this method, they should emit the outletsInserted signal with the new outlet index."""
        raise NotImplementedError("addOutlet() method must be implemented by subclass")

    def removeOutlet(self, outlet:PortT)->bool:
        """
        Remove an outlet from the graph.
        This removes the outlet at the specified index from the model.
        Note: The view will automatically remove connected links.
        """
        raise NotImplementedError("removeOutlet() method must be implemented by subclass")

    @abstractmethod
    def outletNode(self, outlet:PortT) -> NodeT:
        """Return the node index that the given outlet belongs to.
        If the outlet is invalid or not an outlet, return None. TODO: """
        ...

    @abstractmethod
    def outlets(self, node:NodeT) -> List[PortT]:
        """
        Get a list of outlet indexes for a given node.
        Args:
            node (QModelIndex): The index of the node.
        Returns:
            List[QModelIndex]: A list of outlet indexes for the node.
        """
        ...

    def outletCount(self, node) -> int:
        """
        Get the number of outlets for a given node.
        Args:
            node (QModelIndex): The index of the node.
        Returns:
            int: The number of outlets for the node.
        """
        return len(self.outlets(node))
    
    def addLink(self, outlet:OutletT, inlet:PortT)->LinkT:
        """Add a new link between the given outlet and inlet. Returns the _LinkId_ of the newly added link."""
        raise NotImplementedError("addLink() method must be implemented by subclass")

    @abstractmethod
    def linkSource(self, link_index:LinkT) -> OutletT:
        """Return the source _OutletId_ of the given link index."""
        ...

    def setLinkSource(self, link:LinkT, source:PortT)->bool:
        """Set the source of the given link to the given outlet. Returns True if successful."""
        raise NotImplementedError("setLinkSource() method must be implemented by subclass")
    
    @abstractmethod
    def linkTarget(self, link_index:LinkT) -> InletT:
        """Return the target _InletId_ of the given link index."""
        ...

    @abstractmethod
    def links(self, port:PortT|None=None) -> List[LinkT]:
        """
        Get a list of link indexes connected to the given port.
        If port is None, return all links in the graph.
        Args:
            port (PortT, optional): The index of the port. Defaults to None.
        Returns:
            List[LinkT]: A list of link indexes connected to the port, or all links if port is None.
        """
        ...

    def linkCount(self, port:PortT|None=None) -> int:
        """
        Get the number of links connected to the given port.
        If port is None, return the total number of links in the graph.
        Args:
            port (PortT, optional): The index of the port. Defaults to None.
        Returns:
            int: The number of links connected to the port, or total number of links if port is None.
        """
        return len(self.links(port))
    
    def addAttribute(self, owner:NodeT|PortT|LinkT, name:str) -> Hashable:
        """
        Add a new attribute to the given owner (node, port, or link).
        Returns the _AttributeId_ of the newly added attribute.
        """
        raise NotImplementedError("addAttribute() method must be implemented by subclass")

    def removeAttribute(self, attribute:Hashable)->bool:
        """
        Remove an attribute from the graph.
        This removes the attribute at the specified index from the model.
        """
        raise NotImplementedError("removeAttribute() method must be implemented by subclass")

    @abstractmethod
    def attributeOwner(self, attribute:'AttributeT') -> NodeT|PortT|LinkT:
        """
        Get the owner of a given attribute.
        Args:
            attribute (QModelIndex): The index of the attribute.
        Returns:
            QModelIndex: The index of the owner node or port.
        """
        ...
    
    @abstractmethod
    def attributes(self, owner:NodeT|PortT|LinkT) -> list:
        """
        Get a list of attributes for a given node, port, or link.
        Args:
            owner (QModelIndex): The index of the node, port, or link.
        Returns:
            list: A list of attributes for the node, port, or link.
        """
        ...
    
    # behaviour TODO: move to delegate?
    def canLink(self, source:PortT, target:PortT)->bool:
        """
        Check if linking is possible between the source and target indexes.
        """
        if self.itemType(source) != GraphItemType.Outlet or self.itemType(target) != GraphItemType.Inlet:
            return False
        
        if self.outletNode(source) == self.inletNode(target):
            return False
        
        return True

                
                
