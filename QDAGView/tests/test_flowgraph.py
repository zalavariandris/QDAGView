import unittest
import sys
import os

# Add parent directory to path so we can import the module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dataflowmodel import FlowGraphModel
from qtpy.QtCore import QModelIndex, QPersistentModelIndex, Qt


class TestGraphModels(unittest.TestCase):
    """Test cases for the GraphItemModel class."""

    def test_inserting_node_rows(self):
        """Test adding operators to the graph."""
        self.model = FlowGraphModel()
        self.model.insertRows(0, 5, QModelIndex())
        self.assertEqual(self.model.rowCount(), 5, "Should have five operators after insertion")

    def test_inserting_inlet_rows(self):
        """Test adding inlets to the graph."""
        self.model = FlowGraphModel()
        self.model.insertRows(0, 1, QModelIndex())
        self.assertEqual(self.model.rowCount(), 1, "Should have three nodes after insertion")
        node_index = self.model.index(0, 0)
        self.model.insertRows(0, 3, node_index)
        self.assertEqual(self.model.rowCount(node_index), 3, "Should have three inlets after insertion")

    def test_inserting_outlet_rows(self):
        """Test adding outlets to the graph."""
        self.model = FlowGraphModel()
        self.model.insertRows(0, 1, QModelIndex())
        self.assertEqual(self.model.rowCount(), 1, "Should have one node after insertion")

        node_index = self.model.index(0, 0)
        self.model.insertRows(0, 1, node_index) #insert inlet
        self.model.insertRows(1, 2, node_index) #insert outlets
        for row in range(1, 1+2):
            outlet_index = self.model.index(row, 0, node_index)
            self.model.setData(outlet_index, "Outlet", role=self.model.TypeRole)

class TestGraphModels_ParentChildrenRelationship(unittest.TestCase):
    def test_inlet_parent(self):
        """Test the parent-child relationship in the model."""
        self.model = FlowGraphModel()
        self.model.insertRows(0, 1, QModelIndex())
        node_index = QPersistentModelIndex(self.model.index(0, 0))
        self.assertEqual(self.model.parent(node_index), QModelIndex(), "Node should have no parent")
        
        self.model.insertRows(0, 3, node_index)
        for row in range(3):
            inlet_index = self.model.index(row, 0, node_index)
        
        for row in range(self.model.rowCount(node_index)):
            inlet_index = self.model.index(row, 0, node_index)
            parent_index = self.model.parent(inlet_index)
            self.assertEqual(QPersistentModelIndex(parent_index), node_index, f"Inlet at row {row} should have node as parent, got: {parent_index}")


if __name__ == '__main__':
    # Run the tests
    unittest.main(verbosity=2)
