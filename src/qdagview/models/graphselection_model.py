
from __future__ import annotations

import logging
from abc import ABC, ABCMeta, abstractmethod
from typing import Literal, TypeVar, Generic, List, Tuple, Any

from qtpy.QtGui import *
from qtpy.QtCore import *
from qtpy.QtWidgets import *

from ..core import GraphItemType

logger = logging.getLogger(__name__)

from ..models import AbstractGraphModel
from ..models.abstract_graphmodel import GraphItemRef
from typing import Set

class GraphSelectionModel(QObject):
    selectionChanged = Signal(list) # selected: Set[GraphItemRef], deselected: Set[GraphItemRef]
    currentChanged = Signal(GraphItemRef | None, GraphItemRef | None) # current: GraphItemRef | None, previous: GraphItemRef | None

    def select(self, item: Set[GraphItemRef], command:QItemSelectionModel.SelectionFlag=QItemSelectionModel.SelectionFlag.Select):
        if self._model is None:
            return
        
        match command:
            case QItemSelectionModel.SelectionFlag.Clear:
                if len(self._selection) > 0:
                    self._selection = set()
                    self.selectionChanged.emit([], [])
                else:
                    self.selectionChanged.emit([], [])

            case QItemSelectionModel.SelectionFlag.Toggle:
                selected = set()
                deselected = set()
                for it in item:
                    if it in self._selection:
                        self._selection.remove(it)
                        deselected.add(it)
                    else:
                        self._selection.add(it)
                        selected.add(it)
                if len(selected) > 0 or len(deselected) > 0:
                    self.selectionChanged.emit(list(selected), list(deselected))
            case QItemSelectionModel.SelectionFlag.Select:
                selected = set()
                deselected = set()
                for it in item:
                    if it not in self._selection:
                        self._selection.add(it)
                        selected.add(it)
                for it in list(self._selection):
                    if it not in item:
                        self._selection.remove(it)
                        deselected.add(it)
                if len(selected) > 0 or len(deselected) > 0:
                    self.selectionChanged.emit(list(selected), list(deselected))
            case QItemSelectionModel.SelectionFlag.SelectCurrent:
                previous = self.currentRef()
                new_current = next(iter(item)) if len(item) > 0 else None
                if previous != new_current:
                    self._selection = set()
                    if new_current is not None:
                        self._selection.add(new_current)
                    self.currentChanged.emit(new_current, previous)
                    self.selectionChanged.emit(list(self._selection), [])
            case _:
                logger.warning(f"Unsupported selection action: {command}")

    def hasSelection(self) -> bool:
        return len(self._selection) > 0
    
    def currentRef(self) -> GraphItemRef | None:
        if len(self._selection) > 0:
            return next(iter(self._selection))
        return None
    
    def selectedRefs(self) -> List[GraphItemRef]:
        return list(self._selection)

    def model(self) -> AbstractGraphModel:
        return self._model
    
    def setModel(self, model: AbstractGraphModel):
        if self._model is not None:
            self._model.modelReset.disconnect(self.clearSelection)
            self._model.rowsRemoved.disconnect(self.onRowsRemoved)
        self._model = model
        if self._model is not None:
            self._model.modelReset.connect(self.clearSelection)
            self._model.rowsRemoved.connect(self.onRowsRemoved)
        self.clearSelection()
    
    def isSelected(self, item: GraphItemRef) -> bool:
        return item in self._selection
    
    def clearCurrent(self):
        if len(self._selection) > 0:
            self._selection = set()
            self.selectionChanged.emit()

    def clearSelection(self):
        if len(self._selection) > 0:
            self._selection = set()
            self.selectionChanged.emit()

    def clear(self):
        self.clearSelection()
    
