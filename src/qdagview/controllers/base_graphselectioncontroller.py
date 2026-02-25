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

    def __init__(self, graph_controller:BaseGraphController|None=None, parent:QObject|None=None):
        super().__init__(parent)
        self._graph_controller: BaseGraphController | None = None
        self._selected_items: List[NodeT|LinkT] = []
        self._current_item: NodeT|LinkT|None = None
        if graph_controller is not None:
            self.setGraphController(graph_controller)

    def isSelected(self, index:NodeT|LinkT) -> bool:
        return index in self._selected_items
    
    def hasSelection(self) -> bool:
        return len(self._selected_items) > 0
        
    def setGraphController(self, graph_controller:BaseGraphController):
        """Set the graph controller to use.

        This will clear the current selection and disconnect from any previous graph controller and its source selection model.
        """
        self._graph_controller = graph_controller
        self._graph_controller.linksAboutToBeRemoved.connect(self.onLinksAboutToBeRemoved)
        self._graph_controller.nodesAboutToBeRemoved.connect(self.onNodesAboutToBeRemoved)
        
        self.clearSelection()

    def onNodesAboutToBeRemoved(self, node_refs:List[NodeT]):
        # Deselect any nodes that are about to be removed
        deselected_nodes = []
        for node in node_refs:
            if node in self._selected_items:
                self._selected_items.remove(node)
                deselected_nodes.append(node)

        # if len(deselected_nodes) > 0: # TODO: review, if we should emit selectionChanged. check QItemSelectionModel behavior
        #     self.selectionChanged.emit([], deselected_nodes)

    def onLinksAboutToBeRemoved(self, link_refs:List[LinkT]):
        # Deselect any links that are about to be removed
        deselected_links = []
        for link in link_refs:
            if link in self._selected_items:
                self._selected_items.remove(link)
                deselected_links.append(link)

        # if len(deselected_links) > 0: # TODO: review, if we should emit selectionChanged. check QItemSelectionModel behavior
        #     self.selectionChanged.emit([], deselected_links)

    def graphController(self) -> BaseGraphController|None:
        return self._graph_controller
        
    def selectedIndexes(self) -> List[NodeT|LinkT]:
        return self._selected_items

    def select(self, selection:list, command:QItemSelectionModel.SelectionFlag=QItemSelectionModel.SelectionFlag.Select):
        # Store old selection for comparison
        print(f"Selection command: {command}, selection: {selection}, command flags: {QItemSelectionModel.SelectionFlag(command)}")
        # Apply selection logic
        deselected_items:list = list()
        selected_items:list = list()

        # Clear old selection if requested
        if command & QItemSelectionModel.SelectionFlag.Clear:
            for idx in self._selected_items:
                deselected_items.append(idx)
            self._selected_items = list() # clear selection by creating a new empty selection object, to preserve any references to the old selection object that may be held by views or other controllers
            # self.selectionChanged.emit(set(), old_selection)
            # return
        
        if command & QItemSelectionModel.SelectionFlag.Select:
            for idx in selection:
                if idx not in self._selected_items:
                    self._selected_items.append(idx)
                    selected_items.append(idx)

        elif command & QItemSelectionModel.SelectionFlag.Deselect:
            for idx in selection:
                if idx in self._selected_items:
                    self._selected_items.remove(idx)
                    deselected_items.append(idx)

        elif command & QItemSelectionModel.SelectionFlag.Toggle:
            for idx in selection:
                if idx in self._selected_items:
                    self._selected_items.remove(idx)
                    deselected_items.append(idx)
                else:
                    self._selected_items.append(idx)
                    selected_items.append(idx)

        # Update current if requested
        if command & QItemSelectionModel.SelectionFlag.Current and len(selection) > 0:
            self.setCurrentIndex(selection[0])
        
        # Emit selectionChanged signal if selection actually changed
        if len(selected_items)>0 or len(deselected_items)>0:
            self.selectionChanged.emit(selected_items, deselected_items)

    def clearSelection(self):
        if len(self._selected_items) > 0:
            deselected_items = self._selected_items.copy()
            self._selected_items = []
            self.selectionChanged.emit([], deselected_items)

        self.setCurrentIndex(None)

    def currentIndex(self) -> NodeT|None:
        return self._current_item

    def setCurrentIndex(self, index:NodeT|None, command:QItemSelectionModel.SelectionFlag=QItemSelectionModel.SelectionFlag.Current):
        self._current_item = index
        
