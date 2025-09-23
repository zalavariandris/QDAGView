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
def graph_setup()->QItemModelGraphController:
    """Setup graph components for testing."""
    model = FlowGraphModel()
    controller = QItemModelGraphController()
    controller.setModel(model)

    node1 = controller.addNode()
    node2 = controller.addNode()
    node3 = controller.addNode()



    return controller

def test_multiple_links_connected_to_a_single_inlet(qtbot, graph_setup:QItemModelGraphController):
    """Test adding an empty node."""
    controller = graph_setup

    A, B, C = controller.nodes()

    controller.addLink(controller.nodeOutlets(A)[0], controller.nodeInlets(C)[0])
    controller.addLink(controller.nodeOutlets(B)[0], controller.nodeInlets(C)[0])

    assert controller.nodeCount() == 3, "There should be three nodes in the graph"
    assert controller.linkCount() == 2, "There should be two links in the graph"

    link1, link2 = controller.links()
    assert controller.linkSource(link1) == controller.nodeOutlets(A)[0], "Link1 source outlet should match node1's outlet"
    assert controller.linkTarget(link1)  == controller.nodeInlets(C)[0], "Link1 target inlet should match node3's inlet"
    assert controller.linkSource(link2) == controller.nodeOutlets(B)[0], "Link2 source outlet should match node2's outlet"
    assert controller.linkTarget(link2) == controller.nodeInlets(C)[0], "Link2 target inlet should match node3's inlet"


if __name__ == "__main__":
    # runs pytest on this file
    # logging.basicConfig(level=logging.CRITICAL)
    # Or alternatively, disable all logging during tests:
    logging.disable(logging.CRITICAL)
    pytest.main([__file__, "-v"])