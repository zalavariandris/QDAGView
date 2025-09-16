# Managers package - component managers for views
from .linking_manager import LinkingManager
from .widget_manager_using_tree_data_structure import TreeWidgetManager
from .widget_manager_using_persistent_index import PersistentWidgetManager

# Default widget manager (use tree-based version)
WidgetManager = TreeWidgetManager

__all__ = [
    'LinkingManager',
    'WidgetManager'  # Default (tree-based) 
]
