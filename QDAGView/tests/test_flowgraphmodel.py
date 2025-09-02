import unittest
import sys
import os

# Add parent directory to path so we can import the module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flowgraph import FlowGraph
from flowgraphmodel import ExpressionOperator
from flowgraphmodel import FlowGraphModel
from qtpy.QtCore import QModelIndex, QPersistentModelIndex, Qt
from core import GraphDataRole, GraphItemType

from qtpy.QtTest import QSignalSpy
import networkx as nx


def flowmodel_to_nx(model:FlowGraphModel)->nx.MultiDiGraph:
    G = nx.MultiDiGraph()

    # add nodes
    for node_row in range(model.rowCount()):
        node_index = model.index(node_row, 0)

        n = model.data(node_index, Qt.EditRole)
        G.add_node(n, 
            expression=model.data(node_index.siblingAtColumn(1), Qt.EditRole),
            inlets=[model.data(model.index(inlet_row, 0, node_index), Qt.EditRole) for inlet_row in range(model.rowCount(node_index) - 1)]
        )

    for node_row in range(model.rowCount()):
        for inlet_row in range(model.rowCount(model.index(node_row, 0)) - 1):
            inlet_index = model.index(inlet_row, 0, node_index)
            for link_row in range(model.rowCount(inlet_index)):
                link_index = model.index(link_row, 0, inlet_index)
                source_outlet_index = model.data(link_index, GraphDataRole.SourceRole)
                source_node_index = source_outlet_index.parent()
                s = model.data(source_node_index, Qt.EditRole)
                G.add_edge(n, s, inlet=model.data(inlet_index, Qt.EditRole))

    return G


def flowgraph_to_nx(graph: FlowGraph) -> nx.MultiDiGraph:
    G = nx.MultiDiGraph()
    for node in graph.operators():
        G.add_node(node, **graph.node[node])
        for inlet in graph.in_edges(node):
            G.add_edge(inlet[0], node, **graph.edge[inlet])
    return G


class TestFlowGraphModel(unittest.TestCase):
    def setUp(self):
        self.model = FlowGraphModel()  
        self.model.insertRows(0, 1, QModelIndex())

    ## INITIAL Graph
    def test_empty_model(self):
        model = FlowGraphModel()
        self.assertEqual(model.rowCount(), 0, "Initial model should have zero rows")
        self.assertEqual(model.columnCount(), 2, "Initial model should have zero columns")

    ## Default Node
    def test_default_expression(self):
        model = FlowGraphModel()  
        model.insertRows(0, 1, QModelIndex())

        node_index = model.index(0, 0)
        self.assertTrue(node_index.isValid(), "Node index should be valid")
        self.assertEqual(model.rowCount(), 1, "Model should have one operator after insertion")
        self.assertEqual(model.data(node_index.siblingAtColumn(1), Qt.EditRole), "x+y", "No data in new operator")

    def test_initial_inlets_for_new_node(self):
        model = FlowGraphModel()  
        model.insertRows(0, 1, QModelIndex())

        node_index = model.index(0, 0)

        inlet_x_index = model.index(0, 0, node_index)
        self.assertTrue(inlet_x_index.isValid(), "First inlet index should be valid")
        self.assertEqual(model.data(inlet_x_index, Qt.EditRole), "x", "First inlet should be 'x'")

        inlet_y_index = model.index(1, 0, node_index)
        self.assertTrue(inlet_y_index.isValid(), "Second inlet index should be valid")
        self.assertEqual(model.data(inlet_y_index, Qt.EditRole), "y", "Second inlet should be 'y'")

    def test_initial_outlet_for_new_node(self):
        model = FlowGraphModel()  
        model.insertRows(0, 1, QModelIndex())
        node_index = model.index(0, 0)

        outlet_index = model.index(2, 0, node_index)
        self.assertTrue(outlet_index.isValid(), "First outlet index should be valid")
        self.assertEqual(model.data(outlet_index, Qt.ItemDataRole.EditRole), "result")
        self.assertEqual(model.data(outlet_index, GraphDataRole.TypeRole), GraphItemType.OUTLET)
        
    ## UPDATE
    def test_updating_expression_update_inlets_as_well(self):
        model = FlowGraphModel()
        spy_inlet_name_changed = QSignalSpy(model.dataChanged)
        model.insertRows(0, 1, QModelIndex())
        node_index = model.index(0, 0)
        
        self.assertEqual(model.data(node_index.siblingAtColumn(1), Qt.EditRole), "x+y", "No data in new operator")
        success = model.setData(node_index.siblingAtColumn(1), "i*k", Qt.EditRole)
        self.assertTrue(success, "Setting data should succeed")
        self.assertEqual(model.data(node_index.siblingAtColumn(1), Qt.EditRole), "i*k", "No data in new operator")

        self.assertEqual(model.index(0, 0, node_index).data(Qt.EditRole), "i", "first inlet should be 'i'")
        self.assertEqual(model.index(1, 0, node_index).data(Qt.EditRole), "k", "Second inlet should be 'k'")


