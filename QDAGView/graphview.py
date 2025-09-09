#####################
# The Network Scene #
#####################
from __future__ import annotations
import pdb
#
# A Graph view that directly connects to QStandardItemModel
#

import traceback

from enum import Enum
from typing import *
from qtpy.QtGui import *
from qtpy.QtCore import *
from qtpy.QtWidgets import *

from collections import defaultdict
from bidict import bidict

from utils import group_consecutive_numbers

from graphview_widgets import (
    BaseRowWidget, CellWidget, NodeWidget, InletWidget, OutletWidget, LinkWidget, PortWidget
)
from utils.geo import makeLineBetweenShapes, makeLineToShape, makeArrowShape, getShapeCenter

import logging


# from pylive.utils.geo import makeLineBetweenShapes, makeLineToShape
# from pylive.utils.qt import distribute_items_horizontal
# from pylive.utils.unique import make_unique_name
# from pylive.utils.diff import diff_set

import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

from core import GraphDataRole, GraphItemType, GraphMimeType, indexToPath, indexFromPath
from utils import bfs
from graphviewdelegate import GraphDelegate
from dataclasses import dataclass


import networkx as nx


@dataclass
class Payload:
    index: QModelIndex | None
    kind: Literal['head', 'tail', 'inlet', 'outlet']

    @staticmethod
    def fromMimeData(model, mime:QMimeData) -> Payload | None:
        """
        Parse the payload from the mime data.
        This is used to determine the source and target of the link being dragged.
        """
        drag_source_type:Literal['inlet', 'outlet', 'head', 'tail']
        if mime.hasFormat(GraphMimeType.LinkTailData):
            drag_source_type = "tail"
        elif mime.hasFormat(GraphMimeType.LinkHeadData):
            drag_source_type = "head"
        elif mime.hasFormat(GraphMimeType.OutletData):
            drag_source_type = "outlet"
        elif mime.hasFormat(GraphMimeType.InletData):
            drag_source_type = "inlet"


        if mime.hasFormat(GraphMimeType.InletData):
            index_path = mime.data(GraphMimeType.InletData).data().decode("utf-8")

        elif mime.hasFormat(GraphMimeType.OutletData):
            index_path = mime.data(GraphMimeType.OutletData).data().decode("utf-8")

        elif mime.hasFormat(GraphMimeType.LinkTailData):
            index_path = mime.data(GraphMimeType.LinkTailData).data().decode("utf-8")

        elif mime.hasFormat(GraphMimeType.LinkHeadData):
            index_path = mime.data(GraphMimeType.LinkHeadData).data().decode("utf-8")
        else:
            # No valid mime type found
            return None

        index = indexFromPath(model, list(map(int, index_path.split("/"))))

        return Payload(index=index, kind=drag_source_type)
    
    def toMimeData(self) -> QMimeData:
        """
        Convert the payload to mime data.
        This is used to initiate a drag-and-drop operation for linking.
        """
        mime = QMimeData()

        # mime type
        mime_type = self.kind
            
        if mime_type is None:
            return None
        
        index_path = "/".join(map(str, indexToPath(self.index)))
        logger.debug(f"Creating mime data for index: {self.index}, path: {index_path}, type: {self.kind}")
        mime.setData(self.kind, index_path.encode("utf-8"))
        return mime


class WidgetManager_using_persistent_index:
    """Handles widgets mapping to model indexes."""
    def __init__(self):
        self._widgets: bidict[QPersistentModelIndex, BaseRowWidget] = bidict()
    
    def insertWidget(self, index:QModelIndex|QPersistentModelIndex, widget:QGraphicsItem):
        """Insert a widget into the manager."""
        self._widgets[QPersistentModelIndex(index)] = widget

    def removeWidget(self, index:QModelIndex|QPersistentModelIndex, widget:QGraphicsItem):
        """Remove a widget from the manager."""
        del self._widgets[QPersistentModelIndex(index)]

    def getWidget(self, index: QModelIndex) -> QGraphicsItem:
        if not index.isValid():
            logger.warning(f"Index is invalid: {index}")
            return None
        
        # convert to persistent index
        persistent_idx = QPersistentModelIndex(index)
        return self._widgets.get(persistent_idx, None)   
    
    def getIndex(self, widget:QGraphicsItem) -> QModelIndex:
        """
        Get the index of the node widget in the model.
        This is used to identify the node in the model.
        """
        idx = self._widgets.inverse[widget]
        return QModelIndex(idx)

    def widgets(self) -> List[QGraphicsItem]:
        return list(self._widgets.values())
    
    def clearWidgets(self):
        self._widgets.clear()


class WidgetManager_using_tree_data_structure:
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

    def clearWidgets(self):
        """Clear all widgets from the manager."""
        self._root.clear()
        self._widget_to_path.clear()

WidgetManager = WidgetManager_using_tree_data_structure

