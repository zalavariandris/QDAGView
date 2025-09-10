from typing import *
from qtpy.QtGui import *
from qtpy.QtCore import *
from qtpy.QtWidgets import *


class CellWidget(QGraphicsProxyWidget):
    def __init__(self, parent: QGraphicsItem | None = None):
        super().__init__(parent=parent)
        self._label = QLabel("")
        self._label.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        # self._label.setStyleSheet("background: orange;")
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        self.setWidget(self._label)
        # self.setAutoFillBackground(False)
        
        # Make CellWidget transparent to drag events so parent can handle them
        # self.setAcceptDrops(False)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)

    def setEditorWidget(self, editor: QWidget | None):
        if editor is None:
            editor = self._label
        else:
            # Ensure the editor is not parented elsewhere
            if editor.parent() is not None:
                editor.setParent(None)
        self.setWidget(editor)

    def text(self):
        label = self.widget()
        return label.text() if label else ""

    def setText(self, text:str):
        label = self.widget()
        label.setText(text)
        