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

        # setup selection controller
        self.selection_controller = BaseGraphSelectionController(parent=self)
        self.selection_controller.setGraphController(self.graph_controller)
        self.selection_controller.currentChanged.connect(self.update_label)
        self.selection_controller.selectionChanged.connect(self.update_label)
        self.selection_controller.selectionChanged.connect(self.onSelectionChanged)

        # log signals
        self.graph_controller.nodesAboutToBeInserted.connect(lambda node_refs: self.appendLog(f"Nodes about to be inserted: {node_refs}"))
        self.graph_controller.nodesInserted.connect(lambda node_refs: self.appendLog(f"Nodes inserted: {node_refs}"))
        self.graph_controller.inletsAboutToBeInserted.connect(lambda inlet_refs: self.appendLog(f"Inlets about to be inserted: {inlet_refs}"))
        self.graph_controller.linksInserted.connect(lambda link_refs: self.appendLog(f"Links inserted: {link_refs}"))
        self.graph_controller.nodesAboutToBeRemoved.connect(lambda node_refs: self.appendLog(f"Nodes about to be removed: {node_refs}"))
        self.graph_controller.linksAboutToBeRemoved.connect(lambda link_refs: self.appendLog(f"Links about to be removed: {link_refs}"))
        self.graph_controller.nodesRemoved.connect(lambda node_refs: self.appendLog(f"Nodes removed: {node_refs}"))
        self.graph_controller.linksRemoved.connect(lambda link_refs: self.appendLog(f"Links removed: {link_refs}"))

        self.selection_controller.selectionChanged.connect(lambda selected, deselected: self.appendLog(f"Selection changed. Selected: {selected}, Deselected: {deselected}"))
        self.selection_controller.currentChanged.connect(lambda current, previous: self.appendLog(f"Current changed: {current}, Previous: {previous}"))

        # # setup graph view
        self.graphview1 = QDagView(parent=self, factory=WidgetFactory())
        self.graphview1.setController(self.graph_controller)
        self.graphview1.setSelectionController(self.selection_controller)
        self.graphview2 = QDagView(parent=self, factory=WidgetFactory())
        self.graphview2.setController(self.graph_controller)
        self.graphview2.setSelectionController(self.selection_controller)

        # label
        self.label = QLabel("Graph View")
        self.log = QPlainTextEdit("Log:")
        self.log.setReadOnly(True)

        # setup layout
        layout = QVBoxLayout(self)
        layout.setMenuBar(self.toolbar)
        layout.addWidget(self.graphview1)
        layout.addWidget(self.graphview2)
        layout.addWidget(self.label)
        layout.addWidget(self.log)
        self.setLayout(layout)

        # init
        self.update_label()

    def appendLog(self, message:str):
        self.log.appendPlainText(f"Log: {message}")

    def onSelectionChanged(self, selected, deselected):
        print("Selection changed:")
        print("- Selected:", selected)
        print("- Deselected:", deselected)
        print("- Selection:", self.selection_controller.selectedIndexes())
        print("- Current:", self.selection_controller.currentIndex())

    def update_label(self):
        print("Updating label...")
        node_count = self.graph_controller.nodeCount()
        link_count = self.graph_controller.linkCount()
        node_list = ""
        for n in self.graph_controller.nodes():
            inlet_attributes = [self.graph_controller.attributes(i) for i in self.graph_controller.inlets(n)]
            outlet_attributes = [self.graph_controller.attributes(o) for o in self.graph_controller.outlets(n)]

            inlets =  [self.graph_controller.attributeData(a, role=Qt.ItemDataRole.DisplayRole) for attrs in inlet_attributes for a in attrs]
            outlets = [self.graph_controller.attributeData(a, role=Qt.ItemDataRole.DisplayRole) for attrs in outlet_attributes for a in attrs]

            is_selected = self.selection_controller.isSelected(n)

            node_list += f"- [{'x' if is_selected else ' '}] {n} (Inlets: {', '.join(inlets)}, Outlets: {', '.join(outlets)})\n"
        link_list = ""
        for link in self.graph_controller.links():
            source_port = self.graph_controller.linkSource(link)
            target_port = self.graph_controller.linkTarget(link)
            is_selected = self.selection_controller.isSelected(link)
            link_list += f"- [{'x' if is_selected else ' '}] {source_port} -> {target_port}\n"

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
        selected_refs= self.selection_controller.selectedIndexes()
        self.graph_controller.remove_batch(selected_refs)

        # for item in selected_items:
        #     match item:
        #         case QGraphicsWidget() if isinstance(item, QGraphicsWidget):
        #             self.graphview._widget_manager.removeWidget(item)
        #         case _:
        #             print(f"Unknown item type: {type(item)}")


if __name__ == "__main__":
    import sys
    app = QApplication(sys.argv)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())