class TestDynamicInletUpdates(unittest.TestCase):
    def add_node(self, expression:str)->QModelIndex:
        pos = self.model.rowCount(QModelIndex())
        self.model.insertRows(pos, 1, QModelIndex())
        node_index = self.model.index(pos, 0)
        self.set_node_expression(node_index, expression)
    
    def set_node_expression(self, node:QModelIndex, expression:str):
        self.model.setData(node.siblingAtColumn(1), expression, Qt.EditRole)

    def link_nodes(self, outlet: QModelIndex, inlet: QModelIndex):
        self.model.insertRows(inlet.row(), 1, inlet)
        self.model.setData(self.model.index(inlet.row(), 0, inlet), outlet.data(Qt.EditRole), Qt.EditRole)

    def setUp(self):
        self.model = FlowGraphModel()
        self.model.insertRows(0, 1, QModelIndex())
        self.node_index = self.model.index(0, 0)
        self.model.setData(self.node_index.siblingAtColumn(1), "x+y", Qt.EditRole)

    def test_initial_model(self):
        """Test the initial state of the model."""
        # Initial state: x+y should have inlets 'x' and 'y'
        self.assertEqual(self.model.data(self.node_index.siblingAtColumn(1), Qt.EditRole), "x+y")
        self.assertEqual(self.model.index(0, 0, self.node_index).data(Qt.EditRole), "x")
        self.assertEqual(self.model.index(1, 0, self.node_index).data(Qt.EditRole), "y")

    def test_inlets_names_updated_when_expression_changes(self):
        """Test that inlet names are updated when expression changes."""

        spy = QSignalSpy(self.model.dataChanged)
        
        # Change expression to 'a*b*c'
        self.model.setData(self.node_index.siblingAtColumn(1), "m*a", Qt.EditRole)
        
        # Verify inlet names changed
        first_inlet_index = self.model.index(0, 0, self.node_index)
        self.assertEqual(first_inlet_index.data(Qt.EditRole), "m")
        second_inlet_index = self.model.index(1, 0, self.node_index)
        self.assertEqual(second_inlet_index.data(Qt.EditRole), "a")

        # Verify dataChanged emitted for the signals
        def isDataChangedEmittedForInlets(index: QModelIndex, spy: QSignalSpy) -> bool:
            for i in range(len(spy)):
                arguments = spy[i]
                topLeft, bottomRight, roles = arguments
                if index.row() <= bottomRight.row() and index.row() >= topLeft.row() and index.column() >= topLeft.column() and index.column() <= bottomRight.column():
                    return True
            return False

        self.assertTrue(isDataChangedEmittedForInlets(first_inlet_index, spy))
        self.assertTrue(isDataChangedEmittedForInlets(second_inlet_index, spy))

    def test_inlets_added_when_more_variables_in_expression(self):
        """Test that inlets are added when expression has more variables."""
        spy = QSignalSpy(self.model.rowsInserted)
        initial_inlet_count = self.model.rowCount(self.node_index) - 1  # Subtract outlet
        assert initial_inlet_count == 2, "Should have 2 inlets Initially"
        
        # Change from 'x+y' (2 variables) to 'a+b+c+d' (4 variables)
        self.model.setData(self.node_index.siblingAtColumn(1), "a+b+c+d", Qt.EditRole)
        
        new_inlet_count = self.model.rowCount(self.node_index) - 1  # Subtract outlet
        self.assertEqual(new_inlet_count, 4, "Should have 4 inlets after expression change")
        self.assertGreater(new_inlet_count, initial_inlet_count, "Should have more inlets")
        
        # Verify rowsInserted signal was emitted
        self.assertGreater(len(spy), 0, "rowsInserted should be emitted when adding inlets")

    def test_inlets_removed_when_fewer_variables_in_expression(self):
        """Test that inlets are removed when expression has fewer variables."""
        # First add more inlets
        assert self.model.rowCount(self.node_index) - 1 == 2, "Should have 2 inlets Initially"
        
        spy = QSignalSpy(self.model.rowsRemoved)
        
        # Change to fewer variables
        self.model.setData(self.node_index.siblingAtColumn(1), "x", Qt.EditRole)
        
        new_inlet_count = self.model.rowCount(self.node_index) - 1  # Subtract outlet
        self.assertEqual(new_inlet_count, 1, "Should have 1 inlet after expression change")
        
        # Verify rowsRemoved signal was emitted
        self.assertGreater(len(spy), 0, "rowsRemoved should be emitted when removing inlets")

    def test_inlet_data_changed_signals_emitted(self):
        """Test that dataChanged signals are emitted for inlet name changes."""
        spy = QSignalSpy(self.model.dataChanged)
        
        # Change expression which should update inlet names
        self.model.setData(self.node_index.siblingAtColumn(1), "p+q", Qt.EditRole)
                
        # Verify inlet names actually changed
        self.assertEqual(self.model.index(0, 0, self.node_index).data(Qt.EditRole), "p")
        self.assertEqual(self.model.index(1, 0, self.node_index).data(Qt.EditRole), "q")

        # Verify dataChanged signal was emitted
        self.assertGreaterEqual(len(spy), 2, "dataChanged should be for the node index and also for the inlet names")

    def test_outlet_unchanged_when_expression_changes(self):
        """Test that outlet remains unchanged when expression changes."""
        # Get initial outlet
        outlet_row = self.model.rowCount(self.node_index) - 1
        outlet_index = self.model.index(outlet_row, 0, self.node_index)
        initial_outlet_name = self.model.data(outlet_index, Qt.EditRole)
        initial_outlet_type = self.model.data(outlet_index, GraphDataRole.TypeRole)
        
        # Change expression
        self.model.setData(self.node_index.siblingAtColumn(1), "complex_expression", Qt.EditRole)
        
        # Verify outlet unchanged
        new_outlet_row = self.model.rowCount(self.node_index) - 1
        new_outlet_index = self.model.index(new_outlet_row, 0, self.node_index)
        self.assertEqual(self.model.data(new_outlet_index, Qt.EditRole), initial_outlet_name)
        self.assertEqual(self.model.data(new_outlet_index, GraphDataRole.TypeRole), initial_outlet_type)


    def test_when_inlet_replaced_links_are_updated(self):
        """Test that links are updated when an inlet is replaced."""
        # Add a node and an inlet
        


