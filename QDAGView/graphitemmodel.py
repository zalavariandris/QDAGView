from __future__ import annotations

from typing import *
from qtpy.QtWidgets import *
from qtpy.QtCore import *
from qtpy.QtGui import *

from core import GraphDataRole, GraphItemType
from contextlib import contextmanager

class Operator:
    def __call__(self, *args, **kwds):
        pass


class Item:
    def model(self) -> QAbstractItemModel | None:
        return None
    
    @contextmanager
    def insertingRows(self, first: int, last: int):
        """Context manager to handle row insertion."""
        model = self.model()
        if model:
            parent = model.indexFromItem(self)
            model.beginInsertRows(parent, first, last)
        try:
            yield
        finally:
            if model:
                model.endInsertRows()

    @contextmanager
    def removingRows(self, first: int, last: int):
        """Context manager to handle row removal."""
        model = self.model()
        if model:
            parent = model.indexFromItem(self)
            model.beginRemoveRows(parent, first, last)
        try:
            yield
        finally:
            if model:
                model.endRemoveRows()


class GraphItem(Item):
    def __init__(self, name: str = "Graph"):
        self._name = name
        self.nodes: List[NodeItem] = []  # List of nodes in the graph
        self._model: GraphItemModel | None = None  # Reference to the model if needed

    def appendNode(self, node: NodeItem):
        """Append a node to the graph."""
        position = len(self.nodes)
        with self.insertingRows(position, position):
            self.nodes.append(node)
            node.graph = self

    def removeNode(self, node: NodeItem):
        """Remove a node from the graph."""
        position = self.nodes.index(node)
        with self.removingRows(position, position):
            self.nodes.remove(node)
            node.graph = None

    def model(self) -> GraphItemModel | None:
        """Get the model associated with this graph."""
        return self._model
    

class NodeItem(Item):
    def __init__(self, name: str = "Node", operator: Operator | None = None):
        self._name = name
        self.inlets = []
        self.outlets = []
        self.graph: GraphItem | None = GraphItem()  # The graph this node belongs to

    def model(self) -> GraphItemModel | None:
        return self.graph.model()
        
    def appendInlet(self, inlet: InletItem)->bool:
        """Append an inlet to the node."""
        position = len(self.inlets)
        with self.insertingRows(position, position):
            self.inlets.append(inlet)
            inlet.node = self
        return True

    def appendOutlet(self, outlet: OutletItem)->bool:
        """Append an outlet to the node."""
        position = len(self.inlets) + len(self.outlets)
        with self.insertingRows(position, position):
            self.outlets.append(outlet)
            outlet.node = self
        return True
    
    def removeInlet(self, inlet: InletItem)->bool:
        """Remove an inlet from the node."""
        position = self.inlets.index(inlet)
        with self.removingRows(position, position):
            self.inlets.remove(inlet)
            inlet.node = None
        return True

    def removeOutlet(self, outlet: OutletItem)->bool:
        """Remove an outlet from the node."""
        position = len(self.inlets) + self.outlets.index(outlet)
        with self.removingRows(position, position):
            self.outlets.remove(outlet)
            outlet.node = None
        return True

class InletItem(Item):
    def __init__(self, name: str = "Inlet"):
        self._name = name
        self.links = []  # List of links connected to this inlet
        self.node: NodeItem | None = None

    def model(self) -> GraphItemModel | None:
        return self.node.model()
    
    def appendLink(self, link: LinkItem, outlet: OutletItem | None = None)->bool:
        """Append a link to the inlet."""
        position = len(self.links)
        with self.insertingRows(position, position):
            self.links.append(link)
            link.target = self
            link.source = outlet
            if outlet is not None:
                outlet.links.append(link)
        return True

    def removeLink(self, link: LinkItem)->bool:
        """Remove a link from the inlet."""
        position = self.links.index(link)
        with self.removingRows(position, position):
            self.links.pop(position)
            if link.source is not None:
                link.source.links.remove(link)
        return True


class OutletItem(Item):
    def __init__(self, name: str = "Outlet"):
        self._name = name
        self.links = []
        self.node: NodeItem | None = None  # The node this outlet belongs to

    def model(self) -> GraphItemModel | None:
        return self.node.model()


class LinkItem(Item):
    def __init__(self, source: OutletItem|None, target: InletItem):
        self.source = source
        self.target = target

    def model(self) -> GraphItemModel | None:
        return self.target.model()

    def setSource(self, source: OutletItem | None):
        """Set the source outlet for this link."""
        if self.source is not None:
            self.source.links.remove(self)
        self.source = source
        if source is not None:
            source.links.append(self)
        index = self.model().indexFromItem(self)
        self.model().dataChanged.emit(index, index, [GraphDataRole.SourceRole])

    def __repr__(self):
        return f"Link(source={self.source._name}, target={self.target._name})"
    
    def __str__(self):
        return f"{self.source.node._name}.{self.source._name} -> {self.target.node._name}.{self.target._name}"


