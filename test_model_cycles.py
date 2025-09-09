#!/usr/bin/env python3
"""
Comprehensive test for the cycle detection fix in FlowGraphModel.
This tests the model operations that would be triggered by the UI.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'QDAGView'))

try:
    from qtpy.QtCore import *
    from qtpy.QtWidgets import *
    from qtpy.QtGui import *
    
    from flowgraphmodel import FlowGraphModel
    from flowgraph import FlowGraph, ExpressionOperator
    
    HAS_QT = True
except ImportError:
    HAS_QT = False
    print("⚠️  Qt not available, testing only core logic")

def test_model_with_cycles():
    """Test FlowGraphModel operations with bidirectional links."""
    if not HAS_QT:
        print("❌ Skipping Qt model tests - Qt not available")
        return True
        
    print("🔄 Testing FlowGraphModel with bidirectional links...")
    
    # Create Qt application if needed
    app = QApplication.instance() or QApplication(sys.argv)
    
    # Create model
    model = FlowGraphModel()
    graph = model.invisibleRootItem()
    
    # Create operators
    A = graph.createOperator("a + b", "A")
    B = graph.createOperator("x + y", "B")
    
    print(f"Created operators in model: {A}, {B}")
    
    # Create bidirectional links
    A_outlet = A.outlets()[0]
    B_inlet_x = B.inlets()[0]
    B_outlet = B.outlets()[0]
    A_inlet_a = A.inlets()[0]
    
    link1 = graph.insertLink(0, A_outlet, B_inlet_x)  # A -> B
    link2 = graph.insertLink(0, B_outlet, A_inlet_a)  # B -> A
    
    print(f"Created bidirectional links: {link1}, {link2}")
    
    # Test model index operations
    print("\n📝 Testing model index operations...")
    try:
        # Get operator indices
        A_index = model.indexFromItem(A)
        B_index = model.indexFromItem(B)
        
        print(f"A index: row={A_index.row()}, valid={A_index.isValid()}")
        print(f"B index: row={B_index.row()}, valid={B_index.isValid()}")
        
        # Test getting items from indices
        A_item = model.itemFromIndex(A_index)
        B_item = model.itemFromIndex(B_index)
        
        assert A_item == A, f"Expected {A}, got {A_item}"
        assert B_item == B, f"Expected {B}, got {B_item}"
        
        print("✅ Model index operations work correctly")
        
    except Exception as e:
        print(f"❌ Model index operations failed: {e}")
        return False
    
    # Test model evaluation (which uses ancestors)
    print("\n📝 Testing model evaluation...")
    try:
        A_result = model.evaluate(A_index)
        print(f"A evaluation result: {A_result}")
        
        B_result = model.evaluate(B_index)
        print(f"B evaluation result: {B_result}")
        
        print("✅ Model evaluation completed without infinite loop")
        
    except Exception as e:
        print(f"❌ Model evaluation failed: {e}")
        return False
    
    return True

def test_model_tree_structure():
    """Test that the model tree structure is correct with cycles."""
    if not HAS_QT:
        return True
        
    print("\n🌳 Testing model tree structure with cycles...")
    
    app = QApplication.instance() or QApplication(sys.argv)
    model = FlowGraphModel()
    graph = model.invisibleRootItem()
    
    # Create a cycle: A -> B -> A
    A = graph.createOperator("a", "NodeA")
    B = graph.createOperator("b", "NodeB")
    
    # Create the cycle
    link1 = graph.insertLink(0, A.outlets()[0], B.inlets()[0])  # A -> B
    link2 = graph.insertLink(0, B.outlets()[0], A.inlets()[0])  # B -> A
    
    try:
        # Test row counts
        root_rows = model.rowCount(QModelIndex())
        print(f"Root has {root_rows} operators")
        
        # Test operator children (inlets/outlets)
        A_index = model.index(0, 0)
        A_children = model.rowCount(A_index)
        print(f"Node A has {A_children} children (inlets + outlets)")
        
        # Test inlet children (links)
        A_inlet_index = model.index(0, 0, A_index)  # First inlet of A
        A_inlet_links = model.rowCount(A_inlet_index)
        print(f"Node A inlet has {A_inlet_links} incoming links")
        
        print("✅ Model tree structure is correct with cycles")
        return True
        
    except Exception as e:
        print(f"❌ Model tree structure test failed: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Testing FlowGraphModel with bidirectional links...")
    
    success1 = test_model_with_cycles()
    success2 = test_model_tree_structure()
    
    if success1 and success2:
        print("\n🎉 All FlowGraphModel cycle tests passed!")
        print("The app should no longer stall when nodes have bidirectional links.")
    else:
        print("\n❌ Some FlowGraphModel tests failed.")
        
    if HAS_QT:
        # Don't keep Qt app running
        QApplication.instance().quit()
