

from qdagview.controllers.base_graphcontroller import BaseGraphController
import networkx as nx
from typing import List, Dict, Any
from qtpy.QtCore import *
from qtpy.QtGui import *
from qdagview.core import GraphDataRole, GraphItemType

from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class NodeRef:
    id: str

@dataclass(frozen=True, slots=True)
class InletRef:
    node: NodeRef
    name: str

@dataclass(frozen=True, slots=True)
class OutletRef:
    node: NodeRef
    name: str

@dataclass(frozen=True, slots=True)
class LinkRef:
    source: OutletRef
    target: InletRef

@dataclass(frozen=True, slots=True)
class AttributeRef:
    owner: NodeRef|InletRef|OutletRef|LinkRef
    name: str

class NXGraphController(BaseGraphController):
    def __init__(self, graph:nx.MultiDiGraph|None=None, parent=None):
        super().__init__(parent)
        self.G = graph if graph is not None else nx.MultiDiGraph() # underlying NetworkX graph

    def addNode(self, subgraph=None) -> NodeRef:
        if subgraph is not None:
            raise NotImplementedError("Subgraph support is not implemented in this example")
        node_count = len(self.G.nodes)
        new_node_ref = NodeRef(id=f"n{node_count+1}")
        self.G.add_node(new_node_ref, 
            inlets=[InletRef(node=new_node_ref, name="inlet")], 
            outlets=[OutletRef(node=new_node_ref, name="outlet")])
        
        self.nodesInserted.emit([new_node_ref]) # TODO: emit correct index
        return new_node_ref

    def nodes(self, subgraph=None):
        if subgraph is not None:
            raise NotImplementedError("Subgraph support is not implemented in this example")
        return [n for n in self.G.nodes()]

    def nodeCount(self, subgraph = None):
        if subgraph is not None:
            raise NotImplementedError("Subgraph support is not implemented in this example")
        
        return len(self.G.nodes)
    
    def addInlet(self, node:NodeRef) -> InletRef:
        inlets_count = len(self.G.nodes[node]['inlets'])
        new_inlet_ref = InletRef(node=node, name=f"inlet{inlets_count+1}")
        self.G.nodes[node]['inlets'].append(new_inlet_ref)
        self.inletsInserted.emit(node, [new_inlet_ref]) # TODO: emit correct index
        return new_inlet_ref
    
    def inletCount(self, node:NodeRef):
        return len(self.G.nodes[node]['inlets'])
    
    def inlets(self, node:NodeRef):
        return self.G.nodes[node]['inlets']
    
    def addOutlet(self, node:NodeRef) -> OutletRef:
        outlets_count = len(self.G.nodes[node]['outlets'])
        new_outlet_ref = OutletRef(node=node, name=f"outlet{outlets_count+1}")
        self.G.nodes[node]['outlets'].append(new_outlet_ref)
        self.outletsInserted.emit(node, [new_outlet_ref]) # TODO: emit correct index
        return new_outlet_ref
    
    def outletCount(self, node:NodeRef):
        return len(self.G.nodes[node]['outlets'])
    
    def outlets(self, node:NodeRef):
        return self.G.nodes[node]['outlets']
    
    def addLink(self, outlet_index:OutletRef, inlet_index:InletRef) -> bool:
        if not self.canLink(outlet_index, inlet_index):
            return False
        source_node = self.outletNode(outlet_index)
        target_node = self.inletNode(inlet_index)
        self.G.add_edge(source_node, target_node, key=(outlet_index, inlet_index)) # use port indexes as edge key to allow multiple edges between same nodes
        self.linksInserted.emit([LinkRef(source=outlet_index, target=inlet_index)]) # TODO: emit correct index
        return True
    
    def links(self, port:InletRef|OutletRef|None=None)-> List[LinkRef]:
        match port:
            case InletRef():
                node = self.inletNode(port)
                in_edges = self.G.in_edges(node, keys=True)
                return [LinkRef(source=k[0], target=port) for u, v, k in in_edges if k[1] == port] # count only edges connected to the specific inlet
            
            case OutletRef():
                node = self.outletNode(port)
                out_edges = self.G.out_edges(node, keys=True)
                return [LinkRef(source=port, target=k[1]) for u, v, k in out_edges if k[0] == port] # count only edges connected to the specific outlet
            
            case None:
                return [LinkRef(source=k[0], target=k[1]) for u, v, k in self.G.edges(keys=True)]
            
            case _:
                raise ValueError(f"Invalid port type: {port}")

    def linkCount(self, port:InletRef|OutletRef|None=None)->int:
        return len(self.links(port))
    
    def inletNode(self, inlet:InletRef)->NodeRef:
        return inlet.node
    
    def outletNode(self, outlet:OutletRef)->NodeRef:
        return outlet.node
    
    def linkSource(self, link:LinkRef) -> OutletRef:
        return link.source
    
    def linkTarget(self, link:LinkRef) -> InletRef:
        return link.target
    
    def canLink(self, source_port:OutletRef|InletRef, target_port:OutletRef|InletRef) -> bool:
        # For simplicity, allow linking any outlet to any inlet
        return isinstance(source_port, OutletRef) and isinstance(target_port, InletRef)

        ## Data
    
    def attributes(self, index:NodeRef|InletRef|OutletRef|LinkRef) -> List[AttributeRef]:
        match index:
            case NodeRef():
                return [AttributeRef(owner=index, name="name")]
            case InletRef():
                return [AttributeRef(owner=index, name="name")]
            case OutletRef():
                return [AttributeRef(owner=index, name="name")]
            case LinkRef():
                return [AttributeRef(owner=index, name="source"), AttributeRef(owner=index, name="target")]
            case _:
                return []
        
    def attributeOwner(self, attribute:AttributeRef) -> NodeRef|InletRef|OutletRef|LinkRef:
        return attribute.owner

    def attributeData(self, attribute, role:int=Qt.ItemDataRole.DisplayRole) -> Any:
        match attribute.owner:
            case NodeRef():
                match attribute.name:
                    case "name":
                        return attribute.owner.id
            case InletRef():
                match attribute.name:
                    case "name":
                        return attribute.owner.name
            case OutletRef():
                match attribute.name:
                    case "name":
                        return attribute.owner.name
            case LinkRef():
                match attribute.name:
                    case "source":
                        return f"{attribute.owner.source.node.id}:{attribute.owner.source.name}"
                    case "target":
                        return f"{attribute.owner.target.node.id}:{attribute.owner.target.name}"
    
    def setAttributeData(self, attribute, value:Any, role:int=Qt.ItemDataRole.EditRole) -> bool:
        return False
    
    def attributeOwner(self, attribute:AttributeRef)->NodeRef|InletRef|OutletRef|LinkRef:
        return attribute.owner
    
    def itemType(self, index:NodeRef|InletRef|OutletRef|LinkRef) -> GraphItemType:
        match index:
            case NodeRef():
                return GraphItemType.NODE
            case InletRef():
                return GraphItemType.INLET
            case OutletRef():
                return GraphItemType.OUTLET
            case LinkRef():
                return GraphItemType.LINK
            case _:
                raise ValueError(f"Invalid index type: {index}")

    def data(self, index:NodeRef|InletRef|OutletRef|LinkRef, role:int=Qt.ItemDataRole.DisplayRole) -> Any:
        print(f"WARNING: data is deprecated use dedicated attributes to display data")
        if role == Qt.ItemDataRole.DisplayRole:
            match index:
                case NodeRef():
                    return f"{index.id}"
                case InletRef():
                    return f"{index.name}"
                case OutletRef():
                    return f"{index.name}"
                case LinkRef():
                    return f"{index.source} -> {index.target}"
                case _:
                    raise ValueError(f"Invalid index type: {index}")
        else:
            return None
        


