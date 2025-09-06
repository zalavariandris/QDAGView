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
from flowgraphmodel import FlowGraphModel
from itemmodel_graphhelper import ItemGraphHelper

# view
from graphview import GraphView
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
        helper.setExpression(A, "k*k")
        self.assertEqual(view.toNetworkX().nodes["A"]["expression"], "k*k", "Operator A expression incorrect after setExpression")
        assert len(helper.inlets(A)) == 1
        self.assertEqual( view.toNetworkX().nodes["A"]["inlets"], ['k'], "Operator A inlets incorrect after setExpression")

        # # create a second operator
        # B = helper.createOperator("x*x", "B")
        # self.assertEqual( len(view.toNetworkX().nodes()), 2)
        # self.assertIn("B", view.toNetworkX().nodes, "Operator B not in graph")
        # self.assertEqual(view.toNetworkX().nodes["B"]["expression"], "x*x", "Operator B expression incorrect")

        # assert [inlet.data(Qt.ItemDataRole.EditRole) for inlet in helper.inlets()] == ["x"]
        # self.assertEqual( view.toNetworkX().nodes["B"]["inlets"], ['x'], "Operator B inlets incorrect")

# class TestGraphView_UnsupportedModelStructures(unittest.TestCase):
#      ...

if __name__ == "__main__":
	unittest.main()