# Cell manager using persistent model indexes
from typing import List
from qtpy.QtCore import *
from qtpy.QtWidgets import *


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

    def clear(self):
        self._cells.clear()

    def cells(self) -> List[QWidget]:
        return list(self._cells.values())
