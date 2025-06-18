#####################
# The Network Scene #
#####################

#
# A Graph view that directly connects to QStandardItemModel
#
from __future__ import annotations
import traceback

from enum import Enum
from typing import *
from PySide6.QtGui import *
from PySide6.QtCore import *
from PySide6.QtWidgets import *

from collections import defaultdict
from bidict import bidict

from utils import group_consecutive_numbers
from utils.geo import makeLineBetweenShapes, makeLineToShape, makeArrowShape
# from pylive.utils.geo import makeLineBetweenShapes, makeLineToShape
# from pylive.utils.qt import distribute_items_horizontal
# from pylive.utils.unique import make_unique_name
# from pylive.utils.diff import diff_set

import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


from core import GraphDataRole, GraphItemType, GraphMimeData
from graphadapter import GraphAdapter


class GraphView(QGraphicsView):
    class State(Enum):
        IDLE = "IDLE"
        LINKING = "LINKING"
        
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent=parent)
        self._adapter:GraphAdapter | None = None
        self._adapter_connections = []
        self._selection:QItemSelectionModel | None = None
        self._selection_connections:List[Tuple[Signal, Callable]] = []
        # store model widget relations
        self._widgets: bidict[QPersistentModelIndex, NodeWidget] = bidict()
        self._draft_link: QGraphicsLineItem | None = None

        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setCacheMode(QGraphicsView.CacheModeFlag.CacheNone)
        self.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        scene = QGraphicsScene()
        scene.setSceneRect(QRectF(-9999, -9999, 9999 * 2, 9999 * 2))
        self.setScene(scene)
        self.setAcceptDrops(True)

    def indexFromWidget(self, widget:NodeWidget) -> QPersistentModelIndex:
        """
        Get the index of the node widget in the model.
        This is used to identify the node in the model.
        """
        return QPersistentModelIndex(self._widgets.inverse[widget])
    
    def widgetFromIndex(self, index:QModelIndex) -> NodeWidget:
        """
        Get the widget from the index.
        This is used to identify the node in the model.
        """
        return self._widgets[QPersistentModelIndex(index)]

    def setAdapter(self, adapter:GraphAdapter):
        if self._adapter_connections:
            for signal, slot in self._adapter_connections:
                signal.disconnect(slot)
            self._adapter_connections = []
            self._adapter.setSourceModel(None)
            self._adapter = None
        
        if adapter:
            assert isinstance(adapter, GraphAdapter), "Model must be a subclass of QAbstractItemModel"

            self._adapter_connections = [
                (adapter.nodeAdded, self._add_node_widget),
                (adapter.nodeAboutToBeRemoved, self._remove_node_widget),
                (adapter.inletAdded, self._add_inlet_widget),
                (adapter.inletAboutToBeRemoved, self._remove_inlet_widget),
                (adapter.outletAdded, self._add_outlet_widget),
                (adapter.outletAboutToBeRemoved, self._remove_outlet_widget),
                (adapter.linkAdded, self._add_link_widget),
                (adapter.linkAboutToBeRemoved, self._remove_link_widget),
                (adapter.dataChanged, self._set_data)
            ]

            for signal, slot in self._adapter_connections:
                signal.connect(slot)
        self._adapter = adapter
        
        # populate initial scene
        ## clear
        self.scene().clear()
        self._widgets.clear()
        if self._adapter:
            for node in self._adapter.nodes():
                self._add_node_widget(node)
                for inlet in self._adapter.inlets(node):
                    self._add_inlet_widget(inlet)
                for outlet in self._adapter.outlets(node):
                    self._add_outlet_widget(outlet)

    def adapter(self) -> GraphAdapter | None:
        return self._adapter
    
    # # Selection
    def setSelectionModel(self, selection: QItemSelectionModel):
        """
        Set the selection model for the graph view.
        This is used to synchronize the selection of nodes in the graph view
        with the selection model.
        """
        assert isinstance(selection, QItemSelectionModel), f"got: {selection}"
        assert self._adapter, "Model must be set before setting the selection model!"
        assert selection.model() == self._adapter.sourceModel(), "Selection model must be for the same model as the graph view!"
        if self._selection:
            for signal, slot in self._selection_connections:
                signal.disconnect(slot)
            self._selection_connections = []
        
        if selection:
            self._selection_connections = [
                (selection.selectionChanged, self.onSelectionChanged)
            ]
            for signal, slot in self._selection_connections:
                signal.connect(slot)

        self._selection = selection
    
        self.scene().selectionChanged.connect(self.updateSelectionModel)

    def selectionModel(self) -> QItemSelectionModel | None:
        """
        Get the current selection model for the graph view.
        This is used to synchronize the selection of nodes in the graph view
        with the selection model.
        """
        return self._selection
    
    @Slot(QItemSelection, QItemSelection)
    def onSelectionChanged(self, selected:QItemSelection, deselected:QItemSelection):
        """
        Handle selection changes in the selection model.
        This updates the selection in the graph view.
        """
        assert self._selection, "Selection model must be set before handling selection changes!"
        assert self._adapter, "Model must be set before handling selection changes!"
        assert self._selection.model() == self._adapter.sourceModel(), "Selection model must be for the same model as the graph view!"
        scene = self.scene()
        scene.blockSignals(True)
        
        for index in deselected.indexes():
            widget = self._widgets[QPersistentModelIndex(index.siblingAtColumn(0))]
            widget.setSelected(False)
            # widget.update()

        for index in selected.indexes():
            widget = self._widgets[QPersistentModelIndex(index.siblingAtColumn(0))]
            widget.setSelected(True)
            # widget.update()
        scene.blockSignals(False)

    def updateSelectionModel(self):
        """update selection model from scene selection"""
        if self._adapter and self._selection:
            # get currently selected widgets
            selected_widgets = self.scene().selectedItems()

            # map widgets to QModelIndexes
            selected_indexes = map(lambda widget: self._widgets.inverse.get(widget, None), selected_widgets)
            selected_indexes = filter(lambda idx: idx is not None and idx.isValid(), selected_indexes)
            
            assert self._adapter
            assert self._adapter._sourceModel, "Source model must be set before mapping selection"
            def selectionFromIndexes(selected_indexes:Iterable[QPersistentModelIndex]) -> QItemSelection:
                """Create a QItemSelection from a list of selected indexes."""
                item_selection = QItemSelection()
                for index in selected_indexes:
                    if index.isValid():
                        item_selection.select(index, index)
                return item_selection

            # perform selection on model
            item_selection = selectionFromIndexes(selected_indexes)
            self._selection.select(item_selection, QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows)
            if len(item_selection.indexes()) > 0:
                last_selected_index = item_selection.indexes()[-1]
                self._selection.setCurrentIndex(
                    last_selected_index,
                    QItemSelectionModel.SelectionFlag.Current | QItemSelectionModel.SelectionFlag.Rows
                )
    # Manage Widgets
    def _add_node_widget(self, index:QPersistentModelIndex):
        #add widget to view
        assert isinstance(index, QPersistentModelIndex), f"Index must be a QPersistentModelIndex, got: {index}"
        assert index.column()==0, "Index must be in the first column"
        widget = NodeWidget(graphview=self)
        self._widgets[index] = widget
        self._set_data(index, 0)

        # attach to scene or parent widget
        if index.parent().isValid():
            raise NotImplementedError()
        else:
            self.scene().addItem(widget)
        return widget

    def _add_inlet_widget(self, index:QPersistentModelIndex):
        #add widget to view
        assert isinstance(index, QPersistentModelIndex), "Index must be a QPersistentModelIndex"
        assert index.column()==0, "Index must be in the first column"
        # add widget
        widget = InletWidget(graphview=self)
        self._widgets[index] = widget
        self._set_data(index, 0)

        # attach to parent widget
        if index.parent().isValid():
            parent_widget = self._widgets[QPersistentModelIndex(index.parent())]
            if not isinstance(parent_widget, NodeWidget):
                raise ValueError("inlets must have a Node parent")
            parent_widget = cast(NodeWidget, parent_widget)
            parent_widget.addInlet(widget)
        else:
            raise NotImplementedError("root graph inlets are not yet implemented!")
        
    def _add_outlet_widget(self, index:QPersistentModelIndex):
        """add widget to view"""
        assert isinstance(index, QPersistentModelIndex), "Index must be a QPersistentModelIndex"
        assert index.column()==0, "Index must be in the first column"
        widget = OutletWidget(graphview=self)
        self._widgets[index] = widget
        self._set_data(index, 0)

        # attach to parent widget
        self.scene().addItem(widget)
        if index.parent().isValid():
            parent_widget = self._widgets[QPersistentModelIndex(index.parent())]
            parent_widget = cast(NodeWidget, parent_widget)
            parent_widget.addOutlet(widget)

    def _add_link_widget(self, index:QPersistentModelIndex):
        """
        Try to add a link widget to the graph view.
        """
        assert isinstance(index, QPersistentModelIndex), "Index must be a QPersistentModelIndex"
        assert index.column()==0, "Index must be in the first column"

        link_widget = LinkWidget(graphview=self)
        self._widgets[index] = link_widget
        self.scene().addItem(link_widget)
        source_index = self._adapter.linkSource(index)
        source_outlet = self._widgets[QPersistentModelIndex(source_index)] if source_index.isValid() else None
        target_index = self._adapter.linkTarget(index)
        target_inlet = self._widgets[QPersistentModelIndex(target_index)] if target_index.isValid() else None
        link_widget.link(source_outlet, target_inlet)

    def _remove_node_widget(self, index:QPersistentModelIndex):
        """Remove a node widget"""
        assert isinstance(index, QPersistentModelIndex), "Index must be a QPersistentModelIndex"
        assert index.column()==0, "Index must be in the first column"
        
        # Remove all cell widgets for this node
        self._remove_cell_widgets(index.row(), index.parent() )

        # remove widget from graphview
        widget = self._widgets[index]
        del self._widgets[index]
        
        # detach from scene or parent widget
        if index.parent().isValid():
            raise NotImplementedError()
        else:
            self.scene().removeItem(widget)
        
    def _remove_inlet_widget(self, index:QPersistentModelIndex):
        """Remove an inlet widget and its associated cell widgets."""
        assert isinstance(index, QPersistentModelIndex), "Index must be a QPersistentModelIndex"
        assert index.column()==0, "Index must be in the first column"
        # Remove all cell widgets for this inlet
        self._remove_cell_widgets(index.row(), index.parent() )
        
        # remove widget from graphview
        widget = self._widgets[index]
        del self._widgets[index]

        # detach widget from scene (or parent widget)
        if index.parent().isValid():
            parent_widget = self._widgets[QPersistentModelIndex(index.parent())]
            parent_widget = cast(NodeWidget, parent_widget)
            parent_widget.removeInlet(widget)
        else:
            raise NotImplementedError("support inlets attached to the root graph")

    def _remove_outlet_widget(self, index:QPersistentModelIndex):
        """Remove an outlet widget and its associated cell widgets."""
        assert isinstance(index, QPersistentModelIndex), "Index must be a QPersistentModelIndex"
        assert index.column()==0, "Index must be in the first column"
        
        # remove widget from graphview
        widget = self._widgets[index]
        del self._widgets[index]
        
        # detach widget from scene (or parent widget)
        if index.parent().isValid():
            parent_widget = self._widgets[QPersistentModelIndex(index.parent())]
            parent_widget = cast(NodeWidget, parent_widget)
            parent_widget.removeOutlet(widget)
        else:
            raise NotImplementedError("support inlets attached to the root graph")
        
    def _remove_link_widget(self, index:QPersistentModelIndex):
        """Remove an inlet widget and its associated cell widgets."""
        assert isinstance(index, QPersistentModelIndex), "Index must be a QPersistentModelIndex"
        assert index.column()==0, "Index must be in the first column"
        widget = self._widgets[index]
        # detach widget from scene (or parent widget)
        link_widget = cast(LinkWidget, widget)
        
        # link_widget.deleteLater()  # Schedule for deletion
        link_widget.setParentItem(None)
        self.scene().removeItem(link_widget)

        # Remove all cell widgets for this inlet
        # self._remove_cell_widgets(index.row(), index.parent())
        
        # remove widget from graphview
        
        assert isinstance(widget, LinkWidget), "Link widget must be of type LinkWidget"
        del self._widgets[index]

        self.scene().removeItem(link_widget)  # Remove from scene immediately

    def _set_data(self, index:QPersistentModelIndex, column:int, roles:list=[]):
        """Set the data for a node widget."""
        assert isinstance(index, QPersistentModelIndex), "Index must be a QPersistentModelIndex"
        assert index.column() == 0, "Index must be in the first column"
        assert index in self._widgets, f"Index {index} not found in row widgets"

        widget = self._widgets[index]
        widget.setLabel(index.data(Qt.ItemDataRole.DisplayRole))
        # if not isinstance(widget, NodeWidget):
        #     raise ValueError(f"Widget for index {index} is not a NodeWidget")
        
        # # update cell widgets
        # cell_index = index.sibling(index.row(), column)
        # widget = self._cell_widgets[QPersistentModelIndex(cell_index)]
        # proxy = cast(QGraphicsProxyWidget, widget)
        # label = proxy.widget()
        # assert isinstance(label, QLabel)
        # label.setText(cell_index.data(Qt.ItemDataRole.DisplayRole))

    def _createDraftLink(self):
        """Safely create draft link with state tracking"""
        assert self._draft_link is None
            
        self._draft_link = QGraphicsLineItem()
        self._draft_link.setPen(QPen(self.palette().text(), 1))
        self.scene().addItem(self._draft_link)

    def updateDraftLink(self, source:QGraphicsItem|QPointF, target:QGraphicsItem|QPointF):
        """Update the draft link to connect source and target items"""
        assert self._draft_link, "Draft link must be created before updating"
        line = makeLineBetweenShapes(source, target)
        self._draft_link.setLine(line)
 
    def _cleanupDraftLink(self):
        """Safely cleanup draft link"""
        if self._draft_link is None:
            return
        
        self.scene().removeItem(self._draft_link)
        self._draft_link = None

    def dragEnterEvent(self, event)->None:
        if event.mimeData().hasFormat(GraphMimeData.InletData) or event.mimeData().hasFormat(GraphMimeData.OutletData):
            # Create a draft link if the mime data is for inlets or outlets
            self._createDraftLink()
            event.acceptProposedAction()
        if event.mimeData().hasFormat(GraphMimeData.LinkHeadData) or event.mimeData().hasFormat(GraphMimeData.LinkTailData):
            # Create a draft link if the mime data is for link heads or tails
            event.acceptProposedAction()

    def dragMoveEvent(self, event)->None:
        """Handle drag move events to update draft link position"""
        drop_target_index = self.indexAt(event.position().toPoint())
        if self._adapter.canDropMimeData(event.mimeData(), event.dropAction(), drop_target_index):
            if event.mimeData().hasFormat(GraphMimeData.OutletData):
                # Outlet dragged
                outlet_index = self._adapter.decodeOutletMimeData(event.mimeData())
                assert outlet_index.isValid(), "Outlet index must be valid"
                outlet_widget = self._widgets[outlet_index]
                if self._adapter.itemType(drop_target_index) == GraphItemType.INLET:
                    # ...over inlet
                    inlet_widget = self._widgets[drop_target_index]
                    self.updateDraftLink(source=outlet_widget, target=inlet_widget)
                    event.acceptProposedAction()
                    return
                else:
                    # ...over empty space
                    self.updateDraftLink(source=outlet_widget, target=self.mapToScene(event.position().toPoint()))
                    event.acceptProposedAction() 
                    return
            
            if event.mimeData().hasFormat(GraphMimeData.InletData):
                # inlet dragged
                inlet_index = self._adapter.decodeInletMimeData(event.mimeData())
                assert inlet_index.isValid(), "Inlet index must be valid"
                inlet_widget = self._widgets[inlet_index]
                if self._adapter.itemType(drop_target_index) == GraphItemType.OUTLET:
                    # ... over outlet
                    outlet_widget = self._widgets[drop_target_index]
                    self.updateDraftLink(source=outlet_widget, target=inlet_widget)
                    event.acceptProposedAction()
                    return
                else:
                    # ... over empty space
                    self.updateDraftLink(source=self.mapToScene(event.position().toPoint()), target=inlet_widget)
                    event.acceptProposedAction() 
                    return
            
            if event.mimeData().hasFormat(GraphMimeData.LinkHeadData):
                # link head dragged
                link_index = self._adapter.decodeLinkHeadMimeData(event.mimeData())
                assert link_index.isValid(), "Link index must be valid"
                link_widget = self._widgets[QPersistentModelIndex(link_index)]
                if self._adapter.itemType(drop_target_index) == GraphItemType.INLET:
                    # ...over inlet
                    inlet_widget = self._widgets[drop_target_index]
                    link_widget.setLine(makeLineBetweenShapes(link_widget._source, inlet_widget))
                    event.acceptProposedAction()
                    return
                else:
                    # ... over empty space
                    link_widget.setLine(makeLineBetweenShapes(link_widget._source, self.mapToScene(event.position().toPoint())))
                    event.acceptProposedAction()
                    return

            if event.mimeData().hasFormat(GraphMimeData.LinkTailData):
                # link tail dragged
                link_index = self._adapter.decodeLinkTailMimeData(event.mimeData())
                assert link_index.isValid(), "Link index must be valid"
                link_widget = self._widgets[QPersistentModelIndex(link_index)]
                if self._adapter.itemType(drop_target_index) == GraphItemType.OUTLET:
                    # ...over outlet
                    outlet_widget = self._widgets[drop_target_index]
                    link_widget.setLine(makeLineBetweenShapes(outlet_widget, link_widget._target))
                    event.acceptProposedAction()
                    return
                else:
                    # ... over empty space
                    link_widget.setLine(makeLineBetweenShapes(self.mapToScene(event.position().toPoint()), link_widget._target))
                    event.acceptProposedAction()
                    return
            
    def dropEvent(self, event: QDropEvent) -> None:
        drop_target = self.indexAt(event.position().toPoint())
        if self._adapter.dropMimeData(event.mimeData(), event.dropAction(), drop_target):
            event.acceptProposedAction()
        else:
            event.ignore()

        if event.mimeData().hasFormat(GraphMimeData.LinkHeadData):
            link_index = self._adapter.decodeLinkHeadMimeData(event.mimeData())
            if link_widget := self._widgets.get(QPersistentModelIndex(link_index)):
                link_widget.updateLine()  # Ensure the link line is updated after drop

        if event.mimeData().hasFormat(GraphMimeData.LinkTailData):
            link_index = self._adapter.decodeLinkTailMimeData(event.mimeData())
            if link_widget := self._widgets.get(QPersistentModelIndex(link_index)):
                link_widget.updateLine()  # Ensure the link line is updated after drop

        self._cleanupDraftLink()

    def dragLeaveEvent(self, event):
        self._cleanupDraftLink()  # Cleanup draft link if it exists
        # super().dragLeaveEvent(event)
        # self._cleanupDraftLink()
    
    def indexAt(self, pos:QPointF) -> QPersistentModelIndex:
        """
        Find the index at the given position.
        This is used to determine if a drag operation is valid.
        """
        for item in self.items(pos):
            if item in self._widgets.values():
                index = self._widgets.inverse[item]
                return QPersistentModelIndex(index)

        return QPersistentModelIndex()


