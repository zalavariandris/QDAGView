from PySide6.QtCore import Qt, QModelIndex, QAbstractItemModel, QObject
from typing import Any, List, Optional, Union, Dict, Self


class BaseItem:
    def __init__(self, data: List[Any]):
        """Initialize TreeItem with list data format only."""
        self._data: List[Any] = data.copy() if isinstance(data, list) else []
        self._parent_item: Optional['BaseItem'] = None
        self._child_items: List['BaseItem'] = []
        self._model: Optional['GraphModel'] = None
        
    def model(self) -> Optional['GraphModel']:
        """Return the model associated with this item."""
        return self._model
    
    def data(self, column: int) -> Any:
        """Return the data for the specified column."""
        return self._data[column] if 0 <= column < len(self._data) else None
    
    def setData(self, column: int, value: Any) -> bool:
        """Set data for the specified column."""
        if 0 <= column < len(self._data):
            if self._data[column] != value:
                self._data[column] = value
                self._emit_data_changed(column)
            return True  # Always return True for valid column, even if value unchanged
        return False  # Only return False for invalid column index
        
    def insert_child(self, position: int, child: Self) -> None:
        """Insert a child item at the specified position."""
        if 0 <= position <= len(self._child_items):
            self._emit_rows_about_to_be_inserted(position, 1)
            child._parent_item = self
            child._model = self._model  # Pass model reference to child
            self._set_model_recursively(child)  # Set model for all descendants
            self._child_items.insert(position, child)
            self._emit_rows_inserted()

    def append_child(self, child: Self) -> None:
        """Append a child item to this item."""
        self.insert_child(len(self._child_items), child)

    def remove_child(self, child: Self) -> bool:
        """Remove child item at the specified position."""
        position = self._child_items.index(child) if child in self._child_items else -1
        if position == -1:
            return False
        if 0 <= position < len(self._child_items):
            self._emit_rows_about_to_be_removed(position, 1)
            removed_child = self._child_items.pop(position)
            removed_child._parent_item = None
            removed_child._model = None
            self._emit_rows_removed()

    def childAt(self, row: int) -> Optional[Self]:
        """Return the child item at the specified row."""
        return self._child_items[row] if 0 <= row < len(self._child_items) else None

    def childCount(self) -> int:
        """Return the number of child items."""
        return len(self._child_items)
    
    def columnCount(self) -> int:
        """Return the number of columns (list length)."""
        return len(self._data)

    def parent(self) -> Self|None:
        """Return the parent item."""
        return self._parent_item

    def row(self) -> int:
        if self._parent_item:
            return self._parent_item._child_items.index(self)
        return -1
    
    def index(self) -> QModelIndex:
        """Get the QModelIndex for this item."""
        if self._model and self != self._model._root_item:
            return self._model.createIndex(self.row(), 0, self)
        return QModelIndex()
    
    # Helper functions
    def _set_model_recursively(self, item: 'BaseItem') -> None:
        """Recursively set model reference for all children."""
        item._model = self._model
        for child in item._child_items:
            self._set_model_recursively(child)

    def _emit_data_changed(self, column: int) -> None:
        """Emit model's dataChanged signal for this item."""
        if self._model and self != self._model._root_item:
            index = self._model.createIndex(self.row(), column, self)
            self._model.dataChanged.emit(index, index, [Qt.EditRole])

    def _emit_rows_about_to_be_inserted(self, position: int, count: int) -> None:
        """Emit model's beginInsertRows signal for this item."""
        if self._model:
            parent_index = self.index()
            self._model.beginInsertRows(parent_index, position, position + count - 1)

    def _emit_rows_inserted(self) -> None:
        """Emit model's endInsertRows signal."""
        if self._model:
            self._model.endInsertRows()

    def _emit_rows_about_to_be_removed(self, position: int, count: int) -> None:
        """Emit model's beginRemoveRows signal for this item."""
        if self._model:
            parent_index = self.index()
            self._model.beginRemoveRows(parent_index, position, position + count - 1)

    def _emit_rows_removed(self) -> None:
        """Emit model's endRemoveRows signal."""
        if self._model:
            self._model.endRemoveRows()


