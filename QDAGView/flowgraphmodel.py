from __future__ import annotations

from typing import *
from qtpy.QtWidgets import *
from qtpy.QtCore import *
from qtpy.QtGui import *

from dataclasses import dataclass, field
from collections import defaultdict

from core import GraphDataRole, GraphItemType
from utils import bfs

from flowgraph import FlowGraph, ExpressionOperator, Inlet, Outlet, Link


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
        parent_item:FlowGraph | ExpressionOperator | Inlet = self.invisibleRootItem() if not parent.isValid() else parent.internalPointer()
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
                
            case ExpressionOperator():
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

    def indexFromItem(self, item: ExpressionOperator | Inlet | Outlet | Link) -> QModelIndex:
        """Get the index of an item in the model."""
        match item:
            case FlowGraph():
                return QModelIndex()  # Graph itself has no index, it's the root item
            
            case ExpressionOperator():
                operator = item
                row = self._root.operators().index(operator)
                return self.createIndex(row, 0, operator)
        
            case Inlet():
                inlet = item
                operator = inlet.operator
                assert isinstance(operator, ExpressionOperator), "Inlet must have a parent operator."
                row = operator.inlets().index(inlet)
                return self.createIndex(row, 0, inlet)

            case Outlet():
                operator = item.operator
                assert isinstance(operator, ExpressionOperator), "Outlet must have a parent operator."
                inlets = operator.inlets()
                outlets = operator.outlets()
                row = len(inlets) + outlets.index(item)
                return self.createIndex(row, 0, item)
                
            case Link():
                parent_inlet = item.target
                assert isinstance(parent_inlet, Inlet), "Link must have a target inlet."
                parent_node = parent_inlet.operator
                assert isinstance(parent_node, ExpressionOperator), "Link must have a parent operator."
                inlets = parent_node.inlets()
                row = inlets.index(parent_inlet)
                return self.createIndex(row, 0, item)

            case _:
                raise ValueError(f"Unsupported item type: {type(item)}")
    
    def itemFromIndex(self, index: QModelIndex) -> ExpressionOperator | Inlet | Outlet | Link | None:
        """Get the item from a QModelIndex."""
        if not index.isValid():
            return None
        item = QModelIndex(index).internalPointer()
        assert isinstance(item, (ExpressionOperator | Inlet | Outlet | Link))
        return item

    def parent(self, index: QModelIndex) -> QModelIndex:
        index = QModelIndex(index)  # Ensure index is a valid QModelIndex
        if not index.isValid():
            return QModelIndex()
        
        item = index.internalPointer()
        match item:
            case ExpressionOperator():
                # Operator's parent is the root (Graph), so return invalid QModelIndex
                return QModelIndex()

            case Inlet():
                inlet = item
                assert isinstance(inlet, Inlet), "Inlet must have a parent operator."
                parent_operator = inlet.operator
                assert isinstance(parent_operator, ExpressionOperator), "Inlet must have a parent operator."
                graph = self.invisibleRootItem()
                row = graph.operators().index(parent_operator)
                return self.createIndex(row, 0, parent_operator)

            case Outlet():
                outlet = item
                assert isinstance(outlet, Outlet), "Outlet must have a parent operator."
                parent_operator = outlet.operator
                assert isinstance(parent_operator, ExpressionOperator), "Outlet must have a parent operator."
                graph = self.invisibleRootItem()
                row = graph.operators().index(parent_operator)
                return self.createIndex(row, 0, parent_operator)

            case Link():
                link = item
                parent_operator = link.target.operator if link.target else None
                if parent_operator is not None and link.target is not None:
                    inlets = list(parent_operator.inlets())
                    assert link.target in inlets, "Link's target inlet must be in its parent operator's inlets."
                    row = inlets.index(link.target)
                    return self.createIndex(row, 0, link.target)
                return QModelIndex()
            case _:
                return QModelIndex()
            
    def rowCount(self, parent=QModelIndex())->int:
        parent = QModelIndex(parent)  # Ensure parent is a valid QModelIndex
        parent_item:FlowGraph | ExpressionOperator | Inlet | Outlet | Link = self.invisibleRootItem() if not parent.isValid() else parent.internalPointer()
        
        match parent_item:
            case FlowGraph():
                graph = parent_item
                return len(graph.operators())
            
            case ExpressionOperator():
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
        parent_item: FlowGraph | ExpressionOperator | Inlet | Outlet | Link = self.invisibleRootItem() if not index.isValid() else index.internalPointer()

        match parent_item:
            case FlowGraph():
                return len(parent_item.operators())>0
            
            case ExpressionOperator():
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
        parent_item:FlowGraph | ExpressionOperator | Inlet | Outlet | Link = self.invisibleRootItem() if not parent.isValid() else QModelIndex(parent).internalPointer()
        
        match parent_item:
            case FlowGraph():
                return 2
            
            case ExpressionOperator():
                return 1

            case Inlet():
                return 1
                
            case Outlet():
                return 1
            
            case Link():
                return 1
            
            case _:
                raise Exception(f"Invalid parent item type: {type(parent_item)}")

    def data(self, index:QModelIndex, role=Qt.ItemDataRole.DisplayRole):

        if not index.isValid():
            return None
        
        item = index.internalPointer()
        match item:
            case ExpressionOperator():
                operator = item

                match index.column(), role:
                    case 0, Qt.ItemDataRole.DisplayRole:
                        return f"{operator.name()}"
                    
                    case 0, Qt.ItemDataRole.EditRole:
                        return operator.name()

                    case 0, GraphDataRole.TypeRole:
                        return GraphItemType.NODE
                    
                    case 1, Qt.ItemDataRole.DisplayRole:
                        return f"{operator.expression()}"
                    
                    case 1, Qt.ItemDataRole.EditRole:
                        return operator.expression()
                    case _:
                        return None
                            
            case Inlet():
                inlet = item

                match index.column(), role:
                    case 0, GraphDataRole.TypeRole:
                        return GraphItemType.INLET
                    
                    case 0, Qt.ItemDataRole.DisplayRole:
                        return f"{inlet.name}"
                    case 0, Qt.ItemDataRole.EditRole:
                        return inlet.name
                    case _:
                        return None
            
            case Outlet():
                outlet = item

                match index.column(), role:
                    case 0, GraphDataRole.TypeRole:
                        return GraphItemType.OUTLET
                    
                    case 0, Qt.ItemDataRole.DisplayRole:
                        return f"{outlet.name}"
                    
                    case 0, Qt.ItemDataRole.EditRole:
                        return outlet.name
                    
                    case _:
                        return None

            
            case Link():
                link = item

                match index.column(), role:
                    case 0, GraphDataRole.TypeRole:
                        return GraphItemType.LINK
                    
                    case 0, GraphDataRole.SourceRole:
                        return self.indexFromItem(link.source) if link.source else None
                    
                    case 0, Qt.ItemDataRole.DisplayRole:
                        return f"{link.source} -> {link.target}"
                    
                    case _:
                        return None

                return None

            case _:
                return None
    
    def setData(self, index:QModelIndex, value, role:int = Qt.ItemDataRole.EditRole)->bool:
        if not index.isValid():
            print("Invalid index")
            return False

        item = index.sibling(index.row(), 0).internalPointer()
        match item:
            case ExpressionOperator():
                operator = item
                match index.column():
                    case 0: # name
                        name_index = index.sibling(index.row(), 0)
                        match role:
                            case Qt.ItemDataRole.EditRole | Qt.ItemDataRole.DisplayRole:
                                if not isinstance(value, str):
                                    return False
                                operator.setName(value)
                                self.dataChanged.emit(name_index, name_index, [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole])
                                return True
                            case _:
                                return False
                    case 1: # expression
                        operator_index = index.sibling(index.row(), 0)
                        expression_index = index.sibling(index.row(), 1)
                        match role:
                            case Qt.ItemDataRole.EditRole | Qt.ItemDataRole.DisplayRole:
                                if not isinstance(value, str):
                                    print("expression value must be a string")
                                    return False # Ensure value is a string
                                
                                previous_inlets = list(operator.inlets())
                                operator.setExpression(value)
                                next_inlets = list(operator.inlets())

                                # emit dataChanged signal for the operator expression
                                self.dataChanged.emit(expression_index, expression_index, [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole])

                                # if inlets changed, we need to update the model and emit necessary signals
                                inlet_count = max(len(previous_inlets), len(next_inlets))
                                self.dataChanged.emit(
                                    self.index(0, 0, operator_index),
                                    self.index(inlet_count, self.columnCount(operator_index), operator_index),
                                    [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole]
                                )

                                if len(previous_inlets) < len(next_inlets):
                                    self.beginInsertRows(operator_index, len(previous_inlets), len(next_inlets)-1)
                                    # inlets were already updated in the underlying data
                                    self.endInsertRows()

                                if len(previous_inlets) > len(next_inlets):
                                    self.beginRemoveRows(operator_index, len(next_inlets), len(previous_inlets)-1)
                                    # inlets were already updated in the underlying data
                                    self.endRemoveRows()

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
            case ExpressionOperator():
                return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEditable
            
            case Inlet() | Outlet():
                return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
            
            case Link():
                return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
            
            case _:
                return Qt.ItemFlag.NoItemFlags
            
    def insertRows(self, row, count, parent:QModelIndex)->bool:
        parent = QModelIndex(parent)  # Ensure parent is a valid QModelIndex
        parent_item:FlowGraph|ExpressionOperator|Inlet|Outlet|Link = self.invisibleRootItem() if not parent.isValid() else parent.internalPointer()
        assert count > 0, "Count must be greater than 0 for insertRows."
        match parent_item:
            case FlowGraph():
                graph = parent_item
                success = True
                self.beginInsertRows(parent, row, row + count - 1)
                for i in range(count):
                    if not graph.insertOperator(row + i, ExpressionOperator(f"x+y")):
                        raise Exception("Failed to add operator to the graph.")
                        success = False
                self.endInsertRows()
                return success

            case ExpressionOperator():
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
        parent_item:FlowGraph|ExpressionOperator|Inlet|Outlet|Link = self.invisibleRootItem() if not parent.isValid() else parent.internalPointer()
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
            
            case ExpressionOperator():
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
                    assert isinstance(link, Link), f"Expected Link, got {type(link)}"
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
            add_action.triggered.connect(self.appendOperator)
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
                if isinstance(current_node, ExpressionOperator):
                    ancestors = self.model._root.ancestors(self.selection.currentIndex().internalPointer())
                    ancestor_indexes = set([self.model.indexFromItem(op) for op in ancestors])

                    if set(indexes).intersection(ancestor_indexes):
                        self.evaluateCurrent()

            self.selection.currentChanged.connect(lambda current, previous: onChange([current]))
            self.model.dataChanged.connect(self.graphview.update)

        @Slot()
        def appendOperator(self):
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