class CellManager:
    def __init__(self):
        self._cells: dict[QPersistentModelIndex, QWidget] = {}

    def insertCell(self, index:QModelIndex|QPersistentModelIndex, editor:QWidget):
        self._cells[QPersistentModelIndex(index)] = editor

    def removeCell(self, index:QModelIndex|QPersistentModelIndex):
        del self._cells[QPersistentModelIndex(index)]

    def getCell(self, index:QModelIndex|QPersistentModelIndex) -> QWidget|None:
        if not index.isValid():
            return None
        persistent_idx = QPersistentModelIndex(index)
        return self._cells.get(persistent_idx, None)
    
    def getIndex(self, editor:QWidget) -> QModelIndex|None:
        for idx, ed in self._cells.items():
            if ed == editor:
                return QModelIndex(idx)
        return None

    def clearCells(self):
        self._cells.clear()

    def cells(self) -> List[QWidget]:
        return list(self._cells.values())


class GraphView(QGraphicsView):
    class State(Enum):
        IDLE = "IDLE"
        LINKING = "LINKING"

    def __init__(self, delegate:GraphDelegate|None=None, parent: QWidget | None = None):
        super().__init__(parent=parent)
        self._model:QAbstractItemModel | None = None
        self._model_connections: list[tuple[Signal, Slot]] = []
        self._selection:QItemSelectionModel | None = None
        self._selection_connections: list[tuple[Signal, Slot]] = []

        assert isinstance(delegate, GraphDelegate) or delegate is None, "Invalid delegate"
        self._delegate = delegate if delegate else GraphDelegate()
        self._delegate.portPositionChanged.connect(self.onPortScenePositionChanged)

        ## State of the graph view
        self._state = GraphView.State.IDLE
        self._draft_link: QGraphicsLineItem | None = None
        self._linking_payload: QModelIndex = QModelIndex()  # This will hold the index of the item being dragged or linked
        self._link_end: Literal['head', 'tail'] | None = None  # This will hold the end of the link being dragged

        # Widget Manager
        self._widget_manager = WidgetManager()
        self._cell_manager = CellManager()

        # Link management
        self._link_source: defaultdict[LinkWidget, list[OutletWidget]] = defaultdict(list)
        self._link_target: defaultdict[LinkWidget, list[InletWidget]] = defaultdict(list)
        self._inlet_links: defaultdict[InletWidget, list[LinkWidget]] = defaultdict(list)
        self._outlet_links: defaultdict[OutletWidget, list[LinkWidget]] = defaultdict(list)

        # setup the view
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setAcceptDrops(True)

        self.setCacheMode(QGraphicsView.CacheModeFlag.CacheNone)
        self.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        # create a scene
        scene = QGraphicsScene()
        scene.setSceneRect(QRectF(-9999, -9999, 9999 * 2, 9999 * 2))
        self.setScene(scene)
        
    def setModel(self, model:QAbstractItemModel):
        if self._model_connections:
            for signal, slot in self._model_connections:
                signal.disconnect(slot)
        
        if model:
            assert isinstance(model, QAbstractItemModel), "Model must be a subclass of QAbstractItemModel"

            self._model_connections = [
                (model.rowsInserted, self.onRowsInserted),
                (model.rowsAboutToBeRemoved, self.onRowsAboutToBeRemoved),
                (model.rowsRemoved, self.onRowsRemoved),
                (model.dataChanged, self.onDataChanged)
            ]

            for signal, slot in self._model_connections:
                signal.connect(slot)
        self._model = model
        
        # populate initial scene
        ## clear
        scene = self.scene()
        assert scene
        scene.clear()
        self._widget_manager.clearWidgets()
        self._cell_manager.clearCells()

        if self._model.rowCount(QModelIndex()) > 0:
            self.onRowsInserted(QModelIndex(), 0, self._model.rowCount(QModelIndex()) - 1)

    def model(self) -> QAbstractItemModel | None:
        return self._model
    
    ## Index lookup
    def rowAt(self, point:QPoint) -> QModelIndex:
        """
        Find the index at the given position.
        point is in untransformed viewport coordinates, just like QMouseEvent::pos().
        """

        all_widgets = set(self._widget_manager.widgets())
        for item in self.items(point):
            if item in all_widgets:
                # If the item is a widget, return its index
                return self._widget_manager.getIndex(item)
        return QModelIndex()
    
    def indexAt(self, point:QPoint) -> QModelIndex:
        """
        Find the index at the given position.
        point is in untransformed viewport coordinates, just like QMouseEvent::pos().
        """
        all_cells = set(self._cell_manager.cells())
        for item in self.items(point):
            if item in all_cells:
                # If the item is a cell, return its index
                return self._cell_manager.getIndex(item)
            
        # fallback to rowAt if no cell is found
        return self.rowAt(point)

    ## Linking
    def _unlinkWidget(self, link_widget:LinkWidget):
        source_widget = self._link_source[link_widget]
        target_widget = self._link_target[link_widget]

        # unlink widget
        if source_widget:
            del self._link_source[link_widget]
            self._outlet_links[source_widget].remove(link_widget)

        if target_widget:
            del self._link_target[link_widget]
            self._inlet_links[target_widget].remove(link_widget)

        self._update_link_position(link_widget, source_widget, target_widget)

    def _linkWidget(self, link_widget:LinkWidget, source_widget:OutletWidget|None, target_widget:InletWidget):
        assert link_widget is not None, "link_widget must not be None"
        # assert source_widget is not None, "source_widget must not be None"
        assert target_widget is not None, "target_widget must not be None"

        if source_widget:
            self._link_source[link_widget] = source_widget
            self._outlet_links[source_widget].append(link_widget)

        if target_widget:
            self._link_target[link_widget] = target_widget
            self._inlet_links[target_widget].append(link_widget)

        self._update_link_position(link_widget, source_widget, target_widget)

    def _update_link_position(self, link_widget:LinkWidget, source_widget:QGraphicsItem|None=None, target_widget:QGraphicsItem|None=None):
        # Compute the link geometry in the link widget's local coordinates.
        if source_widget and target_widget:
            line = makeLineBetweenShapes(source_widget, target_widget)
            line = QLineF(link_widget.mapFromScene(line.p1()), link_widget.mapFromScene(line.p2()))
            link_widget.setLine(line)

        elif source_widget:
            source_center = getShapeCenter(source_widget)
            source_size = source_widget.boundingRect().size()
            origin = QPointF(source_center.x() - source_size.width()/2, source_center.y() - source_size.height()/2)+QPointF(24,24)
            line = makeLineToShape(origin, source_widget)
            line = QLineF(link_widget.mapFromScene(line.p1()), link_widget.mapFromScene(line.p2()))
            line = QLineF(line.p2(), line.p1())  # Reverse the line direction
            link_widget.setLine(line)

        elif target_widget:
            target_center = getShapeCenter(target_widget)
            target_size = target_widget.boundingRect().size()
            origin = QPointF(target_center.x() - target_size.width()/2, target_center.y() - target_size.height()/2)-QPointF(24,24)
            line = makeLineToShape(origin, target_widget)
            line = QLineF(link_widget.mapFromScene(line.p1()), link_widget.mapFromScene(line.p2()))
            link_widget.setLine(line)
        else:
            ...

        link_widget.update()

    def onPortScenePositionChanged(self, index:QPersistentModelIndex):
        """Reposition all links connected to the moved port widget."""
        widget = self._widget_manager.getWidget(index)

        if isinstance(widget, OutletWidget):
            link_widgets = list(self._outlet_links.get(widget, []))
        elif isinstance(widget, InletWidget):
            link_widgets = list(self._inlet_links.get(widget, []))
        else:
            return

        for link_widget in link_widgets:
            source_widget = self._link_source.get(link_widget, None)
            target_widget = self._link_target.get(link_widget, None)
            self._update_link_position(link_widget, source_widget, target_widget)

    @Slot(QModelIndex, int, int)
    def onRowsInserted(self, parent:QModelIndex, start:int, end:int):
        assert self._model, "Model must be set before handling rows inserted!"

        # get index trees in BFS order
        def get_children(index:QModelIndex) -> Iterable[QModelIndex]:
            if not isinstance(index, QModelIndex):
                raise TypeError(f"Expected QModelIndex, got {type(index)}")
            model = index.model()
            for row in range(model.rowCount(index)):
                child_index = model.index(row, 0, index)
                yield child_index
            return []
        
        sorted_indexes:List[QModelIndex] = list(bfs(
            *[self._model.index(row, 0, parent) for row in range(start, end + 1)], 
            children=get_children, 
            reverse=False
        ))

        ## Add widgets for each index
        for row_index in sorted_indexes:
            # Widget Factory
            parent_widget = self._widget_manager.getWidget(row_index.parent()) if row_index.parent().isValid() else self.scene()
            match self._delegate.itemType(row_index):
                case GraphItemType.SUBGRAPH:
                    raise NotImplementedError("Subgraphs are not yet supported in the graph view")
                case GraphItemType.NODE:
                    row_widget = self._delegate.createNodeWidget(parent_widget, row_index)
                case GraphItemType.INLET:
                    assert isinstance(parent_widget, NodeWidget)
                    row_widget = self._delegate.createInletWidget(parent_widget, row_index)
                case GraphItemType.OUTLET:
                    assert isinstance(parent_widget, NodeWidget)
                    row_widget = self._delegate.createOutletWidget(parent_widget, row_index)
                case GraphItemType.LINK:
                    assert isinstance(parent_widget, InletWidget)
                    row_widget = self._delegate.createLinkWidget(parent_widget, row_index)
                    # link management
                    source_index = self._delegate.linkSource(row_index)
                    source_widget = self._widget_manager.getWidget(source_index) if source_index is not None else None
                    target_index = self._delegate.linkTarget(row_index)
                    target_widget = self._widget_manager.getWidget(target_index) if target_index is not None else None
                    self._linkWidget(row_widget, source_widget, target_widget)
                case _:
                    raise ValueError(f"Unknown item type: {self._delegate.itemType(row_widget)}")

            # widget management
            self._widget_manager.insertWidget(row_index, row_widget)
            
            # Add cells for each column
            for col in range(self._model.columnCount(row_index.parent())):
                cell_index = self._model.index(row_index.row(), col, row_index.parent())
                cell = CellWidget()
                self._cell_manager.insertCell(cell_index, cell)
                row_widget.insertCell(col, cell)
                self._set_cell_data(cell_index, roles=[Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole])

    def onColumnsInserted(self, parent: QModelIndex, start: int, end: int):
        # TODO: add cells
        raise NotImplementedError("Column insertion is not yet implemented in the graph view")

    def onColumnsAboutToBeRemoved(self, parent: QModelIndex, start: int, end: int):
        # TODO: remove cells
        raise NotImplementedError("Column removal is not yet implemented in the graph view")

    @Slot(QModelIndex, int, int)
    def onRowsAboutToBeRemoved(self, parent:QModelIndex, start:int, end:int):
        assert self._model, "Model must be set before handling rows removed!"

        # get index trees in BFS order
        def get_children(index:QModelIndex) -> Iterable[QModelIndex]:
            if not index.isValid():
                return []
            model = index.model()
            for row in range(model.rowCount(index)):
                child_index = model.index(row, 0, index)
                yield child_index

            return []
        
        sorted_indexes:List[QModelIndex] = list(bfs(
            *[self._model.index(row, 0, parent) for row in range(start, end + 1)], 
            children=get_children, 
            reverse=True
        ))
        
        ## Remove widgets for each index
        scene = self.scene()
        assert scene is not None
        scene.blockSignals(True)
        for row_index in sorted_indexes:
            row_widget = self._widget_manager.getWidget(row_index)
            if row_widget is None:
                logger.warning(f"Row widget not found for index: {indexToPath(row_index)}")
                # Already removed, skip
                continue

            # Remove all cells associated with this widget
            for col in range(self._model.columnCount(row_index.parent())):
                cell_index = self._model.index(row_index.row(), col, row_index.parent())
                if cell_widget := self._cell_manager.getCell(cell_index):
                    row_widget.removeCell(cell_widget)
                    self._cell_manager.removeCell(cell_index)

            # Remove the row widget from the scene
            if row_index.parent().isValid():
                parent_widget = self._widget_manager.getWidget(row_index.parent())
            else:
                parent_widget = scene

            ## widget factory
            match self._delegate.itemType(row_index):
                case GraphItemType.SUBGRAPH:
                    raise NotImplementedError("Subgraphs are not yet supported in the graph view")
                case GraphItemType.NODE:
                    self._delegate.destroyNodeWidget(scene, row_widget)
                case GraphItemType.INLET:
                    self._delegate.destroyInletWidget(parent_widget, row_widget)
                case GraphItemType.OUTLET:
                    self._delegate.destroyOutletWidget(parent_widget, row_widget)
                case GraphItemType.LINK:
                    self._delegate.destroyLinkWidget(parent_widget, row_widget)

                    # link management
                    self._unlinkWidget(row_widget)

                case _:
                    raise ValueError(f"Unknown widget type: {type(row_widget)}")

            # widget management
            self._widget_manager.removeWidget(row_index, row_widget)

        scene.blockSignals(False)

    @Slot(QModelIndex, int, int)
    def onRowsRemoved(self, parent:QModelIndex, start:int, end:int):
        ...
    
    def onDataChanged(self, top_left:QModelIndex, bottom_right:QModelIndex, roles:list):
        """
        Handle data changes in the model.
        This updates the widgets in the graph view.
        """
        assert self._model

        if GraphDataRole.SourceRole in roles or roles == []:
            # If the source role is changed, we need to update the link widget
            for row in range(top_left.row(), bottom_right.row() + 1):
                index = self._model.index(row, top_left.column(), top_left.parent())
                match self._delegate.itemType(index):
                    case GraphItemType.LINK:
                        link_widget = cast(LinkWidget, self._widget_manager.getWidget(index))
                        if link_widget:

                            source_widget = self._widget_manager.getWidget(self._delegate.linkSource(index))
                            target_widget = self._widget_manager.getWidget(self._delegate.linkTarget(index))

                            self._unlinkWidget(link_widget)

                            # link
                            self._linkWidget(link_widget, source_widget, target_widget)

        if GraphDataRole.TypeRole in roles or roles == []:
            # if an inlet or outlet type is changed, we need to update the widget
            for row in range(top_left.row(), bottom_right.row() + 1):
                index = self._model.index(row, top_left.column(), top_left.parent())
                if widget := self._widget_manager.getWidget(index):
                    ... # TODO replace Widget

        for row in range(top_left.row(), bottom_right.row() + 1):
            index = self._model.index(row, top_left.column(), top_left.parent())
            self._set_cell_data(index, roles=[Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole])

    @Slot(QItemSelection, QItemSelection)
    def onSelectionChanged(self, selected:QItemSelection, deselected:QItemSelection):
        """
        Handle selection changes in the selection model.
        This updates the selection in the graph view.
        """
        assert self._selection, "Selection model must be set before handling selection changes!"
        assert self._model, "Model must be set before handling selection changes!"
        assert self._selection.model() == self._model, "Selection model must be for the same model as the graph view!"
        if not selected or not deselected:
            return
        scene = self.scene()
        assert scene is not None
        scene.blockSignals(True)
        
        selected_indexes = sorted([idx for idx in selected.indexes()], 
                                  key= lambda idx: idx.row(), 
                                  reverse= True)
        
        deselected_indexes = sorted([idx for idx in deselected.indexes()], 
                                    key= lambda idx: idx.row(), 
                                    reverse= True)
        
        for index in deselected_indexes:
            if index.isValid() and index.column() == 0:
                if widget:=self._widget_manager.getWidget(index):
                    if widget.scene() and widget.isSelected():
                        widget.setSelected(False)

        for index in selected_indexes:
            if index.isValid() and index.column() == 0:
                if widget:=self._widget_manager.getWidget(index):
                    if widget.scene() and not widget.isSelected():
                        widget.setSelected(True)
        
        scene.blockSignals(False)

    # # Selection
    def setSelectionModel(self, selection: QItemSelectionModel):
        """
        Set the selection model for the graph view.
        This is used to synchronize the selection of nodes in the graph view
        with the selection model.
        """
        assert isinstance(selection, QItemSelectionModel), f"got: {selection}"
        assert self._model, "Model must be set before setting the selection model!"
        assert selection.model() == self._model, "Selection model must be for the same model as the graph view!"
        if self._selection:
            for signal, slot in self._selection_connections:
                signal.disconnect(slot)
            self._selection_connections = []
        
        if selection:
            self._selection_connections = [
                (selection.selectionChanged, self.onSelectionChanged)
            ]
            for signal, slot in self._selection_connections:
                signal.connect(slot)

        self._selection = selection
        
        scene = self.scene()
        assert scene is not None
        scene.selectionChanged.connect(self.syncSelectionModel)

    def selectionModel(self) -> QItemSelectionModel | None:
        """
        Get the current selection model for the graph view.
        This is used to synchronize the selection of nodes in the graph view
        with the selection model.
        """
        return self._selection
    
    # # 
    def syncSelectionModel(self):
        """update selection model from scene selection"""
        scene = self.scene()
        assert scene is not None
        if self._model and self._selection:
            # get currently selected widgets
            selected_widgets = scene.selectedItems()

            # map widgets to QModelIndexes
            selected_indexes = map(self._widget_manager.getIndex, selected_widgets)
            selected_indexes = filter(lambda idx: idx is not None and idx.isValid(), selected_indexes)
            
            assert self._model
            def selectionFromIndexes(selected_indexes:Iterable[QModelIndex]) -> QItemSelection:
                """Create a QItemSelection from a list of selected indexes."""
                item_selection = QItemSelection()
                for index in selected_indexes:
                    if index.isValid():
                        item_selection.select(index, index)
                return item_selection

            # perform selection on model
            item_selection = selectionFromIndexes(selected_indexes)
            self._selection.select(item_selection, QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows)
            if len(item_selection.indexes()) > 0:
                last_selected_index = item_selection.indexes()[-1]
                self._selection.setCurrentIndex(
                    last_selected_index,
                    QItemSelectionModel.SelectionFlag.Current | QItemSelectionModel.SelectionFlag.Rows
                )
            else:
                self._selection.clearSelection()
                self._selection.setCurrentIndex(QModelIndex(), QItemSelectionModel.SelectionFlag.Current | QItemSelectionModel.SelectionFlag.Rows)

    def _set_cell_data(self, index:QModelIndex|QPersistentModelIndex, roles:list=[]):
        """Set the data for a cell widget."""
        assert index.isValid(), "Index must be valid"

        if Qt.ItemDataRole.DisplayRole in roles or Qt.ItemDataRole.DisplayRole in roles or roles == []:
            if cell_widget:= self._cell_manager.getCell(index):
                text = index.data(Qt.ItemDataRole.DisplayRole)
                cell_widget.setText(text)

    ## Linking
    def startLinking(self, payload:Payload)->bool:
        """
        Start linking from the given index.
        This is used to initiate a drag-and-drop operation for linking.
        return True if the drag operation was started, False otherwise.
        """

        if self._state != GraphView.State.IDLE:
            # Already in linking state, cannot start linking
            return False

        index_type = self._delegate.itemType(payload.index)
        if index_type not in (GraphItemType.INLET, GraphItemType.OUTLET, GraphItemType.LINK):
            # Only inlets, outlets and links can be dragged
            return False
        
        if index_type in (GraphItemType.OUTLET, GraphItemType.INLET):
            # create a draft link line
            if not self._draft_link:
                self._draft_link = LinkWidget()
                self.scene().addItem(self._draft_link)

        self._state = GraphView.State.LINKING
        self._linking_payload = payload
        
        # mime = payload.toMimeData()
        # if mime is None:
        #     return False
        
        # drag = QDrag(self)
        # drag.setMimeData(mime)

        # # Execute drag
        # try:
        #     action = drag.exec(Qt.DropAction.LinkAction)
        # except Exception as err:
        #     traceback.print_exc()
        # return True

    def updateLinking(self, payload:Payload, pos:QPoint):
        """
        Update the linking position
        """
        if self._state != GraphView.State.LINKING:
            # Not in linking state, cannot update linking
            return
        
        pos = QPoint(int(pos.x()), int(pos.y())) # defense against passing QPointF
        
        # Determine the source and target types
        target_index = self.rowAt(pos)  # Ensure the index is updated
        drop_target_type = self._delegate.itemType(target_index)
        drag_source_type = payload.kind

        # find relevant indexes
        outlet_index, inlet_index, link_index = None, None, None
        match drag_source_type, drop_target_type:
            case 'outlet', GraphItemType.INLET:
                link_index = None
                outlet_index = payload.index
                inlet_index = target_index

            case 'inlet', GraphItemType.OUTLET:
                # inlet dragged over outlet
                link_index = None
                outlet_index = target_index
                inlet_index = payload.index

            case 'tail', GraphItemType.OUTLET:
                # link tail dragged over outlet
                link_index = payload.index
                outlet_index = target_index
                inlet_index = self._delegate.linkTarget(link_index)

            case 'head', GraphItemType.INLET:
                # link head dragged over inlet
                link_index = payload.index
                outlet_index = self._delegate.linkSource(link_index)
                inlet_index = target_index

            case 'outlet', _:
                # outlet dragged over empty space
                link_index = None
                outlet_index = payload.index
                inlet_index = None  

            case 'inlet', _:
                # inlet dragged over empty space
                link_index = None
                outlet_index = None
                inlet_index = payload.index
                
            case 'head', _:
                # link head dragged over empty space
                link_index = payload.index
                outlet_index = self._delegate.linkSource(link_index)
                inlet_index = None

            case 'tail', _:
                # link tail dragged over empty space
                link_index = payload.index
                outlet_index = None
                inlet_index = self._delegate.linkTarget(link_index)

            case _:
                # No valid drag source or drop target, do nothing
                return None


        link_widget = self._widget_manager.getWidget(link_index) if link_index else self._draft_link

        if outlet_index and inlet_index and self._delegate.canLink(outlet_index, inlet_index):
            outlet_widget = self._widget_manager.getWidget(outlet_index)
            inlet_widget = self._widget_manager.getWidget(inlet_index)
            line = makeLineBetweenShapes(outlet_widget, inlet_widget)
            line = QLineF(link_widget.mapFromScene(line.p1()), link_widget.mapFromScene(line.p2()))

        elif outlet_index:
            outlet_widget = self._widget_manager.getWidget(outlet_index)
            line = makeLineBetweenShapes(outlet_widget, self.mapToScene(pos))
            line = QLineF(link_widget.mapFromScene(line.p1()), link_widget.mapFromScene(line.p2()))

        elif inlet_index:
            inlet_widget = self._widget_manager.getWidget(inlet_index)
            line = makeLineBetweenShapes(self.mapToScene(pos), inlet_widget)
            line = QLineF(link_widget.mapFromScene(line.p1()), link_widget.mapFromScene(line.p2()))

        link_widget.setLine(line)

    def finishLinking(self, payload:Payload, target_index:QModelIndex)->bool:
        """
        Finish linking operation.
        """

        if self._state != GraphView.State.LINKING:
            # Not in linking state, cannot finish linking
            return False
        
        # Determine the drop target type
        drop_target_type = self._delegate.itemType(target_index)

        # Determine the drag source type based on the mime data
        drag_source_type:Literal['inlet', 'outlet', 'head', 'tail'] = payload.kind

        # Perform the linking based on the drag source and drop target types
        # return True if the linking was successful, False otherwise
        success = False
        match drag_source_type, drop_target_type:
            case "outlet", GraphItemType.INLET:
                # outlet dropped on inlet
                outlet_index = payload.index
                assert outlet_index.isValid(), "Outlet index must be valid"
                inlet_index = target_index
                if self._delegate.addLink(self._model, outlet_index, inlet_index):
                    success = True

            case "inlet", GraphItemType.OUTLET:
                # inlet dropped on outlet
                inlet_index = payload.index
                assert inlet_index.isValid(), "Inlet index must be valid"
                outlet_index = target_index
                if self._delegate.addLink(self._model, outlet_index, inlet_index):
                    success = True

            case "head", GraphItemType.INLET:
                # link head dropped on inlet
                link_index = payload.index
                new_inlet_index = target_index
                current_outlet_index = self._delegate.linkSource(link_index)
                if self._delegate.removeLink(self._model, link_index):
                    if self._delegate.addLink(self._model, current_outlet_index, new_inlet_index):
                        success = True

            case "tail", GraphItemType.OUTLET:
                # link tail dropped on outlet
                link_index = payload.index
                new_outlet_index = target_index
                current_inlet_index = self._delegate.linkTarget(link_index)
                if self._delegate.removeLink(self._model, link_index):
                    if self._delegate.addLink(self._model, new_outlet_index, current_inlet_index):
                        success = True

            case 'tail', _:
                # tail dropped on empty space
                link_index = payload.index
                assert link_index.isValid(), "Link index must be valid"
                link_source = self._delegate.linkSource(link_index)
                link_target = self._delegate.linkTarget(link_index)
                IsLinked = link_source and link_source.isValid() and link_target and link_target.isValid()
                if IsLinked:
                    if self._delegate.removeLink(self._model, link_index):
                        success = True

            case 'head', _:
                # head dropped on empty space
                link_index = payload.index
                assert link_index.isValid(), "Link index must be valid"
                link_source = self._delegate.linkSource(link_index)
                link_target = self._delegate.linkTarget(link_index)
                IsLinked = link_source and link_source.isValid() and link_target and link_target.isValid()
                if IsLinked:
                    if self._delegate.removeLink(self._model, link_index):
                        success = True

        # cleanup DraftLink
        if self._draft_link:
            self.scene().removeItem(self._draft_link)
            self._draft_link = None

        self._state = GraphView.State.IDLE
        return success

    def cancelLinking(self):
        """
        Cancel the linking operation.
        This is used to remove the draft link and reset the state.
        """
        if self._state == GraphView.State.LINKING:

            if self._delegate.itemType(self._linking_payload.index) == GraphItemType.LINK:
                link_widget = cast(LinkWidget, self._widget_manager.getWidget(self._linking_payload.index))
                assert link_widget is not None, "Link widget must not be None"
                source_widget = self._link_source.get(link_widget, None)
                target_widget = self._link_target.get(link_widget, None)
                self._update_link_position(link_widget, source_widget, target_widget)

            else:
                assert self._draft_link is not None, "Draft link must not be None"
                if self._draft_link:
                    self.scene().removeItem(self._draft_link)
                    self._draft_link = None

            # Reset state
            self._state = GraphView.State.IDLE
            self._linking_payload = None

    ## Handle mouse events
    def mousePressEvent(self, event):
        """
        By default start linking from the item under the mouse cursor.
        if starting a link is not possible, fallback to the QGraphicsView behavior.
        """

        self.setCursor(Qt.CursorShape.DragLinkCursor)  # Reset cursor to default
        if self._state == GraphView.State.LINKING:
            # If we are already linking, cancel the linking operation
            self.cancelLinking()
            return
        
        if self._state == GraphView.State.IDLE:
            pos = event.position()
            index = self.rowAt(QPoint(int(pos.x()), int(pos.y())))  # Ensure the index is updated
            assert index is not None, f"got: {index}"

            match self._delegate.itemType(index):
                case GraphItemType.INLET:
                    if self.startLinking(Payload(index, 'inlet')):
                        return
                case GraphItemType.OUTLET:
                    if self.startLinking(Payload(index, 'outlet')):
                        return

                case GraphItemType.LINK:
                    # If the item is a link, determine which end to drag
                    def getClosestLinkEnd(link_index:QModelIndex, scene_pos:QPointF) -> Literal['head', 'tail']:
                        source_index = self._delegate.linkSource(link_index)
                        target_index = self._delegate.linkTarget(link_index)
                        if source_index and source_index.isValid() and target_index and target_index.isValid():
                            link_widget = cast(LinkWidget, self._widget_manager.getWidget(link_index))
                            local_pos = link_widget.mapFromScene(scene_pos)  # Ensure scene_pos is in the correct coordinate system
                            tail_distance = (local_pos-link_widget.line().p1()).manhattanLength()
                            head_distance = (local_pos-link_widget.line().p2()).manhattanLength()

                            if head_distance < tail_distance:
                                return 'head'  # Drag the head if closer to the mouse position
                            else:
                                return 'tail'
                            
                        elif source_index and source_index.isValid():
                            return 'head'
                        
                        elif target_index and target_index.isValid():
                            return 'tail'
                        
                        else:
                            return 'tail'
                    
                    scene_pos = self.mapToScene(event.position().toPoint())
                    link_end = getClosestLinkEnd(index, scene_pos)
    
                    if self.startLinking(Payload(index, kind=link_end)):
                        return
                    
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._state == self.State.LINKING:
            pos = QPoint(int(event.position().x()), int(event.position().y())) # Ensure pos is in integer coordinates
            self.updateLinking(self._linking_payload, pos)
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self.unsetCursor()
        if self._state == self.State.LINKING:
            
            pos = QPoint(int(event.position().x()), int(event.position().y())) # Ensure pos is in integer coordinates
            drop_target = self.rowAt(pos)  # Ensure the index is updated
            if not self.finishLinking(self._linking_payload, drop_target):
                # Handle failed linking
                logger.warning("WARNING: Linking failed!")
                pass

        else:
            super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event:QMouseEvent):
        index = self.indexAt(QPoint(int(event.position().x()), int(event.position().y())))

        if not index.isValid():
            self._delegate.addNode(self._model, QModelIndex())
            # self._model.insertRows(0, 1, QModelIndex())
            return
            # return super().mouseDoubleClickEvent(event)
                
        def onEditingFinished(editor:QLineEdit, cell_widget:CellWidget, index:QModelIndex):
            self._delegate.setModelData(editor, self._model, index)
            cell_widget.setEditorWidget(None)  # Clear the editor widget
            editor.deleteLater()
            self._set_cell_data(index, roles=[Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole])

        if cell_widget := self._cell_manager.getCell(index):
            editor = self._delegate.createEditor(self, None, index)
            assert editor.parent() is None, "Editor must not have a parent"
            cell_widget.setEditorWidget(editor)  # Clear any existing editor widget
            editor.setText(index.data(Qt.ItemDataRole.EditRole))
            editor.setFocus(Qt.FocusReason.MouseFocusReason)
            editor.editingFinished.connect(lambda editor = editor, cell_widget=cell_widget, index=index: onEditingFinished(editor, cell_widget, index) )
    
    def toNetworkX(self)-> nx.MultiDiGraph:
        G = nx.MultiDiGraph()
        port_to_node: dict[QGraphicsItem, NodeWidget] = {}
        all_widgets = list(self._widget_manager.widgets())
        for widget in all_widgets:
            # collect nodes and ports
            if isinstance(widget, NodeWidget):
                node_widget = cast(NodeWidget, widget)
                node_name = widget.cells()[0].text()
                expression_text = widget.cells()[1].text()
                assert node_name not in G.nodes, f"Duplicate node name: {node_name}"
                inlet_names = []
                for inlet_widget in node_widget.inlets():
                    inlet_name = inlet_widget.cells()[0].text()
                    inlet_names.append(inlet_name)
                    port_to_node[inlet_widget] = node_widget

                for outlet_widget in node_widget.outlets():
                    port_to_node[outlet_widget] = node_widget

                assert node_name not in G.nodes, f"Duplicate node name: {node_name}"
                G.add_node(node_name, inlets=inlet_names, expression=expression_text)
                
            # collect links
            elif isinstance(widget, LinkWidget):
                source_outlet = self._link_source[widget]
                target_inlet = self._link_target[widget]
                assert source_outlet is not None and target_inlet is not None, "Link source and target must be valid"
                source_node_widget = port_to_node[source_outlet]
                target_node_widget = port_to_node[target_inlet]
                G.add_edge(
                    source_node_widget.cells()[0].text(), 
                    target_node_widget.cells()[0].text(), 
                    target_inlet.cells()[0].text()
                )
        return G

    # def dragEnterEvent(self, event)->None:
    #     if event.mimeData().hasFormat(GraphMimeType.InletData) or event.mimeData().hasFormat(GraphMimeType.OutletData):
    #         # Create a draft link if the mime data is for inlets or outlets
            
    #         event.acceptProposedAction()

    #     if event.mimeData().hasFormat(GraphMimeType.LinkHeadData) or event.mimeData().hasFormat(GraphMimeType.LinkTailData):
    #         # Create a draft link if the mime data is for link heads or tails
    #         event.acceptProposedAction()

    # def dragLeaveEvent(self, event):
    #     if self._draft_link:
    #         scene = self.scene()
    #         assert scene is not None
    #         scene.removeItem(self._draft_link)
    #         self._draft_link = None
    #     #self._cleanupDraftLink()  # Cleanup draft link if it exists
    #     # super().dragLeaveEvent(event)
    #     # self._cleanupDraftLink()

    # def dragMoveEvent(self, event)->None:
    #     """Handle drag move events to update draft link position"""
    #     pos = QPoint(int(event.position().x()), int(event.position().y())) # Ensure pos is in integer coordinates

    #     data = event.mimeData()
    #     payload = Payload.fromMimeData(data)
        
    #     self.updateLinking(payload, pos)
    #     return

    # def dropEvent(self, event: QDropEvent) -> None:
    #     pos = QPoint(int(event.position().x()), int(event.position().y())) # Ensure pos is in integer coordinates
    #     drop_target = self.rowAt(pos)  # Ensure the index is updated

    #     # TODO: check for drag action
    #     # match event.proposedAction():
    #     #     case Qt.DropAction.CopyAction:
    #     #         ...
    #     #     case Qt.DropAction.MoveAction:
    #     #         ...
    #     #     case Qt.DropAction.LinkAction:
    #     #         ...
    #     #     case Qt.DropAction.IgnoreAction:
    #     #         ...
        
    #     if self.finishLinking(event.mimeData(), drop_target):
    #         event.acceptProposedAction()
    #     else:
    #         event.ignore()

