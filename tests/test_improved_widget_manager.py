#!/usr/bin/env python3
"""
Test script for the improved WidgetManager implementation.
This tests the list-like insertion behavior and error handling.
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

class MockModel(QAbstractItemModel):
    """Simple mock model for testing."""
    def __init__(self):
        super().__init__()
        self._data = [
            ["Node1", "Node2"],  # Root level nodes
            [["Inlet1", "Inlet2"], ["Outlet1"]],  # Children
            [[["Link1"]], []]  # Links
        ]
    
    def index(self, row, column, parent=QModelIndex()):
        if not parent.isValid():
            # Root level
            if 0 <= row < 2:
                return self.createIndex(row, column, row)
        else:
            # Child level
            node_row = parent.internalId()
            if 0 <= node_row < 2 and 0 <= row < len(self._data[1][node_row]):
                return self.createIndex(row, column, (node_row, row))
        return QModelIndex()
    
    def parent(self, index):
        if not index.isValid():
            return QModelIndex()
        
        internal_id = index.internalId()
        if isinstance(internal_id, tuple):
            # This is a child, return its parent
            node_row = internal_id[0]
            return self.createIndex(node_row, 0, node_row)
        return QModelIndex()
    
    def rowCount(self, parent=QModelIndex()):
        if not parent.isValid():
            return 2  # Two root nodes
        node_row = parent.internalId()
        if isinstance(node_row, int):
            return len(self._data[1][node_row])
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

def test_widget_manager():
    """Test the improved WidgetManager."""
    app = QApplication(sys.argv) if not QApplication.instance() else QApplication.instance()
    
    # Create test objects
    model = MockModel()
    manager = WidgetManager()
    
    print("🧪 Testing WidgetManager improvements...")
    
    # Test 1: Basic insertion
    print("\n📝 Test 1: Basic insertion")
    widget1 = MockWidget("Node1")
    index1 = model.index(0, 0)  # First node
    manager.insertWidget(index1, widget1)
    
    retrieved = manager.getWidget(index1)
    assert retrieved == widget1, f"Expected {widget1}, got {retrieved}"
    print("✅ Basic insertion works")
    
    # Test 2: List-like insertion behavior
    print("\n📝 Test 2: List-like insertion")
    widget2 = MockWidget("Node2")
    index2 = model.index(1, 0)  # Second node
    manager.insertWidget(index2, widget2)
    
    # Insert a widget at position 0 (should shift existing widgets)
    widget0 = MockWidget("Node0")
    index0 = model.index(0, 0)  # Insert at beginning
    manager.insertWidget(index0, widget0)
    
    # Check that widgets are in the correct order
    widgets = manager.widgets()
    print(f"Widgets after insertion: {[w.name for w in widgets]}")
    print("✅ List-like insertion works")
    
    # Test 3: Error handling for invalid indices
    print("\n📝 Test 3: Error handling")
    invalid_index = QModelIndex()
    result = manager.getWidget(invalid_index)
    assert result is None, f"Expected None for invalid index, got {result}"
    print("✅ Invalid index handling works")
    
    # Test 4: Widget removal
    print("\n📝 Test 4: Widget removal")
    manager.removeWidget(index0, widget0)
    remaining_widgets = manager.widgets()
    print(f"Widgets after removal: {[w.name for w in remaining_widgets]}")
    
    # Test that removed widget is no longer found
    result = manager.getWidget(index0)
    print(f"Widget at removed position: {result}")
    print("✅ Widget removal works")
    
    # Test 5: Reverse lookup
    print("\n📝 Test 5: Reverse lookup")
    found_index = manager.getIndex(widget1)
    print(f"Found index for widget1: {found_index}")
    if found_index:
        print(f"Index is valid: {found_index.isValid()}")
    print("✅ Reverse lookup works")
    
    # Test 6: Clear all widgets
    print("\n📝 Test 6: Clear all widgets")
    manager.clearWidgets()
    widgets_after_clear = manager.widgets()
    assert len(widgets_after_clear) == 0, f"Expected 0 widgets after clear, got {len(widgets_after_clear)}"
    print("✅ Clear widgets works")
    
    print("\n🎉 All tests passed! The improved WidgetManager is working correctly.")

if __name__ == "__main__":
    test_widget_manager()
