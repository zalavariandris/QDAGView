import unittest
import sys
import os

# Add parent directory to path so we can import the module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.qdagview.models.code_analyzer import CodeAnalyzer

from src.qdagview.models.flowgraph import (
    FlowGraph,
    ExpressionOperator,
    flowgraph_to_nx
)


class TestExpressionOperator(unittest.TestCase):
    def test_expression_outlets(self):
        op = ExpressionOperator("a + b")
        outlets = op.outlets()
        self.assertEqual({outlet.name for outlet in outlets}, {"result"})

    def test_operator_initial_name(self):
        op = ExpressionOperator("a + b", name="MyOp")
        self.assertEqual(op.name(), "MyOp")
        op.setName("NewName")
        self.assertEqual(op.name(), "NewName")

    def test_initial_inlets(self):
        self.assertEqual([inlet.name for inlet in ExpressionOperator("a+b").inlets()], ["a", "b"])
        self.assertEqual([inlet.name for inlet in ExpressionOperator("a + b").inlets()], ["a", "b"])
        self.assertEqual([inlet.name for inlet in ExpressionOperator("x*x").inlets()], ["x"])
        self.assertEqual([inlet.name for inlet in ExpressionOperator("text").inlets()], ["text"])
        self.assertEqual([inlet.name for inlet in ExpressionOperator("x*y+a").inlets()], ["x", "y", "a"])
        self.assertEqual([inlet.name for inlet in ExpressionOperator("a*x+a").inlets()], ["a", "x"])

    def test_expression_with_values(self):
        self.assertEqual([inlet.name for inlet in ExpressionOperator("None").inlets()], [])
        self.assertEqual([inlet.name for inlet in ExpressionOperator("5").inlets()], [])
        self.assertEqual([inlet.name for inlet in ExpressionOperator("x + 5").inlets()], ["x"])
        self.assertEqual([inlet.name for inlet in ExpressionOperator("5 + y").inlets()], ["y"])
        self.assertEqual([inlet.name for inlet in ExpressionOperator("5 + 5").inlets()], [])

    def test_expression_with_multiple_occurrences(self):
        op = ExpressionOperator("a + a + a + b")
        inlets = op.inlets()
        self.assertEqual({inlet.name for inlet in inlets}, {"a", "b"})

    def test_inlets_order(self):
        op = ExpressionOperator("c + b + a")
        inlets = op.inlets()
        self.assertEqual([inlet.name for inlet in inlets], ["c", "b", "a"])

    def test_inlets_order_with_repeated_vars(self):
        op = ExpressionOperator("c + a + b + a + c")
        inlets = op.inlets()
        self.assertEqual([inlet.name for inlet in inlets], ["c", "a", "b"])

    def test_update_expression(self):
        op = ExpressionOperator("a + b")
        op.setExpression("x + y")
        inlets = op.inlets()
        self.assertEqual({inlet.name for inlet in inlets}, {"x", "y"})

    def test_update_expression_to_no_inlets(self):
        op = ExpressionOperator("a + b")
        op.setExpression("5 + 10")
        inlets = op.inlets()
        self.assertEqual(len(inlets), 0)

 
class TestFlowGraph(unittest.TestCase):
    def test_expression_operators(self):
        graph = FlowGraph()

        # create a single operator
        A = graph.createOperator("a+b", "A")
        self.assertIsInstance(A, ExpressionOperator, "Failed to create operator A")

        # create a second operator
        B = graph.createOperator("x*x", "B")
        self.assertIsInstance( B, ExpressionOperator, "Failed to create operator B" )
        
        #
        self.assertEqual(graph.nodes(), [A, B])

        # check inlets
        self.assertEqual(len(A.inlets()), 2)
        self.assertEqual(len(B.inlets()), 1)

        # update inlets
        A.setExpression("x*x")
        self.assertEqual(len(A.inlets()), 1)
        
        A.setExpression("x * y")
        self.assertEqual(len(A.inlets()), 2)

        A.setExpression("a+b+c")
        self.assertEqual(len(A.inlets()), 3)

        A.setExpression("a")
        self.assertEqual(len(A.inlets()), 1)

        A.setExpression("x*x")
        self.assertEqual(len(A.inlets()), 1)
    
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


class TestFlowGraph(unittest.TestCase):
    def test_simple_graph(self):
        graph = FlowGraph()
        graph.appendOperator(ExpressionOperator("a + b"))

        G = flowgraph_to_nx(graph)
        self.assertEqual(len(G.nodes), 1)
        self.assertEqual(len(G.edges), 0)

        print(G)


if __name__ == '__main__':
    # Run the tests
    unittest.main(verbosity=2)
