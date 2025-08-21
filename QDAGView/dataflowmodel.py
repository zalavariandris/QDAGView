from __future__ import annotations

from typing import *
from qtpy.QtWidgets import *
from qtpy.QtCore import *
from qtpy.QtGui import *

from dataclasses import dataclass, field
from collections import defaultdict

from core import GraphDataRole, GraphItemType
from utils import bfs
from utils.unique import make_unique_id


class Operator:
    def __init__(self, expression: str = "Operator", name:str|None = None):
        self._expression = expression
        self._inlets: List[Inlet] = [Inlet("in1", self), Inlet("in2", self)] 
        self._outlets: List[Outlet] = [Outlet("out", self)]
        self._name = name if name else make_unique_id()

    def expression(self) -> str:
        """Return the expression of the operator."""
        return self._expression

    def setExpression(self, expression:str):
        """Set the expression of the operator."""
        self._expression = expression

    def name(self) -> str:
        """Return the name of the operator."""
        return self._name
    
    def setName(self, name:str):
        """Set the name of the operator."""
        self._name = name

    def __call__(self, *args, **kwds):
        ...

    def inlets(self) -> List[Inlet]:
        """Return the list of inlets for this operator."""
        return self._inlets
    
    def outlets(self) -> List[Outlet]:
        """Return the list of outlets for this operator."""
        return self._outlets
    
    def __repr__(self):
        return f"Operator({self._expression})"
    
    def evaluate(self, *args, **kwargs) -> str:
        """Evaluate the operator."""
        return f"Evaluating {self._expression}"

    
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