if __name__ == "__main__":
    def test_graph_item_ref():
        assert NodeRef(id="n1") in set([NodeRef(id="n1")])
        assert NodeRef(id="n2") not in set([NodeRef(id="n1")])
        
    def test_graph_controller():
        G = NXGraphController()
        n1 = G.addNode()
        n2 = G.addNode()
        G.addLink(OutletRef(n1, "out"), InletRef(n2, name="in"))


        assert G.nodeCount() == 2
        assert G.linkCount() == 1
        assert G.inletCount(n1) == 1
        assert G.outletCount(n1) == 1
        assert set(G.nodes()) == {n1, n2}
        assert set(G.inlets(n1)) == {InletRef(n1, "in")}
        assert set(G.outlets(n1)) == {OutletRef(n1, "out")}
        assert set(G.links()) == {LinkRef(source=OutletRef(n1, "out"), target=InletRef(n2, "in"))}
        assert G.inletNode(InletRef(n1, "in")) == n1
        assert G.outletNode(OutletRef(n1, "out")) == n1
        assert G.linkSource(LinkRef(source=OutletRef(n1, "out"), target=InletRef(n2, "in"))) == OutletRef(n1, "out")
        assert G.linkTarget(LinkRef(source=OutletRef(n1, "out"), target=InletRef(n2, "in"))) == InletRef(n2, "in")
        assert G.canLink(OutletRef(n1, "out"), InletRef(n2, "in")) == True
        assert G.canLink(InletRef(n1, "in"), OutletRef(n2, "out")) == False

    test_graph_controller()
    test_graph_item_ref()