from __future__ import annotations

import logging
logger = logging.getLogger(__name__)

from typing import *

from qtpy.QtGui import *
from qtpy.QtCore import *
from qtpy.QtWidgets import *

from ...core import GraphDataRole, GraphItemType
from ...utils import makeArrowShape

class GraphDelegate(QObject):
    ## Painting
    def paintNode(self, painter:QPainter, option:QStyleOptionViewItem, index: QModelIndex|QPersistentModelIndex):
        ...

    def paintInlet(self, painter:QPainter, option:QStyleOptionViewItem, index: QModelIndex|QPersistentModelIndex):
        ...

    def paintOutlet(self, painter:QPainter, option:QStyleOptionViewItem, index: QModelIndex|QPersistentModelIndex):
        ...

    def paintLink(self, painter:QPainter, option:QStyleOptionViewItem, index: QModelIndex|QPersistentModelIndex):
        ...

    def paintCell(self, painter:QPainter, option:QStyleOptionViewItem, index: QModelIndex|QPersistentModelIndex):
        ...

    ## Editors
    def createEditor(self, parent:QWidget, option:QStyleOptionViewItem, index:QModelIndex|QPersistentModelIndex) -> QWidget:
        editor = QLineEdit(parent=parent)
        editor.setParent(parent)
        return editor
    
    def updateEditorGeometry(self, editor:QWidget, option:QStyleOptionViewItem, index:QModelIndex|QPersistentModelIndex):
        print("updateEditorGeometry", option.rect)
        editor.setGeometry(option.rect)
        
    def setEditorData(self, editor:QWidget, index:QModelIndex|QPersistentModelIndex):
        if isinstance(editor, QLineEdit):
            text = index.data(Qt.ItemDataRole.DisplayRole)
            editor.setText(text)
    
    def setModelData(self, editor:QWidget, model:QAbstractItemModel, index:QModelIndex|QPersistentModelIndex):
        if isinstance(editor, QLineEdit):
            text = editor.text()
            model.setData(index, text, Qt.ItemDataRole.EditRole)
        else:
            raise TypeError(f"Editor must be a QLineEdit, got {type(editor)} instead.")

