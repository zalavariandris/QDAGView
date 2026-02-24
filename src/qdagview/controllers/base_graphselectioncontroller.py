from typing import *
import logging
from enum import Enum
from dataclasses import dataclass

from qtpy.QtGui import *
from qtpy.QtCore import *
from qtpy.QtWidgets import *

from .base_graphcontroller import BaseGraphController

logger = logging.getLogger(__name__)

from ..core.base_types import GraphT, NodeT, LinkT, PortT



class BaseGraphSelectionController(QObject):
    """
    """

    selectionChanged = Signal(list, list) # (selected, deselected_)
    currentChanged = Signal(object, object) # (current, previous) type: NodeT|LinkT|None since current index can be invalid, and we don't want to force users to check for validity of the index before accessing the current item
    modelChanged = Signal() # emitted when the underlying graph _controller_ changes, so views can update their selection state if needed TODO: rename graph controller to model

    def __init__(self, graph_model:BaseGraphController, parent:QObject|None=None):
        super().__init__(parent)
        self._graph_controller: BaseGraphController | None = None
        
    def setGraphController(self, graph_controller:BaseGraphController):
        """Set the graph controller to use.

        This will clear the current selection and disconnect from any previous graph controller and its source selection model.
        """
        self._graph_controller = graph_controller
        self.clearSelection()

    def graphController(self) -> BaseGraphController|None:
        return self._graph_controller
        
    def selectedIndexes(self) -> List[NodeT|LinkT]:
        raise NotImplementedError()

    def select(self, selection:list, command:QItemSelectionModel.SelectionFlag=QItemSelectionModel.SelectionFlag.Select):
        raise NotImplementedError()
    
        self.sourceSelectionModel().select(QItemSelection(selection), command)
        # Store old selection for comparison
        old_selection = self._selection.copy()
        print(f"Selection command: {command}, new_selection: {selection}, old_selection: {old_selection}")
        # Apply selection logic
        deselected_items:list = list()
        selected_items:list = list()

        # Clear old selection if requested
        if command & QItemSelectionModel.SelectionFlag.Clear:
            for idx in self._selection:
                deselected_items.append(idx)
            self._selection = list() # clear selection by creating a new empty selection object, to preserve any references to the old selection object that may be held by views or other controllers
            # self.selectionChanged.emit(set(), old_selection)
            # return
        
        if command & QItemSelectionModel.SelectionFlag.Select:
            for idx in selection:
                if idx not in self._selection:
                    self._selection.append(idx)
                    selected_items.append(idx)

        elif command & QItemSelectionModel.SelectionFlag.Deselect:
            for idx in selection:
                if idx in self._selection:
                    self._selection.remove(idx)
                    deselected_items.append(idx)

        elif command & QItemSelectionModel.SelectionFlag.Toggle:
            for idx in selection:
                if idx in self._selection:
                    self._selection.remove(idx)
                    deselected_items.append(idx)
                else:
                    self._selection.append(idx)
                    selected_items.append(idx)

        # Update current if requested
        if command & QItemSelectionModel.SelectionFlag.Current and len(selection) > 0:
            self.setCurrentIndex(selection[0])
        
        # Emit selectionChanged signal if selection actually changed
        if set(self._selection) != set(old_selection):
            self.selectionChanged.emit(selected_items, deselected_items)

    def clearSelection(self):
        raise NotImplementedError()

    def currentIndex(self) -> NodeT|None:
        raise NotImplementedError()

    def setCurrentIndex(self, index:NodeT|None, command:QItemSelectionModel.SelectionFlag=QItemSelectionModel.SelectionFlag.Current):
        raise NotImplementedError()
        
    def handleSourceSelectionChanged(self, selected:QItemSelection, deselected:QItemSelection):
        ...

    def handleSourceCurrentChanged(self, current:NodeT|None, previous:NodeT|None):
        ...

    def handleNodesAboutToBeRemoved(self, nodes:List[NodeT]):
        ...

    def handleLinksAboutToBeRemoved(self, links:List[LinkT]):
        ...