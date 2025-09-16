# QDAGView - Qt-based Directed Acyclic Graph Visualization Library
"""
A Qt-based library for visualizing and interacting with directed acyclic graphs.
Provides graph models, views, and interaction components for building graph-based applications.
"""

# Import main public API components
from .core import GraphDataRole, GraphItemType, GraphMimeType
from .views import GraphView, GraphDelegate
from .models import FlowGraphModel, FlowGraph, StandardGraphModel
from .controllers import QItemModelGraphController
# Import subpackages for advanced usage
from . import core
from . import models  
from . import views
from . import utils

__version__ = "0.1.0"

__all__ = [
    # Main components (most commonly used)
    'GraphView',
    'GraphDelegate',
    'FlowGraphModel',
    'QItemModelGraphController',
    'FlowGraph',
    'StandardGraphModel',
    'GraphDataRole',
    'GraphItemType',
    'GraphMimeType',
    # Subpackages for advanced usage
    'core',
    'models',
    'views', 
    'utils'
]