class CellWidget(QGraphicsProxyWidget):
    def __init__(self, parent: QGraphicsItem | None = None):
        super().__init__(parent=parent)
        self._label = QLabel("")
        self._label.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._label.setStyleSheet("background: orange;")
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setWidget(self._label)
        self.setAutoFillBackground(False)
        
        # Make CellWidget transparent to drag events so parent can handle them
        self.setAcceptDrops(False)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)

    def text(self):
        return self._label.text()

    def setText(self, text:str):
        self._label.setText(text)


class BaseRowWidget(QGraphicsWidget):
    def __init__(self, graphview:'GraphView', parent: QGraphicsItem | None = None):
        super().__init__(parent=parent)
        self._view = graphview
        layout = QGraphicsLinearLayout(Qt.Orientation.Vertical)
        self.setLayout(layout)
        self._title_widget = CellWidget(parent=self)
        self.addCell(self._title_widget)
        layout.updateGeometry()

    def setLabel(self, label:str):
        """
        Set the label for the row widget.
        This is used to display the name of the node or port.
        """
        self._title_widget.setText(label)
        
    def addCell(self, cell:CellWidget):
        layout = cast(QGraphicsLinearLayout, self.layout())
        layout.addItem(cell)

    def removeCell(self, cell:CellWidget):
        layout = cast(QGraphicsLinearLayout, self.layout())
        layout.removeItem(cell)


