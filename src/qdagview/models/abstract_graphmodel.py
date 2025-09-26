from __future__ import annotations

import logging
from abc import ABC, ABCMeta, abstractmethod
from typing import Literal, TypeVar, Generic, List, Tuple, Any

from qtpy.QtGui import *
from qtpy.QtCore import *
from qtpy.QtWidgets import *

from ..core import GraphItemType

logger = logging.getLogger(__name__)


NodeName:      TypeAlias = str # unique within the graph.
InletName:     TypeAlias = str # unique within a node
OutletName:    TypeAlias = str # unique within a node
AttributeName: TypeAlias = str # unique within an item

# NodeRefT =   Tuple[Literal['N'], NodeName] 
# InletRefT =  Tuple[Literal['I'], NodeRefT, InletName]
# OutletRefT = Tuple[Literal['O'], NodeRefT, OutletName]
# LinkRefT =   Tuple[Literal['L'], OutletRefT, InletRefT]


class GraphItemRef:
    __slots__ = ('_name', '_ptr', '_model')
    def __init__(self, model: AbstractGraphModel, name:str, ptr:Any):
        object.__setattr__(self, '_name', name)
        object.__setattr__(self, '_ptr', ptr)
        object.__setattr__(self, '_model', weakref_ref(model))

    def __setattr__(self, name, value):
        raise AttributeError("Instances of Ref are immutable")

    def kind(self)->GraphItemType:
        raise NotImplementedError()

    def name(self)->str:
        return self._name
    
    def ptr(self)->Any:
        return self._ptr
    
    def model(self)->AbstractGraphModel:
        model = self._model()
        if model is None:
            raise ReferenceError("The AbstractGraphModel referenced by this NodeRef has been garbage collected.")
        return model
    
    def isValid(self)->bool:
        # TODO: check if the referenced item still exists in the model
        model = self._model()
        return model is not None

class NodeRef(GraphItemRef):
    def kind(self)->GraphItemType:
        return GraphItemType.NODE
    
class InletRef(GraphItemRef):
    def kind(self)->GraphItemType:
        return GraphItemType.INLET

class OutletRef(GraphItemRef):
    def kind(self)->GraphItemType:
        return GraphItemType.OUTLET

class LinkRef(GraphItemRef):
    def kind(self)->GraphItemType:
        return GraphItemType.LINK

class AttributeRef(GraphItemRef):
    def kind(self)->GraphItemType:
        return GraphItemType.ATTRIBUTE

from weakref import ref as weakref_ref

from typing import Tuple, Literal, TypeAlias

# Create a compatible metaclass that combines QObject's metaclass with ABCMeta
class QABCMeta(type(QObject), ABCMeta):
    pass


