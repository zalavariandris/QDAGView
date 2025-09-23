import pytest

import sys

import logging

from qtpy.QtCore import QModelIndex, QPersistentModelIndex

from qtpy.QtWidgets import QApplication

from qdagview import GraphView, FlowGraphModel, QItemModelGraphController

@pytest.fixture
def graph_controller_setup()->QItemModelGraphController:
    """Setup graph components for testing."""
    model = FlowGraphModel()
    controller = QItemModelGraphController()
    controller.setModel(model)
    
    return controller

## Tests for inserting nodes and links ##
def test_add_empty_node(graph_controller_setup: QItemModelGraphController):
    """Test adding an empty node."""
    controller = graph_controller_setup    
    result = controller.addNode()

    assert result, "Adding a new node should succeed"
    assert controller.nodeCount() == 1, "One row should be added"

def test_add_multiple_nodes(graph_controller_setup:  QItemModelGraphController):
    """Test adding an empty node."""
    controller = graph_controller_setup   
    num_nodes_to_add = 5
    for _ in range(num_nodes_to_add):
        result = controller.addNode()
        assert result, "Adding a new node should succeed"

    assert controller.nodeCount() == num_nodes_to_add, f"{num_nodes_to_add} rows should be added"

def test_link_nodes(graph_controller_setup: QItemModelGraphController):
    """Test adding an empty node."""
    controller = graph_controller_setup
    
    # Add two nodes first
    node1 = controller.addNode()
    node2 = controller.addNode()

    assert controller.nodeCount() == 2, "Two rows should be added"

    # Link the two nodes
    result = controller.addLink(controller.nodeOutlets(node1)[0], controller.nodeInlets(node2)[0])

    assert result, "Linking the two nodes should succeed"

## test querying nodes and links ##
def test_query_nodes_and_links(graph_controller_setup: QItemModelGraphController):
    """Test adding an empty node."""
    controller = graph_controller_setup
    
    # Add two nodes first
    node1 = controller.addNode()
    node2 = controller.addNode()
    node3 = controller.addNode()

    assert controller.nodeCount() == 3, "Three rows should be added"

    assert len(controller.nodes()) == 3, "There should be three nodes"
    assert all(n in controller.nodes() for n in [node1, node2, node3]), "All nodes should be valid"

    # Query node outlets and inlets
    for n in [node1, node2, node3]:
        inlets = controller.nodeInlets(n)
        outlets = controller.nodeOutlets(n)
        assert len(inlets) > 0, "Node should have at least one inlet"
        assert len(outlets) > 0, "Node should have at least one outlet"

        assert len(inlets) == controller.inletCount(n), "Number of inlets should match"
        assert len(outlets) == controller.outletCount(n), "Number of outlets should match"

    # Link the three nodes in chain
    link1 = controller.addLink(controller.nodeOutlets(node1)[0], controller.nodeInlets(node2)[0])
    link2 = controller.addLink(controller.nodeOutlets(node2)[0], controller.nodeInlets(node3)[0])

    assert link1 is not None, "Linking the two nodes should succeed"
    assert link2 is not None, "Linking the two nodes should succeed"
    assert controller.linkCount() == 2, "Two links should exist"

    # Query links
    links = controller.links()
    assert len(links) == 2, "There should be two links"
    assert all(l in links for l in [link1, link2]), "All links should be valid"

    # Query link sources and targets
    assert controller.linkSource(link1) == controller.nodeOutlets(node1)[0], "Source of link1 should be the outlet of node1"
    assert controller.linkTarget(link1) == controller.nodeInlets(node2)[0], "Target of link1 should be the inlet of node2"
    assert controller.linkSource(link2) == controller.nodeOutlets(node2)[0], "Source of link2 should be the outlet of node2"
    assert controller.linkTarget(link2) == controller.nodeInlets(node3)[0], "Target of link2 should be the inlet of node3"

## tests for removing nodes and links ##
def test_remove_single_node(graph_controller_setup: QItemModelGraphController):
    """Test adding an empty node."""
    controller = graph_controller_setup

    # Add a node first
    node1 = controller.addNode()
    assert controller.nodeCount() == 1, "One row should be added"

    # Now remove the node
    result = controller.removeNode(node1)
    
    assert result, "Removing the node should succeed"
    assert controller.nodeCount() == 0, "No rows should remain after removal"

