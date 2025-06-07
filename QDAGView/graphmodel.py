from PySide6.QtCore import *
from PySide6.QtGui import *
from PySide6.QtWidgets import *
from collections import defaultdict
from typing import *
from core import GraphDataRole, GraphItemType


class BaseItem:
    def __init__(self, data: List[str] = None):
        """Initialize BaseItem with proper data storage for multiple columns and roles."""
        # Use nested dictionary: {role: {column: value}}
        self._data: Dict[int, Dict[int, Any]] = defaultdict(dict)
        
        # Initialize with provided data if any
        if data:
            for column, value in enumerate(data):
                self._data[Qt.DisplayRole][column] = value
                self._data[Qt.EditRole][column] = value
        self._data[GraphDataRole.TypeRole][0] = GraphItemType.BASE
        
        self._parent_item: Optional['BaseItem'] = None
        self._child_items: List['BaseItem'] = []
        self._model: Optional['GraphModel'] = None
        
    # def type(self) -> GraphItemType:
    #     """Return the type of this item."""
    #     return GraphItemType.BASE

    def model(self) -> Optional['GraphModel']:
        """Return the model associated with this item."""
        return self._model
    
    def data(self, column: int, role: int = Qt.EditRole) -> Any:
        """Return the data for the specified column."""
        try:
            return self._data[role][column]
        except (IndexError, KeyError):
            return None
    
    def setData(self, column: int, value: Any, role: int = Qt.EditRole) -> bool:
        """Set data for the specified column."""
        # Check if column is valid (we support unlimited columns)
        if column < 0:
            return False
            
        # Set the data - this will create the nested structure if needed        if self._data[role].get(column) != value:
            self._data[role][column] = value
            self.emitDataChanged(column)
        return True
        
    def insert_child(self, position: int, child: Self) -> None:
        """Insert a child item at the specified position."""

        if 0 <= position <= len(self._child_items):
            if self._model:
                self._model.beginInsertRows(self.index(), position, position)
            child._parent_item = self
            child._model = self._model  # Pass model reference to child
            self._set_model_recursively(child)  # Set model for all descendants
            self._child_items.insert(position, child)
            if self._model:
                self._model.endInsertRows()

    def append_child(self, child: Self) -> None:
        """Append a child item to this item."""
        self.insert_child(len(self._child_items), child)

    def remove_child(self, child: Self) -> bool:
        """Remove child item at the specified position."""
        position = self._child_items.index(child) if child in self._child_items else -1
        if position == -1:
            return False
        
        if 0 <= position < len(self._child_items):
            if self._model:
                self._model.beginRemoveRows(self.index(), position, position)
            removed_child = self._child_items.pop(position)
            removed_child._parent_item = None
            removed_child._model = None
            if self._model:
                self._model.endRemoveRows()
            return True
        return False

    def childAt(self, row: int) -> Optional[Self]:
        """Return the child item at the specified row."""
        return self._child_items[row] if 0 <= row < len(self._child_items) else None

    def childCount(self) -> int:
        """Return the number of child items."""
        return len(self._child_items)
    
    def columnCount(self) -> int:
        """Return the number of columns for this item."""
        # Find the maximum column index across all roles
        max_column = -1
        for role_data in self._data.values():
            if role_data:  # Check if role_data is not empty
                max_column = max(max_column, max(role_data.keys(), default=-1))
        return max_column + 1 if max_column >= 0 else 0

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
            
    def emitDataChanged(self, column: int, roles: List[int] = None) -> None:
        """Emit model's dataChanged signal for this item."""
        if self._model and self != self._model._root_item:
            index = self._model.createIndex(self.row(), column, self)
            if roles is None:
                roles = []
            self._model.dataChanged.emit(index, index, roles)


