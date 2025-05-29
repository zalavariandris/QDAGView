#####################
# The Network Scene #
#####################

#
# A Graph view that directly connects to QStandardItemModel
#


from enum import Enum
from typing import *
from PySide6.QtGui import *
from PySide6.QtCore import *
from PySide6.QtWidgets import *

from collections import defaultdict
from bidict import bidict

from utils import group_consecutive_numbers
# from pylive.utils.geo import makeLineBetweenShapes, makeLineToShape
# from pylive.utils.qt import distribute_items_horizontal
# from pylive.utils.unique import make_unique_name
# from pylive.utils.diff import diff_set

import logging
from enum import StrEnum, IntEnum
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class GraphDataRole(IntEnum):
    TypeRole= Qt.ItemDataRole.UserRole+1
    SourceRole= Qt.ItemDataRole.UserRole+2


class RowType(StrEnum):
    INLET = "INLET"
    OUTLET = "OUTLET"
    NODE = "NODE"
    LINK = "LINK"


class GraphView(QWidget):
    nodesLinked = Signal(QModelIndex, QModelIndex, str, str)
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent=parent)
        self._model:QAbstractItemModel | None = None
        self._selection: QItemSelectionModel | None = None
        self._model_connections = []
        self._selection_connections = []

        # store model widget relations
        # map item index to widgets
        self._row_widgets: bidict[QPersistentModelIndex, BaseRowWidget] = bidict()
        self._cell_widgets: bidict[QPersistentModelIndex, CellWidget] = bidict()
        self._pending_links:Dict[QPersistentModelIndex, QPersistentModelIndex] = dict() # map link source, to a dangling link
        # self._link_widgets: bidict[tuple[QPersistentModelIndex, QPersistentModelIndex], LinkItem] = bidict()
        self._draft_link: QGraphicsLineItem | None = None
        self.setupUI()

    def setupUI(self):
        self.graphicsview = QGraphicsView(self)
        self.graphicsview.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.graphicsview.setCacheMode(QGraphicsView.CacheModeFlag.CacheNone)
        self.graphicsview.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.graphicsview.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        self.graphicsview.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        scene = QGraphicsScene()
        scene.setSceneRect(QRectF(-9999, -9999, 9999 * 2, 9999 * 2))
        self.graphicsview.setScene(scene)
        layout = QVBoxLayout()
        layout.addWidget(self.graphicsview)
        self.setLayout(layout)

        scene.selectionChanged.connect(self.updateSelectionModel)

    def updateSelectionModel(self):
        if self._model and self._selection:
            # get currently selected widgets
            selected_widgets = self.graphicsview.scene().selectedItems()

            # map widgets to QModelIndexes
            selected_indexes = map(lambda widget: self._row_widgets.inverse.get(widget, None), selected_widgets)
            selected_indexes = filter(lambda idx: idx is not None and idx.isValid(), selected_indexes)

            # group indexes by parents
            indexes_by_parent = defaultdict(list)
            for index in selected_indexes:
                parent = index.parent()
                indexes_by_parent[parent].append(index)

            # create QItemSelection
            item_selection = QItemSelection()
            for parent, indexes in indexes_by_parent.items():
                all_rows = sorted(index.row() for index in indexes)
                ranges = group_consecutive_numbers(all_rows)

                for row_range in ranges:
                    top_left = self._model.index(row_range.start, 0, parent)
                    bottom_right = self._model.index(row_range.stop - 1, self._model.columnCount(parent) - 1, parent)
                    selection_range = QItemSelectionRange(top_left, bottom_right)
                    item_selection.append(selection_range)

            # perform selection on model
            self._selection.select(item_selection, QItemSelectionModel.SelectionFlag.ClearAndSelect)

    @Slot(QItemSelection, QItemSelection)
    def onSelectionChanged(self, selected:QItemSelection, deselected:QItemSelection):
        """
        Handle selection changes in the selection model.
        This updates the selection in the graph view.
        """
        print(f"onSelectionChanged: {selected}, {deselected}")
        assert self._selection, "Selection model must be set before handling selection changes!"
        assert self._model, "Model must be set before handling selection changes!"

        scene = self.graphicsview.scene()
        scene.blockSignals(True)
        for index in deselected.indexes():
            widget = self._row_widgets[QPersistentModelIndex(index.siblingAtColumn(0))]
            widget.setSelected(False)
            # widget.update()

        for index in selected.indexes():
            widget = self._row_widgets[QPersistentModelIndex(index.siblingAtColumn(0))]
            widget.setSelected(True)
            # widget.update()
        scene.blockSignals(False)

    def setModel(self, model:QAbstractItemModel):
        if self._model:
            for signal, slot in self._model_connections:
                signal.disconnect(slot)
            self._model_connections = []

        assert isinstance(model, QAbstractItemModel)
 
        if model:
            self._model_connections = [
                (model.dataChanged, self.onDataChanged),
                (model.rowsInserted, self.onRowsInserted),
                (model.rowsAboutToBeRemoved, self.onRowsAboutToBeRemoved)
            ]
            for signal, slot in self._model_connections:
                signal.connect(slot)

        self._model = model

        # populate initial scene
        ## clear
        self.graphicsview.scene().clear()
        self._row_widgets.clear()
        self._cell_widgets.clear()
        self._pending_links = {}
        self.populate(QModelIndex())

    def model(self) -> QAbstractItemModel | None:
        return self._model
    
    def setSelectionModel(self, selection: QItemSelectionModel):
        """
        Set the selection model for the graph view.
        This is used to synchronize the selection of nodes in the graph view
        with the selection model.
        """
        assert isinstance(selection, QItemSelectionModel)
        assert self._model, "Model must be set before setting the selection model!"
        assert selection.model() == self._model, "Selection model must be for the same model as the graph view!"
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

    def selectionModel(self) -> QItemSelectionModel | None:
        """
        Get the current selection model for the graph view.
        This is used to synchronize the selection of nodes in the graph view
        with the selection model.
        """
        return self._selection
    

    def populate(self, *root:QModelIndex):
        # First pass: Create all non-link widgets

        # first pass: collect each row recursively
        def children(index:QModelIndex):
            for row in range(self._model.rowCount(parent=index)):
                yield self._model.index(row, 0, index) 

        # Breadth-first search
        queue:List[QModelIndex] = [*root]
        indexes = list()
        while queue:
            index = queue.pop()
            indexes.append(index)
            for child in children(index):
                queue.append(child)

        # second pass: create nodes and inlets hiearchy
        for index in indexes:
            if not index.isValid():
                continue
            row, parent = index.row(), index.parent()
            row_kind = self.rowKind(row, parent)
            match row_kind:
                case RowType.NODE:
                    self._add_node_widget(row, parent)
                case RowType.INLET:
                    self._add_inlet_widget(row, parent)
                case RowType.OUTLET:
                    self._add_outlet_widget(row, parent)
                    index = self._model.index(row, 0, parent)
                    link = self._pending_links.get(QPersistentModelIndex(index))
                    if link:
                        link_widget = cast(LinkWidget, self._row_widgets[link])
                        link_widget._source_widget = self._row_widgets[QPersistentModelIndex(index)]
                        link_widget.updateLine()
                        
                case RowType.LINK:
                    pass
                case _:
                    raise NotImplementedError(f"Row kind {row_kind} is not implemented!")
        
        # third pass: create the links
        for index in indexes:
            if not index.isValid():
                continue
            row, parent = index.row(), index.parent()
            row_kind = self.rowKind(row, parent)
            match row_kind:
                case RowType.NODE:
                    pass
                case RowType.INLET:
                    pass
                case RowType.OUTLET:
                    pass
                case RowType.LINK:
                    self._add_link_widget(row, parent)
                case _:
                    raise NotImplementedError(f"Row kind {row_kind} is not implemented!")
            
    ## populate
    def _add_cell_widgets(self, row:int, parent: QModelIndex): 
        """Add all cell widgets associated with a row."""       
        # create labels from row cells
        for col in range(self._model.columnCount(parent=parent)):
            cell_index = self._model.index(row, col, parent)
            text = cell_index.data(Qt.ItemDataRole.DisplayRole)
            cell_widget = CellWidget()
            cell_widget.setText(f"{text}")
            self._cell_widgets[QPersistentModelIndex(cell_index)] = cell_widget

            row_widget = self._row_widgets[QPersistentModelIndex(self._model.index(row, 0, parent))]
            row_widget.addCell(cell_widget)
            
    def _add_node_widget(self, row: int, parent:QModelIndex):
        #add widget to view
        index = self._model.index(row, 0, parent)
        widget = NodeWidget()
        self._row_widgets[QPersistentModelIndex(index)] = widget
        self._add_cell_widgets(row, parent)

        # attach to scene or parent widget
        if parent.isValid():
            raise NotImplementedError()
        else:
            self.graphicsview.scene().addItem(widget)
        return widget

    def _add_inlet_widget(self, row:int, parent:QModelIndex):
        # add widget
        index = self._model.index(row, 0, parent)
        widget = InletWidget()
        self._row_widgets[QPersistentModelIndex(index)] = widget
        self._add_cell_widgets(row, parent)

        # attach to parent widget
        if parent.isValid():
            parent_widget = self._row_widgets[QPersistentModelIndex(parent)]
            if not isinstance(parent_widget, NodeWidget):
                raise ValueError("inlets must have a Node parent")
            parent_widget = cast(NodeWidget, parent_widget)
            parent_widget.addInlet(widget)
        else:
            raise NotImplementedError("root graph inlets are not yet implemented!")

        # return widget
        return widget
    
    def _add_outlet_widget(self, row, parent: QModelIndex):
        # add widget
        index = self._model.index(row, 0, parent)
        widget = OutletWidget()
        self._row_widgets[QPersistentModelIndex(index)] = widget
        self._add_cell_widgets(row, parent)

        # attach to parent widget
        parent = index.parent()
        if parent.isValid():
            parent_widget = self._row_widgets[QPersistentModelIndex(parent)]
            parent_widget = cast(NodeWidget, parent_widget)
            parent_widget.addInlet(widget)

        return widget
    
    def _add_link_widget(self, row:int, parent: QModelIndex):
        """Create a link widget. Returns None if source widget doesn't exist yet."""
        index = self._model.index(row, 0, parent)
        source_index = index.data(GraphDataRole.SourceRole)
        target_index = QPersistentModelIndex(parent)

        # Validate source index
        if not isinstance(source_index, QPersistentModelIndex):
            logger.warning(f"Link {index} has invalid source index type: {type(source_index)}")
            return None
        
        # Check if source exists
        if source_index not in self._row_widgets:
            # Store for later creation when source becomes available
            self._pending_links[QPersistentModelIndex(index)] = (source_index, parent)
            logger.debug(f"Link {index} source {source_index} not found, storing as pending")
            return None

        # Create and setup widget
        widget = LinkWidget()
        self._row_widgets[QPersistentModelIndex(index)] = widget
        self._add_cell_widgets(row, parent)
        self.graphicsview.scene().addItem(widget)

        # Setup source and target references
        source_widget = self._row_widgets[source_index]
        target_widget = self._row_widgets[target_index]
        source_widget._links.append(widget)
        target_widget._links.append(widget)
        widget._source_widget = source_widget
        widget._target_widget = target_widget

        widget.updateLine()
        return widget

    def _remove_cell_widgets(self, row:int, parent: QModelIndex):
        """Remove all cell widgets associated with a row."""
          
        # Remove cell widgets for all columns of this row
        for col in range(self._model.columnCount(parent=parent)):
            cell_index = self._model.index(row, col, parent)
            persistent_cell_index = QPersistentModelIndex(cell_index)
            assert persistent_cell_index in self._cell_widgets
            cell_widget = self._cell_widgets[persistent_cell_index]
            row_widget = self._row_widgets[QPersistentModelIndex(self._model.index(row, col, parent))]
            row_widget.removeCell(cell_widget)
            del self._cell_widgets[persistent_cell_index]

    def _remove_node_widget(self, row: int, parent: QModelIndex):
        """Remove a node widget"""
        # Remove all cell widgets for this node
        self._remove_cell_widgets(row, parent)

        # remove widget from graphview
        index = self._model.index(row, 0, parent)
        widget = self._row_widgets[QPersistentModelIndex(index)]
        del self._row_widgets[QPersistentModelIndex(index)]
        
        # detach from scene or parent widget
        if parent.isValid():
            raise NotImplementedError()
        else:
            self.graphicsview.scene().removeItem(widget)
        
    def _remove_inlet_widget(self, row:int, parent:QModelIndex):
        """Remove an inlet widget and its associated cell widgets."""
        # Remove all cell widgets for this inlet
        self._remove_cell_widgets(row, parent)
        
        # remove widget from graphview
        index = self._model.index(row, 0, parent)
        widget = self._row_widgets[QPersistentModelIndex(index)]
        del self._row_widgets[QPersistentModelIndex(index)]

        # detach widget from scene (or parent widget)
        if parent.isValid():
            parent_widget = self._row_widgets[QPersistentModelIndex(parent)]
            parent_widget = cast(NodeWidget, parent_widget)
            parent_widget.removeInlet(widget)
        else:
            raise NotImplementedError("support inlets attached to the root graph")

    def _remove_outlet_widget(self, row:int, parent: QModelIndex):
        """Remove an outlet widget and its associated cell widgets."""
        # Remove all cell widgets for this outlet
        self._remove_cell_widgets(row, parent)
        
        # remove widget from graphview
        index = self._model.index(row, 0, parent)
        widget = self._row_widgets[QPersistentModelIndex(index)]
        del self._row_widgets[QPersistentModelIndex(index)]

        # detach widget from scene (or parent widget)
        if parent.isValid():
            parent_widget = self._row_widgets[QPersistentModelIndex(parent)]
            parent_widget = cast(NodeWidget, parent_widget)
            parent_widget.removeOutlet(widget)
        else:
            raise NotImplementedError("support inlets attached to the root graph")
        
    def _remove_link_widget(self, row:int, parent: QModelIndex):
        # Remove all cell widgets for this outlet
        self._remove_cell_widgets(row, parent)

        # remove widget from graphview
        index = self._model.index(row, 0, parent)
        widget = self._row_widgets[QPersistentModelIndex(index)]
        del self._row_widgets[QPersistentModelIndex(index)]

        # detach widget from scene (or parent widget)
        if parent.isValid():
            self.graphicsview.scene().removeItem(widget)
            source_index = index.data(GraphDataRole.SourceRole)
            assert isinstance(source_index, QPersistentModelIndex), f"Source index mus be a QPersistentIndex, got: {source_index}!"
            assert source_index in self._row_widgets, f"Warning: link({index}) source({source_index}) not found in _row_widgets!"
            target_index = QPersistentModelIndex(parent)
            source_widget = self._row_widgets[source_index]
            target_widget = self._row_widgets[target_index]
            source_widget._links.remove(widget)
            target_widget._links.remove(widget)
        else:
            raise ValueError("Edges Must have an inlet parent!")

    def _defaultRowKind(self, row:int, parent:QModelIndex) -> RowType | None:
        """
        Determine the kind of row based on the index.
        This is used to determine whether to create a Node, Inlet, Outlet or Link widget.
        Args:
            index (QModelIndex): The index of the row.
        """
        index = self._model.index(row, 0, parent)
        if not index.isValid():
            return None
        elif index.parent() == QModelIndex():
            return RowType.NODE
        elif index.parent().isValid() and index.parent().parent() == QModelIndex():
            return RowType.INLET
        elif index.parent().isValid() and index.parent().parent().isValid() and index.parent().parent().parent() == QModelIndex():
            return RowType.LINK
        else:
            raise ValueError(
                f"Invalid index: {index}. "
                "Index must be a valid QModelIndex with a valid parent."
            )
        
    def _validateRowKind(self, row:int, parent:QModelIndex, row_kind: 'RowType') -> bool:
        """
        Validate the row kind based on the index.
        This is used to ensure that the row kind matches the expected kind
        Args:   

            index (QModelIndex): The index of the row.
            row_kind (NodeType | None): The kind of row to validate.
        Returns:
            bool: True if the row kind is valid, False otherwise.
        """
        index = self._model.index(row, 0, parent)
        if not index.isValid():
            return False
        if row_kind is None:
            return True  # No specific row kind, so always valid
        if row_kind == RowType.NODE:
            return index.parent() == QModelIndex()
        elif row_kind == RowType.INLET:
            return index.parent().isValid() and index.parent().parent() == QModelIndex()
        elif row_kind == RowType.OUTLET:
            return index.parent().isValid() and index.parent().parent() == QModelIndex()
        elif row_kind == RowType.LINK:
            return index.parent().isValid() and index.parent().parent().isValid() and index.parent().parent().parent() == QModelIndex()

    def rowKind(self, row:int, parent:QModelIndex):
        index = self._model.index(row, 0, parent)
        row_kind = index.data(GraphDataRole.TypeRole)
        if not row_kind:
            row_kind = self._defaultRowKind(row, parent)
        assert self._validateRowKind(row, parent, row_kind), f"Invalid row kind {row_kind} for index {index}!"
        return row_kind
    

    @Slot(QModelIndex, QModelIndex, int, int)
    def onRowsInserted(self, parent:QModelIndex, first:int, last:int):
        assert self._model

        # populate the new rows
        self.populate(*[self._model.index(row, 0, parent) for row in range(first, last + 1)])

    def _remove_row_recursive(self, row:int, parent:QModelIndex):
        """
        Recursively remove a row and all its children from bottom up.
        This ensures proper cleanup of widget hierarchies.
        """
        assert self._model

        # First handle all children of this row
        index = self._model.index(row, 0, parent)
        row_count = self._model.rowCount(parent=index)
        for child_row in reversed(range(row_count)):
            child_index = self._model.index(child_row, 0, index)
            self._remove_row_recursive(child_row, index)

        # Now handle this row itself
        persistent_index = QPersistentModelIndex(index)
        if persistent_index not in self._row_widgets:
            return

        row_widget = self._row_widgets[persistent_index]
        row_type = index.data(GraphDataRole.TypeRole)
        if not row_type:
            row_type = self._defaultRowKind(index)

        match row_type:
            case RowType.NODE:
                self._remove_node_widget(index, row_widget)
            case RowType.INLET:
                self._remove_inlet_widget(index, row_widget)
            case RowType.OUTLET:
                self._remove_outlet_widget(index, row_widget)
            case RowType.LINK:
                self._remove_link_widget(index, row_widget)
            case _:
                raise ValueError()

    @Slot(QModelIndex, QModelIndex, int, int)
    def onRowsAboutToBeRemoved(self, parent: QModelIndex, first: int, last: int):
        """
        Handle rows being removed from the model.
        This removes the corresponding widgets from the scene and cleans up internal mappings.
        Removal is done recursively from bottom up to ensure proper cleanup of widget hierarchies.
        """
        assert self._model

        # Remove rows in reverse order to handle siblings properly
        for row in reversed(range(first, last + 1)):
            # index = self._model.index(row, 0, parent=parent)
            self._remove_row_recursive(row, parent)

    @Slot(QModelIndex, QModelIndex, list)
    def onDataChanged(self, topLeft:QModelIndex , bottomRight:QModelIndex , roles=[]):
        assert self._model
        for row in range(topLeft.row(), bottomRight.row()+1):
            for col in range(topLeft.column(), bottomRight.column()+1):
                cell_index = self._model.index(row, col)
                widget = self._cell_widgets[QPersistentModelIndex(cell_index)]
                proxy = cast(QGraphicsProxyWidget, widget)
                label = proxy.widget()
                assert isinstance(label, QLabel)
                label.setText(cell_index.data(Qt.ItemDataRole.DisplayRole))
            node_index = self._model.index(row, 0)
            node_widget = cast(NodeWidget, self._cell_widgets[QPersistentModelIndex(node_index)])
            # node_widget.resize(node_widget.layout().sizeHint(Qt.SizeHint.PreferredSize))
            # node_widget.updateGeometry()


