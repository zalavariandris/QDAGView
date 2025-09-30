from typing import *
import logging
from enum import Enum
from dataclasses import dataclass

from qtpy.QtGui import *
from qtpy.QtCore import *
from qtpy.QtWidgets import *

from .graphcontroller_for_qtreemodel import GraphController_for_QTreeModel

logger = logging.getLogger(__name__)


class GraphSelection:
    def __init__(self):
        self._selected = []

    def indexes(self) -> List[QModelIndex]:
        return self._selected


class GraphSelectionController_for_QItemSelectionModel(QObject):
    """
    """

    selectionChanged = Signal(GraphSelection, GraphSelection) # (selected, deselected_)
    currentChanged = Signal(QPersistentModelIndex, QPersistentModelIndex) # (current, previous)

    def __init__(self, graph_model:GraphController_for_QTreeModel, source_selection_model:QItemSelectionModel, parent:QObject|None=None):
        super().__init__(parent)
        self._selection = set() # type: Set[QPersistentModelIndex]
        self._current: QPersistentModelIndex | None = None

        
        self._graph_controller: GraphController_for_QTreeModel | None = None
        self._controller_connections: list[tuple[Signal, Slot]] = []

        self._source_selection_model: QItemSelectionModel | None = None
        self._source_selection_connections: list[tuple[Signal, Slot]] = []

        self.setGraphController(graph_model)
        self.setSourceSelectionModel(source_selection_model)
        
    def setGraphController(self, graph_controller:GraphController_for_QTreeModel):
        """Set the graph controller to use.

        This will clear the current selection and disconnect from any previous graph controller and its source selection model.
        """
        if self._graph_controller:
            for signal, slot in self._controller_connections:
                signal.disconnect(slot)
            self._controller_connections = []

        if graph_controller:
            self._controller_connections = [
                (graph_controller.nodesAboutToBeRemoved, self.handleNodesAboutToBeRemoved), #TODO: shis should probably be handled in source selection model
                (graph_controller.linksAboutToBeRemoved, self.handleLinksAboutToBeRemoved),
            ]

            for signal, slot in self._controller_connections:
                signal.connect(slot)

        self._graph_controller = graph_controller
        self.setSourceSelectionModel(None)

    def graphController(self) -> GraphController_for_QTreeModel|None:
        return self._graph_controller
    
    def setSourceSelectionModel(self, source_selection_model: QItemSelectionModel | None):
        if source_selection_model is self._source_selection_model:
            return
        
        if self._source_selection_model is not None:
            for signal, slot in self._source_selection_connections:
                signal.disconnect(slot)
            self._source_selection_connections = []
            self.selectionChanged.emit(GraphSelection(), self._selection)

        if source_selection_model is not None:
            if source_selection_model.model() is not self._graph_controller.sourceModel():
                logger.error("Selection model's model does not match the graph controller's model")
            
            self._source_selection_connections = [
                (source_selection_model.selectionChanged, self.handleSourceSelectionChanged),
                (source_selection_model.currentChanged, self.handleSourceCurrentChanged),
            ]

            for signal, slot in self._source_selection_connections:
                signal.connect(slot)

            self.selectionChanged.emit(self._selection, GraphSelection())

        self._source_selection_model = source_selection_model

    def sourceSelectionModel(self) -> QItemSelectionModel|None:
        return self._source_selection_model
        
    def selectedIndexes(self) -> List[QPersistentModelIndex]:
        return list(self._selection)

    def select(self, selection:GraphSelection, command:QItemSelectionModel.SelectionFlag=QItemSelectionModel.SelectionFlag.Select):
        # Store old selection for comparison
        old_selection = self._selection.copy()
        
        # Clear old selection if requested
        if command & QItemSelectionModel.SelectionFlag.Clear:
            self._selection.clear()

        # Apply selection logic
        for idx in selection.indexes():
            if command & QItemSelectionModel.SelectionFlag.Select:
                self._selection.add(idx)
            elif command & QItemSelectionModel.SelectionFlag.Deselect:
                self._selection.discard(idx)
            elif command & QItemSelectionModel.SelectionFlag.Toggle:
                if idx in self._selection:
                    self._selection.remove(idx)
                else:
                    self._selection.add(idx)

        # Update current index if requested
        if command & QItemSelectionModel.SelectionFlag.Current and selection.indexes():
            self.setCurrentIndex(selection.indexes()[0])
        
        # Emit selectionChanged signal if selection actually changed
        if self._selection != old_selection:
            # Create GraphSelection objects for selected and deselected items
            selected_items = GraphSelection()
            selected_items._selected = list(self._selection - old_selection)
            
            deselected_items = GraphSelection()
            deselected_items._selected = list(old_selection - self._selection)
            
            self.selectionChanged.emit(selected_items, deselected_items)

    def clearSelection(self):
        if self._selection:
            old_selection = self._selection.copy()
            self._selection.clear()
            
            # Emit selectionChanged signal
            selected_items = GraphSelection()
            deselected_items = GraphSelection()
            deselected_items._selected = list(old_selection)
            
            self.selectionChanged.emit(selected_items, deselected_items)

    def currentIndex(self) -> QPersistentModelIndex:
        return self._current

    def setCurrentIndex(self, index:QPersistentModelIndex, command:QItemSelectionModel.SelectionFlag=QItemSelectionModel.SelectionFlag.Current):
        if command & QItemSelectionModel.SelectionFlag.Current:
            previous_current = getattr(self, '_current', QPersistentModelIndex())
            self._current = index
            
            # Emit currentChanged signal if current index actually changed
            if self._current != previous_current:
                self.currentChanged.emit(self._current, previous_current)
        else:
            # TODO: implement other commands
            raise NotImplementedError("Only 'Current' command is implemented for setCurrentIndex")
        
    def handleSourceSelectionChanged(self, selected:QItemSelection, deselected:QItemSelection):
        ...

    def handleSourceCurrentChanged(self, current:QModelIndex, previous:QModelIndex):
        ...

    def handleNodesAboutToBeRemoved(self, nodes:List[QPersistentModelIndex]):
        ...

    def handleLinksAboutToBeRemoved(self, links:List[QPersistentModelIndex]):
        ...