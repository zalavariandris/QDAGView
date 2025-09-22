import pytest
import logging
from qdagview import GraphView, FlowGraphModel, QItemModelGraphController


def test_basic_graph_view_operaions(qtbot):
    """Basic test to ensure GraphView can be created and displayed."""
    model = FlowGraphModel()
    controller = QItemModelGraphController()
    controller.setModel(model)
    view = GraphView()
    view.setModel(model)
    
    # Add the widget to qtbot for proper Qt handling
    qtbot.addWidget(view)
    view.show()
    with qtbot.waitExposed(view):
        pass  # Wait for the window to be exposed
    
    assert view.isVisible(), "GraphView should be visible"
    assert view.model() is model, "GraphView should have the correct model set"

    # add a node
    node1 = controller.addNode()
    node2 = controller.addNode()

    assert controller.outletCount(node1) > 0, "New node should have at least one outlet by default"
    assert controller.inletCount(node2) > 0, "New node should have at least one inlet by default"

    link1 = controller.addLink(controller.nodeOutlets(node1)[0], controller.nodeInlets(node2)[0])

    controller.removeLink(link1)
    controller.removeNode(node1)
    controller.removeNode(node2)


if __name__ == "__main__":
    # runs pytest on this file
    # logging.basicConfig(level=logging.CRITICAL)
    # Or alternatively, disable all logging during tests:
    logging.disable(logging.CRITICAL)
    pytest.main([__file__, "-v"])