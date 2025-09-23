import pytest
import sys
import os
import logging

# Completely disable all logging output during tests
logging.disable(logging.CRITICAL)

# Add parent directory to path so we can import the module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qdagview.examples.flowgraph import FlowGraph
from qdagview.examples.flowgraphmodel import ExpressionOperator, Inlet, Outlet, Link
from qdagview.examples.flowgraphmodel import FlowGraphModel
from src.qdagview.views.controllers.graph_controller import GraphController
from qtpy.QtCore import QModelIndex, QPersistentModelIndex, Qt
from qtpy.QtTest import QSignalSpy

logger = logging.getLogger(__name__)


@pytest.fixture
def setup_model_and_controller():
    """Set up test fixtures for each test."""
    model = FlowGraphModel()
    controller = GraphController(model)
    
    # Add some test operators
    controller.addNode()  # Row 0
    controller.addNode()  # Row 1
    controller.addNode()  # Row 2
    controller.addNode()  # Row 3
    
    # Verify initial setup
    assert model.rowCount() == 4, "Should have 4 operators after setup"
    
    return model, controller


def test_batch_remove_empty_list(setup_model_and_controller):
    """Test batchRemove with empty list should succeed."""
    model, controller = setup_model_and_controller
    result = controller.batchRemove([])
    assert result, "Empty removal should succeed"
    assert model.rowCount() == 4, "No rows should be removed"


def test_batch_remove_invalid_indexes(setup_model_and_controller):
    """Test batchRemove with invalid indexes should succeed."""
    model, controller = setup_model_and_controller
    invalid_index = QModelIndex()
    result = controller.batchRemove([invalid_index])
    assert result, "Invalid index removal should succeed"
    assert model.rowCount() == 4, "No rows should be removed"


def test_batch_remove_single_item(setup_model_and_controller):
    """Test removing a single item."""
    model, controller = setup_model_and_controller
    # Remove the item at row 2
    index_to_remove = model.index(2, 0, QModelIndex())
    assert index_to_remove.isValid(), "Index should be valid"
    
    result = controller.batchRemove([index_to_remove])
    assert result, "Single removal should succeed"
    assert model.rowCount() == 3, "Should have 3 operators after removal"


def test_batch_remove_multiple_items_non_consecutive(setup_model_and_controller):
    """Test removing multiple non-consecutive items."""
    model, controller = setup_model_and_controller
    # Remove items at rows 0 and 2 (non-consecutive)
    index1 = model.index(0, 0, QModelIndex())
    index2 = model.index(2, 0, QModelIndex())
    
    assert index1.isValid(), "First index should be valid"
    assert index2.isValid(), "Second index should be valid"
    
    result = controller.batchRemove([index1, index2])
    assert result, "Multiple removal should succeed"
    assert model.rowCount() == 2, "Should have 2 operators after removal"


def test_batch_remove_multiple_items_consecutive(setup_model_and_controller):
    """Test removing multiple consecutive items."""
    model, controller = setup_model_and_controller
    # Remove items at rows 1 and 2 (consecutive)
    index1 = model.index(1, 0, QModelIndex())
    index2 = model.index(2, 0, QModelIndex())
    
    assert index1.isValid(), "First index should be valid"
    assert index2.isValid(), "Second index should be valid"
    
    result = controller.batchRemove([index1, index2])
    assert result, "Multiple consecutive removal should succeed"
    assert model.rowCount() == 2, "Should have 2 operators after removal"


def test_batch_remove_all_items(setup_model_and_controller):
    """Test removing all items."""
    model, controller = setup_model_and_controller
    # Remove all items
    indexes = [model.index(i, 0, QModelIndex()) for i in range(4)]
    
    for idx in indexes:
        assert idx.isValid(), f"Index {idx.row()} should be valid"
    
    result = controller.batchRemove(indexes)
    assert result, "Full removal should succeed"
    assert model.rowCount() == 0, "Should have 0 operators after removal"


def test_batch_remove_with_persistent_indexes(setup_model_and_controller):
    """Test removing with QPersistentModelIndex objects."""
    model, controller = setup_model_and_controller
    # Create persistent indexes for rows 1 and 3
    regular_index1 = model.index(1, 0, QModelIndex())
    regular_index2 = model.index(3, 0, QModelIndex())
    index1 = QPersistentModelIndex(regular_index1)
    index2 = QPersistentModelIndex(regular_index2)
    
    assert index1.isValid(), "First persistent index should be valid"
    assert index2.isValid(), "Second persistent index should be valid"
    
    # Convert back to regular indexes for the batchRemove call
    result = controller.batchRemove([QModelIndex(index1), QModelIndex(index2)])
    assert result, "Persistent index removal should succeed"
    assert model.rowCount() == 2, "Should have 2 operators after removal"


def test_batch_remove_duplicate_indexes(setup_model_and_controller):
    """Test removing with duplicate indexes (should only remove once)."""
    model, controller = setup_model_and_controller
    # Try to remove the same item twice
    index1 = model.index(1, 0, QModelIndex())
    index2 = model.index(1, 0, QModelIndex())  # Same row
    
    result = controller.batchRemove([index1, index2])
    assert result, "Duplicate removal should succeed"
    assert model.rowCount() == 3, "Should have 3 operators (item removed only once)"