class NodeItem(BaseItem):
    def __init__(self, text: str=""):
        """Initialize NodeItem with list data format only."""
        super().__init__([text] if text else None)
        self._data[GraphDataRole.TypeRole][0] = GraphItemType.NODE
    #     self._type = GraphItemType.NODE
    
    # def type(self) -> GraphItemType:
    #     """Return the type of this item."""
    #     return self._type
    
    def appendInlet(self, inlet: 'InletItem') -> None:
        """Add an inlet to this node."""
        item_type = inlet.data(0, GraphDataRole.TypeRole)
        if item_type != GraphItemType.INLET:
            raise TypeError("Only InletItem can be added as an inlet.")
        if inlet in self._child_items:
            raise ValueError("Inlet already exists in this node's children.")
        # Ensure the inlet is not already a child of another node
        if inlet.parent() is not None:
            raise ValueError("Inlet is already a child of another node.")
        
        self.append_child(inlet)

    def removeInlet(self, inlet: 'InletItem') -> bool:
        """Remove an inlet from this node."""
        item_type = inlet.data(0, GraphDataRole.TypeRole)
        if item_type != GraphItemType.INLET:
            raise TypeError("Only InletItem can be removed as an inlet.")
        if inlet not in self._child_items:
            raise ValueError("Inlet not found in this node's children.")
        if inlet.parent() != self:
            raise ValueError("Inlet is not a child of this node.")
        return self.remove_child(inlet)

    def appendOutlet(self, outlet: 'OutletItem') -> None:
        """Add an outlet to this node."""
        item_type = outlet.data(0, GraphDataRole.TypeRole)
        if item_type != GraphItemType.OUTLET:
            raise TypeError("Only OutletItem can be added as an outlet.")
        if outlet in self._child_items:
            raise ValueError("Outlet already exists in this node's children.")
        # Ensure the outlet is not already a child of another node
        if outlet.parent() is not None:
            raise ValueError("Outlet is already a child of another node.")
        self.append_child(outlet)

    def removeOutlet(self, outlet: 'OutletItem') -> bool:
        """Remove an outlet from this node."""
        item_type = outlet.data(0, GraphDataRole.TypeRole)
        if item_type != GraphItemType.OUTLET:
            raise TypeError("Only OutletItem can be removed as an outlet.")
        if outlet not in self._child_items:
            raise ValueError("Outlet not found in this node's children.")
        if outlet.parent() != self:
            raise ValueError("Outlet is not a child of this node.")
        return self.remove_child(outlet)


class InletItem(BaseItem):
    def __init__(self, text: str=""):
        """Initialize InletItem with list data format only."""
        super().__init__([text] if text else None)
        self._data[GraphDataRole.TypeRole][0] = GraphItemType.INLET
    #     self._type = GraphItemType.INLET
    
    # def type(self) -> str:
    #     """Return the type of this item."""
    #     return self._type


class OutletItem(BaseItem):
    def __init__(self, text: str=""):
        """Initialize OutletItem with list data format only."""
        super().__init__([text] if text else None)
        self._data[GraphDataRole.TypeRole][0] = GraphItemType.OUTLET
    #     self._type = GraphItemType.OUTLET
    
    # def type(self) -> str:
    #     """Return the type of this item."""
    #     return self._type
    

class LinkItem(BaseItem):
    def __init__(self, text: str=""):
        """Initialize LinkItem with list data format only."""
        super().__init__([text] if text else None)
        self._data[GraphDataRole.TypeRole][0] = GraphItemType.LINK
    #     self._type = GraphItemType.LINK
    
    # def type(self) -> str:
    #     """Return the type of this item."""
    #     return self._type


