import unittest
import sys
import os

# Add parent directory to path so we can import the module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flowgraph import (
    get_unbound_nodes,
    FlowGraph, ExpressionOperator,
    Inlet,
    Outlet,
    Link
)


class TestParsingExpressions(unittest.TestCase):
    """Test cases for parsing expressions."""

    def test_get_unbound_nodes(self):
        code = """x+y"""
        unbound = get_unbound_nodes(code)
        self.assertIn("x", unbound)
        self.assertIn("y", unbound)


class TestExpressionOperator(unittest.TestCase):
    def test_initial_expression(self):
        op = ExpressionOperator("a + b")
        inlets = op.inlets()
        self.assertEqual({inlet.name for inlet in inlets}, {"a", "b"})

    def test_inlets_with_multiple_occurrences(self):
        op = ExpressionOperator("a + a + a + b")
        inlets = op.inlets()
        self.assertEqual({inlet.name for inlet in inlets}, {"a", "b"})

    def test_inlets_order(self):
        op = ExpressionOperator("c + b + a")
        inlets = op.inlets()
        self.assertEqual([inlet.name for inlet in inlets], ["c", "b", "a"])

    def test_update_expression(self):
        op = ExpressionOperator("a + b")
        op.setExpression("x + y")
        inlets = op.inlets()
        self.assertEqual({inlet.name for inlet in inlets}, {"x", "y"})

    def test_expression_outlets(self):
        op = ExpressionOperator("a + b")
        outlets = op.outlets()
        self.assertEqual({outlet.name for outlet in outlets}, {"result"})

    def test_operator_initial_name(self):
        op = ExpressionOperator("a + b", name="MyOp")
        self.assertEqual(op.name(), "MyOp")
        op.setName("NewName")
        self.assertEqual(op.name(), "NewName")

 
class TestFlowGraph(unittest.TestCase):
    def setUp(self):
        """setup a simple graph
        [op1] ──c→ [op2]
        [op3]
        """

        self.graph = FlowGraph()
        self.op1 = ExpressionOperator("a + b")
        self.op2 = ExpressionOperator("c * d")
        self.op3 = ExpressionOperator("e - f")
        self.graph.insertOperator(0, self.op1)
        self.graph.insertOperator(1, self.op2)
        self.graph.insertOperator(2, self.op3)
        self.link = self.graph.insertLink(0, self.op1.outlets()[0], self.op2.inlets()[0])

    def test_initial_graph(self):
        self.assertEqual(len(self.graph.operators()), 3)
        self.assertIn(self.op1, self.graph.operators())
        self.assertIn(self.op2, self.graph.operators())
        self.assertIn(self.op3, self.graph.operators())
        self.assertIn(self.link, self.graph.links())
        self.assertIn(self.link, self.graph.inLinks(self.op2.inlets()[0]))
        self.assertIn(self.link, self.graph.outLinks(self.op1.outlets()[0]))
        
    ## INIT
    def test_empty_graph(self):
        graph = FlowGraph()
        self.assertEqual(len(graph.operators()), 0)

    ## CREATE
    def test_append_operator(self):
        op = ExpressionOperator("x**2")
        self.graph.appendOperator(op)

        self.assertIn(op, self.graph.operators())

    def test_insert_link(self):
        outlet = self.op2.outlets()[0]
        inlet = self.op3.inlets()[0]
        link = self.graph.insertLink(0, self.op2.outlets()[0], self.op3.inlets()[0])

        self.assertIn(link, self.graph.inLinks(inlet))
        self.assertIn(link, self.graph.outLinks(outlet))

    def test_insert_pending_link(self):
        inlet = self.op3.inlets()[0]
        link = self.graph.insertLink(0, None, self.op3.inlets()[0])

        self.assertIn(link, self.graph.inLinks(inlet))

    def test_update_link_source(self):
        self.graph.setLinkSource(self.link, self.op3.outlets()[0])

        self.assertIn(self.link, self.graph.outLinks(self.op3.outlets()[0]))
        self.assertNotIn(self.link, self.graph.outLinks(self.op1.outlets()[0]))


    ## Delete
    def test_remove_operator(self):
        graph = FlowGraph()
        op1 = ExpressionOperator("a + b")
        op2 = ExpressionOperator("c * d")
        graph.appendOperator(op1)
        graph.appendOperator(op2)

        self.assertEqual(len(graph.operators()), 2)
        self.assertEqual(set(graph.operators()), {op1, op2})

        graph.removeOperator(op1)
        self.assertEqual(set(graph.operators()), {op2})

    def test_remove_link(self):
        link = self.graph.links().__next__()
        self.graph.removeLink(link)
        self.assertNotIn(link, self.graph.inLinks(self.op2.inlets()[0]))

    ## QUERY

    

    




if __name__ == '__main__':
    # Run the tests
    unittest.main(verbosity=2)