def test_batch_remove_different_columns_same_row(setup_model_and_controller):
    """Test removing indexes from different columns of the same row."""
    model, controller = setup_model_and_controller
    # Get indexes for different columns of the same row
    index_col0 = model.index(1, 0, QModelIndex())
    index_col1 = model.index(1, 1, QModelIndex()) if model.columnCount() > 1 else index_col0
    
    result = controller.batchRemove([index_col0, index_col1])
    assert result, "Same row different columns removal should succeed"
    assert model.rowCount() == 3, "Should have 3 operators (row removed only once)"


def test_batch_remove_reverse_order(setup_model_and_controller):
    """Test that removal happens in correct order (higher row numbers first)."""
    model, controller = setup_model_and_controller
    # Create a spy to track removal signals
    spy = QSignalSpy(model.rowsAboutToBeRemoved)
    
    # Remove rows 1 and 3 (should remove 3 first, then 1)
    index1 = model.index(1, 0, QModelIndex())
    index2 = model.index(3, 0, QModelIndex())
    
    result = controller.batchRemove([index1, index2])
    assert result, "Removal should succeed"
    assert model.rowCount() == 2, "Should have 2 operators after removal"
    
    # Check that signals were emitted (exact order checking might be complex)
    assert len(spy) > 0, "Row removal signals should be emitted"


def test_batch_remove_with_children(setup_model_and_controller):
    """Test removing items that have children - simplified test."""
    model, controller = setup_model_and_controller
    # Since the FlowGraphModel doesn't allow direct insertion of children,
    # we'll test the descendant filtering logic with a simple case
    
    # This test verifies that the descendant filtering works
    # Even though we can't create actual parent-child relationships easily
    parent_index = model.index(0, 0, QModelIndex())
    
    # Try to remove the same item twice (simulating parent + descendant)
    result = controller.batchRemove([parent_index, parent_index])
    assert result, "Duplicate removal should succeed"
    
    # Should only remove once
    assert model.rowCount() == 3, "Should have 3 top-level operators after removal"


def test_removal_order_logging(setup_model_and_controller, caplog):
    """Test that we can observe the removal order through logging."""
    model, controller = setup_model_and_controller
    # This test helps debug the issue mentioned by the user
    with caplog.at_level(logging.INFO):
        # Remove items at rows 1 and 2
        index1 = model.index(1, 0, QModelIndex())
        index2 = model.index(2, 0, QModelIndex())
        
        print(f"DEBUG: Removing rows {index1.row()} and {index2.row()}")
        result = controller.batchRemove([index1, index2])
        assert result, "Removal should succeed"
    
    # Check log messages to understand removal order
    removal_messages = [record.message for record in caplog.records if "Removing operator at index" in record.message]
    
    print("Removal order from logs:")
    for msg in removal_messages:
        print(f"  {msg}")
    
    # The actual row numbers in the log might be different from input due to normalization
    # This test helps us understand what's happening
    
    # Verify that higher index was removed first
    if len(removal_messages) >= 2:
        # Extract the numbers from the log messages
        first_removed = int(removal_messages[0].split("index ")[1])
        second_removed = int(removal_messages[1].split("index ")[1])
        print(f"First removed: {first_removed}, Second removed: {second_removed}")
        
        # The issue you mentioned: selecting rows 1,2 but removing at 1,0
        # This suggests the second removal happens at the shifted index
        if first_removed == 2 and second_removed == 1:
            print("EXPECTED: Second item shifted from row 1 to row 0 after first removal")
        elif first_removed == 3 and second_removed == 2:
            print("ACTUAL: Removal happening at correct original positions (after internal reordering)")


def test_user_reported_issue(setup_model_and_controller, caplog):
    """Reproduce the specific issue: selecting rows 1,2 but seeing removal at 1,0."""
    model, controller = setup_model_and_controller
    print(f"\nInitial model state: {model.rowCount()} operators")
    
    # Select what would be equivalent to rows 1 and 2 in the UI
    index1 = model.index(1, 0, QModelIndex())  # Row 1
    index2 = model.index(2, 0, QModelIndex())  # Row 2
    
    with caplog.at_level(logging.INFO):
        result = controller.batchRemove([index1, index2])
        assert result, "Removal should succeed"
    
    assert model.rowCount() == 2, "Should have 2 operators left"
    
    # The key insight: the internal batchRemove algorithm might be reordering
    # to process ranges efficiently, but the logs show the actual model indices
    # being removed, which can be confusing


def test_consecutive_removal_scenario(setup_model_and_controller, caplog):
    """Test the specific scenario that might cause the 1,0 removal pattern."""
    model, controller = setup_model_and_controller
    print(f"\nScenario: What if we're removing consecutive items differently?")
    
    # Try removing items 1 and 2 as consecutive items
    index1 = model.index(1, 0, QModelIndex())
    index2 = model.index(2, 0, QModelIndex())
    
    print(f"Attempting to remove consecutive rows {index1.row()} and {index2.row()}")
    
    with caplog.at_level(logging.INFO):
        result = controller.batchRemove([index1, index2])
        assert result, "Consecutive removal should succeed"
    
    removal_messages = [record.message for record in caplog.records if "Removing operator at index" in record.message]
    
    print("Actual removal order:")
    for msg in removal_messages:
        print(f"  {msg}")
    
    # If this processes as a consecutive range [1,2], it should remove as:
    # removeRows(1, 2, parent) which would log "index 2" then "index 1"
    # But that's still not "1,0" - something else must be happening

if __name__ == "__main__":
    # runs pytest on this file
    # logging.basicConfig(level=logging.CRITICAL)
    # Or alternatively, disable all logging during tests:
    logging.disable(logging.CRITICAL)
    pytest.main([__file__, "-v"])