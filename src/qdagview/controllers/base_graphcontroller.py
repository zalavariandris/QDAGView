from __future__ import annotations

import logging
from collections import defaultdict
from itertools import groupby
from operator import attrgetter


logger = logging.getLogger(__name__)

from typing import *

from qtpy.QtGui import *
from qtpy.QtCore import *


from ..core.base_types import GraphT


from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class NodeRef:
    name: Hashable
    def isValid(self):
        return self.name != ""

@dataclass(frozen=True, slots=True)
class InletRef:
    node: NodeRef
    name: Hashable
    def isValid(self):
        return self.node.isValid() and self.name != ""

@dataclass(frozen=True, slots=True)
class OutletRef:
    node: NodeRef
    name: Hashable
    def isValid(self):
        return self.node.isValid() and self.name != ""

@dataclass(frozen=True, slots=True)
class LinkRef:
    source: OutletRef
    target: InletRef
    name: Hashable
    def isValid(self):
        return self.source.isValid() and self.target.isValid()

@dataclass(frozen=True, slots=True)
class AttributeRef:
    owner: NodeRef|InletRef|OutletRef|LinkRef
    name: Hashable
    def isValid(self):
        return self.owner.isValid() and self.name != ""



from qdagview.core import GraphDataRole, GraphItemType


from abc import ABC, abstractmethod, ABCMeta

# 1. Create a combined metaclass
class CombinedMeta(type(QObject), ABCMeta):
    pass

