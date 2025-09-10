#!/usr/bin/env python3
"""
Test script to verify the fix for bidirectional link cycles.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'QDAGView'))

from flowgraph import FlowGraph, ExpressionOperator

def test_bidirectional_links():
    """Test that bidirectional links don't cause infinite loops."""
    print("🔄 Testing bidirectional links...")
    
    # Create a flow graph
    graph = FlowGraph("TestGraph")
    
    # Create two operators
    A = graph.createOperator("a + b", "A")
    B = graph.createOperator("x + y", "B")
    
    print(f"Created operators: {A}, {B}")
    
    # Get their inlets and outlets
    A_outlet = A.outlets()[0]  # "result"
    A_inlet_a = A.inlets()[0]  # "a" 
    A_inlet_b = A.inlets()[1]  # "b"
    
    B_outlet = B.outlets()[0]  # "result"
    B_inlet_x = B.inlets()[0]  # "x"
    B_inlet_y = B.inlets()[1]  # "y"
    
    print(f"A inlets: {[str(i) for i in A.inlets()]}")
    print(f"A outlets: {[str(o) for o in A.outlets()]}")
    print(f"B inlets: {[str(i) for i in B.inlets()]}")
    print(f"B outlets: {[str(o) for o in B.outlets()]}")
    
    # Create bidirectional links: A -> B and B -> A
    print("\n📝 Creating bidirectional links...")
    link1 = graph.insertLink(0, A_outlet, B_inlet_x)  # A.result -> B.x
    link2 = graph.insertLink(0, B_outlet, A_inlet_a)  # B.result -> A.a
    
    print(f"Link 1: {link1}")
    print(f"Link 2: {link2}")
    
    # Test ancestors - this would previously cause infinite loop
    print("\n🔍 Testing ancestors traversal...")
    try:
        A_ancestors = list(graph.ancestors(A))
        print(f"A ancestors: {[str(op) for op in A_ancestors]}")
        
        B_ancestors = list(graph.ancestors(B))
        print(f"B ancestors: {[str(op) for op in B_ancestors]}")
        
        print("✅ Ancestors traversal completed without infinite loop!")
        
    except Exception as e:
        print(f"❌ Error in ancestors traversal: {e}")
        return False
    
    # Test descendants - this would also previously cause infinite loop
    print("\n🔍 Testing descendants traversal...")
    try:
        A_descendants = list(graph.descendants(A))
        print(f"A descendants: {[str(op) for op in A_descendants]}")
        
        B_descendants = list(graph.descendants(B))
        print(f"B descendants: {[str(op) for op in B_descendants]}")
        
        print("✅ Descendants traversal completed without infinite loop!")
        
    except Exception as e:
        print(f"❌ Error in descendants traversal: {e}")
        return False
    
    # Test evaluation - this would also previously cause infinite loop
    print("\n🔍 Testing evaluation...")
    try:
        A_eval = graph.evaluate(A)
        print(f"A evaluation result:\n{A_eval}")
        
        B_eval = graph.evaluate(B)
        print(f"B evaluation result:\n{B_eval}")
        
        print("✅ Evaluation completed without infinite loop!")
        
    except Exception as e:
        print(f"❌ Error in evaluation: {e}")
        return False
        
    return True

def test_larger_cycle():
    """Test a larger cycle A -> B -> C -> A."""
    print("\n🔄 Testing larger cycle (A -> B -> C -> A)...")
    
    graph = FlowGraph("CycleGraph")
    
    # Create three operators
    A = graph.createOperator("a", "A")
    B = graph.createOperator("b", "B") 
    C = graph.createOperator("c", "C")
    
    # Create cycle: A -> B -> C -> A
    link1 = graph.insertLink(0, A.outlets()[0], B.inlets()[0])  # A -> B
    link2 = graph.insertLink(0, B.outlets()[0], C.inlets()[0])  # B -> C
    link3 = graph.insertLink(0, C.outlets()[0], A.inlets()[0])  # C -> A
    
    print(f"Created cycle: {link1}, {link2}, {link3}")
    
    # Test traversal
    try:
        A_ancestors = list(graph.ancestors(A))
        print(f"A ancestors in cycle: {[str(op) for op in A_ancestors]}")
        
        print("✅ Larger cycle traversal completed without infinite loop!")
        return True
        
    except Exception as e:
        print(f"❌ Error in larger cycle traversal: {e}")
        return False

if __name__ == "__main__":
    success1 = test_bidirectional_links()
    success2 = test_larger_cycle()
    
    if success1 and success2:
        print("\n🎉 All bidirectional link tests passed! The app should no longer stall with cycles.")
    else:
        print("\n❌ Some tests failed. There may still be cycle issues.")
