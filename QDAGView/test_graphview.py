
import sys
import unittest

from PySide6.QtCore import *
from PySide6.QtGui import *
from PySide6.QtWidgets import *



from graphview import GraphView
app = QApplication(sys.argv)  # Only one QApplication per app
class TestGraphView(unittest.TestCase):
    def addNode(self, name:str, content:str):
        item = QStandardItem(name)
        item.setData(RowType.NODE, GraphDataRole.TypeRole)
        self.nodes.appendRow([item, QStandardItem(content)])
        return item
    
    def addInlet(self, node:QStandardItem, name:str):
        item = QStandardItem(name)
        item.setData(RowType.INLET, GraphDataRole.TypeRole)
        node.appendRow(item)
        return item
    
    def addOutlet(self, node:QStandardItem, name:str):
        item = QStandardItem(name)
        item.setData(RowType.OUTLET, GraphDataRole.TypeRole)
        node.appendRow(item)
        return item
    
    def addLink(self, source:QStandardItem, target:QStandardItem, data:str):
        # add link to inlet, store as the children of the inlet
        assert source.index().isValid(), "Source must be a valid index"
        assert source.data(GraphDataRole.TypeRole) == RowType.OUTLET, "Source must be an outlet"
        item = QStandardItem()
        item.setData(RowType.LINK, GraphDataRole.TypeRole)
        item.setData(f"{source.index().parent().data(Qt.ItemDataRole.DisplayRole)}.{source.data(Qt.ItemDataRole.DisplayRole)}", Qt.ItemDataRole.DisplayRole)
        item.setData(QPersistentModelIndex(source.index()), GraphDataRole.SourceRole)
        target.appendRow([item, QStandardItem(data)])

    def test_initial_model(self):
        model = QStandardItemModel()

        view = GraphView()
        view.setModel(model)

class TestGraphView_UnsupportedModelStructures(unittest.TestCase):
     ...

if __name__ == "__main__":
	unittest.main()