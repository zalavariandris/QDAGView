from __future__ import annotations

from typing import *
from qtpy.QtWidgets import *
from qtpy.QtCore import *
from qtpy.QtGui import *

from dataclasses import dataclass, field
from collections import defaultdict

from core import GraphDataRole, GraphItemType

class Operator:
    def __init__(self, expression: str = "Operator"):
        self._expression = expression
        self._inlets: List[Inlet] = [Inlet("in1", self), Inlet("in2", self)] 
        self._outlets: List[Outlet] = [Outlet("out", self)]

    def expression(self) -> str:
        """Return the expression of the operator."""
        return self._expression

    def setExpression(self, expression:str):
        """Set the expression of the operator."""
        self._expression = expression

    def __call__(self, *args, **kwds):
        ...

    def inlets(self) -> List[Inlet]:
        """Return the list of inlets for this operator."""
        return self._inlets
    
    def outlets(self) -> List[Outlet]:
        """Return the list of outlets for this operator."""
        return self._outlets
    
    def __str__(self):
        return f"Operator({self._expression})"

    
@dataclass()
class Inlet:
    name: str = "Inlet"
    operator: Operator|None = None

    def __str__(self):
        return f"Inlet({self.operator}.{self.name})"
    
    def __hash__(self):
        return hash((self.name, self.operator))


@dataclass()
class Outlet:
    name: str = "Outlet"
    operator: Operator|None = None

    def __str__(self):
        return f"Outlet({self.operator}.{self.name})"
    
    def __hash__(self):
        return hash((self.name, self.operator))


@dataclass()
class Link:
    source: Outlet = None
    target: Inlet = None

    def __str__(self):
        return  f"Link({self.source} -> {self.target})"


class FlowGraph:
    def __init__(self, name: str = "FlowGraph"):
        self._name = name
        self._operators: List[Operator] = []
        self._in_links: DefaultDict[Inlet, List[Link]] = defaultdict(list)
        self._out_links: DefaultDict[Outlet, List[Link]] = defaultdict(list)

    ## READ
    def operators(self) -> List[Operator]:
        """Return the list of nodes in the graph."""
        return self._operators
    
    def inLinks(self, inlet: Inlet) -> List[Link]:
        return [link for link in self._in_links[inlet]]

    def outLinks(self, outlet: Outlet) -> List[Link]:
        return [link for link in self._out_links[outlet]]

    ## CREATE
    def insertOperator(self, index:int, operator: Operator) -> bool:
        """Add an operator to the graph at the specified index."""
        self._operators.insert(index, operator)
        return True
    
    def insertLink(self, index:int, source:Outlet|None, target:Inlet) -> bool:
        """Link an outlet of a source operator to an inlet of a target operator."""
        link = Link(source, target)
        if source is not None:
            self._out_links[source].append(link)
        self._in_links[target].insert(index, link)
        return True
    
    ## DELETE
    def removeOperator(self, operator: Operator) -> bool:
        """Remove an operator from the graph."""
        if operator in self._operators:
            self._operators.remove(operator)
            # Remove all links associated with this operator
            for inlet in operator.inlets():
                self._in_links.pop(inlet, None)
            for outlet in operator.outlets():
                self._out_links.pop(outlet, None)
            return True
        return False

    ## UPDATE
    def setLinkSource(self, link: Link, source: Outlet | None) -> bool:
        """Relink an existing link to a new source outlet."""
        if link.source is not None:
            self._out_links[link.source].remove(link)
        if source is not None:
            self._out_links[source].append(link)
        link.source = source
        return True
    