class CellWidget(QGraphicsProxyWidget):
    def __init__(self, parent: QGraphicsItem | None = None):
        super().__init__(parent=parent)
        self._label = QLabel("")
        self.setWidget(self._label)

    def text(self):
        return self._label.text()

    def setText(self, text:str):
        self._label.setText(text)


class BaseRowWidget(QGraphicsWidget):
    def __init__(self, parent: QGraphicsItem | None = None):
        super().__init__(parent=parent)

        layout = QGraphicsLinearLayout(Qt.Orientation.Vertical)
        self.setLayout(layout)

        self._links = []
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsScenePositionChanges, True)

    def addCell(self, cell:CellWidget):
        layout = cast(QGraphicsLinearLayout, self.layout())
        layout.addItem(cell)

    def removeCell(self, cell:CellWidget):
        layout = cast(QGraphicsLinearLayout, self.layout())
        layout.removeItem(cell)

    def itemChange(self, change, value):
        match change:
            case QGraphicsItem.GraphicsItemChange.ItemScenePositionHasChanged:
                for link in self._links:
                    link.updateLine()
        return super().itemChange(change, value)


class PortWidget(BaseRowWidget):
    def __init__(self, parent: QGraphicsItem | None = None):
        super().__init__(parent=parent)
        # self.setGeometry(-14,0,14,14)
        
        self.setLayout(QGraphicsLinearLayout(Qt.Orientation.Horizontal, self))

    def paint(self, painter, option, /, widget = ...):
        painter.setBrush(self.palette().alternateBase())
        painter.drawRect(option.rect)


