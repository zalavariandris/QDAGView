# Fix for Bidirectional Link Cycles

## Problem
When two nodes in the QDAGView app are linked bidirectionally (A → B and B → A), the application stalls due to infinite loops in graph traversal algorithms.

## Root Cause
The `bfs` function in `utils/__init__.py` did not implement cycle detection, causing infinite loops when traversing graphs with cycles. This affected:

1. **FlowGraph.ancestors()** - Used to find all dependencies of a node
2. **FlowGraph.descendants()** - Used to find all dependents of a node  
3. **FlowGraphModel.evaluate()** - Used when evaluating expressions
4. **UI operations** - When displaying ancestor highlighting or evaluating nodes

## Solution

### 1. Fixed BFS with Cycle Detection
Updated `utils/__init__.py` to track visited nodes:

```python
def bfs(*root, children:Callable, reverse:bool=False) -> List:
    queue:List = [*root]
    result = list()
    visited = set()  # Track visited nodes to prevent cycles
    
    while queue:
        index = queue.pop(0)  # Remove from front for proper BFS
        
        # Skip if already visited to prevent infinite loops in cyclic graphs
        if index in visited:
            continue
            
        visited.add(index)
        result.append(index)
        
        for child in children(index):
            # Only add child to queue if not already visited
            if child not in visited:
                queue.append(child)

    return reversed(result) if reverse else result
```

### 2. Fixed descendants() Method
The `descendants()` method in `flowgraph.py` had a logic error - it was looking at `link.source.operator` instead of `link.target.operator`:

```python
def descendants(self, node: ExpressionOperator) -> Iterable[ExpressionOperator]:
    """Get all descendants of the given operator."""
    assert node in self._operators
    def outputNodes(node: ExpressionOperator) -> Iterable[ExpressionOperator]:
        """Get all output nodes of the given operator."""
        for outlet in node.outlets():
            for link in self._out_links[outlet]:
                if link.target and link.target.operator is not None:
                    yield link.target.operator
    
    for n in bfs(node, children=outputNodes):
        yield n
```

## Testing
Created comprehensive tests to verify the fix works:

1. **test_bidirectional_links.py** - Tests core graph traversal with cycles
2. **test_model_cycles.py** - Tests FlowGraphModel operations with cycles

Both tests pass, confirming that:
- ✅ Ancestors traversal completes without infinite loops
- ✅ Descendants traversal completes without infinite loops  
- ✅ Expression evaluation works with cyclic dependencies
- ✅ Larger cycles (A → B → C → A) are handled correctly

## Impact
- **Before**: App would freeze/stall when creating bidirectional links
- **After**: App handles bidirectional links gracefully, showing proper dependency relationships without infinite loops

The fix maintains correct graph semantics while preventing the application from becoming unresponsive due to cycles in the node graph.
