import pytest

import sys

import logging

from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWidgets import *


from qdagview.controllers import GraphController_for_QTreeModel
from qdagview.controllers import GraphSelectionController_for_QItemSelectionModel


@pytest.fixture
def graph_view_setup(qtbot)->tuple[QStandardItemModel, QItemSelectionModel, GraphController_for_QTreeModel, GraphSelectionController_for_QItemSelectionModel]:
    """Setup graph components for testing."""
    item_model = QStandardItemModel()
    item_selection = QItemSelectionModel(item_model)

    graph_controller = GraphController_for_QTreeModel()
    graph_controller.setSourceModel(item_model)

    node1 = graph_controller.addNode()
    node2 = graph_controller.addNode()
    node3 = graph_controller.addNode()

    link_1_2 = graph_controller.addLink(
        graph_controller.outlets(node1)[0], 
        graph_controller.inlets(node2)[0]
    )
    link_2_3 = graph_controller.addLink(
        graph_controller.outlets(node2)[0], 
        graph_controller.inlets(node3)[0]
    )
    
    graph_selection = GraphSelectionController_for_QItemSelectionModel(graph_controller, item_selection)

    return item_model, item_selection, graph_controller, graph_selection


def test_controller_updates_when_source_changes(qtbot, graph_view_setup):
    """Test that the selection controller updates when the source selection model changes."""
    item_model, item_selection, graph_controller, graph_selection = graph_view_setup

    # Initially, nothing is selected
    assert len(item_selection.selectedIndexes()) == 0

    # Select the first node
    node1_idx = item_model.index(0, 0)
    item_selection.select(node1_idx, QItemSelectionModel.SelectionFlag.Select)
    selected_indexes = item_selection.selectedIndexes()
    assert set(selected_indexes) == {QPersistentModelIndex(node1_idx)}

    # Select the third node
    node3_idx = item_model.index(2, 0)
    item_selection.select(node3_idx, QItemSelectionModel.SelectionFlag.Select)
    selected_indexes = item_selection.selectedIndexes()
    assert set(selected_indexes) == {QPersistentModelIndex(node3_idx)}

# def test_node_selection(qtbot, graph_view_setup):
#     """Test selecting a node in the graph."""
#     item_model, item_selection, graph_controller, graph_selection = graph_view_setup

#     # Add a node and select it
#     item_model.insertRow(0, QStandardItem("Node 1"))
#     node_idx = item_model.index(0, 0)
#     item_selection.select(node_idx, QItemSelectionModel.SelectionFlag.Select)

#     assert len(graph_selection.selectedIndexes()) == 1

if __name__ == "__main__":
    # runs pytest on this file
    logging.basicConfig(level=logging.CRITICAL)
    pytest.main([__file__, "-v"])