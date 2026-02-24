from typing import *
import logging
from enum import Enum
from dataclasses import dataclass

from qtpy.QtGui import *
from qtpy.QtCore import *
from qtpy.QtWidgets import *

from .qtreemodel_graphcontroller import QTreeModel_GraphController
from .base_graphselectioncontroller import BaseGraphSelectionController

logger = logging.getLogger(__name__)

from qdagview.utils import group_consecutive_numbers
from ..core.base_types import NodeT, LinkT, PortT

class QTreeModel_GraphSelectionController(BaseGraphSelectionController):
    """
    """

    selectionChanged = Signal(list, list) # (selected, deselected_) type: List[QModelIndex], list[QModelIndex]
    currentChanged = Signal(QModelIndex , QModelIndex) # (current, previous)

    def __init__(self, graph_model:QTreeModel_GraphController, source_selection_model:QItemSelectionModel, parent:QObject|None=None):
        super().__init__(parent)

        # models
        self._graph_controller: QTreeModel_GraphController | None = None
        self._controller_connections: list[tuple[Signal, Slot]] = []

        self._source_selection_model: QItemSelectionModel | None = None
        self._source_selection_connections: list[tuple[Signal, Slot]] = []

        # initialize with given arguments
        self.setGraphController(graph_model)
        self.setSourceSelectionModel(source_selection_model)
        
    def setGraphController(self, graph_controller:QTreeModel_GraphController):
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

    def graphController(self) -> QTreeModel_GraphController|None:
        return self._graph_controller
    
    def setSourceSelectionModel(self, source_selection_model: QItemSelectionModel | None):
        if source_selection_model is self._source_selection_model:
            return
        
    
        # Disconnect from previous selection model signals and clear selection
        deselected_items = []
        if self._source_selection_model is not None:
            deselected_items = self.selectedIndexes()
            for signal, slot in self._source_selection_connections:
                signal.disconnect(slot)
            self._source_selection_connections = []

        selected_items = []
        if source_selection_model is not None:
            assert self._graph_controller is not None, "Graph controller must be set before setting source selection model"
            if source_selection_model.model() is not self._graph_controller.sourceModel():
                logger.error("Selection model's model does not match the graph controller's model")
            
            self._source_selection_connections = [
                (source_selection_model.selectionChanged, self.handleSourceSelectionChanged),
                (source_selection_model.currentChanged, self.handleSourceCurrentChanged),
            ]

            for signal, slot in self._source_selection_connections:
                signal.connect(slot)

        self._source_selection_model = source_selection_model
        selected_items = self.selectedIndexes()
        self.selectionChanged.emit(selected_items, deselected_items)

    def sourceSelectionModel(self) -> QItemSelectionModel|None:
        return self._source_selection_model
        
    def selectedIndexes(self) -> List[QModelIndex]:
        if self._source_selection_model is None:
            return []

        return self._source_selection_model.selectedIndexes()
    
    def select(self, selection:List[QPersistentModelIndex], command:QItemSelectionModel.SelectionFlag=QItemSelectionModel.SelectionFlag.Select):
        assert isinstance(selection, list), f"Selection must be a list, got: {selection}"
        assert all(isinstance(idx, QPersistentModelIndex) for idx in selection), f"All items in selection must be QPersistentModelIndex, got: {selection}"
        # collect selection ranges

        new_item_selection = QItemSelection()
        row_groups = group_consecutive_numbers([ idx.row() for idx in selection ])
        for row_group in row_groups:
            index_group = [idx for idx in selection if idx.row() in row_group]
            top_left_index = QModelIndex(index_group[0])
            bottom_right_index = QModelIndex(index_group[-1])
            range_selection = QItemSelection(top_left_index, bottom_right_index)
            new_item_selection.merge(range_selection, QItemSelectionModel.SelectionFlag.Select)

        source_selection_model = self.sourceSelectionModel()
        assert source_selection_model is not None, "Source selection model must be set to apply selection"
        source_selection_model.select(new_item_selection, command)

    def clearSelection(self):
        self.sourceSelectionModel().clearSelection()

    def currentIndex(self) -> QModelIndex:
        if self.sourceSelectionModel() is None:
            return QModelIndex()
        return self.sourceSelectionModel().currentIndex()
    
    def setCurrentIndex(self, index:NodeT|LinkT|None, command:QItemSelectionModel.SelectionFlag=QItemSelectionModel.SelectionFlag.Current):
        if command & QItemSelectionModel.SelectionFlag.Current:
            self.sourceSelectionModel().setCurrentIndex(QModelIndex(index) if index is not None else QModelIndex(), command)
        else:
            # TODO: implement other commands
            raise NotImplementedError("Only 'Current' command is implemented for setCurrentIndex")
        
    def handleSourceSelectionChanged(self, selected:QItemSelection, deselected:QItemSelection):
        print("Source selection changed - selected:", selected.indexes(), "deselected:", deselected.indexes())
        self.selectionChanged.emit(selected.indexes(), deselected.indexes())

    def handleSourceCurrentChanged(self, current:QModelIndex, previous:QModelIndex):
        print("Source current changed - current:", current, "previous:", previous)
        self.currentChanged.emit(current, previous)

    def handleNodesAboutToBeRemoved(self, nodes:List[QPersistentModelIndex]):
        print("Nodes about to be removed:", nodes)

    def handleLinksAboutToBeRemoved(self, links:List[QPersistentModelIndex]):
        print("Links about to be removed:", links)