import unittest
import sys
from unittest.mock import Mock, patch
from PySide6.QtCore import Qt, QModelIndex, QObject
from PySide6.QtWidgets import QApplication

from my_tree_model import TreeModel, TreeItem


class TestTreeItem(unittest.TestCase):
    """Test cases for TreeItem class."""
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        self.app = QApplication.instance() or QApplication(sys.argv)
        self.data = ["Column 1", "Column 2", "Column 3"]
        self.item = TreeItem(self.data)
    
    def tearDown(self):
        """Clean up after each test method."""
        pass
    
    def test_init_with_list_data(self):
        """Test TreeItem initialization with list data."""
        item = TreeItem(["test1", "test2"])
        self.assertEqual(item.data(), ["test1", "test2"])
        self.assertIsNone(item.parent_item)
        self.assertEqual(item.child_items, [])
        self.assertIsNone(item.model())
    
    def test_init_with_non_list_data(self):
        """Test TreeItem initialization with non-list data."""
        item = TreeItem("not a list")
        self.assertEqual(item.data(), [])
    
    def test_data_access(self):
        """Test data access by column."""
        self.assertEqual(self.item.data(0), "Column 1")
        self.assertEqual(self.item.data(1), "Column 2")
        self.assertEqual(self.item.data(2), "Column 3")
        self.assertIsNone(self.item.data(3))  # Out of bounds
        self.assertIsNone(self.item.data(-1))  # Negative index
    
    def test_set_data(self):
        """Test setting data in a column."""
        mock_model = Mock()
        self.item._model = mock_model
        
        # Test successful data change
        result = self.item.setData(0, "New Value")
        self.assertTrue(result)
        self.assertEqual(self.item.data(0), "New Value")
        
        # Test no change when setting same value
        result = self.item.setData(0, "New Value")
        self.assertFalse(result)
        
        # Test out of bounds
        result = self.item.setData(5, "Invalid")
        self.assertFalse(result)
    
    def test_column_count(self):
        """Test column count."""
        self.assertEqual(self.item.column_count(), 3)
        
        empty_item = TreeItem([])
        self.assertEqual(empty_item.column_count(), 0)
    
    def test_child_operations(self):
        """Test child item operations."""
        child1 = TreeItem(["Child 1"])
        child2 = TreeItem(["Child 2"])
        child3 = TreeItem(["Child 3"])
        
        # Test child count initially
        self.assertEqual(self.item.child_count(), 0)
        
        # Test append child
        self.item.append_child(child1)
        self.assertEqual(self.item.child_count(), 1)
        self.assertEqual(self.item.child(0), child1)
        self.assertEqual(child1.parent_item, self.item)
        
        # Test insert child
        self.item.insert_child(0, child2)
        self.assertEqual(self.item.child_count(), 2)
        self.assertEqual(self.item.child(0), child2)
        self.assertEqual(self.item.child(1), child1)
        
        # Test insert at end
        self.item.insert_child(2, child3)
        self.assertEqual(self.item.child_count(), 3)
        self.assertEqual(self.item.child(2), child3)
        
        # Test remove child
        result = self.item.remove_child(1)
        self.assertTrue(result)
        self.assertEqual(self.item.child_count(), 2)
        self.assertEqual(self.item.child(0), child2)
        self.assertEqual(self.item.child(1), child3)
        self.assertIsNone(child1.parent_item)
        self.assertIsNone(child1._model)
        
        # Test remove out of bounds
        result = self.item.remove_child(5)
        self.assertFalse(result)
    
    def test_row_method(self):
        """Test row method returns correct index in parent."""
        parent = TreeItem(["Parent"])
        child1 = TreeItem(["Child 1"])
        child2 = TreeItem(["Child 2"])
        
        parent.append_child(child1)
        parent.append_child(child2)
        
        self.assertEqual(child1.row(), 0)
        self.assertEqual(child2.row(), 1)
        self.assertEqual(parent.row(), 0)  # Root item
    
    def test_model_recursion(self):
        """Test that model reference is set recursively."""
        mock_model = Mock()
        parent = TreeItem(["Parent"])
        child = TreeItem(["Child"])
        grandchild = TreeItem(["Grandchild"])
        
        parent.append_child(child)
        child.append_child(grandchild)
        
        parent._model = mock_model
        parent._set_model_recursively(parent)
        
        self.assertEqual(parent._model, mock_model)
        self.assertEqual(child._model, mock_model)
        self.assertEqual(grandchild._model, mock_model)


