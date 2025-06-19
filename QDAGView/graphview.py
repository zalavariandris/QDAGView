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
from utils import bfs
from graphdelegate import GraphDelegate


class GraphView(QGraphicsView):
    class State(Enum):
        IDLE = "IDLE"
        LINKING = "LINKING"
        
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent=parent)
        self._model:QAbstractItemModel | None = None
        self._model_connections = []
        self._selection:QItemSelectionModel | None = None
        self._selection_connections:List[Tuple[Signal, Callable]] = []
        # store model widget relations
        self._widgets: dict[QPersistentModelIndex, BaseRowWidget] = dict()
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
        self._delegate = GraphDelegate()

    def indexFromWidget(self, widget:BaseRowWidget) -> QPersistentModelIndex|None:
        """
        Get the index of the node widget in the model.
        This is used to identify the node in the model.
        """
        return widget._index
    
    def widgetFromIndex(self, index:QModelIndex) -> BaseRowWidget|None:
        """
        Get the widget from the index.
        This is used to identify the node in the model.
        """
        return self._widgets.get(QPersistentModelIndex(index), None)

    def setModel(self, model:QAbstractItemModel):
        if self._model_connections:
            for signal, slot in self._model_connections:
                signal.disconnect(slot)
        
        if model:
            assert isinstance(model, QAbstractItemModel), "Model must be a subclass of QAbstractItemModel"

            self._model_connections = [
                (model.rowsInserted, self.onRowsInserted),
                (model.rowsAboutToBeRemoved, self.onRowsAboutToBeRemoved),
                (model.rowsRemoved, self.onRowsRemoved),
                (model.dataChanged, self.onDataChanged)
            ]

            for signal, slot in self._model_connections:
                signal.connect(slot)
        self._model = model
        
        # populate initial scene
        ## clear
        self.scene().clear()
        self._widgets.clear()
        self.onRowsInserted(QModelIndex(), 0, self._model.rowCount(QModelIndex()) - 1)

    def model(self) -> QAbstractItemModel | None:
        return self._model
    
    def onRowsInserted(self, parent:QModelIndex, start:int, end:int):
        assert self._model, "Model must be set before handling rows inserted!"
        def children(index:QModelIndex) -> Iterable[QModelIndex]:
            model = index.model()
            for row in range(model.rowCount(index)):
                child_index = model.index(row, 0, index)
                yield child_index
            return []
        
        for index in bfs(*[self._model.index(row, 0, parent) for row in range(start, end + 1)], children=children, reverse=False):
            match self._delegate.itemType(index):
                case GraphItemType.SUBGRAPH:
                    raise NotImplementedError("Subgraphs are not yet supported in the graph view")
                case GraphItemType.NODE:
                    self._add_node_widget(QPersistentModelIndex(index))
                case GraphItemType.INLET:
                    self._add_inlet_widget(QPersistentModelIndex(index))
                case GraphItemType.OUTLET:
                    self._add_outlet_widget(QPersistentModelIndex(index))
                case GraphItemType.LINK:
                    self._add_link_widget(QPersistentModelIndex(index))

    def onRowsAboutToBeRemoved(self, parent:QModelIndex, start:int, end:int):
        ...

        def children(index:QModelIndex) -> Iterable[QModelIndex]:
            model = index.model()
            for row in range(model.rowCount(index)):
                child_index = model.index(row, 0, index)
                yield child_index
            return []
        
        for index in bfs(*[self._model.index(row, 0, parent) for row in range(start, end + 1)], children=children, reverse=True):
            match self._delegate.itemType(index):
                case GraphItemType.SUBGRAPH:
                    raise NotImplementedError("Subgraphs are not yet supported in the graph view")
                case GraphItemType.NODE:
                    self._remove_node_widget(QPersistentModelIndex(index))
                case GraphItemType.INLET:
                    self._remove_inlet_widget(QPersistentModelIndex(index))
                case GraphItemType.OUTLET:
                    self._remove_outlet_widget(QPersistentModelIndex(index))
                case GraphItemType.LINK:
                    self._remove_link_widget(QPersistentModelIndex(index))

    def onRowsRemoved(self, parent:QModelIndex, start:int, end:int):
        ...
    
    def onDataChanged(self, top_left:QModelIndex, bottom_right:QModelIndex, roles:list):
        """
        Handle data changes in the model.
        This updates the widgets in the graph view.
        """
        for row in range(top_left.row(), bottom_right.row() + 1):
            index = self._model.index(row, top_left.column(), top_left.parent())
            if widget := self._widgets.get(QPersistentModelIndex(index)):
                widget.setLabel(index.data(Qt.ItemDataRole.DisplayRole))

    # # Selection
    def setSelectionModel(self, selection: QItemSelectionModel):
        """
        Set the selection model for the graph view.
        This is used to synchronize the selection of nodes in the graph view
        with the selection model.
        """
        assert isinstance(selection, QItemSelectionModel), f"got: {selection}"
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
        assert self._model, "Model must be set before handling selection changes!"
        assert self._selection.model() == self._model, "Selection model must be for the same model as the graph view!"
        print(f"onSelectionChanged: {selected.indexes()}, {deselected.indexes()}")
        scene = self.scene()
        scene.blockSignals(True)
        
        selected_indexes = sorted([idx for idx in selected.indexes()], 
                                  key= lambda idx: idx.row(), 
                                  reverse= True)
        
        deselected_indexes = sorted([idx for idx in deselected.indexes()], 
                                    key= lambda idx: idx.row(), 
                                    reverse= True)
        
        for index in deselected_indexes:
            if index.isValid() and index.column() == 0:
                if widget:=self.widgetFromIndex(QPersistentModelIndex(index)):
                    if widget.scene() and widget.isSelected():
                        widget.setSelected(False)

        for index in selected_indexes:
            if index.isValid() and index.column() == 0:
                if widget:=self.widgetFromIndex(QPersistentModelIndex(index)):
                    if widget.scene() and not widget.isSelected():
                        widget.setSelected(True)
        
        scene.blockSignals(False)

    def updateSelectionModel(self):
        """update selection model from scene selection"""
        print("updateSelectionModel")
        if self._model and self._selection:
            # get currently selected widgets
            selected_widgets = self.scene().selectedItems()

            # map widgets to QModelIndexes
            selected_indexes = map(self.indexFromWidget, selected_widgets)
            selected_indexes = filter(lambda idx: idx is not None and idx.isValid(), selected_indexes)
            
            assert self._model
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
        widget._index = QPersistentModelIndex(index)
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
        widget._index = QPersistentModelIndex(index)
        self._set_data(index, 0)

        # attach to parent widget
        if index.parent().isValid():
            parent_widget = self.widgetFromIndex(index.parent())
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
        widget._index = QPersistentModelIndex(index)
        self._set_data(index, 0)

        # attach to parent widget
        self.scene().addItem(widget)
        if index.parent().isValid():
            parent_widget = self.widgetFromIndex(index.parent())
            parent_widget = cast(NodeWidget, parent_widget)
            parent_widget.addOutlet(widget)

    def _add_link_widget(self, index:QPersistentModelIndex):
        """
        Try to add a link widget to the graph view.
        """
        assert isinstance(index, QPersistentModelIndex), "Index must be a QPersistentModelIndex"
        assert index.column()==0, "Index must be in the first column"

        widget = LinkWidget(graphview=self)
        self._widgets[index] = widget
        widget._index = QPersistentModelIndex(index)
        self.scene().addItem(widget)
        source_index = self._delegate.linkSource(index)
        source_outlet = self._widgets[QPersistentModelIndex(source_index)] if source_index.isValid() else None
        target_index = self._delegate.linkTarget(index)
        target_inlet = self._widgets[QPersistentModelIndex(target_index)] if target_index.isValid() else None
        widget.link(source_outlet, target_inlet)

    def _remove_node_widget(self, index:QPersistentModelIndex):
        """Remove a node widget"""
        assert isinstance(index, QPersistentModelIndex), "Index must be a QPersistentModelIndex"
        assert index.column()==0, "Index must be in the first column"

        self.scene().blockSignals(True) #Block signals to prevent unnecessary updates during removal, eg selection
        # store widget
        widget = self.widgetFromIndex(index)

        # remove widget from graphview
        del self._widgets[index]

        # detach from scene or parent widget
        if index.parent().isValid():
            raise NotImplementedError()
        else:
            self.scene().removeItem(widget)
        print(f"Removed node widget")
        self.scene().blockSignals(False)  # Unblock signals after removal
        
    def _remove_inlet_widget(self, index:QPersistentModelIndex):
        """Remove an inlet widget and its associated cell widgets."""
        assert isinstance(index, QPersistentModelIndex), "Index must be a QPersistentModelIndex"
        assert index.column()==0, "Index must be in the first column"
        
        self.scene().blockSignals(True)  # Block signals to prevent unnecessary updates during removal, eg selection
        # store widget
        widget = self.widgetFromIndex(index)

        # remove widget from graphview
        del self._widgets[index]

        # detach widget from scene (or parent widget)
        if index.parent().isValid():
            parent_widget = self._widgets[QPersistentModelIndex(index.parent())]
            parent_widget = cast(NodeWidget, parent_widget)
            parent_widget.removeInlet(widget)
        else:
            raise NotImplementedError("support inlets attached to the root graph")
        print(f"Removed inlet widget")
        self.scene().blockSignals(False)  # Unblock signals after removal

    def _remove_outlet_widget(self, index:QPersistentModelIndex):
        """Remove an outlet widget and its associated cell widgets."""
        assert isinstance(index, QPersistentModelIndex), "Index must be a QPersistentModelIndex"
        assert index.column()==0, "Index must be in the first column"
        
        self.scene().blockSignals(True)  # Block signals to prevent unnecessary updates during removal, eg selection
        # store widget  
        widget = self.widgetFromIndex(index)

        # remove widget from graphview
        del self._widgets[index]

        # detach widget from scene (or parent widget)
        if index.parent().isValid():
            parent_widget = self._widgets[QPersistentModelIndex(index.parent())]
            parent_widget = cast(NodeWidget, parent_widget)
            parent_widget.removeOutlet(widget)
        else:
            raise NotImplementedError("support inlets attached to the root graph")
        
        
        print(f"Removed outlet widget")
        self.scene().blockSignals(False)  # Unblock signals after removal
        
    def _remove_link_widget(self, index:QPersistentModelIndex):
        """Remove an inlet widget and its associated cell widgets."""
        assert isinstance(index, QPersistentModelIndex), "Index must be a QPersistentModelIndex"
        assert index.column()==0, "Index must be in the first column"
        
        self.scene().blockSignals(True)  # Block signals to prevent unnecessary updates during removal, eg selection
        # store widget
        widget = self.widgetFromIndex(index)

        # remove widget from graphview
        del self._widgets[index]

        # detach widget from scene (or parent widget)
        assert isinstance(widget, LinkWidget), "Link widget must be of type LinkWidget"
        link_widget = cast(LinkWidget, widget)
        link_widget.unlink()  # Unlink the link widget from its source and target items
        link_widget.setParentItem(None)
        self.scene().removeItem(link_widget)  # Remove from scene immediately

        
        print(f"Removed link widget")
        self.scene().blockSignals(False)  # Unblock signals after removal

    def _set_data(self, index:QPersistentModelIndex, column:int, roles:list=[]):
        """Set the data for a node widget."""
        assert isinstance(index, QPersistentModelIndex), "Index must be a QPersistentModelIndex"
        assert index.column() == 0, "Index must be in the first column"

        if widget := self.widgetFromIndex(index):
            widget.setLabel(index.data(Qt.ItemDataRole.DisplayRole))

    ## INTERNAL DRAG AND DROP
    def _inletMimeData(self, inlet:QPersistentModelIndex)->QMimeData:
        """
        Create a QMimeData object for an inlet.
        This is used to provide data for drag-and-drop operations.
        """
        mime = QMimeData()

        # Convert index to path string
        path = []
        idx = inlet
        while idx.isValid():
            path.append(idx.row())
            idx = idx.parent()
        path = "/".join(map(str, reversed(path)))
        mime.setData(GraphMimeData.InletData, path.encode("utf-8"))
        return mime

    def _decodeInletMimeData(self, mime:QMimeData) -> QPersistentModelIndex:
        """
        Decode a QMimeData object to a persistent model index.
        This is used to get the original index from the mime data.
        """
        if not mime.hasFormat(GraphMimeData.InletData):
            return QPersistentModelIndex()
        
        path = mime.data(GraphMimeData.InletData).data().decode("utf-8")
        path = list(map(int, path.split("/")))

        idx = self._model.index(path[0], 0, QModelIndex())
        for row in path[1:]:
            idx = self._model.index(row, 0, idx)
        return QPersistentModelIndex(idx)
    
    def _outletMimeData(self, outlet:QPersistentModelIndex):
        """
        Create a QMimeData object for an inlet.
        This is used to provide data for drag-and-drop operations.
        """
        mime = QMimeData()

        # Convert index to path string
        path = []
        idx = outlet
        while idx.isValid():
            path.append(idx.row())
            idx = idx.parent()
        path = "/".join(map(str, reversed(path)))
        mime.setData(GraphMimeData.OutletData, path.encode("utf-8"))
        return mime
    
    def _decodeOutletMimeData(self, mime:QMimeData) -> QPersistentModelIndex:
        """
        Decode a QMimeData object to a persistent model index.
        This is used to get the original index from the mime data.
        """
        if not mime.hasFormat(GraphMimeData.OutletData):
            return QPersistentModelIndex()
        
        path = mime.data(GraphMimeData.OutletData).data().decode("utf-8")
        path = list(map(int, path.split("/")))

        idx = self._model.index(path[0], 0, QModelIndex())
        for row in path[1:]:
            idx = self._model.index(row, 0, idx)
        return QPersistentModelIndex(idx)
    
    def _linkTailMimeData(self, link:QPersistentModelIndex) -> QMimeData:
        """
        Create a QMimeData object for a link source.
        This is used to provide data for drag-and-drop operations.
        """
        assert link.isValid(), "Link index must be valid"
        mime = QMimeData()

        # Convert index to path string
        path = []
        idx = link
        while idx.isValid():
            path.append(idx.row())
            idx = idx.parent()
        path = "/".join(map(str, reversed(path)))
        mime.setData(GraphMimeData.LinkTailData, path.encode("utf-8"))
        return mime
    
    def _decodeLinkTailMimeData(self, mime:QMimeData) -> QPersistentModelIndex:
        """
        Decode a QMimeData object to a persistent model index.
        This is used to get the original index from the mime data.
        """
        if not mime.hasFormat(GraphMimeData.LinkTailData):
            return QPersistentModelIndex()
        
        path = mime.data(GraphMimeData.LinkTailData).data().decode("utf-8")
        path = list(map(int, path.split("/")))

        idx = self._model.index(path[0], 0, QModelIndex())
        for row in path[1:]:
            idx = self._model.index(row, 0, idx)
        return QPersistentModelIndex(idx)
    
    def _linkHeadMimeData(self, link:QPersistentModelIndex) -> QMimeData:
        """
        Create a QMimeData object for a link head.
        This is used to provide data for drag-and-drop operations.
        """
        mime = QMimeData()

        # Convert index to path string
        path = []
        idx = link
        while idx.isValid():
            path.append(idx.row())
            idx = idx.parent()
        path = "/".join(map(str, reversed(path)))
        mime.setData(GraphMimeData.LinkHeadData, path.encode("utf-8"))
        return mime

    def _decodeLinkHeadMimeData(self, mime:QMimeData) -> QPersistentModelIndex:
        """
        Decode a QMimeData object to a persistent model index.
        This is used to get the original index from the mime data.
        """
        if not mime.hasFormat(GraphMimeData.LinkHeadData):
            return QPersistentModelIndex()
        
        path = mime.data(GraphMimeData.LinkHeadData).data().decode("utf-8")
        path = list(map(int, path.split("/")))

        idx = self._model.index(path[0], 0, QModelIndex())
        for row in path[1:]:
            idx = self._model.index(row, 0, idx)
        return QPersistentModelIndex(idx)

    ## Handle drag and drop
    def _canDropMimeData(self, data:QMimeData, action:Qt.DropAction, drop_target:QPersistentModelIndex) -> bool:
        """
        Check if the mime data can be dropped on the graph view.
        This is used to determine if the drag-and-drop operation is valid.
        """
        drop_target_type = self._delegate.itemType(drop_target)
        if data.hasFormat(GraphMimeData.OutletData):
            return True
        
        elif data.hasFormat(GraphMimeData.InletData):
            return True
        
        elif data.hasFormat(GraphMimeData.LinkTailData):
            return True
        
        elif data.hasFormat(GraphMimeData.LinkHeadData):
            return True
        
        return False

    def _dropMimeData(self, data:QMimeData, action:Qt.DropAction, drop_target:QPersistentModelIndex) -> bool:
        drop_target_type = self._delegate.itemType(drop_target)
        
        if data.hasFormat(GraphMimeData.OutletData):
            # outlet dropped
            
            outlet_index = self._decodeOutletMimeData(data)
            print(f"Outlet {outlet_index.data()} dropped on", drop_target.data())
            assert outlet_index.isValid(), "Outlet index must be valid"
              # Ensure drop target is valid
            if drop_target_type == GraphItemType.INLET:
                # ... on inlet
                inlet_index = drop_target
                self._delegate.addLink(self._model, outlet_index, inlet_index)
                return True

        if data.hasFormat(GraphMimeData.InletData):
            # inlet dropped
            inlet_index = self._decodeInletMimeData(data)
            assert inlet_index.isValid(), "Inlet index must be valid"
            print(f"Inlet {inlet_index.data()} dropped on {drop_target.parent().data()}.{drop_target.data()}")
            if drop_target_type == GraphItemType.OUTLET:
                # ... on outlet
                outlet_index = drop_target
                self._delegate.addLink(self._model, outlet_index, inlet_index)
                return True
            
        if data.hasFormat(GraphMimeData.LinkTailData):
            # link tail dropped
            link_index = self._decodeLinkTailMimeData(data)
            assert link_index.isValid(), "Link index must be valid"
            print(f"Tail {link_index.data()} dropped on", drop_target.data())
            if drop_target_type == GraphItemType.INLET:
                # ... on inlet
                inlet_index = drop_target
                self._delegate.removeLink(self._model, link_index)
                self._delegate.addLink(self._model, outlet_index, inlet_index)
                return True
            elif drop_target_type == GraphItemType.OUTLET:
                # ... on outlet
                # relink outlet
                new_outlet_index = drop_target
                current_inlet_index = self.linkTarget(link_index)
                self._delegate.removeLink(self._model, link_index)
                self._delegate.addLink(self._model, new_outlet_index, current_inlet_index)
                return True
            else:
                # ... on empty space
                IsLinked = self._delegate.linkSource(link_index).isValid() and self._delegate.linkTarget(link_index).isValid()
                if IsLinked:
                    self._delegate.removeLink(self._model, link_index)
                    return True
                return True
            
        if data.hasFormat(GraphMimeData.LinkHeadData):
            # link head dropped
            link_index = self._decodeLinkHeadMimeData(data)
            assert link_index.isValid(), "Link index must be valid"
            print(f"Head {link_index.data()} dropped on", drop_target.data())
            if drop_target_type == GraphItemType.OUTLET:
                # ... on outlet
                outlet_index = drop_target
                self._delegate.removeLink(self._model, link_index)
                self._delegate.addLink(self._model, outlet_index, link_index)
                return True
            
            elif drop_target_type == GraphItemType.INLET:
                # ... on inlet
                # relink inlet
                new_inlet_index = drop_target
                current_outlet_index = self._delegate.linkSource(link_index)
                self._delegate.removeLink(self._model, link_index)
                self._delegate.addLink(self._model, current_outlet_index, new_inlet_index)
                return True
            else:
                # ... on empty space
                IsLinked = self._delegate.linkSource(link_index).isValid() and self._delegate.linkTarget(link_index).isValid()
                if IsLinked:
                    self._delegate.removeLink(self._model, link_index)
                    return True
                return True
    
        return False
    
    ## Handle drag ad drop events
    def _createDraftLink(self):
        """Safely create draft link with state tracking"""
        assert self._draft_link is None
            
        self._draft_link = QGraphicsLineItem()
        self._draft_link.setPen(QPen(self.palette().text(), 1))
        self.scene().addItem(self._draft_link)

    def _updateDraftLink(self, source:QGraphicsItem|QPointF, target:QGraphicsItem|QPointF):
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

    
    # Handle drag and drop events
    def dragMoveEvent(self, event)->None:
        """Handle drag move events to update draft link position"""
        drop_target_index = self.indexAt(event.position().toPoint())
        if self._canDropMimeData(event.mimeData(), event.dropAction(), drop_target_index):
            if event.mimeData().hasFormat(GraphMimeData.OutletData):
                # Outlet dragged
                outlet_index = self._decodeOutletMimeData(event.mimeData())
                assert outlet_index.isValid(), "Outlet index must be valid"
                outlet_widget = self.widgetFromIndex(outlet_index)
                if self._delegate.itemType(drop_target_index) == GraphItemType.INLET:
                    # ...over inlet
                    inlet_widget = self.widgetFromIndex(drop_target_index)
                    self._updateDraftLink(source=outlet_widget, target=inlet_widget)
                    event.acceptProposedAction()
                    return
                else:
                    # ...over empty space
                    self._updateDraftLink(source=outlet_widget, target=self.mapToScene(event.position().toPoint()))
                    event.acceptProposedAction() 
                    return
            
            if event.mimeData().hasFormat(GraphMimeData.InletData):
                # inlet dragged
                inlet_index = self._decodeInletMimeData(event.mimeData())
                assert inlet_index.isValid(), "Inlet index must be valid"
                inlet_widget = self.widgetFromIndex(inlet_index)
                if self._delegate.itemType(drop_target_index) == GraphItemType.OUTLET:
                    # ... over outlet
                    outlet_widget = self.widgetFromIndex(drop_target_index)
                    self._updateDraftLink(source=outlet_widget, target=inlet_widget)
                    event.acceptProposedAction()
                    return
                else:
                    # ... over empty space
                    self._updateDraftLink(source=self.mapToScene(event.position().toPoint()), target=inlet_widget)
                    event.acceptProposedAction() 
                    return
            
            if event.mimeData().hasFormat(GraphMimeData.LinkHeadData):
                # link head dragged
                link_index = self._decodeLinkHeadMimeData(event.mimeData())
                assert link_index.isValid(), "Link index must be valid"
                link_widget = self.widgetFromIndex(link_index)
                if self._delegate.itemType(drop_target_index) == GraphItemType.INLET:
                    # ...over inlet
                    inlet_widget = self.qidgetFromIndex(drop_target_index)
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
                link_index = self._decodeLinkTailMimeData(event.mimeData())
                assert link_index.isValid(), "Link index must be valid"
                link_widget = self.widgetFromIndex(link_index)
                if self._delegate.itemType(drop_target_index) == GraphItemType.OUTLET:
                    # ...over outlet
                    outlet_widget = self.widgetFromIndex(drop_target_index)
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
        if self._dropMimeData(event.mimeData(), event.dropAction(), drop_target):
            event.acceptProposedAction()
        else:
            event.ignore()

        # if event.mimeData().hasFormat(GraphMimeData.LinkHeadData):
        #     link_index = self._model.decodeLinkHeadMimeData(event.mimeData())
        #     if link_widget := self.widgetFromIndex(link_index):
        #         link_widget.updateLine()  # Ensure the link line is updated after drop

        # if event.mimeData().hasFormat(GraphMimeData.LinkTailData):
        #     link_index = self._model.decodeLinkTailMimeData(event.mimeData())
        #     if link_widget := self.widgetFromIndex(link_index):
        #         link_widget.updateLine()  # Ensure the link line is updated after drop

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
                index = self.indexFromWidget(item)
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
        self._index:QPersistentModelIndex | None = None

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

    def paint(self, painter:QPainter, option, /, widget:QWidget|None = None):
        painter.setBrush("lightblue")
        painter.drawRect(option.rect)

    def mousePressEvent(self, event:QGraphicsSceneMouseEvent) -> None:
        assert self._view
        # Setup new drag
        index = self._view.indexFromWidget(self)
        
        assert index.isValid(), "Outlet index must be valid"
        mime = self._view._inletMimeData(index)
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
        outlet_index = self._view.indexFromWidget(self)
        
        assert outlet_index.isValid(), "Outlet index must be valid"
        mime = self._view._outletMimeData(outlet_index)
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
            index = self._view.indexFromWidget(self)
            mime = self._view._linkTailMimeData(index)
            drag = QDrag(self._view)
            drag.setMimeData(mime)

            # Execute drag
            try:
                action = drag.exec(Qt.DropAction.LinkAction)
            except Exception as err:
                traceback.print_exc()

        def startDragHead():
            assert self._view
            index = self._view.indexFromWidget(self)
            mime = self._view._linkHeadMimeData(index)
            drag = QDrag(self._view)
            drag.setMimeData(mime)

            # Execute drag
            try:
                action:Qt.DropAction = drag.exec(Qt.DropAction.LinkAction)
            except Exception as err:
                traceback.print_exc()

        tail_distance = (event.pos() - self.line().p1()).manhattanLength()
        head_distance = (event.pos() - self.line().p2()).manhattanLength()
        if self._source and self._target:
            if tail_distance < head_distance:
                startDragTail()
            else:
                startDragHead()
        elif self._target:
            startDragTail()
        elif self._source:
            startDragHead()
            
        super().mousePressEvent(event) # select on mousepress
