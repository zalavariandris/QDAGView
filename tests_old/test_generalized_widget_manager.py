#!/usr/bin/env python3
"""
Test script for the generalized WidgetManager implementation.
This tests arbitrary tree depth support.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'QDAGView'))

from qtpy.QtCore import *
from qtpy.QtWidgets import *
from qtpy.QtGui import *

# Import our classes
from graphview import WidgetManager
from core import indexFromPath

class DeepMockModel(QAbstractItemModel):
    """Mock model that supports arbitrary depth."""
    def __init__(self, max_depth=5):
        super().__init__()
        self.max_depth = max_depth
    
    def index(self, row, column, parent=QModelIndex()):
        if not parent.isValid():
            # Root level
            if 0 <= row < 3:  # 3 root items
                return self.createIndex(row, column, row)  # Use simple int for root
        else:
            # Child level - create deeper paths
            parent_data = parent.internalId()
            # Convert parent data to tuple if it's an int
            if isinstance(parent_data, int):
                parent_path = (parent_data,)
            else:
                parent_path = parent_data
                
            if len(parent_path) < self.max_depth and 0 <= row < 2:  # 2 children per parent
                new_path = parent_path + (row,)
                return self.createIndex(row, column, new_path)
        return QModelIndex()
    
    def parent(self, index):
        if not index.isValid():
            return QModelIndex()
        
        path_data = index.internalId()
        # Convert to tuple if it's an int
        if isinstance(path_data, int):
            return QModelIndex()  # Root items have no parent
        
        path = path_data
        if len(path) <= 1:
            return QModelIndex()  # Root items have no parent
        
        # Parent path is all but the last element
        parent_path = path[:-1]
        if len(parent_path) == 1:
            # Parent is a root item
            return self.createIndex(parent_path[0], 0, parent_path[0])
        else:
            # Parent is also a nested item
            parent_row = parent_path[-1]
            return self.createIndex(parent_row, 0, parent_path)
    
    def rowCount(self, parent=QModelIndex()):
        if not parent.isValid():
            return 3  # 3 root items
        
        path_data = parent.internalId()
        # Convert to tuple if it's an int
        if isinstance(path_data, int):
            path = (path_data,)
        else:
            path = path_data
            
        if len(path) < self.max_depth:
            return 2  # 2 children per item (unless at max depth)
        return 0
    
    def columnCount(self, parent=QModelIndex()):
        return 1

class MockWidget(QGraphicsWidget):
    """Simple mock widget for testing."""
    def __init__(self, name):
        super().__init__()
        self.name = name
    
    def __repr__(self):
        return f"MockWidget({self.name})"

def test_arbitrary_depth():
    """Test the generalized WidgetManager with arbitrary depth."""
    app = QApplication(sys.argv) if not QApplication.instance() else QApplication.instance()
    
    print("🧪 Testing WidgetManager with arbitrary tree depth...")
    
    # Simple test with one depth at a time
    for max_depth in [3, 5, 7]:
        print(f"\n📊 Testing with max depth: {max_depth}")
        
        model = DeepMockModel(max_depth)
        manager = WidgetManager()
        
        # Test basic operations at each depth level
        test_depth = min(3, max_depth)  # Test up to depth 3 to keep it simple
        
        # Create root widget
        root_index = model.index(0, 0)
        root_widget = MockWidget(f"Root_d{max_depth}")
        manager.insertWidget(root_index, root_widget)
        
        # Verify root widget
        retrieved = manager.getWidget(root_index)
        assert retrieved == root_widget, "Root widget not found"
        print(f"  ✓ Root widget created and retrieved")
        
        # Create child widget if model supports it
        if max_depth > 1:
            child_index = model.index(0, 0, root_index)
            if child_index.isValid():
                child_widget = MockWidget(f"Child_d{max_depth}")
                manager.insertWidget(child_index, child_widget)
                
                retrieved_child = manager.getWidget(child_index)
                assert retrieved_child == child_widget, "Child widget not found"
                print(f"  ✓ Child widget created and retrieved")
                
                # Test reverse lookup
                found_index = manager.getIndex(child_widget)
                assert found_index is not None, "Failed reverse lookup for child"
                assert found_index.isValid(), "Invalid index from reverse lookup"
                print(f"  ✓ Reverse lookup successful")
        
        # Create grandchild widget if model supports it
        if max_depth > 2:
            child_index = model.index(0, 0, root_index)
            if child_index.isValid():
                grandchild_index = model.index(0, 0, child_index)
                if grandchild_index.isValid():
                    grandchild_widget = MockWidget(f"Grandchild_d{max_depth}")
                    manager.insertWidget(grandchild_index, grandchild_widget)
                    
                    retrieved_grandchild = manager.getWidget(grandchild_index)
                    assert retrieved_grandchild == grandchild_widget, "Grandchild widget not found"
                    print(f"  ✓ Grandchild widget created and retrieved")
        
        # Test widget count
        all_widgets = manager.widgets()
        expected_count = 1 + (1 if max_depth > 1 else 0) + (1 if max_depth > 2 else 0)
        print(f"  📝 Expected widgets: {expected_count}, Found: {len(all_widgets)}")
        assert len(all_widgets) >= expected_count, f"Not enough widgets found"
        
        # Test clear
        manager.clearWidgets()
        assert len(manager.widgets()) == 0, "Widgets not cleared"
        print(f"  ✓ Max depth {max_depth} test passed")
    
    print(f"\n🎉 All arbitrary depth tests passed!")

def test_mixed_children_types():
    """Test widgets with and without children capability."""
    app = QApplication(sys.argv) if not QApplication.instance() else QApplication.instance()
    
    print("\n🧪 Testing mixed children types...")
    
    model = DeepMockModel(4)
    manager = WidgetManager()
    
    # Create a container widget (can have children)
    container_index = model.index(0, 0)
    container_widget = MockWidget("Container")
    manager.insertWidget(container_index, container_widget, allow_children=True)
    
    # Verify container widget
    retrieved_container = manager.getWidget(container_index)
    assert retrieved_container == container_widget, "Container widget not found"
    print("✓ Container widget created and retrieved")
    
    # Create a leaf widget (cannot have children) 
    leaf_index = model.index(1, 0)  # Different root to avoid conflicts
    leaf_widget = MockWidget("Leaf")
    manager.insertWidget(leaf_index, leaf_widget, allow_children=False)
    
    # Verify leaf widget
    retrieved_leaf = manager.getWidget(leaf_index)
    assert retrieved_leaf == leaf_widget, "Leaf widget not found"
    print("✓ Leaf widget created and retrieved")
    
    # Test widget count
    widgets = manager.widgets()
    assert len(widgets) == 2, f"Expected 2 widgets, found {len(widgets)}"
    print("✓ Both widget types retrieved successfully")
    
    print("✓ Mixed children types test passed")

if __name__ == "__main__":
    test_arbitrary_depth()
    test_mixed_children_types()
    print("\n🌟 All generalized WidgetManager tests passed!")