class GraphItemModel(QAbstractItemModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._root = GraphItem()
        self._root._model = self  # Set the model reference in the root item

    def invisibleRootItem(self) -> GraphItem:
        """Return the root item of the model."""
        return self._root
    
    def index(self, row, column, parent=QModelIndex())-> QModelIndex:
        parent_item:GraphItem | NodeItem | InletItem = self.invisibleRootItem() if not parent.isValid() else parent.internalPointer()
        assert column == 0, "This model only supports one column."

        match parent_item:
            case GraphItem():
                if 0 <= row < len(parent_item.nodes):
                    node = parent_item.nodes[row]
                    return self.createIndex(row, column, node)
                else:
                    return QModelIndex()
            case NodeItem():
                n_inlets = len(parent_item.inlets)
                n_outlets = len(parent_item.outlets)
                if 0 <= row < n_inlets + n_outlets:
                    # Determine if the row corresponds to an inlet or outlet
                    if row < n_inlets:
                        return self.createIndex(row, column, parent_item.inlets[row])
                    else:
                        return self.createIndex(row, column, parent_item.outlets[row - n_inlets])
                else:
                    return QModelIndex()
            case InletItem():
                if 0 <= row < len(parent_item.links):
                    link = parent_item.links[row]
                    return self.createIndex(row, column, link)
                else:
                    return QModelIndex()
            case _:
                return QModelIndex()

    def indexFromItem(self, item: NodeItem | InletItem | OutletItem | LinkItem) -> QModelIndex:
        """Get the index of an item in the model."""
        match item:
            case GraphItem():
                return QModelIndex()  # Graph itself has no index, it's the root item
            
            case NodeItem():
                row = self._root.nodes.index(item)
                return self.createIndex(row, 0, item)
        
            case InletItem():
                parent_node = item.node
                if parent_node is not None:
                    row = parent_node.inlets.index(item)
                    return self.createIndex(row, 0, item)
                
            case OutletItem():
                parent_node = item.node
                if parent_node is not None:
                    row = len(parent_node.inlets) + parent_node.outlets.index(item)
                    return self.createIndex(row, 0, item)
                
            case LinkItem():
                parent_inlet = item.target
                if parent_inlet is not None:
                    parent_node = parent_inlet.node
                    if parent_node is not None:
                        row = parent_node.inlets.index(parent_inlet)
                        return self.createIndex(row, 0, item)
            case _:
                raise ValueError(f"Unsupported item type: {type(item)}")
    
    def itemFromIndex(self, index: QModelIndex) -> NodeItem | InletItem | OutletItem | LinkItem | None:
        """Get the item from a QModelIndex."""
        if not index.isValid():
            return None
        item = index.internalPointer()
        if isinstance(item, (NodeItem, InletItem, OutletItem, LinkItem)):
            return item
        return None

    def parent(self, index: QModelIndex) -> QModelIndex:
        if not index.isValid():
            return QModelIndex()
        item = index.internalPointer()
        match item:
            case NodeItem():
                # Node's parent is the root (Graph), so return invalid QModelIndex
                return QModelIndex()
            
            case InletItem():
                parent_node = item.node
                if parent_node is not None:
                    row = self._root.nodes.index(parent_node)
                    return self.createIndex(row, 0, parent_node)
                return QModelIndex()
                
            case OutletItem():
                parent_node = item.node
                if parent_node is not None:
                    row = self._root.nodes.index(parent_node)
                    return self.createIndex(row, 0, parent_node)
                return QModelIndex()
   
            case LinkItem():
                parent_inlet = item.target
                parent_node = parent_inlet.node if parent_inlet else None
                if parent_node is not None and parent_inlet is not None:
                    row = parent_node.inlets.index(parent_inlet)
                    return self.createIndex(row, 0, parent_inlet)
                return QModelIndex()
            case _:
                return QModelIndex()
            
    def rowCount(self, parent=QModelIndex())->int:
        parent_item:GraphItem | NodeItem | InletItem = self.invisibleRootItem() if not parent.isValid() else parent.internalPointer()
        
        match parent_item:
            case GraphItem():
                graph = parent_item
                return len(graph.nodes)
            case NodeItem():
                node = parent_item
                return len(node.inlets + node.outlets)
            case InletItem():
                inlet = parent_item
                return len(inlet.links)
            case OutletItem():
                return 0
            case LinkItem():
                return 0
            case _:
                raise Exception(f"Invalid parent item type: {type(parent_item)}")
            
    def hasChildren(self, parent = ...):
        parent_item:GraphItem | NodeItem | InletItem = self.invisibleRootItem() if not parent.isValid() else parent.internalPointer()
        
        match parent_item:
            case GraphItem():
                return len(parent_item.nodes)>0
            case NodeItem():
                return len(parent_item.inlets + parent_item.outlets)>0
            case InletItem():
                return len(parent_item.links)>0
            case OutletItem():
                return False
            case _:
                raise Exception(f"Invalid parent item type: {type(parent_item)}")

    def columnCount(self, parent=QModelIndex()):
        return 1

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):

        if not index.isValid():
            return None
        
        item = index.internalPointer()
        match item:
            case NodeItem():
                node = item
                match role:
                    case GraphDataRole.TypeRole:
                        return GraphItemType.NODE
                    case Qt.ItemDataRole.DisplayRole:
                        return f"{node._name}"
                    case Qt.ItemDataRole.EditRole:
                        return node._name
                    case _:
                        return None
                
            case InletItem():
                match role:
                    case GraphDataRole.TypeRole:
                        return GraphItemType.INLET
                    case Qt.ItemDataRole.DisplayRole | Qt.ItemDataRole.EditRole:
                        return item._name
                    case _:
                        return None
                return item._name
            
            case OutletItem():
                match role:
                    case GraphDataRole.TypeRole:
                        return GraphItemType.OUTLET
                    case Qt.ItemDataRole.DisplayRole | Qt.ItemDataRole.EditRole:
                        return item._name
                    case _:
                        return None
            
            case LinkItem():
                match role:
                    case GraphDataRole.TypeRole:
                        return GraphItemType.LINK
                    
                    case GraphDataRole.SourceRole:
                        link = item
                        return self.indexFromItem(link.source) if link.source else None
                    
                    case Qt.ItemDataRole.DisplayRole:
                        source = f"{item.source.node._name}.{item.source._name}" if item.source else "None"
                        target = f"{item.target.node._name}.{item.target._name}" if item.target else "None"
                        return f"{source} -> {target}"
                    
                    case _:
                        return None
                return 
            
            case _:
                return None
            
    def setData(self, index:QModelIndex, value, role:int = Qt.ItemDataRole.EditRole)->bool:
        if not index.isValid():
            return False
        
        item = index.internalPointer()
        match item:
            case NodeItem():
                node = item
                node._name = value
                self.dataChanged.emit(index, index, [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole])
                return True
                
            case InletItem():
                item._name = value
                self.dataChanged.emit(index, index, [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole])
                return True
            
            case OutletItem():
                item._name = value
                self.dataChanged.emit(index, index, [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole])
                return True
            
            case LinkItem():
                link_item = item
                match role:
                    case GraphDataRole.SourceRole:
                        assert isinstance(value, (QModelIndex, QPersistentModelIndex)), "Source must be a valid QModelIndex."
                        assert value.isValid(), "Source index must be valid."
                        source_item = self.itemFromIndex(value)
                        link_item.setSource(source_item)

        return False
            
    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        
        item = index.internalPointer()
        match item:
            case NodeItem():
                return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEditable
            case InletItem() | OutletItem():
                return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEditable
            case LinkItem():
                return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
            case _:
                return Qt.ItemFlag.NoItemFlags
            
    def insertRows(self, row, count, parent = ...):
        parent_item:GraphItem | NodeItem | InletItem = self.invisibleRootItem() if not parent.isValid() else parent.internalPointer()
        match parent_item:
            case GraphItem():
                graph = parent_item
                return graph.appendNode(NodeItem(name=f"Node {len(graph.nodes) + 1}"))
            case NodeItem():
                node = parent_item
                if row < len(node.inlets):
                    return node.appendInlet(InletItem(name=f"Inlet {len(node.inlets) + 1}"))
                else:
                    return node.appendOutlet(OutletItem(name=f"Outlet {len(node.outlets) + 1}"))
            case InletItem():
                # Note: insertRow is called by the default graphview delegate to create new links.
                # Therefore it must support dangling links.
                inlet = parent_item
                return inlet.appendLink(LinkItem(source=None, target=inlet), outlet=None)
            case _:
                raise Exception(f"Invalid parent item type: {type(parent_item)}")
            
    def removeRows(self, row:int, count:int, parent:QModelIndex)-> bool:
        parent_item:GraphItem|NodeItem|InletItem|OutletItem|LinkItem = self.invisibleRootItem() if not parent.isValid() else parent.internalPointer()
        match parent_item:
            case GraphItem():
                graph = parent_item
                for i in reversed(range(row, row + count)):
                    print(f"Removing node at index {i}")
                    node = graph.nodes[i]
                    if not graph.removeNode(node):
                        return False
                return True
            
            case NodeItem():
                node = parent_item

                for i in reversed(range(row, row + count)):
                    if i < len(node.inlets):
                        # Remove inlet
                        if not node.removeInlet(node.inlets[i]):
                            return False
                    else:
                        # Remove outlet
                        if not node.removeOutlet(node.outlets[i - len(node.inlets)]):
                            return False
                return True
            
            case InletItem():
                inlet = parent_item
                for i in reversed(range(row, row + count)):
                    if not inlet.removeLink(inlet.links[i]):
                        return False
                return True
            case _:
                raise Exception(f"Invalid parent item type: {type(parent_item)}")
    

