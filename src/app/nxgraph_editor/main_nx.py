# A simple example application demonstrating the use of QDAGView for building and evaluating a dataflow graph.
from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWidgets import *
from typing import List

import networkx as nx

from qdagview.controllers.base_graphcontroller import BaseGraphController
from qdagview.controllers.base_graphselectioncontroller import BaseGraphSelectionController
from qdagview.views.graphview_with_BaseGraphController import QDagView

import sys

from nx_graph_controller import NXGraphController

from qdagview.factories.widgetfactory_with_default_widgets import WidgetFactory

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("NetworkX Graph View")
        self.setGeometry(100, 100, 800, 600)
    
        # setup toolbar
        self.toolbar = QMenuBar(self)
        add_action = self.toolbar.addAction("Add Node")
        add_action.triggered.connect(self.appendNode)
        remove_action = self.toolbar.addAction("Remove Node")
        remove_action.triggered.connect(self.removeSelectedItems)
        self.toolbar.setNativeMenuBar(False)

        # setup model controller
        self.graph_controller = NXGraphController(parent=self)
        self.graph_controller.nodesInserted.connect(self.update_label)
        self.graph_controller.inletsInserted.connect(self.update_label)
        self.graph_controller.outletsInserted.connect(self.update_label)
        self.graph_controller.linksInserted.connect(self.update_label)
        self.graph_controller.nodesRemoved.connect(self.update_label)
        self.graph_controller.inletsRemoved.connect(self.update_label)
        self.graph_controller.outletsRemoved.connect(self.update_label)
        self.graph_controller.linksRemoved.connect(self.update_label)

        # # setup graph view
        self.graphview = QDagView(parent=self, factory=WidgetFactory())
        self.graphview.setController(self.graph_controller)

        # label
        self.label = QLabel("Graph View")

        # setup layout
        layout = QVBoxLayout(self)
        layout.setMenuBar(self.toolbar)
        layout.addWidget(self.graphview)
        layout.addWidget(self.label)
        
        self.setLayout(layout)

        # init
        self.update_label()

    def update_label(self):
        node_count = self.graph_controller.nodeCount()
        link_count = self.graph_controller.linkCount()
        node_list = ""
        for n in self.graph_controller.nodes():
            
            inlets = [self.graph_controller.data(i, role=Qt.ItemDataRole.DisplayRole) for i in self.graph_controller.inlets(n)]
            outlets = [self.graph_controller.data(o, role=Qt.ItemDataRole.DisplayRole) for o in self.graph_controller.outlets(n)]
            node_list += f"- {n} (Inlets: {', '.join(inlets)}, Outlets: {', '.join(outlets)})\n"
        link_list = ""
        for link in self.graph_controller.links():
            source_port = self.graph_controller.linkSource(link)
            target_port = self.graph_controller.linkTarget(link)
            link_list += f"- {source_port} -> {target_port}\n"

        from textwrap import dedent
        self.label.setText(dedent(f"""
Nodes: {node_count}
{node_list}
Links: {link_count}
{link_list}
        """))


    def appendNode(self):
        new_node_ref = self.graph_controller.addNode()

    def removeSelectedItems(self):
        ...


if __name__ == "__main__":
    import sys
    app = QApplication(sys.argv)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())