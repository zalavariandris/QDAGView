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
        self._row_widgets: bidict[QPersistentModelIndex, QGraphicsItem] = bidict()
        self._cell_widgets: bidict[QPersistentModelIndex, QGraphicsItem] = bidict()
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
        self.populate()

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
            node_widget.resize(node_widget.layout().sizeHint(Qt.SizeHint.PreferredSize))
            # node_widget.updateGeometry()

    def defaultRowKind(self, index: QModelIndex) -> RowType | None:
        """
        Determine the kind of row based on the index.
        This is used to determine whether to create a Node, Inlet, Outlet or Link widget.
        Args:
            index (QModelIndex): The index of the row.
        """
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
        
    def validateRowKind(self, index, row_kind: 'RowType') -> bool:
        """
        Validate the row kind based on the index.
        This is used to ensure that the row kind matches the expected kind
        Args:   

            index (QModelIndex): The index of the row.
            row_kind (NodeType | None): The kind of row to validate.
        Returns:
            bool: True if the row kind is valid, False otherwise.
        """
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

    def onRowsInserted(self, parent:QModelIndex, first:int, last:int):
        assert self._model

        # populate the new rows
        for row in range(first, last + 1):
            index = self._model.index(row, 0, parent=parent)
            row_kind = index.data(GraphDataRole.TypeRole)
            if not row_kind:
                row_kind = self.defaultRowKind(index)
            assert self.validateRowKind(index, row_kind), f"Invalid row kind {row_kind} for index {index}!"

            match row_kind:
                case RowType.NODE:
                    # create a new NodeWidget for each new row
                    self._add_node_widget(index)
                case RowType.INLET:
                    self._add_inlet_widget(index)
                case RowType.OUTLET:
                    self._add_outlet_widget(index)
                case RowType.LINK:
                    self._add_link_widget(index)
                case _:
                    raise NotImplementedError(f"Row kind {row_kind} is not implemented!")

    def onRowsAboutToBeRemoved(self, parent: QModelIndex, first: int, last: int):
        """
        Handle rows being removed from the model.
        This removes the corresponding widgets from the scene and cleans up internal mappings.
        """
        assert self._model

        for row in range(first, last + 1):
            index = self._model.index(row, 0, parent=parent)
            persistent_index = QPersistentModelIndex(index)
            
            # Check if we have a widget for this row
            if persistent_index not in self._row_widgets:
                continue
                
            row_widget = self._row_widgets[persistent_index]
            row_kind = index.data(GraphDataRole.TypeRole)
            if not row_kind:
                row_kind = self.defaultRowKind(index)
            
            match row_kind:
                case RowType.NODE:
                    self._remove_node_widget(index, row_widget)
                case RowType.INLET:
                    self._remove_inlet_widget(index, row_widget)
                case RowType.OUTLET:
                    self._remove_outlet_widget(index, row_widget)
                case RowType.LINK:
                    self._remove_link_widget(index, row_widget)
                case _:
                    # Generic cleanup for unknown types
                    self._remove_generic_widget(index, row_widget)

    def _remove_node_widget(self, index: QModelIndex, node_widget: QGraphicsItem):
        """Remove a node widget and all its associated cell widgets."""
        # Remove all cell widgets for this node
        self._remove_cell_widgets(index)
        
        # Remove any links connected to this node
        if hasattr(node_widget, '_links'):
            # Create a copy of the list since we'll be modifying it
            links_to_remove = list(node_widget._links)
            for link_widget in links_to_remove:
                # Remove the link from scene
                if link_widget.scene():
                    link_widget.scene().removeItem(link_widget)
                
                # Clean up link references
                if hasattr(link_widget, '_source_widget') and link_widget._source_widget:
                    if hasattr(link_widget._source_widget, '_links'):
                        try:
                            link_widget._source_widget._links.remove(link_widget)
                        except ValueError:
                            pass  # Link wasn't in the list
                
                if hasattr(link_widget, '_target_widget') and link_widget._target_widget:
                    if hasattr(link_widget._target_widget, '_links'):
                        try:
                            link_widget._target_widget._links.remove(link_widget)
                        except ValueError:
                            pass  # Link wasn't in the list
        
        # Remove from scene
        if node_widget.scene():
            node_widget.scene().removeItem(node_widget)
        
        # Remove from mappings
        persistent_index = QPersistentModelIndex(index)
        if persistent_index in self._row_widgets:
            del self._row_widgets[persistent_index]

    def _remove_inlet_widget(self, index: QModelIndex, inlet_widget: QGraphicsItem):
        """Remove an inlet widget and its associated cell widgets."""
        # Remove all cell widgets for this inlet
        self._remove_cell_widgets(index)
        
        # Remove any links connected to this inlet
        if hasattr(inlet_widget, '_links'):
            links_to_remove = list(inlet_widget._links)
            for link_widget in links_to_remove:
                if link_widget.scene():
                    link_widget.scene().removeItem(link_widget)
                
                # Clean up cross-references
                if hasattr(link_widget, '_source_widget') and link_widget._source_widget != inlet_widget:
                    if hasattr(link_widget._source_widget, '_links'):
                        try:
                            link_widget._source_widget._links.remove(link_widget)
                        except ValueError:
                            pass
                
                if hasattr(link_widget, '_target_widget') and link_widget._target_widget != inlet_widget:
                    if hasattr(link_widget._target_widget, '_links'):
                        try:
                            link_widget._target_widget._links.remove(link_widget)
                        except ValueError:
                            pass
        
        # Remove from parent's layout if it's a layout item
        if hasattr(inlet_widget, 'parentLayoutItem') and inlet_widget.parentLayoutItem():
            layout = inlet_widget.parentLayoutItem()
            layout.removeItem(inlet_widget)
        
        # Remove from mappings
        persistent_index = QPersistentModelIndex(index)
        if persistent_index in self._row_widgets:
            del self._row_widgets[persistent_index]

    def _remove_outlet_widget(self, index: QModelIndex, outlet_widget: QGraphicsItem):
        """Remove an outlet widget and its associated cell widgets."""
        # Remove all cell widgets for this outlet
        self._remove_cell_widgets(index)
        
        # Remove any links connected to this outlet
        if hasattr(outlet_widget, '_links'):
            links_to_remove = list(outlet_widget._links)
            for link_widget in links_to_remove:
                if link_widget.scene():
                    link_widget.scene().removeItem(link_widget)
                
                # Clean up cross-references
                if hasattr(link_widget, '_source_widget') and link_widget._source_widget != outlet_widget:
                    if hasattr(link_widget._source_widget, '_links'):
                        try:
                            link_widget._source_widget._links.remove(link_widget)
                        except ValueError:
                            pass
                
                if hasattr(link_widget, '_target_widget') and link_widget._target_widget != outlet_widget:
                    if hasattr(link_widget._target_widget, '_links'):
                        try:
                            link_widget._target_widget._links.remove(link_widget)
                        except ValueError:
                            pass
        
        # Remove from parent's layout if it's a layout item
        if hasattr(outlet_widget, 'parentLayoutItem') and outlet_widget.parentLayoutItem():
            layout = outlet_widget.parentLayoutItem()
            layout.removeItem(outlet_widget)
        
        # Remove from mappings
        persistent_index = QPersistentModelIndex(index)
        if persistent_index in self._row_widgets:
            del self._row_widgets[persistent_index]

    def _remove_link_widget(self, index: QModelIndex, link_widget: QGraphicsItem):
        """Remove a link widget and clean up its connections."""
        # Clean up references in connected widgets
        if hasattr(link_widget, '_source_widget') and link_widget._source_widget:
            if hasattr(link_widget._source_widget, '_links'):
                try:
                    link_widget._source_widget._links.remove(link_widget)
                except ValueError:
                    pass  # Link wasn't in the list
        
        if hasattr(link_widget, '_target_widget') and link_widget._target_widget:
            if hasattr(link_widget._target_widget, '_links'):
                try:
                    link_widget._target_widget._links.remove(link_widget)
                except ValueError:
                    pass  # Link wasn't in the list
        
        # Remove from scene
        if link_widget.scene():
            link_widget.scene().removeItem(link_widget)
        
        # Remove from mappings
        persistent_index = QPersistentModelIndex(index)
        if persistent_index in self._row_widgets:
            del self._row_widgets[persistent_index]

    def _remove_cell_widgets(self, index: QModelIndex):
        """Remove all cell widgets associated with a row."""
        assert index.column() == 0
        
        # Remove cell widgets for all columns of this row
        for col in range(index.model().columnCount(parent=index.parent())):
            cell_index = index.siblingAtColumn(col)
            persistent_cell_index = QPersistentModelIndex(cell_index)
            
            if persistent_cell_index in self._cell_widgets:
                cell_widget = self._cell_widgets[persistent_cell_index]
                
                # Remove from parent's layout if it's a layout item
                if hasattr(cell_widget, 'parentLayoutItem') and cell_widget.parentLayoutItem():
                    layout = cell_widget.parentLayoutItem()
                    layout.removeItem(cell_widget)
                
                # Remove from scene if it's directly in the scene
                elif hasattr(cell_widget, 'scene') and cell_widget.scene():
                    cell_widget.scene().removeItem(cell_widget)
                
                # Remove from mapping
                del self._cell_widgets[persistent_cell_index]

    def _remove_generic_widget(self, index: QModelIndex, widget: QGraphicsItem):
        """Generic cleanup for widgets of unknown types."""
        # Remove from scene
        if hasattr(widget, 'scene') and widget.scene():
            widget.scene().removeItem(widget)
        
        # Remove from parent's layout if it's a layout item
        if hasattr(widget, 'parentLayoutItem') and widget.parentLayoutItem():
            layout = widget.parentLayoutItem()
            layout.removeItem(widget)
        
        # Remove from mappings
        persistent_index = QPersistentModelIndex(index)
        if persistent_index in self._row_widgets:
            del self._row_widgets[persistent_index]
        
        # Also remove any associated cell widgets
        self._remove_cell_widgets(index)
    
    ## populate
    def _add_cell_widgets(self, index: QModelIndex):
        assert index.column() == 0
        
        # create labels from cells
        for col in range(index.model().columnCount(parent=index.parent())):
            cell_index = index.siblingAtColumn(col)
            text = cell_index.data(Qt.ItemDataRole.DisplayRole)
            label = QLabel(f"cell: {text}")
            proxy = QGraphicsProxyWidget()
            proxy.setWidget(label)

            row_widget = self._row_widgets[QPersistentModelIndex(cell_index.siblingAtColumn(0))]
            row_widget.layout().addItem(proxy)
            self._cell_widgets[QPersistentModelIndex(cell_index)] = proxy

    def _add_node_widget(self, index: QModelIndex):
        node_widget = NodeWidget()
        self.graphicsview.scene().addItem(node_widget)
        self._row_widgets[QPersistentModelIndex(index)] = node_widget
        self._add_cell_widgets(index)
        return node_widget

    def _add_inlet_widget(self, index: QModelIndex):
        node_index = index.parent()
        node_widget = self._row_widgets[QPersistentModelIndex(node_index)]
        inlet_widget = InletWidget()
        self._row_widgets[QPersistentModelIndex(index)] = inlet_widget
        node_widget.layout().addItem(inlet_widget)
        self._add_cell_widgets(index)
        return inlet_widget

    def _add_outlet_widget(self, index: QModelIndex):
        node_index = index.parent()
        node_widget = self._row_widgets[QPersistentModelIndex(node_index)]
        outlet_widget = OutletWidget()
        self._row_widgets[QPersistentModelIndex(index)] = outlet_widget
        node_widget.layout().addItem(outlet_widget)
        self._add_cell_widgets(index)
        return outlet_widget

    def _add_link_widget(self, index: QModelIndex):
        source_index = index.data(GraphDataRole.SourceRole)
        assert isinstance(source_index, QPersistentModelIndex), f"Source index mus be a QPersistentIndex, got: {source_index}!"
        assert source_index in self._row_widgets, f"Warning: link({index}) source({source_index}) not found in _row_widgets!"
        target_index = QPersistentModelIndex(index.parent())

        source_widget = self._row_widgets[source_index]
        target_widget = self._row_widgets[target_index]

        link_widget = LinkWidget()
        self._row_widgets[QPersistentModelIndex(index)] = link_widget
        self.graphicsview.scene().addItem(link_widget)

        # store widget references
        source_widget._links.append(link_widget)
        target_widget._links.append(link_widget)
        link_widget._source_widget = source_widget
        link_widget._target_widget = target_widget

        link_widget.updateLine()
    #
    ### Handle Model Signals
    def populate(self):
        assert self._model
        ## clear
        self.graphicsview.scene().clear()
        self._row_widgets.clear()
        self._cell_widgets.clear()

        # create node_items from rows
        for row in range(self._model.rowCount(parent=QModelIndex())):
            node_index = self._model.index(row, 0, parent=QModelIndex())
            node_widget = self._add_node_widget(node_index)

            # create inlets and outlets from children
            for child_row in range(self._model.rowCount(parent=node_index)):
                port_index = self._model.index(child_row, 0, parent=node_index)
                # check the type of the inlet
                item_type = port_index.data(GraphDataRole.TypeRole)
                match item_type:
                    case RowType.INLET | None:
                        # by default create an inlets 
                        inlet_widget = self._add_inlet_widget(port_index)
                    case RowType.OUTLET:
                        # this is an outlet, create an OutletItem
                        outlet_widget = self._add_outlet_widget(port_index)
                    case RowType.LINK:
                        raise NotImplementedError("direct incoming links are not supported yet")
                    case _:
                        raise NotImplementedError("{item_type} is not a valid children!")
                    
        # create links for inlet children
        for row in range(self._model.rowCount(parent=QModelIndex())):
            node_index = self._model.index(row, 0, parent=QModelIndex())
            # create inlets and outlets from children
            for child_row in range(self._model.rowCount(parent=node_index)):
                port_index = self._model.index(child_row, 0, parent=node_index)
                # check the type of the inlet
                item_type = port_index.data(GraphDataRole.TypeRole)
                match item_type:
                    case RowType.INLET | None:
                        inlet_index = port_index

                        # create links for children rows
                        for link_row in range(self._model.rowCount(parent=inlet_index)):
                            link_index = self._model.index(link_row, 0, parent=inlet_index)
                            item_type = link_index.data(GraphDataRole.TypeRole)
                            match item_type:
                                case RowType.LINK | None:
                                    link_widget = self._add_link_widget(link_index)
                                case _:
                                    print(f"Warning: {item_type} is not a valid link type!")