class PortWidget(BaseRowWidget):
    def __init__(self, graphview:'GraphView', parent: QGraphicsItem | None = None):
        super().__init__(graphview, parent=parent)
        self._links:List[LinkWidget] = []
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsScenePositionChanges, True)

    def itemChange(self, change, value):
        match change:
            case QGraphicsItem.GraphicsItemChange.ItemScenePositionHasChanged:
                for link in self._links:
                    link.updateLine()
                    
        return super().itemChange(change, value)

    def paint(self, painter, option, /, widget = ...):
        painter.setBrush(self.palette().alternateBase())
        painter.drawRect(option.rect)


class InletWidget(PortWidget):
    def __init__(self, graphview:'GraphView', parent: QGraphicsItem | None = None):
        super().__init__(graphview, parent=parent)
        self.setAcceptDrops(True)

    def paint(self, painter, option, /, widget:QWidget|None = None):
        painter.setBrush("lightblue")
        painter.drawRect(option.rect)

    def mousePressEvent(self, event:QGraphicsSceneMouseEvent) -> None:
        assert self._view
        # Setup new drag
        index = self._view._widgets.inverse[self]
        
        assert index.isValid(), "Outlet index must be valid"
        mime = self._view._adapter.inletMimeData(index)
        drag = QDrag(self._view)
        drag.setMimeData(mime)

        # Execute drag
        try:
            # self._view._createDraftLink()
            action = drag.exec(Qt.DropAction.LinkAction)
            # self._view._cleanupDraftLink()
        except Exception as err:
            traceback.print_exc()
        return super().mousePressEvent(event)
    

