import pytest
import sys
import os

# Add parent directory to path so we can import the module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qdagview.utils.code_analyzer import CodeAnalyzer
from qdagview.examples.flowgraph import (
    FlowGraph,
    ExpressionOperator,
    Inlet,
    Outlet,
    Link,
    flowgraph_to_nx
)


class TestExpressionOperator:
    def test_expression_outlets(self):
        op = ExpressionOperator("a + b")
        outlets = op.outlets()
        assert {outlet.name for outlet in outlets} == {"result"}

    def test_operator_initial_name(self):
        op = ExpressionOperator("a + b", name="MyOp")
        assert op.name() == "MyOp"
        op.setName("NewName")
        assert op.name() == "NewName"

    def test_operator_auto_generated_name(self):
        op = ExpressionOperator("a + b")
        assert op.name() is not None
        assert len(op.name()) > 0

    def test_initial_inlets(self):
        assert [inlet.name for inlet in ExpressionOperator("a+b").inlets()] == ["a", "b"]
        assert [inlet.name for inlet in ExpressionOperator("a + b").inlets()] == ["a", "b"]
        assert [inlet.name for inlet in ExpressionOperator("x*x").inlets()] == ["x"]
        assert [inlet.name for inlet in ExpressionOperator("text").inlets()] == ["text"]
        assert [inlet.name for inlet in ExpressionOperator("x*y+a").inlets()] == ["x", "y", "a"]
        assert [inlet.name for inlet in ExpressionOperator("a*x+a").inlets()] == ["a", "x"]

    def test_expression_with_values(self):
        assert [inlet.name for inlet in ExpressionOperator("None").inlets()] == []
        assert [inlet.name for inlet in ExpressionOperator("5").inlets()] == []
        assert [inlet.name for inlet in ExpressionOperator("x + 5").inlets()] == ["x"]
        assert [inlet.name for inlet in ExpressionOperator("5 + y").inlets()] == ["y"]
        assert [inlet.name for inlet in ExpressionOperator("5 + 5").inlets()] == []

    def test_expression_with_multiple_occurrences(self):
        op = ExpressionOperator("a + a + a + b")
        inlets = op.inlets()
        assert {inlet.name for inlet in inlets} == {"a", "b"}

    def test_inlets_order(self):
        op = ExpressionOperator("c + b + a")
        inlets = op.inlets()
        assert [inlet.name for inlet in inlets] == ["c", "b", "a"]

    def test_inlets_order_with_repeated_vars(self):
        op = ExpressionOperator("c + a + b + a + c")
        inlets = op.inlets()
        assert [inlet.name for inlet in inlets] == ["c", "a", "b"]

    def test_update_expression(self):
        op = ExpressionOperator("a + b")
        op.setExpression("x + y")
        inlets = op.inlets()
        assert {inlet.name for inlet in inlets} == {"x", "y"}

    def test_update_expression_to_no_inlets(self):
        op = ExpressionOperator("a + b")
        op.setExpression("5 + 10")
        inlets = op.inlets()
        assert len(inlets) == 0

    def test_complex_expressions(self):
        op = ExpressionOperator("(a + b) * (c - d) / e")
        inlets = op.inlets()
        assert {inlet.name for inlet in inlets} == {"a", "b", "c", "d", "e"}

    def test_function_calls_in_expression(self):
        op = ExpressionOperator("sin(x) + cos(y)")
        inlets = op.inlets()
        assert {inlet.name for inlet in inlets} == {"x", "y"}

    def test_expression_with_underscore_variables(self):
        op = ExpressionOperator("var_1 + var_2")
        inlets = op.inlets()
        assert {inlet.name for inlet in inlets} == {"var_1", "var_2"}

    def test_expression_getter(self):
        expression = "a + b * c"
        op = ExpressionOperator(expression)
        assert op.expression() == expression

    def test_inlet_operator_reference(self):
        op = ExpressionOperator("a + b")
        inlets = op.inlets()
        for inlet in inlets:
            assert inlet.operator == op

    def test_outlet_operator_reference(self):
        op = ExpressionOperator("a + b")
        outlets = op.outlets()
        for outlet in outlets:
            assert outlet.operator == op