class SubGraphItem(BaseItem):
    def __init__(self, text: Union[str, List[str]] = ""):
        """Initialize SubGraphItem with list data format only."""
        if isinstance(text, str):
            super().__init__([text] if text else None)
        else:
            super().__init__(text)
        
        self._data[GraphDataRole.TypeRole][0] = GraphItemType.SUBGRAPH
    #     self._type = GraphItemType.SUBGRAPH
    
    # def type(self) -> str:
    #     """Return the type of this item."""
    #     return self._type
    
    def addNode(self, node: NodeItem) -> None:
        """Add a node to this subgraph."""
        assert node.type() == GraphItemType.NODE, "Only NodeItem can be added as a node."
        if node in self._child_items:
            raise ValueError("Node already exists in this subgraph's children.")
        # Ensure the node is not already a child of another subgraph
        if node.parent() is not None:
            raise ValueError("Node is already a child of another subgraph.")
        
        self.append_child(node)

    def removeNode(self, node: NodeItem) -> bool:
        """Remove a node from this subgraph."""
        assert node.type() == GraphItemType.NODE, "Only NodeItem can be removed as a node."
        if node not in self._child_items:
            raise ValueError("Node not found in this subgraph's children.")
        if node.parent() != self:
            raise ValueError("Node is not a child of this subgraph.")
        return self.remove_child(node)


class GraphModel(QAbstractItemModel):
    def __init__(self, parent: QObject|None = None) -> None:
        """Initialize TreeModel with list headers."""
        super().__init__(parent)
        self._root_item = SubGraphItem(["root"])
        self._root_item._model = self
        self._set_model_recursively(self._root_item)  # Set model for all descendants
        self._headers = ["name", "content"]

    def invisibleRootItem(self) -> SubGraphItem:
        """Return the invisible root item of the model."""
        return self._root_item

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
        return item.data(index.column(), role)

    
    ## Optional read methods
    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole) -> Any:
        """Return the data for the given role and section in the header."""
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self._headers[section]
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
        assert isinstance(parent, QModelIndex), "Parent must be a QModelIndex."
        parent_item: BaseItem = self._root_item if not parent.isValid() else parent.internalPointer()
        item_type = parent_item.data(0, GraphDataRole.TypeRole)
        
        match item_type:
            case GraphItemType.SUBGRAPH:
                subgraph_item = cast(SubGraphItem, parent_item)
                for row in range(rows):
                    subgraph_item.addNode(NodeItem(f"New Node {position + row + 1}"))
                return True
            case GraphItemType.NODE:
                # For NodeItem, we insert an inlet
                node_item = cast(NodeItem, parent_item)
                for row in range(rows):
                    node_item.appendInlet(InletItem(f"New Inlet {position + row + 1}"))
                return True
            case _:
                print(f"Warning: Cannot insert rows into {item_type} item.")
                return False
    
    def removeRows(self, position: int, rows: int, parent: QModelIndex = QModelIndex()) -> bool:
        """Remove rows from the model."""
        assert isinstance(parent, QModelIndex), "Parent must be a QModelIndex."
        parent_item: BaseItem = self._root_item if not parent.isValid() else parent.internalPointer()
        
        # Remove in reverse order to avoid index shifting issues
        success = True
        for i in range(rows - 1, -1, -1):
            child_to_remove = parent_item.childAt(position + i)
            if child_to_remove is None or not parent_item.remove_child(child_to_remove):
                success = False
        return success
    
    ## utility methods
    def _set_model_recursively(self, item: BaseItem) -> None:
        """Recursively set model reference for all children."""
        item._model = self
        for child in item._child_items:
            self._set_model_recursively(child)

    ## Graph specific methods
    def addNode(self, node: NodeItem, parent: QModelIndex = QModelIndex()) -> None:
        """Add a node to the graph model."""
        parent_item: BaseItem = self._root_item if not parent.isValid() else parent.internalPointer()
        if not isinstance(node, NodeItem):
            raise TypeError("Only NodeItem can be added as a node.")
        parent_item.append_child(node)

    def removeNode(self, node: NodeItem, parent: QModelIndex = QModelIndex()) -> bool:
        """Remove a node from the graph model."""
        parent_item: BaseItem = self._root_item if not parent.isValid() else parent.internalPointer()
        if not isinstance(node, NodeItem):
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

