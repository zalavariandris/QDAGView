from typing import *
import logging
from enum import Enum
from dataclasses import dataclass

from qtpy.QtGui import *
from qtpy.QtCore import *
from qtpy.QtWidgets import *

from .graphcontroller_for_qtreemodel import GraphController_for_QTreeModel
from ..core import GraphItemType
logger = logging.getLogger(__name__)


class GraphSelection:
    def __init__(self, refs:Iterable[QPersistentModelIndex]|None=[]):
        self._selected = list(refs)

    def indexes(self) -> List[QModelIndex]:
        return self._selected


class GraphSelectionController_for_QItemSelectionModel(QObject):
    """
    """

    selectionChanged = Signal(GraphSelection, GraphSelection) # (selected, deselected_)
    currentChanged = Signal(QPersistentModelIndex, QPersistentModelIndex) # (current, previous)

    def __init__(self, graph_model:GraphController_for_QTreeModel, source_selection_model:QItemSelectionModel, parent:QObject|None=None):
        super().__init__(parent)
        
        self._graph_controller: GraphController_for_QTreeModel | None = None
        self._source_selection_model: QItemSelectionModel | None = None
        self._source_selection_connections: list[tuple[Signal, Slot]] = []

        self.setGraphController(graph_model)
        self.setSourceSelectionModel(source_selection_model)
        
    def setGraphController(self, graph_controller:GraphController_for_QTreeModel):
        """Set the graph controller to use.

        This will clear the current selection and disconnect from any previous graph controller and its source selection model.
        """
        self._graph_controller = graph_controller
        self.setSourceSelectionModel(None)

    def graphController(self) -> GraphController_for_QTreeModel|None:
        return self._graph_controller
    
    def setSourceSelectionModel(self, source_selection_model: QItemSelectionModel | None):
        if source_selection_model is self._source_selection_model:
            return
        
        deselected = []
        if self._source_selection_model is not None:
            for signal, slot in self._source_selection_connections:
                signal.disconnect(slot)
            self._source_selection_connections = []
            deselected = [QPersistentModelIndex(idx) for idx in self._source_selection_model.selectedIndexes() if self._IsSelectable(idx)]

        selected = []
        if source_selection_model is not None:
            if source_selection_model.model() is not self._graph_controller.sourceModel():
                logger.error("Selection model's model does not match the graph controller's model")
            
            self._source_selection_connections = [
                (source_selection_model.selectionChanged, self.handleSourceSelectionChanged),
                (source_selection_model.currentChanged, self.handleSourceCurrentChanged),
            ]

            for signal, slot in self._source_selection_connections:
                signal.connect(slot)

            selected = [QPersistentModelIndex(idx) for idx in source_selection_model.selectedIndexes() if self._IsSelectable(idx)]
        
        self.selectionChanged.emit(GraphSelection(selected), GraphSelection(deselected))
        self._source_selection_model = source_selection_model

    def sourceSelectionModel(self) -> QItemSelectionModel|None:
        return self._source_selection_model
        
    def selectedIndexes(self) -> List[QPersistentModelIndex]:
        selected_node_refs = []
        selected_link_refs = []
        if self._source_selection_model is None:
            return []
        
        return [
            QPersistentModelIndex(idx) 
            for idx in self._source_selection_model.selectedIndexes() 
            if self._IsSelectable(idx)
        ]

    def select(self, selection:GraphSelection, command:QItemSelectionModel.SelectionFlag=QItemSelectionModel.SelectionFlag.Select):
        self._source_selection_model.select(QItemSelection(selection.indexes()), command)

    def clearSelection(self):
        self._source_selection_model.clearSelection()

    def currentIndex(self) -> QPersistentModelIndex:
        return QPersistentModelIndex(self._source_selection_model.currentIndex())

    def setCurrentIndex(self, index:QPersistentModelIndex, command:QItemSelectionModel.SelectionFlag=QItemSelectionModel.SelectionFlag.Current):
        self._source_selection_model.setCurrentIndex(index, command)
    
    # maps source selection model signals to graph selection signals
    def _IsSelectable(self, idx:QModelIndex)->bool:
        # determine if the index corresponds to a selectable graph item (node or link)
        if not idx.isValid():
            return False
        item_type = self._graph_controller.itemType(idx)
        return item_type in {GraphItemType.NODE, GraphItemType.LINK}
    
    def handleSourceSelectionChanged(self, selected:QItemSelection, deselected:QItemSelection):
        # map the selected and deselected indexes to nodes and links
        selected_ref = map(QPersistentModelIndex,
            filter(lambda idx: 
                self._IsSelectable(idx), 
                selected.indexes()
        ))

        deselected_ref = map(QPersistentModelIndex,
            filter(lambda idx: 
                self._IsSelectable(idx), 
                deselected.indexes()
        ))

        # emit the selectionChanged signal
        self.selectionChanged.emit(GraphSelection(selected_ref), GraphSelection(deselected_ref))

    def handleSourceCurrentChanged(self, current:QModelIndex, previous:QModelIndex):
        if current.isValid() and self._IsSelectable(current):
            current_ref = QPersistentModelIndex(current)
        else:
            current_ref = QPersistentModelIndex()

        if previous.isValid() and self._IsSelectable(previous):
            previous_ref = QPersistentModelIndex(previous)
        else:
            previous_ref = QPersistentModelIndex()

        self.currentChanged.emit(current_ref, previous_ref)
