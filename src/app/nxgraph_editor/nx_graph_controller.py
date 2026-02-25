

from qdagview.controllers.base_graphcontroller import (
    BaseGraphController, NodeRef, InletRef, OutletRef, LinkRef, AttributeRef
)
import networkx as nx
from typing import List, Dict, Any, override
from qtpy.QtCore import *
from qtpy.QtGui import *
from qdagview.core import GraphDataRole, GraphItemType


class NXGraphController(BaseGraphController):
    def __init__(self, graph:nx.MultiDiGraph|None=None, parent=None):
        super().__init__(parent)
        self.G = graph if graph is not None else nx.MultiDiGraph() # underlying NetworkX graph

    def addNode(self, subgraph=None) -> NodeRef:
        if subgraph is not None:
            raise NotImplementedError("Subgraph support is not implemented in this example")
        node_count = len(self.G.nodes)
        new_node_ref = NodeRef(f"n{node_count+1}")
        self.nodesAboutToBeInserted.emit([new_node_ref]) # Emit about-to-be-inserted signal
        self.G.add_node(new_node_ref,
            inlets=[InletRef(node=new_node_ref, name="inlet")],
            outlets=[OutletRef(node=new_node_ref, name="outlet")])
        self.nodesInserted.emit([new_node_ref]) # TODO: emit correct index
        return new_node_ref
    
    def removeNode(self, node:NodeRef) -> bool:
        if not node.isValid():
            return False
        try:
            self.nodesAboutToBeRemoved.emit([node])
            self.G.remove_node(node)
            self.nodesRemoved.emit([node])
            return True
        except KeyError:
            return False

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
    
    def addLink(self, outlet_index:OutletRef, inlet_index:InletRef) -> LinkRef:
        if not self.canLink(outlet_index, inlet_index):
            return False
        source_node = self.outletNode(outlet_index)
        target_node = self.inletNode(inlet_index)
        link_ref = LinkRef(source=outlet_index, target=inlet_index, name=0)
        self.linksAboutToBeInserted.emit([link_ref]) # Emit about-to-be-inserted signal
        self.G.add_edge(source_node, target_node, key=(outlet_index, inlet_index)) # use port indexes as edge key to allow multiple edges between same nodes
        self.linksInserted.emit([link_ref]) # TODO: emit correct index
        return link_ref
    
    def removeLink(self, link:LinkRef) -> bool:
        if not link.isValid():
            return False
        source_node = self.outletNode(link.source)
        target_node = self.inletNode(link.target)
        try:
            self.linksAboutToBeRemoved.emit([link])
            self.G.remove_edge(source_node, target_node, key=(link.source, link.target))
            self.linksRemoved.emit([link])
            return True
        except KeyError:
            return False

    def links(self, port:InletRef|OutletRef|None=None)-> List[LinkRef]:
        match port:
            case InletRef():
                node = self.inletNode(port)
                in_edges = self.G.in_edges(node, keys=True)
                return [LinkRef(source=k[0], target=port, name=0) for u, v, k in in_edges if k[1] == port] # count only edges connected to the specific inlet
            
            case OutletRef():
                node = self.outletNode(port)
                out_edges = self.G.out_edges(node, keys=True)
                return [LinkRef(source=port, target=k[1], name=0) for u, v, k in out_edges if k[0] == port] # count only edges connected to the specific outlet
            
            case None:
                return [LinkRef(source=k[0], target=k[1], name=0) for u, v, k in self.G.edges(keys=True)]
            
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
                        return attribute.owner.name
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
                        return f"{attribute.owner.source.node.name}:{attribute.owner.source.name}"
                    case "target":
                        return f"{attribute.owner.target.node.name}:{attribute.owner.target.name}"
    
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
        
    def remove_batch(self, items:List[NodeRef|InletRef|OutletRef|LinkRef]):
        nodes_to_remove = [item for item in items if isinstance(item, NodeRef)]
        links_to_remove = [item for item in items if isinstance(item, LinkRef)]

        for link in links_to_remove:
            self.removeLink(link)

        for node in nodes_to_remove:
            self.removeNode(node)

        if any(not isinstance(item, (NodeRef, LinkRef)) for item in items):
            #TODO: implement batch removal of inlets/outlets
            raise NotImplementedError(f"Batch removal of inlets/outlets is not implemented yet, got: items={items}")


