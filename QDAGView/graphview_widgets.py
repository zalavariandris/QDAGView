from typing import *
from qtpy.QtGui import *
from qtpy.QtCore import *
from qtpy.QtWidgets import *

from utils.geo import makeLineBetweenShapes, makeLineToShape, makeArrowShape, getShapeCenter



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

    def displayText(self):
        label = self.widget()  # Ensure the widget is created
        return label.text() if label else ""

    def setDisplayText(self, text:str):
        label = self.widget()  # Ensure the widget is created
        label.setText(text)


class BaseRowWidget(QGraphicsWidget):
    def __init__(self, parent: QGraphicsItem | None = None):
        super().__init__(parent=parent)
        # create layout
        layout = QGraphicsLinearLayout(Qt.Orientation.Vertical)
        self.setLayout(layout)
        layout.updateGeometry()        
        
    def insertCell(self, pos:int, cell:CellWidget):
        layout = cast(QGraphicsLinearLayout, self.layout())
        layout.insertItem(pos, cell)
        layout.setStretchFactor(cell, 1)
        layout.setAlignment(cell, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)

    def removeCell(self, cell:CellWidget):
        layout = cast(QGraphicsLinearLayout, self.layout())
        layout.removeItem(cell)

    def paint(self, painter, option, /, widget:QWidget|None = None):
        painter.setBrush(QColor("lightblue"))
        painter.drawRect(option.rect)


class PortWidget(BaseRowWidget):
    scenePositionChanged = Signal(QPointF)
    def __init__(self, parent: QGraphicsItem | None = None):
        super().__init__(parent=parent)
        self._links:List[LinkWidget] = []
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsScenePositionChanges, True)

    def itemChange(self, change, value):
        match change:
            case QGraphicsItem.GraphicsItemChange.ItemScenePositionHasChanged:
                if self.scene():
                    # Emit signal when position changes
                    self.scenePositionChanged.emit(value)

                    # Update all links connected to this port
                    for link in self._links:
                        link.updateLine()

                    
        return super().itemChange(change, value)

    def paint(self, painter, option, /, widget = ...):
        # return
        painter.setBrush(self.palette().alternateBase())
        painter.drawRect(option.rect)


class InletWidget(PortWidget):
    def __init__(self, parent: QGraphicsItem | None = None):
        super().__init__(parent=parent)
        self.setAcceptDrops(True)

    # def paint(self, painter:QPainter, option, /, widget:QWidget|None = None):
    #     # return
    #     painter.setBrush(QColor("lightblue"))
    #     painter.drawRect(option.rect)
    

class OutletWidget(PortWidget):
    def __init__(self, parent: QGraphicsItem | None = None):
        super().__init__(parent=parent)
        self.setAcceptDrops(True)

    # def paint(self, painter, option, /, widget:QWidget|None = None):
    #     return
    #     painter.setBrush(QColor("purple"))
    #     painter.drawRect(option.rect)


class NodeWidget(BaseRowWidget):
    def __init__(self, parent: QGraphicsItem | None = None):
        super().__init__(parent=parent)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)

        layout = cast(QGraphicsLinearLayout, self.layout())
        layout.setOrientation(Qt.Orientation.Vertical)

        self._cells_layout = QGraphicsLinearLayout(Qt.Orientation.Vertical)
        layout.addItem(self._cells_layout)

        ports_layout = QGraphicsLinearLayout(Qt.Orientation.Horizontal)
        layout.addItem(ports_layout)

        self._inlets_layout = QGraphicsLinearLayout(Qt.Orientation.Vertical)
        self._outlets_layout = QGraphicsLinearLayout(Qt.Orientation.Vertical)
        ports_layout.addItem(self._inlets_layout)
        ports_layout.addItem(self._outlets_layout)

    def insertInlet(self, pos: int, inlet: InletWidget):
        layout = self._inlets_layout
        layout.insertItem(pos, inlet)

    def removeInlet(self, inlet:InletWidget):
        layout = self._inlets_layout
        layout.removeItem(inlet)

    def insertOutlet(self, pos: int, outlet: OutletWidget):
        layout = self._outlets_layout
        layout.insertItem(pos, outlet)

    def removeOutlet(self, outlet: OutletWidget):
        layout = self._outlets_layout
        layout.removeItem(outlet)

    def insertCell(self, pos, cell):
        layout = self._cells_layout
        layout.insertItem(pos, cell)
    
    def removeCell(self, cell):
        layout = self._cells_layout
        layout.removeItem(cell)

    def paint(self, painter: QPainter, option: QStyleOption, widget=None):
        rect = option.rect       
        painter.setBrush(self.palette().alternateBase())
        if self.isSelected():
            painter.setBrush(self.palette().highlight())
        painter.drawRoundedRect(rect, 6, 6)

        
