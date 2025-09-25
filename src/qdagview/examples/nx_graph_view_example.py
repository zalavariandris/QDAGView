# A simple example application demonstrating the use of QDAGView for building and evaluating a dataflow graph.
from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWidgets import *
from typing import List

# from qdagview.models import FlowGraphModel, ExpressionOperator
from qdagview.models import NXGraphModel
from qdagview.views import GraphModel_GraphView

import logging
logger = logging.getLogger(__name__)



import sys

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("NetworkX Graph View")
        self.setGeometry(100, 100, 800, 600)
        
        self.graph_model = NXGraphModel(parent=self) # graph model backed by a NetworkX graph

        self.toolbar = QMenuBar(self)
        add_action = self.toolbar.addAction("Add Node")
        add_action.triggered.connect(self.appendNode)
        remove_action = self.toolbar.addAction("Remove Node")
        remove_action.triggered.connect(self.removeSelectedItems)
        self.toolbar.setNativeMenuBar(False)

        self.graphview = GraphModel_GraphView(parent=self)
        self.graphview.setModel(self.graph_model)

        layout = QVBoxLayout(self)
        layout.setMenuBar(self.toolbar)
        layout.addWidget(self.graphview)
        self.setLayout(layout)

    def appendNode(self):
        node_ref = self.graph_model.addNode()
        logger.info(f"Added node: {node_ref}")

    def removeSelectedItems(self):
        ...


if __name__ == "__main__":

    logging.basicConfig(level=logging.DEBUG)



    import sys
    app = QApplication(sys.argv)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())