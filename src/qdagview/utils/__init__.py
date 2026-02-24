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

from .graphutils import bfs, dfs, group_consecutive_numbers

from functools import wraps
def listify(gen):
    """Decorator to convert a generator function to a list-returning function."""
    # TODO: this is redundant with utils.listify
    @wraps(gen)
    def wrapper(*args, **kwargs):
        return list(gen(*args, **kwargs))
    return wrapper



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