class FlowGraphModel(QAbstractItemModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._root = FlowGraph()
        self._root._model = self  # Set the model reference in the root item

    def invisibleRootItem(self) -> FlowGraph:
        """Return the root item of the model."""
        return self._root
    
    def index(self, row, column, parent=QModelIndex())-> QModelIndex:
        parent = QModelIndex(parent)  # Ensure parent is a valid QModelIndex
        parent_item:FlowGraph | Operator | Inlet = self.invisibleRootItem() if not parent.isValid() else parent.internalPointer()
        assert column == 0, "This model only supports one column."
        match parent_item:
            case FlowGraph():
                graph = parent_item
                operators = graph.operators()
                if 0 <= row < len(operators):
                    node = operators[row]
                    return self.createIndex(row, column, node)
                else:
                    return QModelIndex()
                
            case Operator():
                operator = parent_item
                inlets = operator.inlets()
                outlets = operator.outlets()
                n_inlets = len(inlets)
                n_outlets = len(outlets)
                if 0 <= row < n_inlets + n_outlets:
                    # Determine if the row corresponds to an inlet or outlet
                    if row < n_inlets:
                        inlet = inlets[row]
                        return self.createIndex(row, column, inlet)
                    else:
                        outlet = outlets[row - n_inlets]
                        return self.createIndex(row, column, outlet)
                else:
                    return QModelIndex()
                
            case Inlet():
                inlet = parent_item
                graph = self.invisibleRootItem()
                links:List[Link] = graph.inLinks(inlet)

                if 0 <= row < len(links):
                    link = links[row]
                    return self.createIndex(row, column, link)
                else:
                    return QModelIndex()
                
            case _:
                return QModelIndex()

    def indexFromItem(self, item: Operator | Inlet | Outlet | Link) -> QModelIndex:
        """Get the index of an item in the model."""
        match item:
            case FlowGraph():
                return QModelIndex()  # Graph itself has no index, it's the root item
            
            case Operator():
                operator = item
                row = self._root.operators().index(operator)
                return self.createIndex(row, 0, operator)
        
            case Inlet():
                inlet = item
                operator = inlet.operator
                assert isinstance(operator, Operator), "Inlet must have a parent operator."
                row = operator.inlets().index(inlet)
                return self.createIndex(row, 0, inlet)

            case Outlet():
                operator = item.operator
                assert isinstance(operator, Operator), "Outlet must have a parent operator."
                inlets = operator.inlets()
                outlets = operator.outlets()
                row = len(inlets) + outlets.index(item)
                return self.createIndex(row, 0, item)
                
            case Link():
                parent_inlet = item.target
                assert isinstance(parent_inlet, Inlet), "Link must have a target inlet."
                parent_node = parent_inlet.operator
                assert isinstance(parent_node, Operator), "Link must have a parent operator."
                inlets = parent_node.inlets()
                row = inlets.index(parent_inlet)
                return self.createIndex(row, 0, item)

            case _:
                raise ValueError(f"Unsupported item type: {type(item)}")
    
    def itemFromIndex(self, index: QModelIndex) -> Operator | Inlet | Outlet | Link | None:
        """Get the item from a QModelIndex."""
        if not index.isValid():
            return None
        item = index.internalPointer()
        assert isinstance(item, (Operator | Inlet | Outlet | Link))
        return item

    def parent(self, index: QModelIndex) -> QModelIndex:
        index = QModelIndex(index)  # Ensure index is a valid QModelIndex
        if not index.isValid():
            return QModelIndex()
        
        item = index.internalPointer()
        match item:
            case Operator():
                # Operator's parent is the root (Graph), so return invalid QModelIndex
                return QModelIndex()

            case Inlet():
                inlet = item
                assert isinstance(inlet, Inlet), "Inlet must have a parent operator."
                parent_operator = inlet.operator
                assert isinstance(parent_operator, Operator), "Inlet must have a parent operator."
                graph = self.invisibleRootItem()
                row = graph.operators().index(parent_operator)
                return self.createIndex(row, 0, parent_operator)

            case Outlet():
                outlet = item
                assert isinstance(outlet, Outlet), "Outlet must have a parent operator."
                parent_operator = outlet.operator
                assert isinstance(parent_operator, Operator), "Outlet must have a parent operator."
                graph = self.invisibleRootItem()
                row = graph.operators().index(parent_operator)
                return self.createIndex(row, 0, parent_operator)

            case Link():
                parent_inlet = item.target
                parent_operator = parent_inlet.operator if parent_inlet else None
                if parent_operator is not None and parent_inlet is not None:
                    row = parent_operator.inlets().index(parent_inlet)
                    return self.createIndex(row, 0, parent_inlet)
                return QModelIndex()
            case _:
                return QModelIndex()
            
    def rowCount(self, parent=QModelIndex())->int:
        parent = QModelIndex(parent)  # Ensure parent is a valid QModelIndex
        parent_item:FlowGraph | Operator | Inlet | Outlet | Link = self.invisibleRootItem() if not parent.isValid() else parent.internalPointer()
        
        match parent_item:
            case FlowGraph():
                graph = parent_item
                return len(graph.operators())
            
            case Operator():
                operator = parent_item
                n_inlets = len(operator.inlets())
                n_outlets = len(operator.outlets())
                return n_inlets + n_outlets

            case Inlet():
                inlet = parent_item
                graph:FlowGraph = self.invisibleRootItem()
                in_links = graph.inLinks(inlet)
                return len(in_links)
                
            case Outlet():
                return 0
            
            case Link():
                return 0
            
            case _:
                raise Exception(f"Invalid parent item type: {type(parent_item)}")

    def hasChildren(self, index: QModelIndex) -> bool:
        parent_item: FlowGraph | Operator | Inlet | Outlet | Link = self.invisibleRootItem() if not index.isValid() else index.internalPointer()

        match parent_item:
            case FlowGraph():
                return len(parent_item.operators())>0
            
            case Operator():
                operator = parent_item
                n_inlets = len(operator.inlets())
                n_outlets = len(operator.outlets())
                return n_inlets + n_outlets > 0
            
            case Inlet():
                inlet = parent_item
                graph: FlowGraph = self.invisibleRootItem()
                in_links = graph.inLinks(inlet)
                return len(in_links) > 0
            
            case Outlet():
                return False
            
            case _:
                return False

    def columnCount(self, parent=QModelIndex()):
        return 1

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):

        if not index.isValid():
            return None
        
        item = index.internalPointer()
        match item:
            case Operator():
                operator = item
                match role:
                    case GraphDataRole.TypeRole:
                        return GraphItemType.NODE
                    
                    case Qt.ItemDataRole.DisplayRole:
                        return f"NODE {operator.expression()}"
                    
                    case Qt.ItemDataRole.EditRole:
                        return operator.expression()
                    case _:
                        return None
                
            case Inlet():
                inlet = item
                match role:
                    case GraphDataRole.TypeRole:
                        return GraphItemType.INLET
                    
                    case Qt.ItemDataRole.DisplayRole | Qt.ItemDataRole.EditRole:
                        return f"IN {inlet.name}"
                    case _:
                        return None
                return None
            
            case Outlet():
                outlet = item
                match role:
                    case GraphDataRole.TypeRole:
                        return GraphItemType.OUTLET
                    case Qt.ItemDataRole.DisplayRole | Qt.ItemDataRole.EditRole:
                        return f"OUT {outlet.name}"
                    case _:
                        return None
            
            case Link():
                link = item
                match role:
                    case GraphDataRole.TypeRole:
                        return GraphItemType.LINK
                    
                    case GraphDataRole.SourceRole:
                        return self.indexFromItem(link.source) if link.source else None
                    
                    case Qt.ItemDataRole.DisplayRole:
                        return f"LINK {link.source} -> {link.target}"
                    
                    case _:
                        return None
                return None

            case _:
                return None
            
    def setData(self, index:QModelIndex, value, role:int = Qt.ItemDataRole.EditRole)->bool:
        if not index.isValid():
            return False
        
        item = index.internalPointer()
        match item:
            case Operator():
                operator = item
                match role:
                    case Qt.ItemDataRole.EditRole | Qt.ItemDataRole.DisplayRole:
                        if not isinstance(value, str):
                            return False # Ensure value is a string
                        operator.setExpression(value)
                        self.dataChanged.emit(index, index, [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole])
                        return True
                    case _:
                        return False
                
            case Inlet():
                inlet = item
                match role:
                    case Qt.ItemDataRole.EditRole | Qt.ItemDataRole.DisplayRole:
                        if not isinstance(value, str):
                            return False # Ensure value is a string
                        inlet.name = value
                        self.dataChanged.emit(index, index, [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole])
                        return True
                    case _:
                        return False

            case Outlet():
                outlet = item
                match role:
                    case Qt.ItemDataRole.EditRole | Qt.ItemDataRole.DisplayRole:
                        if not isinstance(value, str):
                            return False # Ensure value is a string
                        outlet.name = value
                        self.dataChanged.emit(index, index, [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole])
                        return True
                    case _:
                        return False

            case Link():
                link = item
                match role:
                    case GraphDataRole.SourceRole:
                        assert isinstance(value, (QModelIndex, QPersistentModelIndex)), "Source must be a valid QModelIndex."
                        assert value.isValid(), "Source index must be valid."
                        source_item = self.itemFromIndex(value)
                        graph = self.invisibleRootItem()
                        graph.setLinkSource(link, source_item)  # Relink the existing link to the new source
                        self.dataChanged.emit(index, index, [GraphDataRole.SourceRole])
                        return True

        return False
            
    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        
        item = index.internalPointer()
        match item:
            case Operator():
                return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEditable
            
            case Inlet() | Outlet():
                return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEditable
            
            case Link():
                return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
            
            case _:
                return Qt.ItemFlag.NoItemFlags
            
    def insertRows(self, row, count, parent:QModelIndex)->bool:
        parent = QModelIndex(parent)  # Ensure parent is a valid QModelIndex
        parent_item:FlowGraph|Operator|Inlet|Outlet|Link = self.invisibleRootItem() if not parent.isValid() else parent.internalPointer()
        assert count > 0, "Count must be greater than 0 for insertRows."
        match parent_item:
            case FlowGraph():
                graph = parent_item
                success = True
                self.beginInsertRows(parent, row, row + count - 1)
                for i in range(count):
                    if not graph.insertOperator(row + i, Operator(f"print")):
                        raise Exception("Failed to add operator to the graph.")
                        success = False
                self.endInsertRows()
                return success

            case Operator():
                raise Exception("With this model inlets cannot be inserted directly under an operator. they are determined by the operator's implementation.")
                return False # Cannot insert rows directly under an operator. It is dependent on the Operator expression
            
            case Inlet():
                # Note: insertRows must support dangling link, 
                # because it's called by the default graphview delegate to create new links.
                inlet = parent_item
                target = inlet.operator
                graph:FlowGraph = self.invisibleRootItem()
                success = True
                self.beginInsertRows(parent, row, row + count - 1)
                for i in range(count):
                    if not graph.insertLink(i, source=None, target=inlet):
                        success = False
                self.endInsertRows()
                return success
            case _:
                raise Exception(f"Invalid parent item type: {type(parent_item)}")
            
    def removeRows(self, row:int, count:int, parent:QModelIndex)-> bool:
        parent_item:FlowGraph|Operator|Inlet|Outlet|Link = self.invisibleRootItem() if not parent.isValid() else parent.internalPointer()
        match parent_item:
            case FlowGraph():
                graph = parent_item
                self.beginRemoveRows(parent, row, row + count - 1)
                for i in reversed(range(row, row + count)):
                    print(f"Removing operator at index {i}")
                    operators = graph.operators()
                    if i < len(operators):
                        operator = operators[i]
                        if not graph.removeOperator(operator):
                            self.endRemoveRows()
                            return False
                self.endRemoveRows()
                return True
            
            case Operator():
                # Cannot remove inlets/outlets directly from an operator
                # These are determined by the operator's implementation
                return False
            
            case Inlet():
                inlet = parent_item
                graph = self.invisibleRootItem()
                self.beginRemoveRows(parent, row, row + count - 1)
                # Remove links connected to this inlet
                # This is a simplified implementation - you may need more sophisticated link management
                for i in reversed(range(row, row + count)):
                    # Implementation would depend on how links are stored and managed
                    pass
                self.endRemoveRows()
                return True
            case _:
                return False
    
