import pytest

import sys

import logging

from qtpy.QtCore import QModelIndex, QPersistentModelIndex

from qtpy.QtWidgets import QApplication

from qdagview import GraphView, FlowGraphModel, QItemModelGraphController


@pytest.fixture(scope="session")
def qapp():
    """Create QApplication instance for Qt tests."""
    if not QApplication.instance():
        app = QApplication(sys.argv)
    else:
        app = QApplication.instance()
    yield app
    # QApplication cleanup is handled automatically


@pytest.fixture
def graph_setup(qtbot):
    """Setup graph components for testing."""
    model = FlowGraphModel()
    controller = QItemModelGraphController(model)
    view = GraphView()
    view.setModel(model)
    
    qtbot.addWidget(view)
    view.show()
    with qtbot.waitExposed(view):
        pass
    
    return model, controller, view

def test_add_empty_node(qtbot, graph_setup):
    """Test adding an empty node."""
    model, controller, view = graph_setup
    
    result = controller.addNode()
    assert result is True, "Adding a new node should succeed"

    assert view._widget_manager.getWidget(model.index(0,0, QModelIndex())), "widget should be added for the node index"
    
    # Process any pending events
    qtbot.wait(100)  # Wait 100ms for any async operations

def test_add_multiple_nodes(qtbot, graph_setup):
    """Test adding an empty node."""
    model, controller, view = graph_setup
    
    num_nodes_to_add = 5
    for _ in range(num_nodes_to_add):
        result = controller.addNode()
        assert result is True, "Adding a new node should succeed"

    assert all(view._widget_manager.getWidget(model.index(i, 0, QModelIndex())) for i in range(num_nodes_to_add)), "widgets should be added for all node indices"
    
    # Process any pending events
    qtbot.wait(100)  # Wait 100ms for any async operations

def test_remove_single_node(qtbot):
    """Test removing a node."""
    model = FlowGraphModel()
    controller = QItemModelGraphController(model)
    view = GraphView()
    view.setModel(model)
    
    # Add the widget to qtbot for proper Qt handling
    qtbot.addWidget(view)
    view.show()
    with qtbot.waitExposed(view):
        pass  # Wait for the window to be exposed
    
    # Add a node first
    controller.addNode()
    assert model.rowCount() == 1, "One row should be added"
    
    # Now remove the node
    index_to_remove = model.index(0, 0, QModelIndex())
    result = controller.batchRemove([index_to_remove])
    
    assert result is True, "Removing the node should succeed"
    assert view._widget_manager.getWidget(index_to_remove) is None, "widget should have been removed"
    
    # Process any pending events
    qtbot.wait(100)  # Wait 100ms for any async operations

def test_remove_multiple_nodes(qtbot):
    """Test removing multiple nodes."""
    model = FlowGraphModel()
    controller = QItemModelGraphController(model)
    view = GraphView()
    view.setModel(model)
    
    # Add the widget to qtbot for proper Qt handling
    qtbot.addWidget(view)
    view.show()
    with qtbot.waitExposed(view):
        pass  # Wait for the window to be exposed
    
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

    # Process any pending events
    qtbot.wait(100)  # Wait 100ms for any async operations

def test_remove_nonexistent_node(qtbot):
    """Test removing a node that does not exist."""
    model = FlowGraphModel()
    controller = QItemModelGraphController(model)
    view = GraphView()
    view.setModel(model)
    
    # Add the widget to qtbot for proper Qt handling
    qtbot.addWidget(view)
    view.show()
    with qtbot.waitExposed(view):
        pass  # Wait for the window to be exposed
    
    # Attempt to remove a node from an empty model
    nonexistent_index = model.index(0, 0, QModelIndex())
    result = controller.batchRemove([nonexistent_index])
    
    assert result is False, "Removing a nonexistent node should fail"
    assert model.rowCount() == 0, "No rows should exist in the model"
    
    # Process any pending events
    qtbot.wait(100)  # Wait 100ms for any async operations

def test_remove_all_nodes(qtbot):
    """Test removing all nodes."""
    model = FlowGraphModel()
    controller = QItemModelGraphController(model)
    view = GraphView()
    view.setModel(model)
    
    # Add the widget to qtbot for proper Qt handling
    qtbot.addWidget(view)
    view.show()
    with qtbot.waitExposed(view):
        pass  # Wait for the window to be exposed
    
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
    
    # Process any pending events
    qtbot.wait(100)  # Wait 100ms for any async operations

def test_link_nodes(qtbot):
    """Test linking two nodes."""
    model = FlowGraphModel()
    controller = QItemModelGraphController(model)
    view = GraphView()
    view.setModel(model)
    
    # Add the widget to qtbot for proper Qt handling
    qtbot.addWidget(view)
    view.show()
    with qtbot.waitExposed(view):
        pass  # Wait for the window to be exposed
    
    # Add two nodes first
    controller.addNode()
    controller.addNode()
    
    assert model.rowCount() == 2, "Two rows should be added"
    
    # Link the two nodes
    first_node_index = model.index(0, 0, QModelIndex())
    second_node_index = model.index(1, 0, QModelIndex())

    result = controller.addLink(controller.nodeOutlets(first_node_index)[0], controller.nodeInlets(second_node_index)[0])

    assert result is True, "Linking the two nodes should succeed"
    
    # Process any pending events
    qtbot.wait(100)  # Wait 100ms for any async operations


def test_update_expression_to_no_inlets(qtbot):
    """Test updating an expression from multiple inlets to no inlets."""
    model = FlowGraphModel()
    controller = QItemModelGraphController(model)
    view = GraphView()
    view.setModel(model)
    
    # Add the widget to qtbot for proper Qt handling
    qtbot.addWidget(view)
    view.show()
    with qtbot.waitExposed(view):
        pass  # Wait for the window to be exposed
    
    # Add two nodes first
    controller.addNode()
    model.setData(model.index(0, 1, QModelIndex()), "a+b+c")  # Set expression with two inlets

    assert model.rowCount() == 1, "One row should be added"
    assert len(controller.nodeInlets(model.index(0, 0, QModelIndex()))) == 3, "Node should have three inlets"
    inlet_widgets = [view._widget_manager.getWidget(idx) for idx in controller.nodeInlets(model.index(0, 0, QModelIndex()))]
    assert len(inlet_widgets) == 3 and all(inlet_widgets), "All inlet widgets should be created"

    model.setData(model.index(0, 1, QModelIndex()), "5 + 10")  # Update expression to no inlets
    inlet_widgets = [view._widget_manager.getWidget(idx) for idx in controller.nodeInlets(model.index(0, 0, QModelIndex()))]
    assert len(inlet_widgets) == 0 and all(inlet_widgets), "All inlet widgets should be created"

    
    # Process any pending events
    qtbot.wait(100)  # Wait 100ms for any async operations




if __name__ == "__main__":
    # runs pytest on this file
    # logging.basicConfig(level=logging.CRITICAL)
    # Or alternatively, disable all logging during tests:
    logging.disable(logging.CRITICAL)
    pytest.main([__file__, "-v"])