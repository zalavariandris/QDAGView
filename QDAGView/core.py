from qtpy.QtCore import *
from enum import IntEnum, StrEnum


class GraphDataRole(IntEnum):
    TypeRole= Qt.ItemDataRole.UserRole+1
    SourceRole= Qt.ItemDataRole.UserRole+2


class GraphItemType(StrEnum):
    BASE = "BASE"
    SUBGRAPH = "SUBGRAPH"
    INLET = "INLET"
    OUTLET = "OUTLET"
    NODE = "NODE"
    LINK = "LINK"


class GraphMimeType(StrEnum):
    OutletData = 'application/outlet'
    InletData = 'application/inlet'
    LinkTailData = 'application/link/source'
    LinkHeadData = 'application/link/target'

from typing import List, Tuple, Iterable
def indexToPath(index: QModelIndex) -> Tuple[int, ...]:
    """
    Find the path of a QModelIndex in a tree structure.
    Args:
        index: The QModelIndex to find the path for
    Returns:
        A list of integers representing the path from root to the index.
    """
    if not index.isValid():
        return ()
    
    path_parts = []
    current = index
    
    # Walk up the tree to build the path
    while current.isValid():        
        # Add row
        path_parts.append(current.row())
        
        # Move to parent
        current = current.parent()
    
    # Reverse to show root -> leaf order
    path_parts.reverse()
    
    return tuple(path_parts)

def indexFromPath(model:QAbstractItemModel, path: Tuple[int, ...]) -> QModelIndex:
    """
    Convert a path representation back to a QModelIndex in the given model.
    Args:
        model: The model to search in
        path: A list of integers representing the path from root to the index.
    Returns:
        The QModelIndex corresponding to the path.
    """
    if not path:
        return QModelIndex()

    # Start from the root
    current = QModelIndex()

    for part in path:
        # Find the child corresponding to the current part
        current = model.index(part, 0, current)
        if not current.isValid():
            raise KeyError(f"Path {path} not found in model")

    return current