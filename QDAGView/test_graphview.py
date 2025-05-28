
import sys
import unittest

from PySide6.QtCore import Qt
from PySide6.QtGui import QApplication, QStandardItemModel, QStandardItem
from PySide6.QtWidgets import *



from graphview import GraphView

class TestGraphView(unittest.TestCase):
    @Slot(str, str)
    def addNode(self, name:str, content:str):
        item = QStandardItem(name)
        item.setData(RowType.NODE, GraphDataRole.TypeRole)
        self.nodes.appendRow([item, QStandardItem(content)])
        return item
    
    @Slot(QStandardItem, str)
    def addInlet(self, node:QStandardItem, name:str):
        item = QStandardItem(name)
        item.setData(RowType.INLET, GraphDataRole.TypeRole)
        node.appendRow(item)
        return item
    
    @Slot(QStandardItem, str)
    def addOutlet(self, node:QStandardItem, name:str):
        item = QStandardItem(name)
        item.setData(RowType.OUTLET, GraphDataRole.TypeRole)
        node.appendRow(item)
        return item
    
    @Slot(QStandardItem, QStandardItem)
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
        model

        view = GraphView()
        view.setModel(model)