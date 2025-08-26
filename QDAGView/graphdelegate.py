from typing import *
from qtpy.QtGui import *
from qtpy.QtCore import *
from qtpy.QtWidgets import *
from graphview_widgets import InletWidget, LinkWidget, NodeWidget, OutletWidget
from core import GraphDataRole, GraphItemType


from graphview_widgets import NodeWidget, InletWidget, OutletWidget, LinkWidget


class GraphDelegate(QObject):
    """
    Delegate for the GraphView.
    This is used to handle events and interactions with the graph view.
    """

    portPositionChanged = Signal(QPersistentModelIndex)

    def __init__(self):
        super().__init__()

    ## READ MODEL
    def linkSource(self, link_index:QModelIndex|QPersistentModelIndex) -> QModelIndex|None:
        source_index = link_index.data(GraphDataRole.SourceRole)
        assert source_index is None or source_index.isValid(), f"Source index must be valid or None, got: {source_index}"
        return QModelIndex(source_index) if source_index else None
    
    def linkTarget(self, link_index:QModelIndex|QPersistentModelIndex) -> QModelIndex:
        assert link_index.isValid(), "Link index must be valid"
        target_index = link_index.parent()
        assert target_index.isValid(), "Target index must be valid"
        return target_index
    
    def itemType(self, index:QModelIndex|QPersistentModelIndex)-> GraphItemType | None:
        row_kind = index.data(GraphDataRole.TypeRole)
        if not row_kind:
            row_kind = self._defaultItemType(index)
        assert self._validateItemType(index, row_kind), f"Invalid row kind {row_kind} for index {index}!"
        return row_kind
    
    def _defaultItemType(self, index:QModelIndex|QPersistentModelIndex) -> GraphItemType | None:
        """
        Determine the kind of row based on the index.
        This is used to determine whether to create a Node, Inlet, Outlet or Link widget.
        Args:
            index (QModelIndex): The index of the row.
        """
        if not index.isValid():
            return GraphItemType.SUBGRAPH
        elif index.parent() == QModelIndex():
            return GraphItemType.NODE
        elif index.parent().isValid() and index.parent().parent() == QModelIndex():
            return GraphItemType.INLET
        elif index.parent().isValid() and index.parent().parent().isValid() and index.parent().parent().parent() == QModelIndex():
            return GraphItemType.LINK
        else:
            raise ValueError(
                f"Invalid index: {index}. "
                "Index must be a valid QModelIndex with a valid parent."
            )
        
    def _validateItemType(self, index:QModelIndex|QPersistentModelIndex, item_type: 'GraphItemType') -> bool:
        """
        Validate the row kind based on the index.
        This is used to ensure that the row kind matches the expected kind
        Args:   

            index (QModelIndex): The index of the row.
            row_kind (NodeType | None): The kind of row to validate.
        Returns:
            bool: True if the row kind is valid, False otherwise.
        """

        if item_type is None:
            return True  # No specific row kind, so always valid
        elif item_type == GraphItemType.SUBGRAPH:
            return not index.isValid()
        if item_type == GraphItemType.NODE:
            return index.parent() == QModelIndex()
        elif item_type == GraphItemType.INLET:
            return index.parent().isValid() and index.parent().parent() == QModelIndex()
        elif item_type == GraphItemType.OUTLET:
            return index.parent().isValid() and index.parent().parent() == QModelIndex()
        elif item_type == GraphItemType.LINK:
            return index.parent().isValid() and index.parent().parent().isValid() and index.parent().parent().parent() == QModelIndex()

    def canLink(self, source:QModelIndex, target:QModelIndex)->bool:
        """
        Check if linking is possible between the source and target indexes.
        """

        if source.parent() == target.parent():
            # Cannot link items in the same parent
            return False
        
        source_type = self.itemType(source)
        target_type = self.itemType(target)
        if  (source_type, target_type) == (GraphItemType.INLET, GraphItemType.OUTLET) or \
            (source_type, target_type) == (GraphItemType.OUTLET, GraphItemType.INLET):
            # Both source and target must be either inlet or outlet
            return True
        
        return False
    
    def inletCount(self, node:QModelIndex|QPersistentModelIndex) -> int:
        """
        Get the number of inlets for a given node.
        Args:
            node (QModelIndex): The index of the node.
        Returns:
            int: The number of inlets for the node.
        """
        assert self.itemType(node) == GraphItemType.NODE, "Node index must be of type NODE"
        model = node.model()
        inlet_count = 0
        for row in range(model.rowCount(node)):
            child_index = model.index(row, 0, node)
            if self.itemType(child_index) == GraphItemType.INLET:
                inlet_count += 1
        return inlet_count

    def outletCount(self, node:QModelIndex|QPersistentModelIndex) -> int:
        """
        Get the number of outlets for a given node.
        Args:
            node (QModelIndex): The index of the node.
        Returns:
            int: The number of outlets for the node.
        """
        assert self.itemType(node) == GraphItemType.NODE, "Node index must be of type NODE"
        model = node.model()
        outlet_count = 0
        for row in range(model.rowCount(node)):
            child_index = model.index(row, 0, node)
            if self.itemType(child_index) == GraphItemType.OUTLET:
                outlet_count += 1
        return outlet_count

    ## CREATE MODEL
    def addNode(self, model:QAbstractItemModel, subgraph:QModelIndex|QPersistentModelIndex=QModelIndex()):
        position = model.rowCount(subgraph)
        if model.insertRows(position, 1, subgraph):
            new_index = model.index(position, 0, subgraph)
            assert new_index.isValid(), "Created index is not valid"
            new_node_name = f"{'Node'}#{position + 1}"
            success = model.setData(new_index, new_node_name, Qt.ItemDataRole.DisplayRole)
            assert success, "Failed to set data for the new child item"
            return True
        return False

    def addInlet(self, model:QAbstractItemModel, node:QModelIndex|QPersistentModelIndex)->bool:
        assert node.isValid(), "Node index must be valid"
        assert self.itemType(node) == GraphItemType.NODE, "Node index must be of type NODE"
        
        # Make sure the parent has at least one column for children, otherwise the treeview won't show them
        if model.columnCount(node) == 0:
            model.insertColumns(0, 1, node)

        # Append child to the selected item using generic methods
        position = model.rowCount(node)
        if model.insertRows(position, 1, node):
            new_index = model.index(position, 0, node)
            assert new_index.isValid(), "Created index is not valid"
            new_inlet_name = f"{'in'}#{position + 1}"
            success = model.setData(new_index, new_inlet_name, Qt.ItemDataRole.DisplayRole)
            assert success, "Failed to set data for the new child item"
            return True
        return False

    def addOutlet(self, model:QAbstractItemModel, node:QModelIndex|QPersistentModelIndex)->bool:
        assert node.isValid(), "Node index must be valid"
        assert self.itemType(node) == GraphItemType.NODE, "Node index must be of type NODE"
        
        if model.columnCount(node) == 0:
            # Make sure the parent has at least one column for children, otherwise the treeview won't show them
            model.insertColumns(0, 1, node)

        position = model.rowCount(node)
        if model.insertRows(position, 1, node):
            new_index = model.index(position, 0, node)
            assert new_index.isValid(), "Created index is not valid"
            new_outlet_name = f"{'out'}#{position + 1}"
            success = model.setData(new_index, new_outlet_name, Qt.ItemDataRole.DisplayRole)
            success = model.setData(new_index, GraphItemType.OUTLET, GraphDataRole.TypeRole)
            assert success, "Failed to set data for the new child item"
            return True
        return False

    def addLink(self, model:QAbstractItemModel, outlet:QModelIndex|QPersistentModelIndex, inlet:QModelIndex|QPersistentModelIndex):
        """Add a child item to the currently selected item."""
        assert model is not None, "Source model must be set before adding child items"
        assert outlet.isValid()
        assert self.itemType(outlet) == GraphItemType.OUTLET, "Outlet index must be of type OUTLET"
        assert inlet.isValid()
        assert self.itemType(inlet) == GraphItemType.INLET, "Inlet index must be of type INLET"

        # Add child to the selected item using generic methods
        position = model.rowCount(inlet)

        # Make sure the parent has at least one column for children, otherwise the treeview won't show them
        if model.columnCount(inlet) == 0:
            model.insertColumns(0, 1, inlet)
        
        if model.insertRows(position, 1, inlet):
            link_index = model.index(position, 0, inlet)
            new_link_name = f"{'Link'}#{position + 1}"
            model.setData(link_index, new_link_name, role=Qt.ItemDataRole.DisplayRole)
            model.setData(link_index, outlet, role=GraphDataRole.SourceRole)
        
    ## UPDATE MODEL
    def setLinkSource(self, model:QAbstractItemModel, link:QModelIndex|QPersistentModelIndex, source:QModelIndex|QPersistentModelIndex):
        """
        Set the source of a link.
        This sets the source of the link at the specified index to the given source index.
        """
        assert model, "Source model must be set before setting a link source"
        assert link.isValid(), "Link index must be valid"
        assert source.isValid(), "Source index must be valid"
        model.setData(link, source, role=GraphDataRole.SourceRole)

    ## DELETE MODEL
    def removeLink(self, model:QAbstractItemModel, link:QModelIndex|QPersistentModelIndex):
        """
        Remove a link from the graph.
        This removes the link at the specified index from the model.
        """
        assert model, "Source model must be set before removing a link"
        assert link.isValid(), "Link index must be valid"
        model.removeRows(link.row(), 1, link.parent())

    ## Widgets
    def createNodeWidget(self, parent_widget:QGraphicsScene | QGraphicsScene, index:QModelIndex) -> 'NodeWidget':
        assert isinstance(parent_widget, QGraphicsScene)
        widget = NodeWidget()
        parent_widget.addItem(widget)
        return widget

    def destroyNodeWidget(self, parent_widget:QGraphicsScene, widget:NodeWidget):
        assert isinstance(parent_widget, QGraphicsScene)
        parent_widget.removeItem(widget)

    def createInletWidget(self, parent_widget:'NodeWidget', index:QModelIndex) -> 'InletWidget':
        widget = InletWidget()
        node_index = index.parent()
        pos = self.inletCount(node_index)
        parent_widget.insertInlet(pos, widget)
        widget.scenePositionChanged.connect(lambda pos, idx=QPersistentModelIndex(index): self.portPositionChanged.emit(idx))
        return widget
    
    def destroyInletWidget(self, parent_widget:'NodeWidget', widget:InletWidget):
        assert isinstance(parent_widget, NodeWidget)
        node_widget = parent_widget
        inlet_widget = cast(InletWidget, widget)
        node_widget.removeInlet(inlet_widget)
    
    def createOutletWidget(self, parent_widget:'NodeWidget', index:QModelIndex) -> 'OutletWidget':
        widget = OutletWidget()
        node_index = index.parent()
        pos = self.outletCount(node_index)
        parent_widget.insertOutlet(pos, widget)
        widget.scenePositionChanged.connect(lambda pos, idx=QPersistentModelIndex(index): self.portPositionChanged.emit(idx))
        return widget
    
    def destroyOutletWidget(self, parent_widget:'NodeWidget', widget:OutletWidget):
        assert isinstance(parent_widget, NodeWidget)
        outlet_widget = cast(OutletWidget, widget)
        node_widget = parent_widget
        node_widget.removeOutlet(outlet_widget)
        
    def createLinkWidget(self, parent_widget:QGraphicsItem | QGraphicsScene, index:QModelIndex) -> 'LinkWidget':
        assert isinstance(parent_widget, InletWidget)
        link_widget = LinkWidget()
        parent_widget.scene().addItem(link_widget)
        return link_widget
    
    def destroyLinkWidget(self, parent_widget:QGraphicsItem | QGraphicsScene, widget:LinkWidget):
        assert isinstance(parent_widget, InletWidget)
        link_widget = cast(LinkWidget, widget)
        parent_widget.scene().removeItem(link_widget)

    ## QT delegate
    def createEditor(self, parent:QWidget, option:QStyleOptionViewItem, index:QModelIndex|QPersistentModelIndex) -> QWidget:
        return QLineEdit(parent=None)

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
        
    
    