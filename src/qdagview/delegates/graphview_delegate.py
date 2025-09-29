from __future__ import annotations

from ctypes import alignment
import logging

from qdagview.controllers.qitemmodel_graphcontroller import QItemModelGraphController
logger = logging.getLogger(__name__)

from typing import *

from qtpy.QtGui import *
from qtpy.QtCore import *
from qtpy.QtWidgets import *

from ..core import GraphDataRole, GraphItemType
from ..utils import makeArrowShape

class GraphDelegate(QObject):
    ## Painting
    def paintNode(self, painter:QPainter, option:QStyleOptionViewItem, index: QModelIndex|QPersistentModelIndex):
        # Access palette from the option (preferred)
        palette = option.palette

        # Pick base color depending on selection state
        if option.state & QStyle.State_Selected:
            bg_color = palette.highlight()
        else:
            bg_color = palette.alternateBase()
        
        # Paint background
        painter.save()
        painter.setBrush(bg_color)
        painter.drawRoundedRect(option.rect, 6, 6)
        painter.restore()

    def paintInlet(self, painter:QPainter, option:QStyleOptionViewItem, index: QModelIndex|QPersistentModelIndex):
        palette = option.palette
        if option.state & QStyle.State_MouseOver:
            bg_color = palette.highlight()
        else:
            bg_color = palette.alternateBase()
        painter.setBrush(bg_color)
        painter.drawEllipse(option.rect)

    def paintOutlet(self, painter:QPainter, option:QStyleOptionViewItem, index: QModelIndex|QPersistentModelIndex):
        palette = option.palette
        if option.state & QStyle.State_MouseOver:
            bg_color = palette.highlight()
        else:
            bg_color = palette.alternateBase()
        painter.setBrush(bg_color)
        painter.drawEllipse(option.rect)

    def paintLink(self, painter:QPainter, option:QStyleOptionViewItem, index: QModelIndex|QPersistentModelIndex):
        # Get the rectangle to draw in

        # TODO: Mimicing the QItemDelegate currently has issues when drawing the link.
        # eg: QStyleOptionViewItem.rect is integer based. therefore the movement of the link is not smooth.
        # Consider using a more precise representation for the link's position and size, but how?
        # so this should be refined later. using a simple delegate is not ideal.
        # or the position of the link should be done in the view, to handle subpixel rendering.
        # or the view could have a special delegate for links only.
        # and only the cell painting is done here.

        # adjust for padding
        rect = QRect(option.rect).adjusted(5,5,-5,-5)

        # Get alignment from option
        alignment = option.decorationAlignment

        # Create line based on decoration alignment
        if alignment & Qt.AlignmentFlag.AlignBottom and alignment & Qt.AlignmentFlag.AlignRight:
            line = QLineF(QPointF(rect.topLeft()), QPointF(rect.bottomRight()))
        elif alignment & Qt.AlignmentFlag.AlignBottom and alignment & Qt.AlignmentFlag.AlignLeft:
            line = QLineF(QPointF(rect.topRight()), QPointF(rect.bottomLeft()))
        elif alignment & Qt.AlignmentFlag.AlignTop and alignment & Qt.AlignmentFlag.AlignRight:
            line = QLineF(QPointF(rect.bottomLeft()), QPointF(rect.topRight()))
        elif alignment & Qt.AlignmentFlag.AlignTop and alignment & Qt.AlignmentFlag.AlignLeft:
            line = QLineF(QPointF(rect.bottomRight()), QPointF(rect.topLeft()))
        else:
            line = QLineF(QPointF(rect.topLeft()), QPointF(rect.bottomRight()))  # Default
        
        # Pick color based on state
        palette = option.palette
        if option.state & QStyle.StateFlag.State_Selected:
            color = palette.highlight()
        elif option.state & QStyle.StateFlag.State_MouseOver:
            color = palette.brightText()
        else:
            color = palette.text()
        
        # Paint the arrow
        painter.save()
        painter.setBrush(color)
        painter.setPen(Qt.PenStyle.NoPen)
        
        # Use the existing makeArrowShape utility
        arrow_path = makeArrowShape(line, width=2.0)
        painter.drawPath(arrow_path)
        
        painter.restore()

    def paintCell(self, painter:QPainter, option:QStyleOptionViewItem, controller:QItemModelGraphController, index: QModelIndex|QPersistentModelIndex):
        # Paint background
        painter.save()
        painter.drawText(option.rect, Qt.AlignmentFlag.AlignCenter, controller.attributeData(index, Qt.ItemDataRole.DisplayRole))
        painter.restore()

    ## Editors
    def createEditor(self, parent:QWidget, option:QStyleOptionViewItem, controller:QItemModelGraphController, index:QModelIndex|QPersistentModelIndex) -> QWidget:
        editor = QLineEdit(parent=parent)
        editor.setParent(parent)
        return editor
    
    def updateEditorGeometry(self, editor:QWidget, option:QStyleOptionViewItem, index:QModelIndex|QPersistentModelIndex):
        print("updateEditorGeometry", option.rect)
        editor.setGeometry(option.rect)
        
    def setEditorData(self, editor:QWidget, controller:QItemModelGraphController , index:QModelIndex|QPersistentModelIndex):
        if isinstance(editor, QLineEdit):
            text = controller.attributeData(index, Qt.ItemDataRole.DisplayRole)
            editor.setText(text)
    
    def setModelData(self, editor:QWidget, controller:QItemModelGraphController, index:QModelIndex|QPersistentModelIndex):
        if isinstance(editor, QLineEdit):
            text = editor.text()
            controller.setAttributeData(index, text, Qt.ItemDataRole.EditRole)
        else:
            raise TypeError(f"Editor must be a QLineEdit, got {type(editor)} instead.")

