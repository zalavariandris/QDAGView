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

from typing import List
def indexToPath(index: QModelIndex) -> List[str]:
    """
    Print the path of a QModelIndex in a tree structure.
    
    Args:
        index: The QModelIndex to print the path for
        
    Returns:
        A string representation of the index path in the tree
    """
    if not index.isValid():
        return "Invalid Index"
    
    path_parts = []
    current = index
    
    # Walk up the tree to build the path
    while current.isValid():
        # Get the display text for this index
        display_text = current.data(Qt.ItemDataRole.DisplayRole)
        
        # Add row info and display text
        path_part = f"[{current.row()}:{current.column()}] {display_text}"
        path_parts.append(path_part)
        
        # Move to parent
        current = current.parent()
    
    # Reverse to show root -> leaf order
    path_parts.reverse()
    
    return path_parts