class NodeItem(BaseItem):
    def __init__(self, data: List[Any]):
        """Initialize NodeItem with list data format only."""
        super().__init__(data)
        self._type = "Node"
    
    def type(self) -> str:
        """Return the type of this item."""
        return self._type
    
    def appendInlet(self, inlet: 'InletItem') -> None:
        """Add an inlet to this node."""
        assert inlet.type() == "Inlet", "Only InletItem can be added as an inlet."
        if inlet in self._child_items:
            raise ValueError("Inlet already exists in this node's children.")
        # Ensure the inlet is not already a child of another node
        if inlet.parent() is not None:
            raise ValueError("Inlet is already a child of another node.")
        
        self.append_child(inlet)

    def removeInlet(self, inlet: 'InletItem') -> bool:
        """Remove an inlet from this node."""
        assert inlet.type() == "Inlet", "Only InletItem can be removed as an inlet."
        if inlet not in self._child_items:
            raise ValueError("Inlet not found in this node's children.")
        if inlet.parent() != self:
            raise ValueError("Inlet is not a child of this node.")
        return self.remove_child(inlet)

    def appendOutlet(self, outlet: 'OutletItem') -> None:
        """Add an outlet to this node."""
        assert outlet.type() == "Outlet", "Only OutletItem can be added as an outlet."
        if outlet in self._child_items:
            raise ValueError("Outlet already exists in this node's children.")
        # Ensure the outlet is not already a child of another node
        if outlet.parent() is not None:
            raise ValueError("Outlet is already a child of another node.")
        self.append_child(outlet)

    def removeOutlet(self, outlet: 'OutletItem') -> bool:
        """Remove an outlet from this node."""
        assert outlet.type() == "Outlet", "Only OutletItem can be removed as an outlet."
        if outlet not in self._child_items:
            raise ValueError("Outlet not found in this node's children.")
        if outlet.parent() != self:
            raise ValueError("Outlet is not a child of this node.")
        return self.remove_child(outlet)


class InletItem(BaseItem):
    def __init__(self, data: List[Any]):
        """Initialize InletItem with list data format only."""
        super().__init__(data)
        self._type = "Inlet"
    
    def type(self) -> str:
        """Return the type of this item."""
        return self._type


class OutletItem(BaseItem):
    def __init__(self, data: List[Any]):
        """Initialize OutletItem with list data format only."""
        super().__init__(data)
        self._type = "Outlet"
    
    def type(self) -> str:
        """Return the type of this item."""
        return self._type
    

class LinkItem(BaseItem):
    def __init__(self, data: List[Any]):
        """Initialize LinkItem with list data format only."""
        super().__init__(data)
        self._type = "Link"
    
    def type(self) -> str:
        """Return the type of this item."""
        return self._type


class SubGraphItem(BaseItem):
    def __init__(self, data: List[Any]):
        """Initialize SubGraphItem with list data format only."""
        super().__init__(data)
        self._type = "SubGraph"
    
    def type(self) -> str:
        """Return the type of this item."""
        return self._type