class TestInletOutlet:
    def test_inlet_creation(self):
        op = ExpressionOperator("a + b")
        inlet = Inlet("test", op)
        assert inlet.name == "test"
        assert inlet.operator == op

    def test_outlet_creation(self):
        op = ExpressionOperator("a + b")
        outlet = Outlet("result", op)
        assert outlet.name == "result"
        assert outlet.operator == op

    def test_inlet_str_representation(self):
        inlet = Inlet("test_inlet")
        assert str(inlet) == "test_inlet"

    def test_outlet_str_representation(self):
        outlet = Outlet("test_outlet")
        assert str(outlet) == "test_outlet"

    def test_inlet_hash(self):
        op = ExpressionOperator("a + b")
        inlet1 = Inlet("test", op)
        inlet2 = Inlet("test", op)
        assert hash(inlet1) == hash(inlet2)

    def test_outlet_hash(self):
        op = ExpressionOperator("a + b")
        outlet1 = Outlet("result", op)
        outlet2 = Outlet("result", op)
        assert hash(outlet1) == hash(outlet2)


class TestLink:
    def test_link_creation(self):
        op1 = ExpressionOperator("a + b")
        op2 = ExpressionOperator("c * d")
        outlet = op1.outlets()[0]
        inlet = op2.inlets()[0]
        link = Link(outlet, inlet)
        assert link.source == outlet
        assert link.target == inlet

    def test_link_str_representation(self):
        op1 = ExpressionOperator("a + b")
        op2 = ExpressionOperator("c * d")
        outlet = op1.outlets()[0]
        inlet = op2.inlets()[0]
        link = Link(outlet, inlet)
        assert "Link(" in str(link)
        assert "->" in str(link)


class TestFlowGraph:
    @pytest.fixture
    def simple_graph(self):
        """Setup a simple graph: [op1] ──c→ [op2], [op3]"""
        graph = FlowGraph()
        op1 = ExpressionOperator("a + b")
        op2 = ExpressionOperator("c * d")
        op3 = ExpressionOperator("e - f")
        graph.insertOperator(0, op1)
        graph.insertOperator(1, op2)
        graph.insertOperator(2, op3)
        link = graph.insertLink(0, op1.outlets()[0], op2.inlets()[0])
        return graph, op1, op2, op3, link

    def test_expression_operators(self):
        graph = FlowGraph()

        # create a single operator
        A = graph.createOperator("a+b", "A")
        assert isinstance(A, ExpressionOperator)

        # create a second operator
        B = graph.createOperator("x*x", "B")
        assert isinstance(B, ExpressionOperator)
        
        assert graph.operators() == [A, B]

        # check inlets
        assert len(A.inlets()) == 2
        assert len(B.inlets()) == 1

        # update inlets
        A.setExpression("x*x")
        assert len(A.inlets()) == 1
        
        A.setExpression("x * y")
        assert len(A.inlets()) == 2

        A.setExpression("a+b+c")
        assert len(A.inlets()) == 3

        A.setExpression("a")
        assert len(A.inlets()) == 1

        A.setExpression("x*x")
        assert len(A.inlets()) == 1

    def test_initial_graph(self, simple_graph):
        graph, op1, op2, op3, link = simple_graph
        assert len(graph.operators()) == 3
        assert op1 in graph.operators()
        assert op2 in graph.operators()
        assert op3 in graph.operators()
        assert link in list(graph.links())
        assert link in graph.inLinks(op2.inlets()[0])
        assert link in graph.outLinks(op1.outlets()[0])
        
    def test_empty_graph(self):
        graph = FlowGraph()
        assert len(graph.operators()) == 0

    def test_graph_name(self):
        graph = FlowGraph("TestGraph")
        assert graph._name == "TestGraph"

    def test_append_operator(self, simple_graph):
        graph, _, _, _, _ = simple_graph
        op = ExpressionOperator("x**2")
        graph.appendOperator(op)
        assert op in graph.operators()

    def test_insert_link(self, simple_graph):
        graph, _, op2, op3, _ = simple_graph
        outlet = op2.outlets()[0]
        inlet = op3.inlets()[0]
        link = graph.insertLink(0, op2.outlets()[0], op3.inlets()[0])

        assert link in graph.inLinks(inlet)
        assert link in graph.outLinks(outlet)

    def test_insert_pending_link(self, simple_graph):
        graph, _, _, op3, _ = simple_graph
        inlet = op3.inlets()[0]
        link = graph.insertLink(0, None, op3.inlets()[0])
        assert link in graph.inLinks(inlet)

    def test_update_link_source(self, simple_graph):
        graph, op1, _, op3, link = simple_graph
        graph.setLinkSource(link, op3.outlets()[0])

        assert link in graph.outLinks(op3.outlets()[0])
        assert link not in graph.outLinks(op1.outlets()[0])

    def test_remove_operator(self):
        graph = FlowGraph()
        op1 = ExpressionOperator("a + b")
        op2 = ExpressionOperator("c * d")
        graph.appendOperator(op1)
        graph.appendOperator(op2)

        assert len(graph.operators()) == 2
        assert set(graph.operators()) == {op1, op2}

        result = graph.removeOperator(op1)
        assert result is True
        assert set(graph.operators()) == {op2}

    def test_remove_nonexistent_operator(self):
        graph = FlowGraph()
        op1 = ExpressionOperator("a + b")
        result = graph.removeOperator(op1)
        assert result is False

    def test_remove_link(self, simple_graph):
        graph, _, op2, _, _ = simple_graph
        link = next(graph.links())
        result = graph.removeLink(link)
        assert result is True
        assert link not in graph.inLinks(op2.inlets()[0])

    def test_multiple_links_same_inlet(self, simple_graph):
        graph, op1, op2, op3, _ = simple_graph
        # Add another link to the same inlet
        inlet = op2.inlets()[0]
        link2 = graph.insertLink(1, op3.outlets()[0], inlet)
        
        links = graph.inLinks(inlet)
        assert len(links) == 2
        assert link2 in links

    def test_ancestors(self, simple_graph):
        graph, op1, op2, _, _ = simple_graph
        ancestors = list(graph.ancestors(op2))
        assert op2 in ancestors
        assert op1 in ancestors

    def test_descendants(self, simple_graph):
        graph, op1, op2, _, _ = simple_graph
        descendants = list(graph.descendants(op1))
        assert op1 in descendants
        assert op2 in descendants

    def test_evaluate(self, simple_graph):
        graph, _, op2, _, _ = simple_graph
        result = graph.evaluate(op2)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_build_script(self, simple_graph):
        graph, _, op2, _, _ = simple_graph
        script = graph.buildScript(op2)
        assert isinstance(script, str)
        assert len(script) > 0


