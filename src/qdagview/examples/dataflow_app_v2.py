# A simple example application demonstrating the use of QDAGView for building and evaluating a dataflow graph.
from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWidgets import *
from typing import List

from qdagview.models import FlowGraphModel, ExpressionOperator, ItemGraphHelper
from qdagview.views import GraphView


if __name__ == "__main__":
    import sys

    class MainWindow(QWidget):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("DataFlow")
            self.setGeometry(100, 100, 800, 600)
            self.model = FlowGraphModel(self)
            self.helper = ItemGraphHelper(self.model)
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
            self.helper.createOperator("a+b", "NewOp")

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