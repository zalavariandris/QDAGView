import pytest

import sys

import logging

from qtpy.QtCore import QModelIndex, QPersistentModelIndex

from qtpy.QtWidgets import QApplication

from qdagview import GraphView, FlowGraphModel, QItemModelGraphController


def test_add_empty_node():
    """Test adding an empty node."""
    model = FlowGraphModel()
    controller = QItemModelGraphController(model)
    
    result = controller.addNode()

    assert result is True, "Adding a new node should succeed"
    assert model.rowCount() == 1, "One row should be added"


def test_add_multiple_nodes():
    """Test adding multiple nodes."""
    model = FlowGraphModel()
    controller = QItemModelGraphController(model)

    num_nodes_to_add = 5
    for _ in range(num_nodes_to_add):
        result = controller.addNode()
        assert result is True, "Adding a new node should succeed"
    
    assert model.rowCount() == num_nodes_to_add, f"{num_nodes_to_add} rows should be added"

def test_remove_single_node():
    """Test removing a node."""
    model = FlowGraphModel()
    controller = QItemModelGraphController(model)

    # Add a node first
    controller.addNode()
    assert model.rowCount() == 1, "One row should be added"
    
    # Now remove the node
    index_to_remove = model.index(0, 0, QModelIndex())
    result = controller.batchRemove([index_to_remove])
    
    assert result is True, "Removing the node should succeed"
    assert model.rowCount() == 0, "No rows should remain after removal"
    
def test_remove_multiple_nodes():
    """Test removing multiple nodes."""
    model = FlowGraphModel()
    controller = QItemModelGraphController(model)

    
    # Add multiple nodes first
    num_nodes_to_add = 5
    for _ in range(num_nodes_to_add):
        controller.addNode()
    
    assert model.rowCount() == num_nodes_to_add, f"{num_nodes_to_add} rows should be added"
    
    # Now remove some of the nodes
    first_node_index = QPersistentModelIndex(model.index(0, 0, QModelIndex()))
    second_node_index = QPersistentModelIndex(model.index(1, 0, QModelIndex()))
    third_node_index = QPersistentModelIndex(model.index(2, 0, QModelIndex()))
    fourth_node_index = QPersistentModelIndex(model.index(3, 0, QModelIndex()))
    fifth_node_index = QPersistentModelIndex(model.index(4, 0, QModelIndex()))

    result = controller.batchRemove([model.index(i, 0, QModelIndex()) for i in range(1, 3)])
    
    assert result is True, "Removing the nodes should succeed"
    assert model.rowCount() == num_nodes_to_add - 2, f"{num_nodes_to_add - 2} rows should remain after removal"
    assert first_node_index.isValid(), "First node should still be valid"
    assert not second_node_index.isValid(), "Second node should be removed"
    assert fifth_node_index.isValid(), "Fifth node should still be valid"

def test_remove_nonexistent_node():
    """Test removing a node that does not exist."""
    model = FlowGraphModel()
    controller = QItemModelGraphController(model)
    
    # Attempt to remove a node from an empty model
    nonexistent_index = model.index(0, 0, QModelIndex())
    result = controller.batchRemove([nonexistent_index])
    
    assert result is False, "Removing a nonexistent node should fail"
    assert model.rowCount() == 0, "No rows should exist in the model"

def test_remove_multiple_nodes_with_a_single_nonexistent_node():
    """batch removing nodes with a node that does not exist."""
    model = FlowGraphModel()
    controller = QItemModelGraphController(model)

    # Add some nodes
    num_nodes_to_add = 3
    for _ in range(num_nodes_to_add):
        controller.addNode()

    assert model.rowCount() == num_nodes_to_add, f"{num_nodes_to_add} rows should be added"

    # Prepare valid indexes and one nonexistent index
    valid_indexes = [model.index(i, 0, QModelIndex()) for i in range(num_nodes_to_add)]
    nonexistent_index = model.index(num_nodes_to_add, 0, QModelIndex())  # Out of range

    # Try to batch remove with one nonexistent index included
    result = controller.batchRemove(valid_indexes + [nonexistent_index])

    assert result is False, "Batch remove should fail if any index does not exist"
    assert model.rowCount() == num_nodes_to_add, "No nodes should be removed if batch remove fails"

def test_remove_all_nodes():
    """Test removing all nodes."""
    model = FlowGraphModel()
    controller = QItemModelGraphController(model)

    
    # Add multiple nodes first
    num_nodes_to_add = 5
    for _ in range(num_nodes_to_add):
        controller.addNode()
    
    assert model.rowCount() == num_nodes_to_add, f"{num_nodes_to_add} rows should be added"
    
    # Now remove all nodes
    all_indexes = [model.index(i, 0, QModelIndex()) for i in range(num_nodes_to_add)]
    result = controller.batchRemove(all_indexes)
    
    assert result is True, "Removing all nodes should succeed"
    assert model.rowCount() == 0, "No rows should remain after removal"
    

def test_link_nodes(qtbot):
    """Test linking two nodes."""
    model = FlowGraphModel()
    controller = QItemModelGraphController(model)
    
    # Add two nodes first
    controller.addNode()
    controller.addNode()
    
    assert model.rowCount() == 2, "Two rows should be added"
    
    # Link the two nodes
    first_node_index = model.index(0, 0, QModelIndex())
    second_node_index = model.index(1, 0, QModelIndex())

    result = controller.addLink(controller.nodeOutlets(first_node_index)[0], controller.nodeInlets(second_node_index)[0])

    assert result is True, "Linking the two nodes should succeed"
    
if __name__ == "__main__":
    # runs pytest on this file
    # logging.basicConfig(level=logging.CRITICAL)
    # Or alternatively, disable all logging during tests:
    logging.disable(logging.CRITICAL)
    pytest.main([__file__, "-v"])