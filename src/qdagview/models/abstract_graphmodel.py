from __future__ import annotations

import logging
from abc import ABC, ABCMeta, abstractmethod
from typing import TypeVar, Generic, List, Optional, Any, Hashable

from qtpy.QtGui import *
from qtpy.QtCore import *
from qtpy.QtWidgets import *

from ..core import GraphItemType

logger = logging.getLogger(__name__)

NodeT = TypeVar('NodeT')
InletT = TypeVar('InletT')
OutletT = TypeVar('OutletT')
LinkT = TypeVar('LinkT')
AttributeT = TypeVar('AttributeT')

from typing import Tuple, Literal, TypeAlias

# Create a compatible metaclass that combines QObject's metaclass with ABCMeta
class QABCMeta(type(QObject), ABCMeta):
    pass


class AbstractGraphModel(QObject, ABC, Generic[NodeT, InletT, OutletT, LinkT], metaclass=QABCMeta):
    """
    Controller for a graph backed by a QAbstractItemModel.
    This class provides methods to interact with a graph structure stored in a QAbstractItemModel.
    """

    nodesInserted = Signal(list) # list of NodeT
    nodesAboutToBeRemoved = Signal(list) # list of NodeT
    nodesDataChanged = Signal(list, list, list) # list of NodeT, list of attributes,  list of roles

    inletsInserted = Signal(list) # list of InletT
    inletsAboutToBeRemoved = Signal(list) # list of InletT
    inletsDataChanged = Signal(list, list, list) # list of InletT, list of attributes,  list of roles

    outletsInserted = Signal(list) # list of OutletT
    outletsAboutToBeRemoved = Signal(list) # list of OutletT
    outletsDataChanged = Signal(list, list, list) # list of OutletT, list of attributes,  list of roles

    linksInserted = Signal(list) # list of LinkT
    linksAboutToBeRemoved = Signal(list) # list of LinkT
    linksDataChanged = Signal(list, list, list) # list of LinkT, list of attributes,  list of roles

    attributesInserted = Signal(list) # list of AttributeT
    attributesAboutToBeRemoved = Signal(list) # list of AttributeT
    attributeDataChanged = Signal(list) # list of AttributeT


    def __init__(self, parent:QObject|None=None):
        super().__init__(parent)

    @abstractmethod
    def createIndexForNode(self, name:str)->NodeT:
        pass
    
    @abstractmethod
    def createIndexForInlet(self, name:str, node:NodeT)->InletT:
        pass
    
    @abstractmethod
    def createIndexForOutlet(self, name:str, node:NodeT)->OutletT:
        pass
    
    @abstractmethod
    def createIndexForLink(self, outlet:OutletT, inlet:InletT)->LinkT:
        pass

    @abstractmethod
    def data(self, item:NodeT|InletT|OutletT|LinkT, attribute:Hashable, role:int=Qt.ItemDataRole.DisplayRole) -> Any:
        """
        Get data for the specified graph item.
        This method should be overridden in a subclass to provide access to item attributes.
        Parameters:
            item: The graph item (node, inlet, outlet, or link).
            attribute: The attribute to retrieve.
            role: The Qt data role (default is DisplayRole).
        
        """
        pass
    
    @abstractmethod
    def setData(self, item:NodeT|InletT|OutletT|LinkT, value:Any, attribute:Hashable, role:int=Qt.ItemDataRole.EditRole) -> bool:
        """
        Set data for the specified graph item.
        This method should be overridden in a subclass to provide access to item attributes.
        Parameters:
            item: The graph item (node, inlet, outlet, or link).
            value: The value to set.
            attribute: The attribute to set.
            role: The Qt data role (default is EditRole).
        
        """
        pass

    ## QUERY MODEL
    @abstractmethod
    def itemType(self, item:NodeT|InletT|OutletT|LinkT)-> GraphItemType | None:
        """Get the type of the specified graph item."""
        pass

    @abstractmethod
    def nodeCount(self) -> int:
        """Get the number of nodes in the graph."""
        pass

    @abstractmethod
    def linkCount(self) -> int:
        """Get the number of links in the graph."""
        pass

    @abstractmethod
    def inletCount(self, node:NodeT) -> int:
        """Get the number of inlets for the specified node."""
        pass

    @abstractmethod
    def outletCount(self, node:NodeT) -> int:
        """Get the number of outlets for the specified node."""
        pass

    @abstractmethod
    def nodes(self) -> List[NodeT]:
        """Get the list of nodes."""
        pass

    @abstractmethod
    def nodeInlets(self, node:NodeT) -> List[InletT]:
        """Get the list of inlets for the specified node."""
        pass

    @abstractmethod
    def nodeOutlets(self, node:NodeT) -> List[OutletT]:
        """Get the list of outlets for the specified node."""
        pass

    @abstractmethod
    def inletLinks(self, inlet:InletT) -> List[LinkT]:
        """Get the list of links for the specified inlet."""
        pass

    @abstractmethod
    def outletLinks(self, outlet:OutletT) -> List[LinkT]:
        """Get the list of links for the specified outlet."""
        pass

    @abstractmethod
    def inletNode(self, inlet:InletT) -> NodeT:
        """Get the node associated with the specified inlet."""
        pass

    @abstractmethod
    def outletNode(self, outlet:OutletT) -> NodeT:
        """Get the node associated with the specified outlet."""
        pass

    @abstractmethod
    def linkSource(self, link:LinkT) -> OutletT:
        """Get the source outlet for the specified link."""
        pass

    @abstractmethod
    def linkTarget(self, link:LinkT) -> InletT:
        """Get the target inlet for the specified link."""
        pass

    ## CREATE
    ## # TODO: IMPLEMENT Adding and REMOVING multiple items at once

    def addNode(self)->NodeT|None:
        """
        Add a new node to the graph.
        Base implementation returns None (read-only mode).
        Override in subclass to enable node creation.
        """
        return None

    def addInlet(self, node:NodeT)->InletT|None:
        """
        Add a new inlet to the specified node.
        Base implementation returns None (read-only mode).
        Override in subclass to enable inlet creation.
        """
        return None

    def addOutlet(self, node:NodeT)->OutletT|None:
        """
        Add a new outlet to the specified node.
        Base implementation returns None (read-only mode).
        Override in subclass to enable outlet creation.
        """
        return None

    def addLink(self, outlet:OutletT, inlet:InletT)->LinkT|None:
        """
        Add a new link between the specified outlet and inlet.
        Base implementation returns None (read-only mode).
        Override in subclass to enable link creation.
        """
        return None

    ## DELETE
    def removeNode(self, node:NodeT)->bool:
        """
        Remove the specified node from the graph.
        Override this method in a subclass to support node removal.
        """
        return False

    def removeInlet(self, inlet:InletT)->bool:
        """
        Remove the specified inlet from the graph.
        Override this method in a subclass to support inlet removal.
        """
        return False

    def removeOutlet(self, outlet:OutletT)->bool:
        """
        Remove the specified outlet from the graph.
        Override this method in a subclass to support outlet removal.
        """
        return False

    def removeLink(self, link:LinkT)->bool:
        """
        Remove the specified link from the graph.
        Override this method in a subclass to support link removal.
        """
        return False