from graphview import GraphView
class DataFlowApp(QWidget):
    def __init__(self):
        super().__init__()
        # setup view
        self.setWindowTitle("DataFlowGraph Example")

        # toolbar
        button_layout = QHBoxLayout()
        self.create_node_btn = QPushButton("Create Node")
        self.create_node_btn.clicked.connect(self.createNode)
        self.create_inlet_btn = QPushButton("Create Inlet")
        self.create_inlet_btn.clicked.connect(self.createInlet)
        self.create_outlet_btn = QPushButton("Create Outlet")
        self.create_outlet_btn.clicked.connect(self.createOutlet)
        self.remove_btn = QPushButton("Remove Selected")
        self.remove_btn.clicked.connect(self.removeSelected)
        button_layout.addWidget(self.create_node_btn)
        button_layout.addWidget(self.create_inlet_btn)
        button_layout.addWidget(self.create_outlet_btn)
        button_layout.addWidget(self.remove_btn)

        ## treeview
        self._treeview = QTreeView()
        self._treeview.viewport().installEventFilter(self)
        self._treeview.setSelectionMode(QTreeView.SelectionMode.ExtendedSelection)
        self._treeview.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked | QAbstractItemView.EditTrigger.SelectedClicked)
        self._treeview.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)

        ## graphview
        self._graphview = GraphView()

        # layout widgets
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._treeview)
        splitter.addWidget(self._graphview)

        layout = QVBoxLayout(self)
        layout.addLayout(button_layout)
        layout.addWidget(splitter)
        self.setLayout(layout)

        # setup model and selection
        self._model:GraphItemModel|None = None
        self._selection:QItemSelectionModel|None = None 
        self.setModel(GraphItemModel())
        self.setSelectionModel(QItemSelectionModel(self.model()))

    def setModel(self, model: GraphItemModel):
        """Set the model for the treeview."""
        self._model = model
        self._treeview.setModel(model)
        self._graphview.setModel(model)

    def model(self) -> GraphItemModel:
        """Get the current model."""
        assert self._model is not None, "Model must be set before accessing it"
        return self._model

    def setSelectionModel(self, selection: QItemSelectionModel):
        """Set the selection model for the treeview."""
        self._selection = selection
        self._treeview.setSelectionModel(self._selection)
        self._graphview.setSelectionModel(self._selection)

    def selectionModel(self) -> QItemSelectionModel:
        """Get the current selection model."""
        assert self._selection is not None, "Selection model must be set before accessing it"
        return self._selection

    @Slot()
    def createNode(self):
        graph = self.model().invisibleRootItem()
        graph.appendNode(NodeItem(name=f"Node {len(graph.nodes) + 1}"))

    @Slot()
    def createInlet(self):
        current = self._selection.currentIndex()
        node = self.model().itemFromIndex(current)
        if isinstance(node, NodeItem):
            node.appendInlet(InletItem(name=f"Inlet {len(node.inlets) + 1}"))
        else:
            QMessageBox.warning(self, "Error", "Please select a node to add an inlet.")
            return

    @Slot()
    def createOutlet(self):
        current = self._selection.currentIndex()
        node = current.internalPointer()
        if isinstance(node, NodeItem):
            node.appendOutlet(OutletItem(name=f"Outlet {len(node.outlets) + 1}"))
        else:
            QMessageBox.warning(self, "Error", "Please select a node to add an inlet.")
            return

    @Slot()
    def removeSelected(self):
        """Remove selected items from the model."""
        selected_indexes = self._treeview.selectedIndexes()
        if not selected_indexes:
            return
        
        for index in selected_indexes:
            if index.isValid():
                self.model().removeRow(index.row(), index.parent())


if __name__ == "__main__":
    import sys
    # Example usage of the Operator class
    class AddOperator(Operator):
        def __call__(self, a, b):
            return a + b

    add_op = AddOperator()
    result = add_op(3, 5)
    print(f"Result of addition: {result}")  # Output: Result of addition: 8

    app = QApplication(sys.argv)

    window = DataFlowApp()
    window.show()
    sys.exit(app.exec())