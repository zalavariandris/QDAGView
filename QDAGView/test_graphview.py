
import sys
import unittest

from PySide6.QtCore import *
from PySide6.QtGui import *
from PySide6.QtWidgets import *


def addNode(model:QStandardItemModel, name:str, content:str):
    item = QStandardItem(name)
    item.setData(RowType.NODE, GraphDataRole.TypeRole)
    model.appendRow([item, QStandardItem(content)])
    return item.index()

def addInlet(model:QStandardItemModel, node:QStandardItem, name:str):
    item = QStandardItem(name)
    item.setData(RowType.INLET, GraphDataRole.TypeRole)
    node.appendRow(item)
    return item

def addOutlet(model:QStandardItemModel, node:QStandardItem, name:str):
    item = QStandardItem(name)
    item.setData(RowType.OUTLET, GraphDataRole.TypeRole)
    node.appendRow(item)
    return item

def addLink(model:QStandardItemModel, source:QStandardItem, target:QStandardItem, data:str):
    # add link to inlet, store as the children of the inlet
    assert source.index().isValid(), "Source must be a valid index"
    assert source.data(GraphDataRole.TypeRole) == RowType.OUTLET, "Source must be an outlet"
    item = QStandardItem()
    item.setData(RowType.LINK, GraphDataRole.TypeRole)
    item.setData(f"{source.index().parent().data(Qt.ItemDataRole.DisplayRole)}.{source.data(Qt.ItemDataRole.DisplayRole)}", Qt.ItemDataRole.DisplayRole)
    item.setData(QPersistentModelIndex(source.index()), GraphDataRole.SourceRole)
    target.appendRow([item, QStandardItem(data)])


from graphview import GraphView, RowType, GraphDataRole
app = QApplication(sys.argv)  # Only one QApplication per app
class TestGraphView(unittest.TestCase):
    def test_initial_model(self):
        model = QStandardItemModel()
        addNode(model, "read", "read()")

        view = GraphView()
        view.setModel(model)

class TestLinks(unittest.TestCase):
    def setUp(self):
        self.view = GraphView()
        self.model = QStandardItemModel()
        self.view.setModel(self.model)
        # add node1
        self.node1 = QStandardItem("node1")
        self.node1.setData(RowType.NODE, GraphDataRole.TypeRole)
        self.model.appendRow([self.node1, QStandardItem("")])

        self.out1 = QStandardItem("out")
        self.out1.setData(RowType.OUTLET, GraphDataRole.TypeRole)
        self.node1.appendRow(self.out1)

        # add node2
        self.node2 = QStandardItem("node2")
        self.node2.setData(RowType.NODE, GraphDataRole.TypeRole)
        self.model.appendRow([self.node2, QStandardItem("")])

        self.in1 = QStandardItem("in")
        self.in1.setData(RowType.OUTLET, GraphDataRole.TypeRole)
        self.node2.appendRow(self.in1)
        
    def test_link_creation(self):
        # link
        link = QStandardItem("link")
        link.setData(QPersistentModelIndex( self.out1.index() ), GraphDataRole.SourceRole)
        self.in1.appendRow(link)

        # test if link has a corresponding widget
        link_id = QPersistentModelIndex(link.index())
        self.assertIn(link_id, self.view._row_widgets)
        self.assertIsInstance(self.view._row_widgets[link_id], QGraphicsItem)

    def test_create_danglink_link(self):
        # link
        link = QStandardItem("link")
        self.in1.appendRow(link)

        # dangling links should not create a widget
        link_id = QPersistentModelIndex(link.index())
        self.assertNotIn(link_id, self.view._row_widgets)

        # 
        link.setData(QPersistentModelIndex( self.out1.index() ), GraphDataRole.SourceRole)
        # self.assertIn(link_id, self.view._row_widgets)


class TestGraphView_UnsupportedModelStructures(unittest.TestCase):
     ...

if __name__ == "__main__":
	unittest.main()