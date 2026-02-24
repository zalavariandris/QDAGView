# A simple example application demonstrating the use of QDAGView for building and evaluating a dataflow graph.
from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWidgets import *
from typing import List

# from qdagview.models import FlowGraphModel, ExpressionOperator
from flowgraphmodel import FlowGraphModel
from flowgraph import ExpressionOperator
from qdagview.factories.widgetfactory_with_default_widgets import WidgetFactory
from qdagview.views.graphview_with_BaseGraphController import QDagView
from qdagview.controllers.qtreemodel_graphcontroller import QTreeModel_GraphController
from qdagview.controllers.qtreemodel_graphselectioncontroller import QTreeModel_GraphSelectionController

import logging
logger = logging.getLogger(__name__)


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DataFlow")
        self.setGeometry(100, 100, 800, 600)

        # - SETUP MODELS AND CONTROLLERS -
        self.tree_model = FlowGraphModel(self) # ground truth QItemModel
        self.graph_controller = QTreeModel_GraphController()
        self.graph_controller.setSourceModel(self.tree_model)
        self.item_selection = QItemSelectionModel(self.tree_model)
        self.graph_selection_controller = QTreeModel_GraphSelectionController(self.graph_controller, self.item_selection)
        
        self.graph_selection_controller.selectionChanged.connect(lambda selected, deselected: print(f"Graph selection changed - selected: {[index.data() for index in selected]}, deselected: {[index.data() for index in deselected]}"))
        self.graph_selection_controller.currentChanged.connect(lambda current, previous: print(f"Graph current changed - current: {current.data() if current.isValid() else None}, previous: {previous.data() if previous.isValid() else None}"))

        # - SETUP UI -
        # - Toolbar -
        self.toolbar = QMenuBar(self)
        add_action = self.toolbar.addAction("Add Operator")
        add_action.triggered.connect(self.appendOperator)
        remove_action = self.toolbar.addAction("Remove Operator")
        remove_action.triggered.connect(self.removeSelectedItems)
        evaluate_action = self.toolbar.addAction("Evaluate Expression")
        evaluate_action.triggered.connect(self.evaluateCurrent)
        self.toolbar.setNativeMenuBar(False)

        # - node tree view -
        self.tree_view = QTreeView(parent=self)
        self.tree_view.setModel(self.tree_model)
        self.tree_view.setSelectionModel(self.item_selection)
        self.tree_view.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked | QAbstractItemView.EditTrigger.SelectedClicked)
        self.tree_view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tree_view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        # model = GraphItemModel()
        # self.view.setModel(model)

        # - nodes graph view -
        self.graphview = QDagView(parent=self, factory=WidgetFactory())
        self.graphview.setController(self.graph_controller)
        self.graphview.setSelectionController(self.graph_selection_controller)
        # self.graphview.setModel(self.tree_model)
        self.graphview.setSelectionController(self.graph_selection_controller)

        # - viewer -
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
            current_node = self.item_selection.currentIndex().internalPointer()
            if isinstance(current_node, ExpressionOperator):
                ancestors = self.tree_model._root.ancestors(self.item_selection.currentIndex().internalPointer())
                ancestor_indexes = set([self.tree_model._indexFromItem(op) for op in ancestors])

                if set(indexes).intersection(ancestor_indexes):
                    self.evaluateCurrent()

        self.item_selection.currentChanged.connect(lambda current, previous: onChange([current]))
        self.tree_model.dataChanged.connect(self.graphview.update)

    @Slot()
    def appendOperator(self):
        """Add a new operator to the graph."""
        self.graph_controller.addNode()

    @Slot()
    def removeSelectedItems(self):
        """Remove the currently selected items from the graph."""
        selected_indexes = self.item_selection.selectedRows()
        print("Removing indexes:", selected_indexes)
        self.graph_controller.remove(selected_indexes)

    @Slot()
    def evaluateCurrent(self):
        index = self.item_selection.currentIndex()
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