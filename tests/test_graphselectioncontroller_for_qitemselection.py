import pytest

import sys

import logging

from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWidgets import *


from qdagview.controllers import QTreeModel_GraphController
from qdagview.controllers import QTreeModel_GraphSelectionController




@pytest.fixture
def graph_view_setup(qtbot)->tuple[QStandardItemModel, QItemSelectionModel, QTreeModel_GraphController, QTreeModel_GraphSelectionController]:
    """Setup graph components for testing."""
    item_model = QStandardItemModel()
    item_selection = QItemSelectionModel(item_model)

    graph_controller = QTreeModel_GraphController()
    graph_controller.setSourceModel(item_model)
    
    graph_selection = QTreeModel_GraphSelectionController(graph_controller, item_selection)

    return item_model, item_selection, graph_controller, graph_selection

def test_node_selection(qtbot, graph_view_setup):
    """Test selecting a node in the graph."""
    item_model, item_selection, graph_controller, graph_selection = graph_view_setup

    # Add a node and select it
    node1 = graph_controller.addNode()
    item_selection.select(node1, QItemSelectionModel.SelectionFlag.Select)

    assert node1 in graph_selection.selectedIndexes()

if __name__ == "__main__":
    # runs pytest on this file
    # logging.basicConfig(level=logging.CRITICAL)
    # Or alternatively, disable all logging during tests:
    logging.disable(logging.CRITICAL)
    pytest.main([__file__, "-v"])