class LinkWidget(BaseRowWidget):
    def __init__(self, parent: QGraphicsItem | None = None):
        super().__init__(parent=parent)
        # self.setZValue(-1)  # Ensure links are drawn below nodes
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self._line = QLineF(0, 0, 100, 100)
        self._label = QLabel("Link")
        self._source: QGraphicsItem | None = None
        self._target: QGraphicsItem | None = None
        self.setAcceptHoverEvents(True)
        # self.layout().
    
    def insertCell(self, pos:int, cell:CellWidget):
        layout = cast(QGraphicsLinearLayout, self.layout())
        layout.insertItem(pos, cell)
        layout.setStretchFactor(cell, 0)  # Don't stretch the cell
        layout.setAlignment(cell, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)

    def removeCell(self, cell:CellWidget):
        layout = cast(QGraphicsLinearLayout, self.layout())
        layout.removeItem(cell)
        
    def line(self)->QLineF:
        """Get the line of the link widget."""
        return self._line
    
    def setLine(self, line:QLineF):
        """Set the line of the link widget."""
        
        self.prepareGeometryChange()
        self._line = line

        self.layout().setGeometry(QRectF(
            line.p1(), line.p2()
        ).normalized())

        self.update()

    def boundingRect(self):
        _ = QRectF(self._line.p1(), self._line.p2())
        _ = _.normalized()
        _ = _.adjusted(-5,-5,5,5)
        return _
    
    def shape(self)->QPainterPath:
        path = QPainterPath()
        path.moveTo(self._line.p1())
        path.lineTo(self._line.p2())
        stroker = QPainterPathStroker()
        stroker.setWidth(4)
        return stroker.createStroke(path)
    
    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget=None):

        if self.isSelected():
            painter.setBrush(self.palette().accent())
        elif option.state & QStyle.StateFlag.State_MouseOver:
            painter.setBrush(Qt.red)
        else:
            painter.setBrush(self.palette().text())
        painter.setPen(Qt.PenStyle.NoPen)
        arrow = makeArrowShape(self._line, 2)
        painter.drawPath(arrow)

    # def link(self, source:QGraphicsItem|None, target:QGraphicsItem|None):
    #     """Link this widget to a source and target item."""
    #     self.unlink()  # Unlink any existing connections
    #     self._source = source
    #     self._target = target
    #     if source:
    #         source._links.append(self)
    #     if target:
    #         target._links.append(self)
    #     self.updateLine()
    #     self.update()

    # def unlink(self):
    #     """Unlink this widget from its source and target items."""
    #     if self._source:
    #         self._source._links.remove(self)
    #         self._source = None
    #     if self._target:
    #         self._target._links.remove(self)
    #         self._target = None
    #     self.updateLine()
    #     self.update()

    def updateLine(self):
        if self._source and self._target:
            line = makeLineBetweenShapes(self._source, self._target)
            line = QLineF(self.mapFromScene(line.p1()), self.mapFromScene(line.p2()))
            self.setLine(line)

        elif self._source:
            source_center = getShapeCenter(self._source)
            source_size = self._source.boundingRect().size()
            origin = QPointF(source_center.x() - source_size.width()/2, source_center.y() - source_size.height()/2)+QPointF(24,24)
            line = makeLineToShape(origin, self._source) 
            line = QLineF(self.mapFromScene(line.p1()), self.mapFromScene(line.p2()))
            line = QLineF(line.p2(), line.p1())  # Reverse the line direction
            self.setLine(line)

        elif self._target:
            target_center = getShapeCenter(self._target)
            target_size = self._target.boundingRect().size()
            origin = QPointF(target_center.x() - target_size.width()/2, target_center.y() - target_size.height()/2)-QPointF(24,24)
            line = makeLineToShape(origin, self._target)
            line = QLineF(self.mapFromScene(line.p1()), self.mapFromScene(line.p2()))
            self.setLine(line)
        else:
            ...
