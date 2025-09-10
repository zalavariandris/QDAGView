from enum import Enum
from typing import *
from qtpy.QtGui import *
from qtpy.QtCore import *
from qtpy.QtWidgets import *

import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


from ...core import indexToPath, indexFromPath


class TreeWidgetManager:
    """Handles widgets mapping to model indexes."""
    def __init__(self):
        # Root container for the tree structure - can have arbitrary depth
        self._root: List[Tuple[QGraphicsItem, QAbstractItemModel, List]] = []
        # Reverse lookup cache for performance
        self._widget_to_path: Dict[QGraphicsItem, Tuple[int, ...]] = {}

    def insertWidget(self, index: QModelIndex | QPersistentModelIndex, widget: QGraphicsItem, allow_children: bool = True):
        """Insert a widget into the manager at the position specified by the index."""
        if not index.isValid():
            logger.warning(f"Cannot insert widget for invalid index: {index}")
            return
            
        try:
            path = indexToPath(index)
        except Exception as e:
            logger.error(f"Failed to get path for index {index}: {e}")
            return
            
        if not path:
            logger.warning(f"Empty path for index: {index}")
            return
        
        # Navigate to the parent container and insert at the correct position
        try:
            self._insertAtPath(path, widget, index.model(), allow_children)
            # Update reverse lookup cache
            self._rebuildReverseCache()
        except Exception as e:
            logger.error(f"Failed to insert widget at path {path}: {e}")
    
    def _insertAtPath(self, path: Tuple[int, ...], widget: QGraphicsItem, model: QAbstractItemModel, allow_children: bool = True):
        """Insert widget at the specified path, creating parent containers as needed."""
        # Navigate to the parent container
        current_container = self._root
        
        # Navigate through all but the last path component
        for i, path_component in enumerate(path[:-1]):
            if path_component >= len(current_container):
                raise IndexError(f"Path component {path_component} at depth {i} out of range, container has {len(current_container)} items")
            
            # Get the children container of the current item
            _, _, children = current_container[path_component]
            if children is None:
                raise ValueError(f"Cannot navigate deeper - item at path {path[:i+1]} has no children")
            
            current_container = children
        
        # Insert at the final position
        final_position = path[-1]
        if final_position > len(current_container):
            raise IndexError(f"Cannot insert at position {final_position}, container has {len(current_container)} items")
        
        # Create new item - with or without children depending on the flag
        children_container = [] if allow_children else None
        new_item = (widget, model, children_container)
        current_container.insert(final_position, new_item)
    
    def _rebuildReverseCache(self):
        """Rebuild the reverse lookup cache after structural changes."""
        self._widget_to_path.clear()
        for path, _, widget in self._items():
            self._widget_to_path[widget] = path

    def _items(self) -> Iterator[Tuple[Tuple[int, ...], QAbstractItemModel, QGraphicsItem]]:
        """Iterate over all widgets in the manager recursively."""
        def _recursive_items(container: List, current_path: Tuple[int, ...]):
            """Recursively iterate through the tree structure."""
            for index, (widget, model, children) in enumerate(container):
                path = current_path + (index,)
                yield path, model, widget
                
                # Recursively iterate through children if they exist
                if children is not None and len(children) > 0:
                    yield from _recursive_items(children, path)
        
        yield from _recursive_items(self._root, ())

    def getWidget(self, index: QModelIndex) -> QGraphicsItem | None:
        """Get widget for the given model index."""
        if not index.isValid():
            logger.debug(f"Index is invalid: {index}")
            return None
        
        try:
            path = indexToPath(index)
        except Exception as e:
            logger.error(f"Failed to get path for index {index}: {e}")
            return None
            
        if not path:
            logger.debug(f"Empty path for index: {index}")
            return None
            
        try:
            return self._getWidgetAtPath(path)
        except (IndexError, ValueError) as e:
            logger.debug(f"Widget not found at path {path}: {e}")
            return None
    
    def _getWidgetAtPath(self, path: Tuple[int, ...]) -> QGraphicsItem:
        """Get widget at the specified path using recursive navigation."""
        current_container = self._root
        
        # Navigate through all but the last path component
        for i, path_component in enumerate(path[:-1]):
            if path_component >= len(current_container):
                raise IndexError(f"Path component {path_component} at depth {i} out of range")
            
            # Get the children container of the current item
            _, _, children = current_container[path_component]
            if children is None:
                raise ValueError(f"Cannot navigate deeper - item at path {path[:i+1]} has no children")
            
            current_container = children
        
        # Get the final widget
        final_index = path[-1]
        if final_index >= len(current_container):
            raise IndexError(f"Final index {final_index} out of range")
        
        widget, _, _ = current_container[final_index]
        return widget

    def removeWidget(self, index: QModelIndex | QPersistentModelIndex, widget: QGraphicsItem):
        """Remove a widget from the manager, shifting subsequent elements."""
        if not index.isValid():
            logger.warning(f"Cannot remove widget for invalid index: {index}")
            return
            
        try:
            path = indexToPath(index)
        except Exception as e:
            logger.error(f"Failed to get path for index {index}: {e}")
            return
            
        if not path:
            logger.warning(f"Empty path for index: {index}")
            return
            
        try:
            self._removeAtPath(path)
            # Rebuild reverse cache after removal since indices may have shifted
            self._rebuildReverseCache()
        except Exception as e:
            logger.error(f"Failed to remove widget at path {path}: {e}")
    
    def _removeAtPath(self, path: Tuple[int, ...]):
        """Remove widget at the specified path, shifting subsequent elements."""
        current_container = self._root
        
        # Navigate through all but the last path component
        for i, path_component in enumerate(path[:-1]):
            if path_component >= len(current_container):
                raise IndexError(f"Path component {path_component} at depth {i} out of range")
            
            # Get the children container of the current item
            _, _, children = current_container[path_component]
            if children is None:
                raise ValueError(f"Cannot navigate deeper - item at path {path[:i+1]} has no children")
            
            current_container = children
        
        # Remove the final item
        final_index = path[-1]
        if final_index >= len(current_container):
            raise IndexError(f"Final index {final_index} out of range")
        
        del current_container[final_index]
    
    def getIndex(self, widget: QGraphicsItem) -> QModelIndex | None:
        """
        Get the index of the widget in the model.
        """
        # Use cached reverse lookup first
        if widget in self._widget_to_path:
            path = self._widget_to_path[widget]
            # Find the model by traversing to the widget location
            try:
                model = self._getModelAtPath(path)
                return indexFromPath(model, path)
            except (IndexError, KeyError) as e:
                logger.warning(f"Failed to get model for cached path {path}: {e}")
                # Fall back to full search
        
        # Fallback: search through all widgets (rebuild cache if needed)
        try:
            for path, model, stored_widget in self._items():
                if stored_widget == widget:
                    # Update the cache while we're at it
                    self._widget_to_path[widget] = path
                    return indexFromPath(model, path)
        except Exception as e:
            logger.error(f"Failed to find widget in manager: {e}")
        
        logger.debug(f"Widget not found in manager: {widget}")
        return None
    
    def _getModelAtPath(self, path: Tuple[int, ...]) -> QAbstractItemModel:
        """Get the model at the specified path."""
        current_container = self._root
        
        # Navigate through all but the last path component
        for i, path_component in enumerate(path[:-1]):
            if path_component >= len(current_container):
                raise IndexError(f"Path component {path_component} at depth {i} out of range")
            
            # Get the children container of the current item
            _, _, children = current_container[path_component]
            if children is None:
                raise ValueError(f"Cannot navigate deeper - item at path {path[:i+1]} has no children")
            
            current_container = children
        
        # Get the model from the final item
        final_index = path[-1]
        if final_index >= len(current_container):
            raise IndexError(f"Final index {final_index} out of range")
        
        _, model, _ = current_container[final_index]
        return model

    def widgets(self) -> List[QGraphicsItem]:
        all_widgets = []
        for _, _, widget in self._items():
            all_widgets.append(widget)
        return all_widgets

    def clear(self):
        """Clear all widgets from the manager."""
        self._root.clear()
        self._widget_to_path.clear()
