import unittest
import sys
import os

# Add parent directory to path so we can import the module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flowgraph import (
    get_unbound_nodes,
    FlowGraph,
    ExpressionOperator,
    Inlet,
    Outlet,
    Link,
    flowgraph_to_nx
)

class Test_FlowGraph_To_NetworkX(unittest.TestCase):
    def test_simple_graph(self):
        graph = FlowGraph()
        op1 = ExpressionOperator("a + b", name="A")
        op2 = ExpressionOperator("x*x", name="B")
        op3 = ExpressionOperator("text", name="C")
        graph.appendOperator(op1)
        graph.appendOperator(op2)
        graph.appendOperator(op3)
        graph.insertLink(0, op1.outlets()[0], op2.inlets()[0])
        graph.insertLink(0, op2.outlets()[0], op3.inlets()[0])

        G = flowgraph_to_nx(graph)
        # Check that the graph has the correct nodes
        self.assertEqual(list(G.nodes()), [
            "A", "B", "C"
        ])

        # Check that all the nodes has the correct attributes
        self.assertEqual(list(G.nodes(data=True)), [
            ("A", {"expression": "a + b", 'inlets': ['a', 'b']}),
            ("B", {"expression": "x*x", 'inlets': ['x']}),
            ("C", {"expression": "text", 'inlets': ['text']})
        ])

        # Check that a specific node has the correct attributes
        self.assertEqual(G.nodes["A"],
            {"expression": "a + b", 'inlets': ['a', 'b']}
        )

        #
        self.assertEqual(list(G.edges(data=True)), [
            ("A", "B", {'inlet':'x'}),
            ("B", "C", {'inlet':'text'})
        ])

    


if __name__ == '__main__':
    # Run the tests
    unittest.main(verbosity=2)