class InletWidget(PortWidget):
    ...


class OutletWidget(PortWidget):
    ...


class NodeWidget(BaseRowWidget):
    def __init__(self, parent: QGraphicsItem | None = None):
        super().__init__(parent=parent)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsScenePositionChanges, True)

        layout = QGraphicsLinearLayout(Qt.Orientation.Vertical)
        self.setLayout(layout)
        self._links = []

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

    def addCell(self, cell):
        return super().addCell(cell)

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

        self._source_widget: QGraphicsItem | None = None
        self._target_widget: QGraphicsItem | None = None
        self._line = QLineF(0, 0, 20, 20)

        self._data_column = QGraphicsWidget(parent=self)
        self._data_column.setLayout(QGraphicsLinearLayout(Qt.Orientation.Vertical))

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
        stroker.setWidth(2)
        return stroker.createStroke(path)
    
    def addCell(self, cell:CellWidget):
        layout = cast(QGraphicsLinearLayout, self._data_column.layout())
        layout.addItem(cell)

    def removeCell(self, cell:CellWidget):
        layout = cast(QGraphicsLinearLayout, self._data_column.layout())
        layout.addItem(cell)

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget=None):
        if self.isSelected():
            painter.setBrush(self.palette().accent())
        else:
            painter.setBrush(self.palette().text())
        painter.setPen(Qt.PenStyle.NoPen)

        shape = self.shape()
        painter.drawPath(shape)

    def updateLine(self):
        self.prepareGeometryChange()
        if self._source_widget and self._target_widget:
            source_pos = self._source_widget.scenePos()
            target_pos = self._target_widget.scenePos()
            self._line = QLineF(source_pos, target_pos)

        self.update()
        self._data_column.setPos(self._line.center())