def test_remove_multiple_nodes(graph_controller_setup: QItemModelGraphController):
    """Test adding an empty node."""
    controller = graph_controller_setup

    # Add multiple nodes first
    nodes = []
    num_nodes_to_add = 5
    for _ in range(num_nodes_to_add):
        node = controller.addNode()
        nodes.append(node)

    assert controller.nodeCount() == num_nodes_to_add, f"{num_nodes_to_add} rows should be added"
    
    # Now remove some of the nodes

    for node in nodes[1:3]:
        assert node in controller.nodes(), "Node should be valid before removal"
        result = controller.removeNode(node)
        assert result, "Removing the node should succeed"
    
    assert controller.nodeCount() == num_nodes_to_add - 2, f"{num_nodes_to_add - 2} rows should remain after removal"
    assert nodes[0] in controller.nodes(), "First node should still be valid"
    assert nodes[1] not in controller.nodes(), "Second node should be removed"
    assert nodes[4] in controller.nodes(), "Fifth node should still be valid"

def test_remove_nonexistent_node(graph_controller_setup: QItemModelGraphController):
    """Test adding an empty node."""
    controller = graph_controller_setup
    
    # Attempt to remove a node from an empty model
    result = controller.removeNode(None)
    
    assert result is False, "Removing a nonexistent node should fail"
    assert controller.nodeCount() == 0, "No rows should exist in the model"

def test_removing_nodes_also_remove_links(graph_controller_setup: QItemModelGraphController):
    """Test adding an empty node."""
    controller = graph_controller_setup
    
    # Add two nodes first
    node1 = controller.addNode()
    node2 = controller.addNode()
    node3 = controller.addNode()
    
    assert controller.nodeCount() == 3, "Two rows should be added"
    
    # Link the three nodes in chain
    link1 = controller.addLink(controller.nodeOutlets(node1)[0], controller.nodeInlets(node2)[0])
    link2 = controller.addLink(controller.nodeOutlets(node2)[0], controller.nodeInlets(node3)[0])

    assert link1 is not None, "Linking the two nodes should succeed"
    assert link2 is not None, "Linking the two nodes should succeed"
    assert controller.linkCount() == 2, "Two links should exist"
    
    # Now remove the middle node
    result = controller.removeNode(node2)
    
    assert result is True, "Removing the node should succeed"
    assert controller.nodeCount() == 2, "One row should remain after removal"
    
    # Check that the links were also removed
    assert controller.linkCount() == 0, "All links should be removed when a node is removed"


#####################
# Test Batch remove #
#####################
# def test_remove_multiple_nodes_with_a_single_nonexistent_node(graph_controller_setup: QItemModelGraphController):
#     """Test adding an empty node."""
#     controller = graph_controller_setup

#     # Add some nodes
#     num_nodes_to_add = 3
#     for _ in range(num_nodes_to_add):
#         controller.addNode()

#     assert controller.nodesCount() == num_nodes_to_add, f"{num_nodes_to_add} rows should be added"

#     # Prepare valid indexes and one nonexistent index
#     valid_indexes = [model.index(i, 0, QModelIndex()) for i in range(num_nodes_to_add)]
#     nonexistent_index = model.index(num_nodes_to_add, 0, QModelIndex())  # Out of range

#     # Try to batch remove with one nonexistent index included
#     result = controller.batchRemove(valid_indexes + [nonexistent_index])

#     assert not result, "Batch remove should fail if any index does not exist"
#     assert model.rowCount() == num_nodes_to_add, "No nodes should be removed if batch remove fails"

# def test_remove_all_nodes(graph_controller_setup: tuple[FlowGraphModel, QItemModelGraphController]):
#     """Test adding an empty node."""
#     model, controller = graph_controller_setup

    
#     # Add multiple nodes first
#     num_nodes_to_add = 5
#     for _ in range(num_nodes_to_add):
#         controller.addNode()
    
#     assert model.rowCount() == num_nodes_to_add, f"{num_nodes_to_add} rows should be added"
    
#     # Now remove all nodes
#     all_indexes = [model.index(i, 0, QModelIndex()) for i in range(num_nodes_to_add)]
#     result = controller.batchRemove(all_indexes)
    
#     assert result, "Removing all nodes should succeed"
#     assert model.rowCount() == 0, "No rows should remain after removal"


if __name__ == "__main__":
    # runs pytest on this file
    # logging.basicConfig(level=logging.CRITICAL)
    # Or alternatively, disable all logging during tests:
    logging.disable(logging.CRITICAL)
    pytest.main([__file__, "-v"])