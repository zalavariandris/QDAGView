import unittest

from flowgraphmodel import (
    FlowGraphModel,
    itemmodel_to_nx,
)

from graphdelegate import GraphDelegate
from typing import *
from qtpy.QtCore import *


class GraphAdapter:
    def __init__(self, model:FlowGraphModel):
        self.model = model
        self.graph = itemmodel_to_nx(model)

    def createOperator(self, expression:str, name:str)->QPersistentModelIndex|None:
        assert isinstance(expression, str) and expression, "Expression must be a non-empty string"
        assert isinstance(name, str) and name, "Name must be a non-empty string"

        position = self.model.rowCount(QModelIndex())
        assert self.model.insertRows(position, 1, QModelIndex())       
        new_operator_index = self.model.index(position, 0, QModelIndex())
        assert new_operator_index.isValid(), "Created index is not valid"
        new_node_name = name
        assert self.model.setData(new_operator_index, new_node_name, Qt.ItemDataRole.DisplayRole), "Failed to set data for the new child item"
        return new_operator_index
    
    def expression(self, node:QPersistentModelIndex)->str:
        return self.model.data(node.siblingAtColumn(1), Qt.ItemDataRole.DisplayRole)

    def setExpression(self, node:QPersistentModelIndex, expression:str):
        self.model.setData(node.siblingAtColumn(1), expression, Qt.ItemDataRole.DisplayRole)

    def inlets(self, operator:QPersistentModelIndex)->List[QPersistentModelIndex]:
        return [QPersistentModelIndex(self.model.index(row, 0, operator)) for row in range(self.model.rowCount(operator)-1)]

    def outlet(self, operator:QPersistentModelIndex)->QPersistentModelIndex|None:
        if operator.isValid():
            return QPersistentModelIndex(self.model.index(self.model.rowCount(operator)-1, 0, operator))
        return None

    def createLink(self, outlet:QPersistentModelIndex, inlet:QPersistentModelIndex)->QPersistentModelIndex:
        assert outlet.isValid(), "Source outlet index is not valid"
        assert inlet.isValid(), "Target inlet index is not valid"
        assert outlet.parent().isValid(), "Source node index is not valid"
        assert inlet.parent().isValid(), "Target node index is not valid"
        assert outlet.parent() != inlet.parent(), "Source and target must not have the same parent"

        position = self.model.rowCount(inlet)
        # Make sure the parent has at least one column for children, otherwise the treeview won't show them
        if self.model.columnCount(inlet) == 0:
            self.model.insertColumns(0, 1, inlet)

        # create the link index
        assert self.model.insertRows(position, 1, inlet)
        new_link_index = self.model.index(position, 0, QModelIndex())
        assert new_link_index.isValid(), "Created index is not valid"
        assert self.model.setData(new_link_index, (outlet, inlet), Qt.ItemDataRole.DisplayRole), "Failed to set data for the new link"
        return QPersistentModelIndex(new_link_index)
    
    def deleteOperator(self, operator:QPersistentModelIndex):
        assert operator.isValid(), "Invalid operator index"
        assert self.model.removeRows(operator.row(), 1, QModelIndex()), "Failed to remove operator"

    def deleteLink(self, link:QPersistentModelIndex):
        assert link.isValid(), "Invalid link index"
        inlet_index = link.parent()
        assert inlet_index.isValid(), "Link is not a child of a valid inlet"
        assert self.model.removeRows(link.row(), 1, inlet_index), "Failed to remove link"


class Test_FlowGraph_To_NetworkX(unittest.TestCase):
    def test_simple_graph(self):
        model = FlowGraphModel()
        delegate = GraphDelegate()
        
        delegate.addNode(model)
        delegate.addNode(model)
        delegate.addNode(model)
        node_A = model.index(0, 0)
        node_B = model.index(1, 0)
        node_C = model.index(2, 0)
        model.setData(node_A, "A")
        model.setData(node_B, "B")
        model.setData(node_C, "C")
        model.setData(node_A.siblingAtColumn(1), "a + b")
        model.setData(node_B.siblingAtColumn(1), "x*x")
        model.setData(node_C.siblingAtColumn(1), "text")
        outlet_A = model.index(2, 0, node_A)
        inlet_B = model.index(0, 0, node_B)
        inlet_C = model.index(0, 0, node_C)
        assert delegate.addLink(model, outlet_A, inlet_B)
        assert delegate.addLink(model, , model.index(0, 0, node_B))

        G = itemmodel_to_nx(model)
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