class OutletWidget(PortWidget):
    def __init__(self, graphview:'GraphView', parent: QGraphicsItem | None = None):
        super().__init__(graphview, parent=parent)
        self.setAcceptDrops(True)

    def paint(self, painter, option, /, widget:QWidget|None = None):
        painter.setBrush("purple")
        painter.drawRect(option.rect)

    def mousePressEvent(self, event:QGraphicsSceneMouseEvent) -> None:
        assert self._view
        # Setup new drag
        outlet_index = self._view._widgets.inverse[self]
        
        assert outlet_index.isValid(), "Outlet index must be valid"
        mime = self._view._adapter.outletMimeData(outlet_index)
        drag = QDrag(self._view)
        drag.setMimeData(mime)

        # Execute drag
        try:
            # self._view._createDraftLink()
            action = drag.exec(Qt.DropAction.LinkAction)
            # self._view._cleanupDraftLink()
        except Exception as err:
            traceback.print_exc()
        return super().mousePressEvent(event)


class NodeWidget(BaseRowWidget):
    def __init__(self, graphview:'GraphView', parent: QGraphicsItem | None = None):
        super().__init__(graphview, parent=parent)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        # layout = QGraphicsLinearLayout(Qt.Orientation.Vertical)
        # self.setLayout(layout)

    def addInlet(self, inlet:InletWidget):
        layout = cast(QGraphicsLinearLayout, self.layout())
        layout.addItem(inlet)

    def removeInlet(self, inlet:InletWidget):
        layout = cast(QGraphicsLinearLayout, self.layout())
        layout.removeItem(inlet)

    def addOutlet(self, outlet:OutletWidget):
        layout = cast(QGraphicsLinearLayout, self.layout())
        layout.addItem(outlet)

    def removeOutlet(self, outlet:InletWidget):
        layout = cast(QGraphicsLinearLayout, self.layout())
        layout.removeItem(outlet)

    def paint(self, painter: QPainter, option: QStyleOption, widget=None):
        rect = option.rect       
        painter.setBrush(self.palette().alternateBase())
        if self.isSelected():
            painter.setBrush(self.palette().highlight())
        painter.drawRoundedRect(rect, 6, 6)


