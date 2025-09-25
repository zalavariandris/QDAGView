# Managers package - component managers for views
from .widget_manager_protocol import WidgetManagerProtocol
from .linking_manager import LinkingManager
from .widget_manager_using_tree_data_structure import TreeWidgetManager
from .widget_manager_using_persistent_index import PersistentWidgetManager

from .widget_managet_using_bidict import BidictWidgetManager

__all__ = [
    'LinkingManager',
    'TreeWidgetManager',
    'PersistentWidgetManager',
    'WidgetManagerProtocol',
    'BidictWidgetManager'
]