class AbstractGraphModel(QObject):
    """
    Controller for a graph backed by a QAbstractItemModel.
    This class provides methods to interact with a graph structure stored in a QAbstractItemModel.
    """

    nodesInserted = Signal(list) # list of NodeRef
    nodesAboutToBeRemoved = Signal(list) # list of NodeRef

    inletsInserted = Signal(list) # list of InletRef
    inletsAboutToBeRemoved = Signal(list) # list of InletRef
    
    outletsInserted = Signal(list) # list of OutletRef
    outletsAboutToBeRemoved = Signal(list) # list of OutletRef

    linksInserted = Signal(list) # list of LinkRef
    linksAboutToBeRemoved = Signal(list) # list of LinkRef

    attributesInserted = Signal(list) # list of AttributeRef
    attributesAboutToBeRemoved = Signal(list) # list of AttributeRef
    dataChanged = Signal(list, list) # list of AttributeRef, list of roles


    def __init__(self, parent:QObject|None=None):
        super().__init__(parent)

    ## Reference CREATION
    def createNodeRef(self, name:NodeName, ptr:Any=None)->NodeRef:
        return NodeRef(self, name, ptr)
    
    def createInletRef(self, name:InletName, ptr:Any)->InletRef:
        return InletRef(self, name, ptr)
    
    def createOutletRef(self, name:OutletName, ptr:Any)->OutletRef:
        return OutletRef(self, name, ptr)
    
    def createLinkRef(self, ptr:Any)->LinkRef:
        return LinkRef(self, "", ptr)

    def createAttributeRef(self, name:AttributeName, ptr:Any)->AttributeRef:
        return AttributeRef(self, name, ptr)

    @abstractmethod
    def nodeRef(self, name:NodeName)->NodeRef:
        return self.createNodeRef(name, None)
    
    @abstractmethod
    def inletRef(self, name:InletName, node:NodeRef)->InletRef:
        node_name = node.name()
        return self.createInletRef(name, node_name)
    
    @abstractmethod
    def outletRef(self, name:OutletName, node:NodeRef)->OutletRef:
        node_name = node.name()
        return self.createOutletRef(name, node_name)
    
    @abstractmethod
    def linkRef(self, outlet:OutletRef, inlet:InletRef)->LinkRef:
        outlet_name = outlet.name()
        source_node_name = outlet.ptr()
        inlet_name = inlet.name()
        target_node_name = inlet.ptr()
        ptr = (source_node_name, outlet_name, target_node_name, inlet_name)
        return self.createLinkRef("link", ptr)

    @abstractmethod
    def attributeRef(self, name:AttributeName, parent:GraphItemRef)->AttributeRef:
        parent_ptr = parent.ptr() 
        return self.createAttributeRef(name, parent_ptr)
    
    ## CREATE
    ## # TODO: IMPLEMENT Adding and REMOVING multiple items at once
    def addNode(self, name:NodeName|None=None)->NodeRef|None:
        """
        Add a new node to the graph.
        Base implementation returns None (read-only mode).
        Override in subclass to enable node creation.
        """
        return None

    def addInlet(self, node:NodeRef, name:InletName|None=None)->InletRef|None:
        """
        Add a new inlet to the specified node.
        Base implementation returns None (read-only mode).
        Override in subclass to enable inlet creation.
        """
        return None

    def addOutlet(self, node:NodeRef, name:OutletName|None=None)->OutletRef|None:
        """
        Add a new outlet to the specified node.
        Base implementation returns None (read-only mode).
        Override in subclass to enable outlet creation.
        """
        return None

    def addLink(self, outlet:OutletRef, inlet:InletRef)->LinkRef|None:
        """
        Add a new link between the specified outlet and inlet.
        Base implementation returns None (read-only mode).
        Override in subclass to enable link creation.
        """
        return None

    ## DELETE
    def removeNode(self, node:NodeRef)->bool:
        """
        Remove the specified node from the graph.
        Override this method in a subclass to support node removal.
        """
        return False

    def removeInlet(self, inlet:InletRef)->bool:
        """
        Remove the specified inlet from the graph.
        Override this method in a subclass to support inlet removal.
        """
        return False

    def removeOutlet(self, outlet:OutletRef)->bool:
        """
        Remove the specified outlet from the graph.
        Override this method in a subclass to support outlet removal.
        """
        return False

    def removeLink(self, link:LinkRef)->bool:
        """
        Remove the specified link from the graph.
        Override this method in a subclass to support link removal.
        """
        return False

    ## DATA UPDATE
    def setData(self, attribute: AttributeRef, value: Any, role: int = Qt.ItemDataRole.DisplayRole) -> bool:
        return False
        
    ## READ DATA
    @abstractmethod
    def data(self, attribute: AttributeRef, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        return None

    ## QUERY DATA
    def nodeAttributes(self, node:NodeRef) -> List[AttributeName]:
        """Get the list of attribute names for the specified node."""
        return []

    def inletAttributes(self, inlet:InletRef) -> List[AttributeName]:
        """Get the list of attribute names for the specified inlet."""
        return []

    def outletAttributes(self, outlet:OutletRef) -> List[AttributeName]:
        """Get the list of attribute names for the specified outlet."""
        return []

    def linkAttributes(self, link:LinkRef) -> List[AttributeName]:
        """Get the list of attribute names for the specified link."""
        return []

    ## QUERY MODEL
    def itemType(self, item:GraphItemRef)-> GraphItemType | None:
        return item.kind()

    @abstractmethod
    def nodeCount(self) -> int:
        """Get the number of nodes in the graph."""
        pass

    @abstractmethod
    def linkCount(self, item:InletRef|OutletRef|None) -> int:
        """Get the number of links.
        If item is None, return the total number of links in the graph.
        If item is an InletRef or OutletRef, return the number of links connected to that port.
        """
        pass

    @abstractmethod
    def inletCount(self, node:NodeRef) -> int:
        """Get the number of inlets for the specified node."""
        pass

    @abstractmethod
    def outletCount(self, node:NodeRef) -> int:
        """Get the number of outlets for the specified node."""
        pass

    ### item relationships
    @abstractmethod
    def nodes(self) -> List[NodeRef]:
        """Get the list of nodes."""
        pass

    @abstractmethod
    def inlets(self, node:NodeRef) -> List[InletRef]:
        """Get the list of inlets for the specified node."""
        pass

    @abstractmethod
    def outlets(self, node:NodeRef) -> List[OutletRef]:
        """Get the list of outlets for the specified node."""
        pass

    @abstractmethod
    def inletNode(self, inlet:InletRef) -> NodeRef:
        """Get the node associated with the specified inlet."""
        pass

    @abstractmethod
    def outletNode(self, outlet:OutletRef) -> NodeRef:
        """Get the node associated with the specified outlet."""
        pass

    @abstractmethod
    def linkSource(self, link:LinkRef) -> OutletRef:
        """Get the source outlet for the specified link."""
        pass

    @abstractmethod
    def linkTarget(self, link:LinkRef) -> InletRef:
        """Get the target inlet for the specified link."""
        pass

    @abstractmethod
    def attributeOwner(self, attribute:AttributeRef) -> GraphItemRef:
        """Get the parent item for the specified attribute."""
        pass