## Generic Graph Model Tests
"""
Any model used for a Graph should support graph operations by QAbstractItemModel default insertRows and removeRows methods.

TODO: phraise this properly
the default assumption for tree items is that the root is a graph.
items are organized in a parent-child hierarchy.
the first level contains the nodes, and each node child items are inlets and outlets.
any child items of a node by default are considered inlets.
if specified by the _GraphItemType.Outlet_ then it is an outlet.
Any child item of an _inlet_ is a _link_
the structure is as follows:
- node
  - inlet
  - inlet
    - link
  - outlet(if type is specified)
"""
# class TestGraphModels(unittest.TestCase):
#     """Test cases for the GraphItemModel class."""

#     def test_inserting_multiple_node_rows(self):
#         """Test adding operators to the graph."""
#         self.model = FlowGraphModel()
#         self.model.insertRows(0, 5, QModelIndex())
#         self.assertEqual(self.model.rowCount(), 5, "Should have five operators after insertion")

#     def test_inserting_multiple_inlet_rows(self):
#         """Test adding inlets to the graph."""
#         self.model = FlowGraphModel()
#         self.model.insertRows(0, 1, QModelIndex())
#         self.assertEqual(self.model.rowCount(), 1, "Should have three nodes after insertion")
#         node_index = self.model.index(0, 0)
#         self.model.insertRows(0, 3, node_index)
#         self.assertEqual(self.model.rowCount(node_index), 3, "Should have three inlets after insertion")

#     def test_inserting_multiple_outlet_rows(self):
#         """Test adding outlets to the graph."""
#         self.model = FlowGraphModel()
#         self.model.insertRows(0, 1, QModelIndex())
#         self.assertEqual(self.model.rowCount(), 1, "Should have one node after insertion")

#         node_index = self.model.index(0, 0)
#         self.model.insertRows(0, 1, node_index) #insert inlet
#         self.model.insertRows(1, 2, node_index) #insert outlets
#         for row in range(1, 1+2):
#             outlet_index = self.model.index(row, 0, node_index)
#             self.model.setData(outlet_index, "Outlet", role=self.model.TypeRole)


# class TestGraphModels_ParentChildrenRelationship(unittest.TestCase):
#     def test_inlet_parent(self):
#         """Test the parent-child relationship in the model."""
#         self.model = FlowGraphModel()
#         self.model.insertRows(0, 1, QModelIndex())
#         node_index = QPersistentModelIndex(self.model.index(0, 0))
#         self.assertEqual(self.model.parent(node_index), QModelIndex(), "Node should have no parent")
        
#         self.model.insertRows(0, 3, node_index)
#         for row in range(3):
#             inlet_index = self.model.index(row, 0, node_index)
        
#         for row in range(self.model.rowCount(node_index)):
#             inlet_index = self.model.index(row, 0, node_index)
#             parent_index = self.model.parent(inlet_index)
#             self.assertEqual(QPersistentModelIndex(parent_index), node_index, f"Inlet at row {row} should have node as parent, got: {parent_index}")


if __name__ == '__main__':
    # Run the tests
    unittest.main(verbosity=2)