class LinkWidget(BaseRowWidget):
    def __init__(self, graphview:'GraphView', parent: QGraphicsItem | None = None):
        super().__init__(graphview, parent=parent)
        # self.setZValue(-1)  # Ensure links are drawn below nodes
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self._line = QLineF(0, 0, 100, 100)
        self._label = QLabel("Link")
        self._data_column = QGraphicsWidget(parent=self)
        self._data_column.setLayout(QGraphicsLinearLayout(Qt.Orientation.Vertical))

        self._source: QGraphicsItem | None = None
        self._target: QGraphicsItem | None = None
        self.setAcceptHoverEvents(True)

    def boundingRect(self):
        _ = QRectF(self._line.p1(), self._line.p2())
        _ = _.normalized()
        _ = _.adjusted(-5,-5,5,5)
        return _
    
    def line(self)->QLineF:
        """Get the line of the link widget."""
        return self._line
    
    def setLine(self, line:QLineF):
        """Set the line of the link widget."""
        
        self.prepareGeometryChange()
        self._line = line

        self._data_column.layout().setGeometry(
            QRectF(self._line.p1(), self._line.p2())
            .adjusted(-5, -5, 5, 5)
            .normalized()
        )

        self.update()
    
    def shape(self)->QPainterPath:
        path = QPainterPath()
        path.moveTo(self._line.p1())
        path.lineTo(self._line.p2())
        stroker = QPainterPathStroker()
        stroker.setWidth(4)
        return stroker.createStroke(path)
    
    def addCell(self, cell:CellWidget):
        ...
        # layout = cast(QGraphicsLinearLayout, self._data_column.layout())
        # layout.addItem(cell)

    def removeCell(self, cell:CellWidget):
        ...
        # layout = cast(QGraphicsLinearLayout, self._data_column.layout())
        # layout.addItem(cell)

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

    def link(self, source:QGraphicsItem|None, target:QGraphicsItem|None):
        """Link this widget to a source and target item."""
        self.unlink()  # Unlink any existing connections
        self._source = source
        self._target = target
        if source:
            source._links.append(self)
        if target:
            target._links.append(self)
        self.updateLine()
        self.update()

    def unlink(self):
        """Unlink this widget from its source and target items."""
        if self._source:
            self._source._links.remove(self)
            self._source = None
        if self._target:
            self._target._links.remove(self)
            self._target = None
        self.updateLine()
        self.update()

    def updateLine(self):
        if self._source and self._target:
            line = makeLineBetweenShapes(self._source, self._target)
            line = QLineF(self.mapFromScene(line.p1()), self.mapFromScene(line.p2()))
            self.setLine(line)
        elif self._source:
            source_pos = self._source.scenePos()-self.scenePos()
            line = QLineF(source_pos, source_pos+QPointF(24,24))
            line = QLineF(self.mapFromScene(line.p1()), self.mapFromScene(line.p2()))
            self.setLine(line)
        elif self._target:
            target_pos = self._target.scenePos()-self.scenePos()
            line = QLineF(target_pos-QPointF(24,24), target_pos)
            line = QLineF(self.mapFromScene(line.p1()), self.mapFromScene(line.p2()))
            self.setLine(line)
        else:
            ...

    def mousePressEvent(self, event:QGraphicsSceneMouseEvent) -> None:
        assert self._view
        def startDragTail():
            assert self._view
            index = self._view._widgets.inverse[self]
            mime = self._view._adapter.linkTailMimeData(index)
            drag = QDrag(self._view)
            drag.setMimeData(mime)

            # Execute drag
            try:
                action = drag.exec(Qt.DropAction.LinkAction)
            except Exception as err:
                traceback.print_exc()

        def startDragHead():
            assert self._view
            index = self._view._widgets.inverse[self]
            mime = self._view._adapter.linkHeadMimeData(index)
            drag = QDrag(self._view)
            drag.setMimeData(mime)

            # Execute drag
            try:
                action:Qt.DropAction = drag.exec(Qt.DropAction.LinkAction)
            except Exception as err:
                traceback.print_exc()

        tail_distance = (event.pos() - self.line().p1()).manhattanLength()
        head_distance = (event.pos() - self.line().p2()).manhattanLength()
        if self._source is None and self._target is None:
            if tail_distance < head_distance:
                startDragTail()
            else:
                startDragHead()
        elif self._target is not None:
            startDragTail()
        elif self._source is not None:
            startDragHead()
            
        super().mousePressEvent(event) # select on mousepress