class GraphModel(QAbstractItemModel):
    def __init__(self, parent: QObject|None = None) -> None:
        """Initialize TreeModel with list headers."""
        super().__init__(parent)
        self._root_item = SubGraphItem(["root"])

    # Override Read Methods for compatibility with standard views
    def index(self, row: int, column: int, parent: QModelIndex = QModelIndex()) -> QModelIndex:
        if not self.hasIndex(row, column, parent):
            return QModelIndex()

        parent_item = self._root_item if not parent.isValid() else parent.internalPointer()
        child_item = parent_item.childAt(row)
        if child_item:
            return self.createIndex(row, column, child_item)
        return QModelIndex()
    
    def parent(self, index: QModelIndex) -> QModelIndex:
        if not index.isValid():
            return QModelIndex()

        child_item: BaseItem = index.internalPointer()
        if not child_item:
            return QModelIndex()

        parent_item = child_item.parent()
        # If parent_item is None or is the root, return invalid QModelIndex
        if parent_item is None or parent_item == self._root_item:
            return QModelIndex()

        return self.createIndex(parent_item.row(), 0, parent_item)
    
    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        parent_item = self._root_item if not parent.isValid() else parent.internalPointer()
        return parent_item.childCount()
    
    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return self._root_item.columnCount() if not parent.isValid() else parent.internalPointer().columnCount()

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        """Return the data stored under the given role for the item referred to by the index."""
        if not index.isValid():
            return None

        item: BaseItem = index.internalPointer()
        if role in (Qt.DisplayRole, Qt.EditRole):
            return item.data(index.column())
        return None
    
    ## Optional read methods
    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole) -> Any:
        """Return the data for the given role and section in the header."""
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self._root_item.data(section)
        return None
    
    # Enable editing with builtin views
    def setData(self, index: QModelIndex, value: Any, role: int = Qt.EditRole) -> bool:
        """Set the role data for the item at index to value."""
        if index.isValid() and role == Qt.EditRole:
            item: BaseItem = index.internalPointer()
            return item.setData(index.column(), value)
        return False
    
    def setHeaderData(self, section, orientation, value, /, role = ...):
        return super().setHeaderData(section, orientation, value, role)
    
    def flags(self, index: QModelIndex) -> Qt.ItemFlags:
        """Return the item flags for the given index."""
        if not index.isValid():
            return Qt.ItemIsEnabled
        return Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable
    
    # Insert and remove methods
    def insertRows(self, position: int, rows: int, parent: QModelIndex = QModelIndex()) -> bool:
        """Insert rows into the model."""
        parent_item: BaseItem = self._root_item if not parent.isValid() else parent.internalPointer()
        
        for i in range(rows):
            # Create new item with list format
            new_data = [f"New Item {position + i + 1}"]
            child = BaseItem(new_data)
            parent_item.insert_child(position + i, child)
        
        return True

    def removeRows(self, position: int, rows: int, parent: QModelIndex = QModelIndex()) -> bool:
        """Remove rows from the model."""
        parent_item: BaseItem = self._root_item if not parent.isValid() else parent.internalPointer()
        
        # Remove in reverse order to avoid index shifting issues
        success = True
        for i in range(rows - 1, -1, -1):
            if not parent_item.remove_child(position + i):
                success = False
        
        return success
    
    ## utility methods
    def _set_model_recursively(self, item: BaseItem) -> None:
        """Recursively set model reference for all children."""
        item._model = self
        for child in item.child_items:
            self._set_model_recursively(child)

    ## Graph specific methods
    def addNode(self, node: NodeItem, parent: QModelIndex = QModelIndex()) -> None:
        """Add a node to the graph model."""
        parent_item: BaseItem = self._root_item if not parent.isValid() else parent.internalPointer()
        if not isinstance(node, SubGraphItem):
            raise TypeError("Only NodeItem can be added as a node.")
        parent_item.append_child(node)

    def removeNode(self, node: NodeItem, parent: QModelIndex = QModelIndex()) -> bool:
        """Remove a node from the graph model."""
        parent_item: BaseItem = self._root_item if not parent.isValid() else parent.internalPointer()
        if not isinstance(node, SubGraphItem):
            raise TypeError("Only NodeItem can be removed as a node.")
        return parent_item.remove_child(node)

    def addInlet(self, inlet: InletItem, node_index: QModelIndex) -> None:
        """Add an inlet to a node."""
        if not isinstance(inlet, InletItem):
            raise TypeError("Only InletItem can be added as an inlet.")
        node_item: NodeItem = node_index.internalPointer()
        if not isinstance(node_item, NodeItem):
            raise TypeError("Parent index must point to a NodeItem.")
        node_item.appendInlet(inlet)

    def removeOutlet(self, outlet: OutletItem, node_index: QModelIndex) -> bool:
        """Remove an outlet from a node."""
        if not isinstance(outlet, OutletItem):
            raise TypeError("Only OutletItem can be removed as an outlet.")
        node_item: NodeItem = node_index.internalPointer()
        if not isinstance(node_item, NodeItem):
            raise TypeError("Parent index must point to a NodeItem.")
        return node_item.removeOutlet(outlet)

    def addOutlet(self, outlet: OutletItem, node_index: QModelIndex) -> None:
        """Add an outlet to a node."""
        if not isinstance(outlet, OutletItem):
            raise TypeError("Only OutletItem can be added as an outlet.")
        node_item: NodeItem = node_index.internalPointer()
        if not isinstance(node_item, NodeItem):
            raise TypeError("Parent index must point to a NodeItem.")
        node_item.appendOutlet(outlet)

    def addLink(self, link: LinkItem, source_index: QModelIndex, target_index: QModelIndex) -> None:
        """Add a link between two nodes."""
        if not isinstance(link, LinkItem):
            raise TypeError("Only LinkItem can be added as a link.")
        source_item: NodeItem = source_index.internalPointer()
        target_item: NodeItem = target_index.internalPointer()
        if not isinstance(source_item, NodeItem) or not isinstance(target_item, NodeItem):
            raise TypeError("Source and target indices must point to NodeItems.")
        
        # Here you would typically handle the logic of linking nodes
        # For simplicity, we just append the link to the root item
        self._root_item.append_child(link)

    def removeLink(self, link: LinkItem) -> bool:
        """Remove a link from the graph model."""
        if not isinstance(link, LinkItem):
            raise TypeError("Only LinkItem can be removed as a link.")
        return self._root_item.remove_child(link)
    
    def clear(self) -> None:
        """Clear the entire graph model."""
        self.beginResetModel()
        self._root_item = SubGraphItem(["root"])
        self.endResetModel()