class BaseGraphController(QObject, ABC, metaclass=CombinedMeta):
    """
    all nodes, links, and ports must be a uniquely identifiable.
    """

    nodesInserted =   Signal(list) # list of QPersistentModelIndex
    inletsInserted =  Signal(list) # list of QPersistentModelIndex
    outletsInserted = Signal(list) # list of QPersistentModelIndex
    linksInserted =   Signal(list) # list of QPersistentModelIndex

    nodesAboutToBeInserted =   Signal(list) # list of QPersistentModelIndex
    inletsAboutToBeInserted =  Signal(list) # list of QPersistentModelIndex
    outletsAboutToBeInserted = Signal(list) # list of QPersistentModelIndex
    linksAboutToBeInserted =   Signal(list) # list of QPersistentModelIndex

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
    def itemType(self, index: NodeRef|OutletRef|InletRef|LinkRef) -> GraphItemType:
        """
        Return the type of the item at the given index.
        This is used by the graph view to determine how to render the item.
        """
        ...

    def addNode(self, subgraph:GraphT|None)->NodeRef:
        """
        Add a new node to the graph.
        If subgraph is specified, add the node to the given subgraph.
        Returns the _NodeId_ of the newly added node.
        """
        raise NotImplementedError("addNode() method must be implemented by subclass")

    def removeNode(self, node:NodeRef)->bool:
        """
        Remove a node from the graph.
        This removes the node at the specified index from the model.
        Note: The view will automatically remove connected links.
        """
        raise NotImplementedError("removeNode() method must be implemented by subclass")

    @abstractmethod
    def nodes(self, subgraph:GraphT|None=None) -> List[NodeRef]:
        """Return a list of all _NodeIds_ in the model."""
        ...

    def nodeCount(self, subgraph:GraphT|None=None) -> int:
        """Return the number of nodes in the model."""
        return len(self.nodes(subgraph))
    
    def addInlet(self, node:NodeRef)->InletRef:
        """Add a new inlet to the given node. Returns the _InletId_ of the newly added inlet."""
        raise NotImplementedError("addInlet() method must be implemented by subclass")

    def removeInlet(self, inlet:InletRef)->bool:
        """
        Remove an inlet from the graph.
        This removes the inlet at the specified index from the model.
        Note: The view will automatically remove connected links.
        """
        raise NotImplementedError("removeInlet() method must be implemented by subclass")

    @abstractmethod
    def inletNode(self, inlet:InletRef) -> NodeRef:
        """Return the node index that the given inlet belongs to.
        If the inlet is invalid or not an inlet, return None. TODO: """
        ...
    
    @abstractmethod
    def inlets(self, node:NodeRef) -> List[InletRef]:
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
    
    def addOutlet(self, node:NodeRef)->OutletRef:
        """Add a new outlet to the given node. Returns the _OutletId_ of the newly added outlet.
        when subclasses implement this method, they should emit the outletsInserted signal with the new outlet index."""
        raise NotImplementedError("addOutlet() method must be implemented by subclass")

    def removeOutlet(self, outlet:OutletRef)->bool:
        """
        Remove an outlet from the graph.
        This removes the outlet at the specified index from the model.
        Note: The view will automatically remove connected links.
        """
        raise NotImplementedError("removeOutlet() method must be implemented by subclass")

    @abstractmethod
    def outletNode(self, outlet:OutletRef) -> NodeRef:
        """Return the node index that the given outlet belongs to.
        If the outlet is invalid or not an outlet, return None. TODO: """
        ...

    @abstractmethod
    def outlets(self, node:NodeRef) -> List[OutletRef]:
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
    
    def addLink(self, outlet:OutletRef, inlet:InletRef)->LinkRef:
        """Add a new link between the given outlet and inlet. Returns the _LinkId_ of the newly added link."""
        raise NotImplementedError("addLink() method must be implemented by subclass")

    def removeLink(self, link:LinkRef)->bool:
        """
        Remove a link from the graph.
        This removes the link at the specified index from the model.
        """
        raise NotImplementedError("removeLink() method must be implemented by subclass")

    @abstractmethod
    def linkSource(self, link_index:LinkRef) -> OutletRef:
        """Return the source _OutletId_ of the given link index."""
        ...

    def setLinkSource(self, link:LinkRef, source:OutletRef)->bool:
        """Set the source of the given link to the given outlet. Returns True if successful."""
        raise NotImplementedError("setLinkSource() method must be implemented by subclass")
    
    @abstractmethod
    def linkTarget(self, link_index:LinkRef) -> InletRef:
        """Return the target _InletId_ of the given link index."""
        ...

    @abstractmethod
    def links(self, port:InletRef|OutletRef|None=None) -> List[LinkRef]:
        """
        Get a list of link indexes connected to the given port.
        If port is None, return all links in the graph.
        Args:
            port (InletRef|OutletRef, optional): The index of the port. Defaults to None.
        Returns:
            List[LinkRef]: A list of link indexes connected to the port, or all links if port is None.
        """
        ...

    def linkCount(self, port:InletRef|OutletRef|None=None) -> int:
        """
        Get the number of links connected to the given port.
        If port is None, return the total number of links in the graph.
        Args:
            port (InletRef|OutletRef, optional): The index of the port. Defaults to None.
        Returns:
            int: The number of links connected to the port, or total number of links if port is None.
        """
        return len(self.links(port))
    
    def addAttribute(self, owner:NodeRef|InletRef|OutletRef|LinkRef, name:str) -> AttributeRef:
        """
        Add a new attribute to the given owner (node, port, or link).
        Returns the _AttributeId_ of the newly added attribute.
        """
        raise NotImplementedError("addAttribute() method must be implemented by subclass")

    def removeAttribute(self, attribute:AttributeRef)->bool:
        """
        Remove an attribute from the graph.
        This removes the attribute at the specified index from the model.
        """
        raise NotImplementedError("removeAttribute() method must be implemented by subclass")

    @abstractmethod
    def attributeOwner(self, attribute:AttributeRef) -> NodeRef|OutletRef|InletRef|LinkRef:
        """
        Get the owner of a given attribute.
        Args:
            attribute (QModelIndex): The index of the attribute.
        Returns:
            QModelIndex: The index of the owner node or port.
        """
        ...
    
    @abstractmethod
    def attributes(self, owner:NodeRef|OutletRef|InletRef|LinkRef) -> list:
        """
        Get a list of attributes for a given node, port, or link.
        Args:
            owner (QModelIndex): The index of the node, port, or link.
        Returns:
            list: A list of attributes for the node, port, or link.
        """
        ...
    
    # behaviour TODO: move to delegate?
    def canLink(self, source:OutletRef, target:InletRef)->bool:
        """
        Check if linking is possible between the source and target indexes.
        """
        if self.itemType(source) != GraphItemType.Outlet or self.itemType(target) != GraphItemType.Inlet:
            return False
        
        if self.outletNode(source) == self.inletNode(target):
            return False
        
        return True

                
                
