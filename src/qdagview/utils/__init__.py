# Utils package - utility functions and helpers
from typing import *
from itertools import groupby
from typing import Iterable, List, Callable

# Import geometry utilities
from .geo import (
    makeLineBetweenShapes, 
    makeLineToShape, 
    makeArrowShape, 
    getShapeCenter,
    makeVerticalRoundedPath,
    makeHorizontalRoundedPath)

from .qt import distribute_items

# Import unique utilities
from .unique import make_unique_name

def bfs(*root, children:Callable, reverse:bool=False) -> List:
    """Perform a breadth-first search (BFS) traversal
    starting from the given root nodes."""
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

def dfs(*root, children:Callable, reverse:bool=False) -> List:
    """Perform a depth-first search (DFS) traversal
    starting from the given root nodes."""
    stack:List = [*root]
    result = list()
    visited = set()  # Track visited nodes to prevent cycles
    
    while stack:
        index = stack.pop()  # Remove from end for proper DFS
        
        # Skip if already visited to prevent infinite loops in cyclic graphs
        if index in visited:
            continue
            
        visited.add(index)
        result.append(index)
        
        for child in children(index):
            # Only add child to stack if not already visited
            if child not in visited:
                stack.append(child)

    return reversed(result) if reverse else result

def _group_consecutive_numbers_clever(numbers:Iterable[int])->Iterable[range]:
    from itertools import groupby
    from operator import itemgetter

    ranges = []

    for k, g in groupby(enumerate(numbers),lambda x:x[0]-x[1]):
        group = ( map(itemgetter(1), g) )
        group = list( map(int, group) )
        ranges.append(range(group[0],group[-1]+1))
    return ranges

def _group_consecutive_numbers_readable(numbers:list[int])->Iterable[range]:
    if not len(numbers)>0:
        return []

    first = last = numbers[0]
    for n in numbers[1:]:
        if n - 1 == last: # Part of the group, bump the end
            last = n
        else: # Not part of the group, yield current group and start a new
            yield range(first, last+1)
            first = last = n
    yield range(first, last+1) # Yield the last group

from functools import wraps
def listify(gen):
    """Decorator to convert a generator function to a list-returning function."""
    # TODO: this is redundant with utils.listify
    @wraps(gen)
    def wrapper(*args, **kwargs):
        return list(gen(*args, **kwargs))
    return wrapper

group_consecutive_numbers = _group_consecutive_numbers_readable

__all__ = [
    # Utility decorators
    listify,
    
    # BFS and graph utilities
    'bfs',
    'group_consecutive_numbers',

    # Geometry utilities  
    'makeLineBetweenShapes',
    'makeLineToShape', 
    'makeArrowShape',
    'makeVerticalRoundedPath',
    'makeHorizontalRoundedPath',
    'getShapeCenter',

    # Naming utilities
    'make_unique_name',

    # Qt utilities
    'distribute_items',
]