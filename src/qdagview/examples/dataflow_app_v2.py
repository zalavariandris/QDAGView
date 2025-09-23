# A simple example application demonstrating the use of QDAGView for building and evaluating a dataflow graph.
from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWidgets import *
from typing import List

# from qdagview.models import FlowGraphModel, ExpressionOperator
from qdagview.examples.flowgraphmodel import FlowGraphModel
from qdagview.examples.flowgraph import ExpressionOperator
from qdagview.views import GraphView
from qdagview.models import QItemModelGraphModel

import logging
logger = logging.getLogger(__name__)


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.DEBUG)
    class MainWindow(QWidget):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("DataFlow")
            self.setGeometry(100, 100, 800, 600)
            self.tree_model = FlowGraphModel(self) # ground truth QItemModel
            self.graph_model = QItemModelGraphModel(parent=self) # graph model backed by the QItemModel
            self.graph_model.setSourceModel(self.tree_model)
            self.selection = QItemSelectionModel(self.tree_model)

            self.toolbar = QMenuBar(self)
            add_action = self.toolbar.addAction("Add Operator")
            add_action.triggered.connect(self.appendOperator)
            remove_action = self.toolbar.addAction("Remove Operator")
            remove_action.triggered.connect(self.removeSelectedItems)
            evaluate_action = self.toolbar.addAction("Evaluate Expression")
            evaluate_action.triggered.connect(self.evaluateCurrent)
            self.toolbar.setNativeMenuBar(False)

            self.tree = QTreeView(parent=self)
            self.tree.setModel(self.tree_model)
            self.tree.setSelectionModel(self.selection)
            self.tree.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked | QAbstractItemView.EditTrigger.SelectedClicked)
            self.tree.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
            self.tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
            # model = GraphItemModel()
            # self.view.setModel(model)
            self.graphview = GraphView(parent=self)
            self.graphview.setModel(self.graph_model)
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
                    ancestors = self.tree_model._root.ancestors(self.selection.currentIndex().internalPointer())
                    ancestor_indexes = set([self.tree_model._indexFromItem(op) for op in ancestors])

                    if set(indexes).intersection(ancestor_indexes):
                        self.evaluateCurrent()

            self.selection.currentChanged.connect(lambda current, previous: onChange([current]))
            self.tree_model.dataChanged.connect(self.graphview.update)

        @Slot()
        def appendOperator(self):
            """Add a new operator to the graph."""
            self.graph_model.addNode()

        @Slot()
        def removeSelectedItems(self):
            """Remove the currently selected items from the graph."""
            selected_indexes = self.selection.selectedRows()
            print("Removing indexes:", selected_indexes)
            self.graph_model.batchRemove(selected_indexes)

        @Slot()
        def evaluateCurrent(self):
            index = self.selection.currentIndex()
            if not index.isValid():
                return
            result = self.tree_model.evaluate(index)
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