class TestTreeModel(unittest.TestCase):
    """Test cases for TreeModel class."""
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        self.app = QApplication.instance() or QApplication(sys.argv)
        self.headers = ["Name", "Type", "Value"]
        self.model = TreeModel(self.headers)
    
    def tearDown(self):
        """Clean up after each test method."""
        pass
    
    def test_init(self):
        """Test TreeModel initialization."""
        self.assertIsInstance(self.model.root_item, TreeItem)
        self.assertEqual(self.model.root_item._data, self.headers)
        self.assertEqual(self.model.root_item._model, self.model)
    
    def test_column_count(self):
        """Test columnCount method."""
        # Root level column count
        self.assertEqual(self.model.columnCount(), 3)
        
        # Add a child with different column count
        child = TreeItem(["A", "B"])
        self.model.root_item.append_child(child)
        child_index = self.model.index(0, 0)
        self.assertEqual(self.model.columnCount(child_index), 2)
    
    def test_row_count(self):
        """Test rowCount method."""
        # Initially no children
        self.assertEqual(self.model.rowCount(), 0)
        
        # Add children
        child1 = TreeItem(["Child 1"])
        child2 = TreeItem(["Child 2"])
        self.model.root_item.append_child(child1)
        self.model.root_item.append_child(child2)
        
        self.assertEqual(self.model.rowCount(), 2)
        
        # Test child row count
        grandchild = TreeItem(["Grandchild"])
        child1.append_child(grandchild)
        
        child1_index = self.model.index(0, 0)
        self.assertEqual(self.model.rowCount(child1_index), 1)
    
    def test_index_creation(self):
        """Test index method."""
        # Add a child
        child = TreeItem(["Child"])
        self.model.root_item.append_child(child)
        
        # Test valid index
        index = self.model.index(0, 0)
        self.assertTrue(index.isValid())
        self.assertEqual(index.row(), 0)
        self.assertEqual(index.column(), 0)
        self.assertEqual(index.internalPointer(), child)
        
        # Test invalid indices
        invalid_index = self.model.index(1, 0)  # Row out of bounds
        self.assertFalse(invalid_index.isValid())
        
        invalid_index = self.model.index(0, 5)  # Column out of bounds
        self.assertFalse(invalid_index.isValid())
    
    def test_parent_method(self):
        """Test parent method."""
        # Add parent and child
        parent_item = TreeItem(["Parent"])
        child_item = TreeItem(["Child"])
        self.model.root_item.append_child(parent_item)
        parent_item.append_child(child_item)
        
        # Get indices
        parent_index = self.model.index(0, 0)
        child_index = self.model.index(0, 0, parent_index)
        
        # Test parent of child
        result_parent = self.model.parent(child_index)
        self.assertEqual(result_parent, parent_index)
        
        # Test parent of root child (should be invalid)
        root_parent = self.model.parent(parent_index)
        self.assertFalse(root_parent.isValid())
        
        # Test invalid index
        invalid_parent = self.model.parent(QModelIndex())
        self.assertFalse(invalid_parent.isValid())
    
    def test_data_and_set_data(self):
        """Test data and setData methods."""
        # Add a child
        child = TreeItem(["Original Value", "Type"])
        self.model.root_item.append_child(child)
        
        index = self.model.index(0, 0)
        
        # Test data retrieval
        data = self.model.data(index, Qt.DisplayRole)
        self.assertEqual(data, "Original Value")
        
        data = self.model.data(index, Qt.EditRole)
        self.assertEqual(data, "Original Value")
        
        # Test unsupported role
        data = self.model.data(index, Qt.BackgroundRole)
        self.assertIsNone(data)
        
        # Test setData
        result = self.model.setData(index, "New Value", Qt.EditRole)
        self.assertTrue(result)
        
        # Verify data changed
        data = self.model.data(index, Qt.DisplayRole)
        self.assertEqual(data, "New Value")
        
        # Test setData with unsupported role
        result = self.model.setData(index, "Another Value", Qt.BackgroundRole)
        self.assertFalse(result)
    
    def test_flags(self):
        """Test flags method."""
        # Add a child
        child = TreeItem(["Test"])
        self.model.root_item.append_child(child)
        
        index = self.model.index(0, 0)
        flags = self.model.flags(index)
        
        expected_flags = Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable
        self.assertEqual(flags, expected_flags)
        
        # Test invalid index
        invalid_flags = self.model.flags(QModelIndex())
        self.assertEqual(invalid_flags, Qt.ItemIsEnabled)
    
    def test_header_data(self):
        """Test headerData method."""
        # Test horizontal header
        header = self.model.headerData(0, Qt.Horizontal, Qt.DisplayRole)
        self.assertEqual(header, "Name")
        
        header = self.model.headerData(1, Qt.Horizontal, Qt.DisplayRole)
        self.assertEqual(header, "Type")
        
        header = self.model.headerData(2, Qt.Horizontal, Qt.DisplayRole)
        self.assertEqual(header, "Value")
        
        # Test out of bounds
        header = self.model.headerData(5, Qt.Horizontal, Qt.DisplayRole)
        self.assertIsNone(header)
        
        # Test vertical header (not supported)
        header = self.model.headerData(0, Qt.Vertical, Qt.DisplayRole)
        self.assertIsNone(header)
        
        # Test unsupported role
        header = self.model.headerData(0, Qt.Horizontal, Qt.BackgroundRole)
        self.assertIsNone(header)
    
    def test_insert_rows(self):
        """Test insertRows method."""
        # Insert rows at root level
        initial_count = self.model.rowCount()
        result = self.model.insertRows(0, 2)
        self.assertTrue(result)
        self.assertEqual(self.model.rowCount(), initial_count + 2)
        
        # Check inserted items
        index1 = self.model.index(0, 0)
        index2 = self.model.index(1, 0)
        self.assertTrue(index1.isValid())
        self.assertTrue(index2.isValid())
        
        data1 = self.model.data(index1, Qt.DisplayRole)
        data2 = self.model.data(index2, Qt.DisplayRole)
        self.assertEqual(data1, "New Item 1")
        self.assertEqual(data2, "New Item 2")
        
        # Insert rows with parent
        parent_index = self.model.index(0, 0)
        result = self.model.insertRows(0, 1, parent_index)
        self.assertTrue(result)
        self.assertEqual(self.model.rowCount(parent_index), 1)
    
    def test_remove_rows(self):
        """Test removeRows method."""
        # Add some rows first
        self.model.insertRows(0, 3)
        initial_count = self.model.rowCount()
        
        # Remove rows
        result = self.model.removeRows(1, 1)
        self.assertTrue(result)
        self.assertEqual(self.model.rowCount(), initial_count - 1)
        
        # Try to remove out of bounds
        result = self.model.removeRows(10, 1)
        self.assertTrue(result)  # Should still return True even if no items removed
        
        # Remove multiple rows
        result = self.model.removeRows(0, 2)
        self.assertTrue(result)
        self.assertEqual(self.model.rowCount(), 0)
    
    @patch('my_tree_model.TreeItem._emit_data_changed')
    def test_signal_emission_on_data_change(self, mock_emit):
        """Test that signals are emitted when data changes."""
        child = TreeItem(["Test"])
        self.model.root_item.append_child(child)
        
        index = self.model.index(0, 0)
        self.model.setData(index, "New Value", Qt.EditRole)
        
        # Verify signal emission was called
        mock_emit.assert_called_once_with(0)
    
    def test_model_reference_propagation(self):
        """Test that model references are properly propagated to children."""
        # Create a hierarchy
        parent = TreeItem(["Parent"])
        child = TreeItem(["Child"])
        grandchild = TreeItem(["Grandchild"])
        
        # Build hierarchy
        parent.append_child(child)
        child.append_child(grandchild)
        
        # Add to model
        self.model.root_item.append_child(parent)
        
        # Check all items have model reference
        self.assertEqual(parent._model, self.model)
        self.assertEqual(child._model, self.model)
        self.assertEqual(grandchild._model, self.model)


