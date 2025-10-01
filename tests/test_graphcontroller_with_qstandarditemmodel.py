import pytest

import sys

import logging

from qtpy.QtGui import *
from qtpy.QtCore import *
from qtpy.QtWidgets import *

from qdagview.controllers import GraphController_for_QTreeModel
from qdagview.core import GraphItemType, GraphDataRole

@pytest.fixture
def graph_controller_setup()->tuple[QStandardItemModel, GraphController_for_QTreeModel]:
    """Setup graph components for testing."""
    model = QStandardItemModel()
    controller = GraphController_for_QTreeModel()
    controller.setSourceModel(model)

    return model, controller

def test_model_in_sync(graph_controller_setup: tuple[QStandardItemModel, GraphController_for_QTreeModel]):
    """Test adding a node to the model."""
    model, controller = graph_controller_setup

    ## Add a node first
    node_ref1 = controller.addNode()
    node_idx = QPersistentModelIndex(node_ref1)
    assert node_idx.isValid()
    assert controller.nodes() == [node_idx]

    ## add inlet to the node
    inlet_ref1 = controller.addInlet(node_ref1)
    inlet_idx = QPersistentModelIndex(inlet_ref1)
    assert inlet_idx.isValid()
    assert controller.inlets(node_ref1) == [inlet_idx]

    ## add outlet to the node
    outlet_ref1 = controller.addOutlet(node_ref1)
    outlet_idx = QPersistentModelIndex(outlet_ref1)
    assert outlet_idx.isValid()
    assert controller.outlets(node_ref1) == [outlet_idx]

def test_controller_in_sync(graph_controller_setup: tuple[QStandardItemModel, GraphController_for_QTreeModel]):
    """Test adding an inlet to a node."""
    model, controller = graph_controller_setup

    ## Add a node first
    node_item = QStandardItem("node1")
    model.appendRow(node_item)
    node_idx = model.indexFromItem(node_item)

    assert node_idx.isValid()
    assert controller.nodes() == [QPersistentModelIndex(node_idx)]

    ## Now add an inlet to the node
    inlet_item = QStandardItem("inlet1")
    node_item.appendRow(inlet_item)
    inlet_idx = model.indexFromItem(inlet_item)
    assert inlet_idx.isValid()
    assert controller.inlets(node_idx) == [QPersistentModelIndex(inlet_idx)]

    ## Now add an outlet to the node
    outlet_item = QStandardItem("outlet1")
    outlet_item.setData(GraphItemType.OUTLET, GraphDataRole.TypeRole)
    node_item.appendRow(outlet_item)
    outlet_idx = model.indexFromItem(outlet_item)
    assert outlet_idx.isValid()
    assert controller.outlets(node_idx) == [QPersistentModelIndex(outlet_idx)]
    ... # TODO: test further actions

if __name__ == "__main__":
    # runs pytest on this file
    # logging.basicConfig(level=logging.CRITICAL)
    # Or alternatively, disable all logging during tests:
    logging.disable(logging.CRITICAL)
    pytest.main([__file__, "-v"])