from graphview import GraphView
if __name__ == "__main__":
    import sys

    class MainWindow(QWidget):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("DataFlow")
            self.setGeometry(100, 100, 800, 600)
            self.model = FlowGraphModel(self)
            self.selection = QItemSelectionModel(self.model)

            self.toolbar = QMenuBar(self)
            add_action = self.toolbar.addAction("Add Operator")
            add_action.triggered.connect(self.addOperator)
            remove_action = self.toolbar.addAction("Remove Operator")
            remove_action.triggered.connect(self.removeSelectedItems)

            self.tree = QTreeView(parent=self)
            self.tree.setModel(self.model)
            self.tree.setSelectionModel(self.selection)
            self.tree.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked | QAbstractItemView.EditTrigger.SelectedClicked)
            # model = GraphItemModel()
            # self.view.setModel(model)
            self.graphview = GraphView(parent=self)
            self.graphview.setModel(self.model)
            self.graphview.setSelectionModel(self.selection)

            layout = QHBoxLayout(self)
            splitter = QSplitter(Qt.Orientation.Horizontal, self)
            splitter.addWidget(self.tree)
            splitter.addWidget(self.graphview)
            layout.setMenuBar(self.toolbar)
            layout.addWidget(splitter)

            self.setLayout(layout)

        @Slot()
        def addOperator(self):
            """Add a new operator to the graph."""
            self.model.insertRows(0, 1, QModelIndex())

        @Slot()
        def removeSelectedItems(self):
            """Remove the currently selected items from the graph."""
            selected_indexes = self.selection.selectedIndexes()
            if not selected_indexes:
                return
            
            for index in selected_indexes:
                if index.isValid():
                    self.model.removeRows(index.row(), 1, index.parent())

    # graph = model.invisibleRootItem()
    # operator = Operator("TestOperator")
    # graph.addOperator(operator)
    
    # index = model.index(0, 0, QModelIndex())
    # print(model.data(index, Qt.ItemDataRole.DisplayRole))  # Should print "TestOperator"

    import sys
    app = QApplication(sys.argv)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())