class TestTreeModelIntegration(unittest.TestCase):
    """Integration tests for TreeModel with complex scenarios."""
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        self.app = QApplication.instance() or QApplication(sys.argv)
        self.model = TreeModel(["Name", "Value"])
    
    def test_complex_hierarchy(self):
        """Test complex tree hierarchy operations."""
        # Build a complex tree structure
        # Root
        #   ├── Parent1
        #   │   ├── Child1
        #   │   └── Child2
        #   └── Parent2
        #       └── Child3
        
        # Add parents
        self.model.insertRows(0, 2)  # Add 2 root children
        
        parent1_index = self.model.index(0, 0)
        parent2_index = self.model.index(1, 0)
        
        # Set parent names
        self.model.setData(parent1_index, "Parent1")
        self.model.setData(parent2_index, "Parent2")
        
        # Add children to Parent1
        self.model.insertRows(0, 2, parent1_index)
        child1_index = self.model.index(0, 0, parent1_index)
        child2_index = self.model.index(1, 0, parent1_index)
        
        self.model.setData(child1_index, "Child1")
        self.model.setData(child2_index, "Child2")
        
        # Add child to Parent2
        self.model.insertRows(0, 1, parent2_index)
        child3_index = self.model.index(0, 0, parent2_index)
        self.model.setData(child3_index, "Child3")
        
        # Verify structure
        self.assertEqual(self.model.rowCount(), 2)
        self.assertEqual(self.model.rowCount(parent1_index), 2)
        self.assertEqual(self.model.rowCount(parent2_index), 1)
        
        # Verify data
        self.assertEqual(self.model.data(parent1_index), "Parent1")
        self.assertEqual(self.model.data(child1_index), "Child1")
        self.assertEqual(self.model.data(child2_index), "Child2")
        self.assertEqual(self.model.data(child3_index), "Child3")
        
        # Test parent relationships
        self.assertEqual(self.model.parent(child1_index), parent1_index)
        self.assertEqual(self.model.parent(child3_index), parent2_index)
        self.assertFalse(self.model.parent(parent1_index).isValid())
    
    def test_batch_operations(self):
        """Test batch insert and remove operations."""
        # Insert multiple rows at once
        self.model.insertRows(0, 5)
        self.assertEqual(self.model.rowCount(), 5)
        
        # Remove multiple rows
        self.model.removeRows(1, 3)
        self.assertEqual(self.model.rowCount(), 2)
        
        # Verify remaining items
        remaining1 = self.model.data(self.model.index(0, 0))
        remaining2 = self.model.data(self.model.index(1, 0))
        self.assertEqual(remaining1, "New Item 1")
        self.assertEqual(remaining2, "New Item 5")


if __name__ == '__main__':
    # Ensure QApplication exists for tests
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    # Run tests
    unittest.main()
