"""
Manual tests

- [x] from outlet to inlet: connect
- [x] from inlet to outlet: connect

- [x] from outlet to canvas: do nothing
- [x] from inlet to canvas: do nothing

- [x] link tail to canvas: remove link
- [x] link head to canvas: remove link

- [x] link tail to outlet: reconnect link
- [x] link head to inlet: reconnect link
"""


# Add parent directory to path so we can import the module
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# unittest
import unittest

# QT
from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWidgets import *

# model
from core import GraphDataRole
from src.qdagview.models.flowgraphmodel import FlowGraphModel
from src.qdagview.models.itemmodel_graphhelper import ItemGraphHelper

# view
from src.qdagview.views.graphview import GraphView
app = QApplication(sys.argv)  # Only one QApplication per app


class TestGraphView(unittest.TestCase):
    def test_operators(self):
        model = FlowGraphModel()
        helper = ItemGraphHelper(model)
        view = GraphView()
        view.setModel(model)

        # create a single operator
        A = helper.createOperator("a+b", "A")
        assert A.isValid(), "Failed to create operator A"
        assert model.rowCount(QModelIndex()) == 1
        assert QPersistentModelIndex(A) in {A: "A"}
        self.assertEqual( len(view.toNetworkX().nodes()), 1)
        self.assertIn("A", view.toNetworkX().nodes, "Operator A not in graph")
        self.assertEqual(view.toNetworkX().nodes["A"]["expression"], "a+b", "Operator A expression incorrect")
        
        # set node expression
        helper.setExpression(A, "x*y")
        self.assertEqual(view.toNetworkX().nodes["A"]["expression"], "x*y", "Operator A expression incorrect after setExpression")

        # check inlets
        assert model.rowCount(A) == 3 # 2 inlets + 1 outlet
        assert len(helper.inlets(A)) == 2
        self.assertEqual( view.toNetworkX().nodes["A"]["inlets"], ['x', 'y'], "Operator A inlets incorrect")

        # set node expression
        helper.setExpression(A, "x*x")
        self.assertEqual(view.toNetworkX().nodes["A"]["expression"], "x*x", "Operator A expression incorrect after setExpression")
        
        # test dynamic inlets
        assert len(helper.inlets(A)) == 1
        self.assertEqual( view.toNetworkX().nodes["A"]["inlets"], ['x'], "Operator A inlets incorrect after setExpression")

        # create a second operator
        B = helper.createOperator("a/b", "B")
        self.assertEqual( len(view.toNetworkX().nodes()), 2)
        self.assertIn("B", view.toNetworkX().nodes, "Operator B not in graph")

        assert [inlet.data(Qt.ItemDataRole.EditRole) for inlet in helper.inlets(B)] == ["a", 'b']
        self.assertEqual( view.toNetworkX().nodes["B"]["inlets"], ['a', 'b'], "Operator B inlets incorrect")

        # create a link from A to B
        A_outlet = helper.outlet(A)
        B_inlet_a = helper.inlets(B)[0]
        link = helper.createLink(A_outlet, B_inlet_a)
        assert link.isValid(), "Failed to create link from A to B"
        self.assertEqual( len(view.toNetworkX().edges()), 1)
        self.assertIn( ("A", "B", "a"), view.toNetworkX().edges, "Link from A to B.a not in graph")

        # create a third operator
        C = helper.createOperator("'value'", "C")
        self.assertEqual( len(view.toNetworkX().nodes()), 3)
        self.assertIn("C", view.toNetworkX().nodes, "Operator C not in graph")
        self.assertEqual( view.toNetworkX().nodes["C"]["inlets"], [], "Operator C inlets incorrect")

        # create a link from C to B
        C_outlet = helper.outlet(C)
        link2 = helper.createLink(C_outlet, helper.inlets(B)[1])
        assert link2.isValid(), "Failed to create link from C to B"
        self.assertEqual( len(view.toNetworkX().edges()), 2)
        self.assertIn( ("C", "B", "b"), view.toNetworkX().edges, "Link from C to B.b not in graph")

        # delete link2
        helper.deleteLink(link2)
        self.assertEqual( len(view.toNetworkX().edges()), 1)

# class TestGraphView_UnsupportedModelStructures(unittest.TestCase):
#      ...

if __name__ == "__main__":
	unittest.main()