class TestFlowGraphToNetworkX:
    def test_simple_graph(self):
        graph = FlowGraph()
        graph.appendOperator(ExpressionOperator("a + b"))

        G = flowgraph_to_nx(graph)
        assert len(G.nodes) == 1
        assert len(G.edges) == 0

    def test_graph_with_links(self):
        graph = FlowGraph()
        op1 = ExpressionOperator("a + b", "op1")
        op2 = ExpressionOperator("c * d", "op2")
        graph.appendOperator(op1)
        graph.appendOperator(op2)
        graph.insertLink(0, op1.outlets()[0], op2.inlets()[0])

        G = flowgraph_to_nx(graph)
        assert len(G.nodes) == 2
        assert len(G.edges) == 1
        assert "op1" in G.nodes
        assert "op2" in G.nodes

    def test_empty_graph_to_nx(self):
        graph = FlowGraph()
        G = flowgraph_to_nx(graph)
        assert len(G.nodes) == 0
        assert len(G.edges) == 0

    def test_complex_graph_to_nx(self):
        graph = FlowGraph()
        op1 = ExpressionOperator("a", "input1")
        op2 = ExpressionOperator("b", "input2")
        op3 = ExpressionOperator("x + y", "sum")
        
        graph.appendOperator(op1)
        graph.appendOperator(op2)
        graph.appendOperator(op3)
        
        graph.insertLink(0, op1.outlets()[0], op3.inlets()[0])
        graph.insertLink(0, op2.outlets()[0], op3.inlets()[1])

        G = flowgraph_to_nx(graph)
        assert len(G.nodes) == 3
        assert len(G.edges) == 2


class TestFlowGraphEdgeCases:
    def test_operator_with_no_variables(self):
        graph = FlowGraph()
        op = graph.createOperator("42", "constant")
        assert len(op.inlets()) == 0
        assert len(op.outlets()) == 1

    def test_self_referencing_expression(self):
        op = ExpressionOperator("x + x + x")
        inlets = op.inlets()
        assert len(inlets) == 1
        assert inlets[0].name == "x"

    def test_remove_operator_with_links(self):
        graph = FlowGraph()
        op1 = ExpressionOperator("a + b")
        op2 = ExpressionOperator("c * d")
        graph.appendOperator(op1)
        graph.appendOperator(op2)
        link = graph.insertLink(0, op1.outlets()[0], op2.inlets()[0])
        
        # Remove op1, which should also remove the link
        graph.removeOperator(op1)
        
        assert op1 not in graph.operators()
        assert link not in list(graph.links())

    def test_link_with_none_source(self):
        graph = FlowGraph()
        op = ExpressionOperator("a + b")
        graph.appendOperator(op)
        
        # Create a pending link with no source
        link = graph.insertLink(0, None, op.inlets()[0])
        assert link.source is None
        assert link.target == op.inlets()[0]
        
        # Update the link source
        op2 = ExpressionOperator("x")
        graph.appendOperator(op2)
        graph.setLinkSource(link, op2.outlets()[0])
        
        assert link.source == op2.outlets()[0]
        assert link in graph.outLinks(op2.outlets()[0])