from utils import bfs
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
        assert isinstance(inlet, Inlet), "Inlet must be an instance of Inlet"
        return [link for link in self._in_links[inlet]]

    def outLinks(self, outlet: Outlet) -> List[Link]:
        return [link for link in self._out_links[outlet]]

    def ancestors(self, node: Operator) -> Iterable[Operator]:
        """Get all dependencies of the given operator."""
        assert node in self._operators
        def inputNodes(node: Operator) -> Iterable[Operator]:
            """Get all input nodes of the given operator."""
            for inlet in node.inlets():
                for link in self.inLinks(inlet):
                    if link.source.operator is not None:
                        yield link.source.operator
        
        for n in bfs(node, children=inputNodes):
            yield n

    def descendants(self, node: Operator) -> Iterable[Operator]:
        """Get all descendants of the given operator."""
        assert node in self._operators
        def outputNodes(node: Operator) -> Iterable[Operator]:
            """Get all output nodes of the given operator."""
            for link in self._out_links[node]:
                if link.source.operator is not None:
                    yield link.source.operator
        
        for n in bfs(node, outputNodes):
            yield n

    def evaluate(self, node: Operator) -> str:
        """Evaluate the graph starting from the given node."""
        assert node in self._operators
        result = ""
        ancestors = list(self.ancestors(node))
        print(f"Evaluating item: {node}, ancestors: {ancestors}")
        for op in ancestors:
            result += f"{op.expression()}\n"
        return result

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
    
    def removeLink(self, link: Link) -> bool:
        """Remove a link from the graph."""
        if link.source is not None:
            self._out_links[link.source].remove(link)
        if link.target is not None:
            self._in_links[link.target].remove(link)
        return True

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
        # assert column == 0, "This model only supports one column."
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
        parent_item:FlowGraph | Operator | Inlet | Outlet | Link = self.invisibleRootItem() if not parent.isValid() else parent.internalPointer()
        
        match parent_item:
            case FlowGraph():
                return 2
            
            case Operator():
                return 1

            case Inlet():
                return 1
                
            case Outlet():
                return 1
            
            case Link():
                return 1
            
            case _:
                raise Exception(f"Invalid parent item type: {type(parent_item)}")

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):

        if not index.isValid():
            return None
        
        item = index.internalPointer()
        match item:
            case Operator():
                operator = item
                match index.column():
                    case 0:
                        match role:
                            case Qt.ItemDataRole.DisplayRole:
                                return f"{operator.name()}"
                            
                            case Qt.ItemDataRole.EditRole:
                                return operator.name()
                            case _:
                                return None
                            
                    case 1:
                        match role:
                            case GraphDataRole.TypeRole:
                                return GraphItemType.NODE
                            
                            case Qt.ItemDataRole.DisplayRole:
                                return f"{operator.expression()}"
                            
                            case Qt.ItemDataRole.EditRole:
                                return operator.expression()
                            case _:
                                return None
                    case _:
                        return None
                            
            case Inlet():
                inlet = item
                match role:
                    case GraphDataRole.TypeRole:
                        return GraphItemType.INLET
                    
                    case Qt.ItemDataRole.DisplayRole:
                        return f"{inlet.name}"
                    case Qt.ItemDataRole.EditRole:
                        return inlet.name
                    case _:
                        return None
                return None
            
            case Outlet():
                outlet = item
                match role:
                    case GraphDataRole.TypeRole:
                        return GraphItemType.OUTLET
                    case Qt.ItemDataRole.DisplayRole:
                        return f"{outlet.name}"
                    case Qt.ItemDataRole.EditRole:
                        return outlet.name
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
                        return f"{link.source} -> {link.target}"
                    
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
                match index.column():
                    case 0:
                        match role:
                            case Qt.ItemDataRole.EditRole | Qt.ItemDataRole.DisplayRole:
                                if not isinstance(value, str):
                                    return False
                                operator.setName(value)
                                self.dataChanged.emit(index, index, [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole])
                                return True
                    case 1:
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
                return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
            
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
                    link = self.index(i, 0, parent).internalPointer()
                    assert isinstance(link, Link)
                    if not graph.removeLink(link):
                        self.endRemoveRows()
                        return False
                    pass # TODO: Implement link removal logic
                self.endRemoveRows()
                return True
            case _:
                print(f"Invalid parent item type: {type(parent_item)}")
                return False

    def evaluate(self, index: QModelIndex) -> Any:
        """create a python script from the selected operator and its ancestors."""

        script_text = ""
        item = self.itemFromIndex(index)  # Ensure the index is valid
        ancestors = list(self._root.ancestors(item))
        for op in reversed(ancestors):
            params = dict()
            inlets = op.inlets()  # Ensure inlets are populated
            for inlet in inlets:
                links = self._root.inLinks(inlet)
                outlets = [link.source for link in links if link.source is not None]
                if len(outlets) > 0:
                    params[inlet.name] = outlets[0].operator.name()

            line = f"{op.name()} = {op.expression()}({ ",".join(f"{k}={v}" for k, v in params.items()) })"
            
            script_text += f"{line}\n"
            
        return script_text
        

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
            evaluate_action = self.toolbar.addAction("Evaluate Expression")
            evaluate_action.triggered.connect(self.evaluateCurrent)
            self.toolbar.setNativeMenuBar(False)

            self.tree = QTreeView(parent=self)
            self.tree.setModel(self.model)
            self.tree.setSelectionModel(self.selection)
            self.tree.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked | QAbstractItemView.EditTrigger.SelectedClicked)
            # model = GraphItemModel()
            # self.view.setModel(model)
            self.graphview = GraphView(parent=self)
            self.graphview.setModel(self.model)
            self.graphview.setSelectionModel(self.selection)

            self.viewer = QLabel("viewer")

            layout = QHBoxLayout(self)
            splitter = QSplitter(Qt.Orientation.Horizontal, self)
            splitter.addWidget(self.tree)
            splitter.addWidget(self.graphview)
            splitter.addWidget(self.viewer)
            layout.setMenuBar(self.toolbar)
            layout.addWidget(splitter)
            self.setLayout(layout)

        
            def onChange(indexes: List[QModelIndex]):
                current_node = self.selection.currentIndex().internalPointer()
                if isinstance(current_node, Operator):
                    ancestors = self.model._root.ancestors(self.selection.currentIndex().internalPointer())
                    ancestor_indexes = set([self.model.indexFromItem(op) for op in ancestors])

                    if set(indexes).intersection(ancestor_indexes):
                        self.evaluateCurrent()

            self.selection.currentChanged.connect(lambda current, previous: onChange([current]))
            self.model.dataChanged.connect(self.graphview.update)

        @Slot()
        def addOperator(self):
            """Add a new operator to the graph."""
            self.model.insertRows(0, 1, QModelIndex())

        @Slot()
        def removeSelectedItems(self):
            """Remove the currently selected items from the graph."""
            # Get all selected indexes, sort by depth (deepest first), and unique by (parent, row)
            selected_indexes = self.selection.selectedIndexes()
            if not selected_indexes:
                return

            # Filter only top-level indexes (remove children if parent is selected)
            def is_descendant(index, selected_set):
                parent = index.parent()
                while parent.isValid():
                    if parent in selected_set:
                        return True
                    parent = parent.parent()
                return False

            selected_set = set(selected_indexes)
            filtered_indexes = [
                idx for idx in selected_indexes if not is_descendant(idx, selected_set)
            ]

            # Remove duplicates by (parent, row)
            unique_keys = set()
            unique_indexes = []
            for idx in filtered_indexes:
                key = (idx.parent(), idx.row())
                if key not in unique_keys:
                    unique_keys.add(key)
                    unique_indexes.append(idx)

            # Remove from bottom up (descending row order per parent)
            unique_indexes.sort(key=lambda idx: (idx.parent(), -idx.row()))

            for idx in unique_indexes:
                if idx.isValid():
                    self.model.removeRows(idx.row(), 1, idx.parent())

        @Slot()
        def evaluateCurrent(self):
            index = self.selection.currentIndex()
            if not index.isValid():
                return
            result = self.model.evaluate(index)
            self.viewer.setText(result)

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