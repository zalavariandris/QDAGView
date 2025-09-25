# A simple example application demonstrating the use of QDAGView for building and evaluating a dataflow graph.
from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWidgets import *
from typing import List

# from qdagview.models import FlowGraphModel, ExpressionOperator
from qdagview.examples.flowgraphmodel import FlowGraphModel
from qdagview.examples.flowgraph import ExpressionOperator
from qdagview.views.graphview_with_QItemModel import QItemModel_GraphView
from qdagview.controllers.qitemmodel_graphcontroller import QItemModelGraphController

import logging
logger = logging.getLogger(__name__)

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DataFlow")
        self.setGeometry(100, 100, 800, 600)
        self.tree_model = FlowGraphModel(self) # ground truth QItemModel
        self.graph_controller = QItemModelGraphController()
        self.graph_controller.setModel(self.tree_model)
        self.selection = QItemSelectionModel(self.tree_model)

        self.toolbar = QMenuBar(self)
        add_action = self.toolbar.addAction("Add Operator")
        add_action.triggered.connect(self.appendOperator)
        remove_action = self.toolbar.addAction("Remove Operator")
        remove_action.triggered.connect(self.removeSelectedItems)
        evaluate_action = self.toolbar.addAction("Evaluate Expression")
        evaluate_action.triggered.connect(self.evaluateCurrent)
        self.toolbar.setNativeMenuBar(False)

        self.tree_view = QTreeView(parent=self)
        self.tree_view.setModel(self.tree_model)
        self.tree_view.setSelectionModel(self.selection)
        self.tree_view.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked | QAbstractItemView.EditTrigger.SelectedClicked)
        self.tree_view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tree_view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        # model = GraphItemModel()
        # self.view.setModel(model)
        self.graphview = QItemModel_GraphView(parent=self)
        self.graphview.setModel(self.tree_model)
        self.graphview.setSelectionModel(self.selection)

        self.viewer = QLabel("viewer")

        layout = QHBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.addWidget(self.tree_view)
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
        self.graph_controller.addNode()

    @Slot()
    def removeSelectedItems(self):
        """Remove the currently selected items from the graph."""
        selected_indexes = self.selection.selectedRows()
        print("Removing indexes:", selected_indexes)
        self.graph_controller.batchRemove(selected_indexes)

    @Slot()
    def evaluateCurrent(self):
        index = self.selection.currentIndex()
        if not index.isValid():
            return
        result = self.tree_model.evaluate(index)
        self.viewer.setText(result)

if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.DEBUG)
    
    import sys
    app = QApplication(sys.argv)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())