from __future__ import annotations

from typing import *
from qtpy.QtWidgets import *
from qtpy.QtCore import *
from qtpy.QtGui import *

from core import GraphDataRole, GraphItemType
from contextlib import contextmanager


class Graph:
    def __init__(self, name: str = "Graph"):
        self._name = name
        self.nodes: List[Node] = []  # List of nodes in the graph


class Node:
    def __init__(self, name: str = "Node"):
        self._name = name
        self.inlets = []
        self.outlets = []


class Inlet:
    def __init__(self, name: str = "Inlet"):
        self._name = name
        self.links = []  # List of links connected to this inlet
        self.node: Node | None = None


class Outlet:
    def __init__(self, name: str = "Outlet"):
        self._name = name
        self.links = []
        self.node: Node | None = None  # The node this outlet belongs to


class Link:
    def __init__(self, source: Outlet|None, target: Inlet):
        self.source = source
        self.target = target

    def __repr__(self):
        return f"Link(source={self.source._name}, target={self.target._name})"
    
    def __str__(self):
        return f"{self.source.node._name}.{self.source._name} -> {self.target.node._name}.{self.target._name}"


class GraphModel(QAbstractItemModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._root = Graph()

    def invisibleRootItem(self) -> Graph:
        """Return the root item of the model."""
        return self._root
    
    def index(self, row, column, parent=QModelIndex())-> QModelIndex:
        parent_item:Graph | Node | Inlet = self.invisibleRootItem() if not parent.isValid() else parent.internalPointer()
        assert column == 0, "This model only supports one column."

        match parent_item:
            case Graph():
                if 0 <= row < len(parent_item.nodes):
                    node = parent_item.nodes[row]
                    return self.createIndex(row, column, node)
                else:
                    return QModelIndex()
            case Node():
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
            case Inlet():
                if 0 <= row < len(parent_item.links):
                    link = parent_item.links[row]
                    return self.createIndex(row, column, link)
                else:
                    return QModelIndex()
            case _:
                return QModelIndex()

    def indexFromItem(self, item: Node | Inlet | Outlet | Link) -> QModelIndex:
        """Get the index of an item in the model."""
        match item:
            case Graph():
                return QModelIndex()  # Graph itself has no index, it's the root item
            
            case Node():
                row = self._root.nodes.index(item)
                return self.createIndex(row, 0, item)
        
            case Inlet():
                parent_node = item.node
                if parent_node is not None:
                    row = parent_node.inlets.index(item)
                    return self.createIndex(row, 0, item)
                
            case Outlet():
                parent_node = item.node
                if parent_node is not None:
                    row = len(parent_node.inlets) + parent_node.outlets.index(item)
                    return self.createIndex(row, 0, item)
                
            case Link():
                parent_inlet = item.target
                if parent_inlet is not None:
                    parent_node = parent_inlet.node
                    if parent_node is not None:
                        row = parent_node.inlets.index(parent_inlet)
                        return self.createIndex(row, 0, item)
            case _:
                raise ValueError(f"Unsupported item type: {type(item)}")
    
    def itemFromIndex(self, index: QModelIndex) -> Node | Inlet | Outlet | Link | None:
        """Get the item from a QModelIndex."""
        if not index.isValid():
            return None
        item = index.internalPointer()
        if isinstance(item, (Node, Inlet, Outlet, Link)):
            return item
        return None

    def parent(self, index: QModelIndex) -> QModelIndex:
        if not index.isValid():
            return QModelIndex()
        item = index.internalPointer()
        match item:
            case Node():
                # Node's parent is the root (Graph), so return invalid QModelIndex
                return QModelIndex()
            
            case Inlet():
                parent_node = item.node
                if parent_node is not None:
                    row = self._root.nodes.index(parent_node)
                    return self.createIndex(row, 0, parent_node)
                return QModelIndex()
                
            case Outlet():
                parent_node = item.node
                if parent_node is not None:
                    row = self._root.nodes.index(parent_node)
                    return self.createIndex(row, 0, parent_node)
                return QModelIndex()
   
            case Link():
                parent_inlet = item.target
                parent_node = parent_inlet.node if parent_inlet else None
                if parent_node is not None and parent_inlet is not None:
                    row = parent_node.inlets.index(parent_inlet)
                    return self.createIndex(row, 0, parent_inlet)
                return QModelIndex()
            case _:
                return QModelIndex()
            
    def rowCount(self, parent=QModelIndex())->int:
        parent_item:Graph | Node | Inlet = self.invisibleRootItem() if not parent.isValid() else parent.internalPointer()
        
        match parent_item:
            case Graph():
                graph = parent_item
                return len(graph.nodes)
            case Node():
                node = parent_item
                return len(node.inlets + node.outlets)
            case Inlet():
                inlet = parent_item
                return len(inlet.links)
            case Outlet():
                return 0
            case Link():
                return 0
            case _:
                raise Exception(f"Invalid parent item type: {type(parent_item)}")
            
    def hasChildren(self, parent = ...):
        parent_item:Graph | Node | Inlet = self.invisibleRootItem() if not parent.isValid() else parent.internalPointer()
        
        match parent_item:
            case Graph():
                return len(parent_item.nodes)>0
            case Node():
                return len(parent_item.inlets + parent_item.outlets)>0
            case Inlet():
                return len(parent_item.links)>0
            case Outlet():
                return False
            case Link():
                return False
            case _:
                return super().hasChildren(parent)

    def columnCount(self, parent=QModelIndex()):
        return 1

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):

        if not index.isValid():
            return None
        
        item = index.internalPointer()
        match item:
            case Node():
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
                
            case Inlet():
                match role:
                    case GraphDataRole.TypeRole:
                        return GraphItemType.INLET
                    case Qt.ItemDataRole.DisplayRole | Qt.ItemDataRole.EditRole:
                        return item._name
                    case _:
                        return None
                return item._name
            
            case Outlet():
                match role:
                    case GraphDataRole.TypeRole:
                        return GraphItemType.OUTLET
                    case Qt.ItemDataRole.DisplayRole | Qt.ItemDataRole.EditRole:
                        return item._name
                    case _:
                        return None
            
            case Link():
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
            case Node():
                node = item
                node._name = value
                self.dataChanged.emit(index, index, [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole])
                return True
                
            case Inlet():
                item._name = value
                self.dataChanged.emit(index, index, [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole])
                return True
            
            case Outlet():
                item._name = value
                self.dataChanged.emit(index, index, [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole])
                return True
            
            case Link():
                link = item
                match role:
                    case GraphDataRole.SourceRole:
                        assert isinstance(value, (QModelIndex, QPersistentModelIndex)), "Source must be a valid QModelIndex."
                        assert value.isValid(), "Source index must be valid."
                        return self.setLinkSource(index, value)

        return False
            
    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        
        item = index.internalPointer()
        match item:
            case Node():
                return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEditable
            case Inlet() | Outlet():
                return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEditable
            case Link():
                return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
            case _:
                return Qt.ItemFlag.NoItemFlags
            
    def insertRows(self, row, count, parent = ...):
        parent_item:Graph | Node | Inlet = self.invisibleRootItem() if not parent.isValid() else parent.internalPointer()
        match parent_item:
            case Graph():
                return self.appendNode(name=f"New Node {row + 1}")
            case Node():
                node = parent_item
                if row < len(node.inlets):
                    return self.appendInlet(parent)
                else:
                    return self.appendOutlet(parent)
            case Inlet():
                # Note: insertRow is called by the default graphview delegate to create new links.
                # Therefore it must support dangling links.
                return self.appendLink(parent, QModelIndex())
            case _:
                raise Exception(f"Invalid parent item type: {type(parent_item)}")
            
    def removeRows(self, row:int, count:int, parent:QModelIndex)-> bool:
        parent_item:Graph|Node|Inlet|Outlet|Link = self.invisibleRootItem() if not parent.isValid() else parent.internalPointer()
        match parent_item:
            case Graph():
                graph = parent_item
                self.beginRemoveRows(parent, row, row + count - 1)
                for i in reversed(range(row, row + count)):
                    node = graph.nodes.pop(i)
                self.endRemoveRows()
                return True
            case Node():
                node = parent_item
                self.beginRemoveRows(parent, row, row + count - 1)
                if row < len(node.inlets):
                    for i in reversed(range(row, row + count)):
                        node.inlets.pop(i)
                else:
                    for i in reversed(range(row-len(node.inlets), row-len(node.inlets)+count)):
                        node.outlets.pop(i)
                self.endRemoveRows()
                return True
            case Inlet():
                inlet = parent_item
                self.beginRemoveRows(parent, row, row + count - 1)
                for i in reversed(range(row, row + count)):
                    link = inlet.links.pop(i)
                    outlet = link.source
                    if outlet is not None:
                        assert link in outlet.links, (
                            f"Invariant error: Link {link} should be in outlet.links of {outlet}, "
                            f"but was not found. This indicates a logic error or double removal."
                        )
                        outlet.links.remove(link)
                self.endRemoveRows()
                return True
            case _:
                raise Exception(f"Invalid parent item type: {type(parent_item)}")
    
    ## Helper methods for managing nodes, inlets, outlets, and links
    def appendNode(self, name: str = "New Node") -> bool:
        """Add a new node to the graph."""
        graph = self._root
        if not isinstance(graph, Graph):
            raise ValueError("Root item must be a Graph.")
        
        position = len(graph.nodes)
        new_node = Node(f"{name}{position}")
        
        self.beginInsertRows(QModelIndex(), position, position)
        graph.nodes.append(new_node)
        new_node.graph = graph
        self.endInsertRows()
        return True

    def appendInlet(self, node_index: QModelIndex, name:str="inlet") -> bool:
        assert node_index.isValid(), "Node index must be valid."
        node = node_index.internalPointer()
        if not isinstance(node, Node):
            raise ValueError("Parent index must point to a Node.")
        
        position = len(node.inlets)
        new_inlet = Inlet(f"{name}{position}")
        
        self.beginInsertRows(node_index, position, position)
        node.inlets.append(new_inlet)
        new_inlet.node = node
        self.endInsertRows()
        return True
    
    def appendOutlet(self, node_index: QModelIndex, name:str="outlet") -> bool:
        assert node_index.isValid(), "Node index must be valid."
        node = node_index.internalPointer()
        if not isinstance(node, Node):
            raise ValueError("Parent index must point to a Node.")
        
        position = len(node.outlets)
        new_outlet = Outlet(f"{name}{position}")

        self.beginInsertRows(node_index, len(node.inlets)+position, len(node.inlets)+position)
        node.outlets.append(new_outlet)
        new_outlet.node = node
        self.endInsertRows()
        return True

    def appendLink(self, inlet_index:QModelIndex, outlet_index:QModelIndex=QModelIndex())->bool:
        """
        Add a link between an outlet and an inlet.
        If source is invalid, it will create a dangling link.
        """
        assert inlet_index.isValid(), "Inlet index must be valid."

        
        inlet = inlet_index.internalPointer()
        if not isinstance(inlet, Inlet):
            raise ValueError("Inlet index must point to an Inlet.")

        outlet = outlet_index.internalPointer()
        if not (isinstance(outlet, Outlet) or outlet is None):
            raise ValueError(f"Source must be an Outlet or None. got {outlet}")
        
        new_link = Link(outlet, inlet)

        self.beginInsertRows(inlet_index, len(inlet.links), len(inlet.links))
        inlet.links.append(new_link)
        new_link.target = inlet
        new_link.source = outlet
        if outlet is not None:
            outlet.links.append(new_link)
        self.endInsertRows()
        return True
    
    def removeLink(self, link_index:QModelIndex)->bool:
        """
        Remove a link from the model.
        """
        assert link_index.isValid(), "Link index must be valid."
        link = link_index.internalPointer()
        if not isinstance(link, Link):
            raise ValueError("Link index must point to a Link.")
        
        inlet = link.target
        outlet = link.source
        
        self.beginRemoveRows(link_index.parent(), link_index.row(), link_index.row())
        
        # unlink from inlet
        if inlet is not None:
            assert link in inlet.links, (
                f"Invariant error: Link {link} should be in inlet.links of {inlet}, "
                f"but was not found. This indicates a logic error or double removal."
            )
            inlet.links.remove(link)
        
        # unlink from outlet
        if outlet is not None:
            assert link in outlet.links, (
                f"Invariant error: Link {link} should be in outlet.links of {outlet}, "
                f"but was not found. This indicates a logic error or double removal."
            )
            outlet.links.remove(link)
        
        self.endRemoveRows()
        return True
    
    def setLinkSource(self, link_index:QModelIndex, outlet_index:QModelIndex)->bool:
        """
        Set the source of a link.
        If outlet_index is invalid, it will create a dangling link.
        """
        assert link_index.isValid(), "Link index must be valid."
        link = link_index.internalPointer()
        if not isinstance(link, Link):
            raise ValueError("Link index must point to a Link.")
        
        # unlink current source
        if link.source is not None:
            link.source.links.remove(link)

        # link new source
        if outlet_index is not None and outlet_index.isValid():
            outlet = outlet_index.internalPointer()
            if not isinstance(outlet, Outlet):
                raise ValueError("Outlet index must point to an Outlet.")
            
            link.source = outlet
            outlet.links.append(link)

        self.dataChanged.emit(link_index, link_index, [GraphDataRole.SourceRole, Qt.ItemDataRole.DisplayRole])


from graphview import GraphView
class MainWindow(QWidget):
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
        self._model:GraphModel|None = None
        self._selection:QItemSelectionModel|None = None 
        self.setModel(GraphModel())
        self.setSelectionModel(QItemSelectionModel(self.model()))

    def setModel(self, model: GraphModel):
        """Set the model for the treeview."""
        self._model = model
        self._treeview.setModel(model)
        self._graphview.setModel(model)

    def model(self) -> GraphModel:
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
        self._model.appendNode(name="New Node")

    @Slot()
    def createInlet(self):
        current = self._selection.currentIndex()
        item = current.internalPointer()
        if isinstance(item, Node):
            self._model.appendInlet(current, name="New Inlet")
        else:
            QMessageBox.warning(self, "Error", "Please select a node to add an inlet.")
            return

    @Slot()
    def createOutlet(self):
        current = self._selection.currentIndex()
        item = current.internalPointer()
        if isinstance(item, Node):
            self._model.appendOutlet(current, name="New Outlet")
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
    app = QApplication(sys.argv)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())