if __name__ == "__main__":
    def test_graph_item_ref():
        assert NodeRef("n1") in set([NodeRef("n1")])
        assert NodeRef("n2") not in set([NodeRef("n1")])
    try:
        test_graph_item_ref()
        print("✅ NodeRef test passed")
    except Exception as e:
        print(f"🚨 NodeRef test failed: {e}")
        
    def test_graph_add():
        graph = NXGraphController()
        n1 = graph.addNode()
        n2 = graph.addNode()
        assert set(graph.nodes()) == {n1, n2}
        
        assert len(graph.outlets(n1)) == 1

        assert len(graph.inlets(n2)) == 1

        outlet = graph.outlets(n1)[0]
        inlet = graph.inlets(n2)[0]
        link = graph.addLink(outlet, inlet)
        assert graph.links() == [link]

        assert graph.linkSource(link) == outlet
        assert graph.linkTarget(link) == inlet
        assert graph.outletNode(outlet) == n1
        assert graph.inletNode(inlet) == n2

        graph.removeNode(n1)
        assert n1 not in graph.nodes()
        assert link not in graph.links() # link should be removed when node is removed
    try:
        test_graph_add()
        print("✅ GraphController test passed")
    except Exception as e:
        print(f"🚨 GraphController test failed: {e}")

    # import signal spy to test signals
    from qtpy.QtTest import QSignalSpy
    def test_graph_signals():
        graph = NXGraphController()
        node_about_to_insert_spy = QSignalSpy(graph.nodesAboutToBeInserted)
        node_inserted_spy = QSignalSpy(graph.nodesInserted)
        node_removed_spy = QSignalSpy(graph.nodesRemoved)
        link_about_to_insert_spy = QSignalSpy(graph.linksAboutToBeInserted)
        link_inserted_spy = QSignalSpy(graph.linksInserted)
        link_removed_spy = QSignalSpy(graph.linksAboutToBeRemoved)

        n1 = graph.addNode()
        assert len(node_about_to_insert_spy) == 1
        assert len(node_inserted_spy) == 1
        n2 = graph.addNode()
        assert len(node_about_to_insert_spy) == 2
        assert len(node_inserted_spy) == 2
        n3 = graph.addNode()
        assert len(node_about_to_insert_spy) == 3
        assert len(node_inserted_spy) == 3

        graph.removeNode(n1)
        assert len(node_removed_spy) == 1

        outlet = graph.outlets(n2)[0]
        inlet = graph.inlets(n3)[0]
        link = graph.addLink(outlet, inlet)
        assert len(link_about_to_insert_spy) == 1
        assert len(link_inserted_spy) == 1
        graph.removeLink(link)
        assert len(link_removed_spy) == 1
    try:
        test_graph_signals()
        print("✅ Graph signals test passed")
    except Exception as e:
        print(f"🚨 Graph signals test failed: {e}")

    from qdagview.controllers.base_graphselectioncontroller import BaseGraphSelectionController
    def test_graph_selection():
        graph = NXGraphController()
        n1 = graph.addNode()
        n2 = graph.addNode()
        outlet = graph.outlets(n1)[0]
        inlet = graph.inlets(n2)[0]
        link = graph.addLink(outlet, inlet)

        selection_model = BaseGraphSelectionController()
        selection_model.setGraphController(graph)

        selection_model.select([n1], QItemSelectionModel.SelectionFlag.Select)
        assert selection_model.isSelected(n1)
        assert not selection_model.isSelected(n2)
        assert not selection_model.isSelected(link)

        selection_model.select([link], QItemSelectionModel.SelectionFlag.Select)
        assert selection_model.isSelected(link)

        selection_model.select([n1], QItemSelectionModel.SelectionFlag.Deselect)
        assert not selection_model.isSelected(n1)
    try:
        test_graph_selection()
        print("✅ Graph selection test passed")
    except Exception as e:
        print(f"🚨 Graph selection test failed: {e}")

    def test_graph_selection_signals():
        graph = NXGraphController()
        n1 = graph.addNode()
        n2 = graph.addNode()
        outlet = graph.outlets(n1)[0]
        inlet = graph.inlets(n2)[0]
        link = graph.addLink(outlet, inlet)

        selection_model = BaseGraphSelectionController()
        selection_model.setGraphController(graph)

        selection_changed_spy = QSignalSpy(selection_model.selectionChanged)
        selection_model.select([n1], QItemSelectionModel.SelectionFlag.Select)
        assert len(selection_changed_spy) == 1
        selected, deselected = selection_changed_spy[0]
        assert selected == [n1]
        assert deselected == []

        selection_model.select([link], QItemSelectionModel.SelectionFlag.Select)
        assert len(selection_changed_spy) == 2
        selected, deselected = selection_changed_spy[1]
        assert selected == [link]
        assert deselected == []
        assert set(selection_model.selectedIndexes()) == {n1, link}
    try:
        test_graph_selection_signals()
        print("✅ Graph selection signals test passed")
    except Exception as e:
        print(f"🚨 Graph selection signals test failed: {e}")
