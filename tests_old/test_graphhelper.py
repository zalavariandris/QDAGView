import unittest
import sys
import os

# Add parent directory to path so we can import the module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import (
    GraphDataRole
)
from qdagview.examples.flowgraphmodel import (
    FlowGraphModel
)

from qdagview.models.graphhelper import (
    ItemGraphHelper
)

from typing import *
from qtpy.QtCore import *



class TestGraphHelper(unittest.TestCase):
    def test_operators(self):
        model = FlowGraphModel()
        helper = ItemGraphHelper(model)

        # create a single operator
        A = helper.createOperator("a+b", "A")
        self.assertTrue( A.isValid(), "Failed to create operator A" )

        # create a second operator
        B = helper.createOperator("x*x", "B")
        self.assertTrue( B.isValid(), "Failed to create operator B" )
        self.assertEqual(helper.nodes(), [A, B])

        # check inlets
        self.assertEqual(model.rowCount(A), 3) # 2 inlets + 1 outlet
        self.assertEqual(len(helper.inlets(A)), 2)
        self.assertEqual([model.data(inlet, Qt.ItemDataRole.EditRole) for inlet in helper.inlets(A)], ["a", "b"])
        self.assertEqual(len(helper.inlets(B)), 1)
        self.assertEqual([model.data(inlet, Qt.ItemDataRole.EditRole) for inlet in helper.inlets(B)], ["x"])

        # update inlets
        helper.setExpression(A, "x*x")
        assert helper.expression(A) == "x*x"
        self.assertEqual(len(helper.inlets(A)), 1)
        
        helper.setExpression(A, "x * y")
        self.assertEqual(len(helper.inlets(A)), 2)

        helper.setExpression(A, "a+b+c")
        self.assertEqual(len(helper.inlets(A)), 3)

        helper.setExpression(A, "a")
        self.assertEqual(len(helper.inlets(A)), 1)

        helper.setExpression(A, "x*x")
        self.assertEqual(len(helper.inlets(A)), 1)

    # def test_simple_graph(self):
    #     model = FlowGraphModel()
    #     helper = ItemGraphHelper(model)

    #     A = helper.createOperator("a+b", "A")
    #     B = helper.createOperator("x*x", "B")
    #     C = helper.createOperator("t+t", "C")

    #     assert helper.createLink(helper.outlet(A), helper.inlets(B)[0])
    #     assert helper.createLink(helper.outlet(B), helper.inlets(C)[0])

    #     G = itemmodel_to_nx(model)
        
    #     # Check that the graph has the correct nodes
    #     self.assertEqual(list(G.nodes()), [
    #         "A", "B", "C"
    #     ])

    #     print(G.nodes(data=True))
    #     print(G.edges(data=True))

        # Check that all the nodes has the correct attributes
        # self.assertEqual(list(G.nodes(data=True)), [
        #     ("A", {"expression": "a + b", 'inlets': ['a', 'b']}),
        #     ("B", {"expression": "x*x", 'inlets': ['x']}),
        #     ("C", {"expression": "text", 'inlets': ['text']})
        # ])

        # # Check that a specific node has the correct attributes
        # self.assertEqual(G.nodes["A"],
        #     {"expression": "a + b", 'inlets': ['a', 'b']}
        # )

        # #
        # self.assertEqual(list(G.edges(data=True)), [
        #     ("A", "B", {'inlet':'x'}),
        #     ("B", "C", {'inlet':'text'})
        # ])


if __name__ == '__main__':
    # Run the tests
    unittest.main(verbosity=2)
