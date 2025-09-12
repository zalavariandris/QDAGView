from typing import *
from qtpy.QtGui import *
from qtpy.QtCore import *
from qtpy.QtWidgets import *

if TYPE_CHECKING:
    from ..graphview_delegate import GraphDelegate


class CellWidget(QGraphicsTextItem):
    def __init__(self, parent: QGraphicsItem | None = None):
        super().__init__("port", parent=parent)

        # Make CellWidget transparent to drag events so parent can handle them
        # self.setAcceptDrops(False)
        font = self.font()
        font.setPointSize(8)
        self.setFont(font)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
    
    def setEditorWidget(self, editor: QWidget | None):
        raise NotImplementedError
        # if editor is None:
        #     editor = self._label
        # else:
        #     # Ensure the editor is not parented elsewhere
        #     if editor.parent() is not None:
        #         editor.setParent(None)
        # self.setWidget(editor)

    def text(self):
        return self.toPlainText()

    def setText(self, text:str):
        self.setPlainText(text)

    def boundingRect(self):
        return super().boundingRect()
    
    def paint(self, painter:QPainter, option, /, widget:QWidget|None = None):
        # painter.setBrush(QColor(100,100,200,50))
        # painter.drawRect(option.rect)
        super().paint(painter, option, widget)
        