class LinkWidget(QGraphicsLineItem):
    def __init__(self, parent: QGraphicsItem | None = None):
        super().__init__(parent=parent)
        self.setPen(QPen(Qt.GlobalColor.white, 3))
        # self.setZValue(-1)  # Ensure links are drawn below nodes
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setLine(QLineF(0, 0, 20, 20))  # Initialize with a default line
        self._source_widget: QGraphicsItem | None = None
        self._target_widget: QGraphicsItem | None = None

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget=None):
        if self.isSelected():
            painter.setPen(QPen(Qt.GlobalColor.cyan, 2))
        else:
            painter.setPen(QPen(Qt.GlobalColor.blue, 2))
        painter.drawLine(self.line())
        # super().paint(painter, option, widget)

    def updateLine(self):
        if self._source_widget and self._target_widget:
            source_pos = self._source_widget.scenePos()
            target_pos = self._target_widget.scenePos()
            self.setLine(QLineF(source_pos, target_pos))


class PortWidget(QGraphicsWidget):
    def __init__(self, parent: QGraphicsItem | None = None):
        super().__init__(parent=parent)
        # self.setGeometry(-14,0,14,14)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsScenePositionChanges, True)
        self.setLayout(QGraphicsLinearLayout(Qt.Orientation.Horizontal, self))
        self._links = []

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
    ...


class OutletWidget(PortWidget):
    ...


class NodeWidget(QGraphicsWidget):
    def __init__(self, parent: QGraphicsItem | None = None):
        super().__init__(parent=parent)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsScenePositionChanges, True)

        layout = QGraphicsLinearLayout(Qt.Orientation.Vertical)
        self.setLayout(layout)
        self._links = []

    def paint(self, painter: QPainter, option: QStyleOption, widget=None):
        rect = option.rect       
        painter.setBrush(self.palette().alternateBase())
        if self.isSelected():
            painter.setBrush(self.palette().highlight())
        painter.drawRoundedRect(rect, 6, 6)

    def itemChange(self, change, value):
        match change:
            case QGraphicsItem.GraphicsItemChange.ItemScenePositionHasChanged:
                for link in self._links:
                    link.updateLine()
        return super().itemChange(change, value)