if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication, QTreeView
    from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QHBoxLayout
    from PySide6.QtCore import QEvent, QPoint
    from PySide6.QtWidgets import QAbstractItemView
    from collections import defaultdict

    app = QApplication(sys.argv)
    class MainWidget(QWidget):
        def __init__(self):
            super().__init__()
            layout = QVBoxLayout(self)
            button_layout = QHBoxLayout()

            self.add_btn = QPushButton("Add Item")
            self.remove_btn = QPushButton("Remove Selected")
            button_layout.addWidget(self.add_btn)
            button_layout.addWidget(self.remove_btn)
            layout.addLayout(button_layout)

            self.treeview = QTreeView()

            # Event filter to deselect all when clicking on a blank area
            self.treeview.viewport().installEventFilter(self)
            self.treeview.setSelectionMode(QTreeView.ExtendedSelection)
            layout.addWidget(self.treeview)
            
            self.model = GraphModel()
            self.treeview.setModel(self.model)

            # Add root children
            root = self.model._root_item
            child1 = BaseItem(["Item 1"])
            child2 = BaseItem(["Item 2"])
            root.append_child(child1)
            root.append_child(child2)

            # Add nested children
            child1.append_child(BaseItem(["Child 1"]))
            child1.append_child(BaseItem(["Child 2"]))

            # Direct item edit — model will emit signals!
            child1.setData(0, "Updated Item 1")

            self.treeview.expandAll()

            self.add_btn.clicked.connect(self.add_item)
            self.remove_btn.clicked.connect(self.remove_item)

        def eventFilter(self, obj, event):
            if event.type() == QEvent.MouseButtonPress and obj is self.treeview.viewport():
                index = self.treeview.indexAt(event.position().toPoint())
                if not index.isValid():
                    self.treeview.clearSelection()
            return super().eventFilter(obj, event)

        def add_item(self):
            index = self.treeview.currentIndex()
            parent = index if index.isValid() else QModelIndex()
            self.model.insertRows(self.model.rowCount(parent), 1, parent)

        def remove_item(self):
            indexes = self.treeview.selectionModel().selectedRows()
            # Group indexes by parent to avoid shifting issues
            parent_map = defaultdict(list)
            for index in indexes:
                parent_map[index.parent()].append(index.row())
            for parent, rows in parent_map.items():
                for row in sorted(rows, reverse=True):
                    self.model.removeRows(row, 1, parent)

    main_widget = MainWidget()


    main_widget.resize(400, 300)
    main_widget.show()

    sys.exit(app.exec())
