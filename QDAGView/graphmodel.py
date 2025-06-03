from PySide6.QtCore import Qt, QModelIndex, QAbstractItemModel, QEvent
from PySide6.QtWidgets import QApplication, QTreeView
import sys
from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QHBoxLayout
from typing import *


from __future__ import annotations



class NodeItem:
    def __init__(self, name:str, content:str):
        self._name = name
        self._content = content
        self._model:GraphModel|None = None

        self._inlets:list[InletItem] = []

    def name(self):
        return self._name
    
    def content(self):
        return self._content
    
    def inlets(self)->list:
        return self._inlets
    
    def appendInlet(self, inlet:InletItem):
        self._inlets.append(inlet)
        inlet._node = self

    def removeInlet(self, inlet:InletItem):
        self._inlets.remove(inlet)
        inlet._node = None


class InletItem:
    def __init__(self, name:str, content:str):
        self._name = name
        self._content = content
        self._model:GraphModel|None

    def name(self):
        return self._name
    
    def setName(self, value:str):
        self._name = value
    
    def content(self):
        return self._content
    
    def setContent(self, value:str):
        if self._model:
            self._model.dataChanged.emit()
        self._content = value
    
    def node(self)->NodeItem|None:
        return self._node
    
    def links(self)->list:
        return []
    

class OutletItem:
    def __init__(self, name:str, content:str):
        self._name = name
        self._content = content
        self._model:GraphModel|None = None

        self._inlets:list[InletItem] = []

class LinkItem:
    def __init__(self, name:str, content:str):
        self._name = name
        self._content = content
        self._model:GraphModel|None = None

        self._inlets:list[InletItem] = []


class TreeItem:
    def __init__(self, data: list[dict], parent=None):
        self.parentItem = parent
        self.itemData = data
        self.childItems = []

    def appendChild(self, item):
        self.childItems.append(item)

    def child(self, row):
        return self.childItems[row]

    def childCount(self):
        return len(self.childItems)

    def columnCount(self):
        # Always return 1 for now since we're only showing name
        return 1

    def data(self, column):
        match column:
            case 0:
                return self.itemData.get("name", "")
            case 1:
                return self.itemData.get("content", "")
        return None

    def parent(self):
        return self.parentItem

    def row(self):
        if self.parentItem:
            return self.parentItem.childItems.index(self)
        return 0

class GraphModel(QAbstractItemModel):
    def __init__(self, parent=None):
        super(GraphModel, self).__init__(parent)
        self._nodes = []


    def columnCount(self, parent=QModelIndex()):
        return 2

    def rowCount(self, parent=QModelIndex()):
        if not parent.isValid():
            return len(self._nodes)
        
        match parent.internalPointer():
            case NodeItem():
                node = cast(NodeItem, parent.internalPointer())
                return len(node.inlets())
            case InletItem():
                inlet = cast(InletItem, parent.internalPointer())
                return len(inlet.links())
            case OutletItem():
                return 0
            case LinkItem():
                return 0
    
    def addNode(self, node:NodeItem):
        ...
    
    def insertRows(self, row, count, parent=QModelIndex()):
        parentItem = self.rootItem if not parent.isValid() else parent.internalPointer()
        self.beginInsertRows(parent, row, row + count - 1)
        for i in range(count):
            item = TreeItem({"name": "New Item", "content": None, "children": []}, parentItem)
            parentItem.childItems.insert(row, item)
        self.endInsertRows()
        return True

    def removeRows(self, row, count, parent=QModelIndex()):
        parentItem = self.rootItem if not parent.isValid() else parent.internalPointer()
        if row < 0 or (row + count) > parentItem.childCount():
            return False
        self.beginRemoveRows(parent, row, row + count - 1)
        for i in range(count):
            del parentItem.childItems[row]
        self.endRemoveRows()
        return True
    
    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        
        if role == Qt.DisplayRole or role == Qt.EditRole:
            match index.internalPointer():
                case NodeItem():
                    node = cast(NodeItem, index.internalPointer())
                    match index.column():
                        case 0:
                            return node.name()
                        case 1:
                            return node.content()
                        case _:
                            return None
  
                case InletItem():
                    inlet = cast(InletItem, index.internalPointer())
                    match index.column():
                        case 0:
                            return inlet.name()
                        case 1:
                            return inlet.content()
                        case _:
                            return None
                        
                case OutletItem():
                    outlet = cast(OutletItem, index.internalPointer())
                    match index.column():
                        case 0:
                            return outlet.name()
                        case 1:
                            return outlet.content()
                        case _:
                            return None
                        
                case LinkItem():
                    link = cast(LinkItem, index.internalPointer())
                    match index.column():
                        case 0:
                            return link.name()
                        case 1:
                            return link.content()
                        case _:
                            return None
                        
                case _:
                    return None
        return None
    
    def setData(self, index, value, role=Qt.EditRole):
        if not index.isValid() or role != Qt.EditRole:
            return False
        item = index.internalPointer()
        col = index.column()

        if role == Qt.DisplayRole or role == Qt.EditRole:
            match index.internalPointer():
                case NodeItem():
                    node = cast(NodeItem, index.internalPointer())
                    match index.column():
                        case 0:
                            return node.setName(value)
                        case 1:
                            return node.setContent(value)
                        case _:
                            return None
  
                case InletItem():
                    inlet = cast(InletItem, index.internalPointer())
                    match index.column():
                        case 0:
                            return inlet.setName(value)
                        case 1:
                            return inlet.setContent(value)
                        case _:
                            return None
                        
                case OutletItem():
                    outlet = cast(OutletItem, index.internalPointer())
                    match index.column():
                        case 0:
                            return outlet.setName(value)
                        case 1:
                            return outlet.setContent(value)
                        case _:
                            return None
                        
                case LinkItem():
                    link = cast(LinkItem, index.internalPointer())
                    match index.column():
                        case 0:
                            return link.setName(value)
                        case 1:
                            return link.setContent(value)
                        case _:
                            return None
                        
                case _:
                    return None
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return ["name", "content"][section]
        return None

    def flags(self, index):
        if not index.isValid():
            return Qt.NoItemFlags
        return Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable

    def parent(self, index):
        if not index.isValid():
            return QModelIndex()
        childItem = index.internalPointer()
        parentItem = childItem.parent()
        if parentItem == self.rootItem or parentItem is None:
            return QModelIndex()
        return self.createIndex(parentItem.row(), 0, parentItem)

    def index(self, row, column, parent=QModelIndex()):
        if not self.hasIndex(row, column, parent):
            return QModelIndex()
        parentItem = self.rootItem if not parent.isValid() else parent.internalPointer()
        childItem = parentItem.child(row)
        if childItem:
            return self.createIndex(row, column, childItem)
        return QModelIndex()
    

if __name__ == "__main__":
    app = QApplication(sys.argv)
    QApplication.setStyle("Fusion")
    class MainWidget(QWidget):
        def __init__(self, model, view:QTreeView):
            super().__init__()
            self.model = model
            self.view = view

            layout = QVBoxLayout(self)
            layout.addWidget(self.view)

            btn_layout = QHBoxLayout()
            self.insert_btn = QPushButton("Insert Row")
            self.remove_btn = QPushButton("Remove Selected")
            btn_layout.addWidget(self.insert_btn)
            btn_layout.addWidget(self.remove_btn)
            layout.addLayout(btn_layout)

            self.insert_btn.clicked.connect(self.insert_row)
            self.remove_btn.clicked.connect(self.remove_selected)

            self.view.viewport().installEventFilter(self)
            # self.installEventFilter(self.view.viewport())

        def eventFilter(self, watched, event:QEvent):
            if watched is self.view.viewport() and event.type() == QEvent.MouseButtonPress:
                index = self.view.indexAt(event.position().toPoint())
                if not index.isValid():
                    self.view.selectionModel().clearSelection()
                    self.view.selectionModel().clearCurrentIndex()
                    return True

            return super().eventFilter(watched, event)

        def insert_row(self):
            index = self.view.currentIndex()
            parent = index if index.isValid() else QModelIndex()
            self.model.insertRows(0, 1, parent)

        def remove_selected(self):
            selected_indexes = self.view.selectionModel().selectedIndexes()
            rows_to_remove = set()
            for index in selected_indexes:
                if index.isValid():
                    rows_to_remove.add((index.parent(), index.row()))
            # Remove from bottom to top to avoid shifting indices
            for parent, row in sorted(rows_to_remove, key=lambda x: -x[1]):
                self.model.removeRows(row, 1, parent)
            index = self.view.currentIndex()

    headers = ["Name"]
    data = [
        {
            "name": "Root1",
            "content": "Root1 content",
            "children": [
                {
                    "name": "Child1",
                    "content": "Child1 content",
                    "children": [
                        {"name": "Grandchild1", "content": "Grandchild1 content", "children": []},
                        {"name": "Grandchild2", "content": "Grandchild2 content", "children": []}
                    ]
                },
                {
                    "name": "Child2",
                    "content": "Child2 content",
                    "children": []
                }
            ]
        },
        {
            "name": "Root2",
            "content": "Root2 content",
            "children": [
                {
                    "name": "Child3",
                    "content": "Child3 content",
                    "children": []
                }
            ]
        }
    ]    # Data is already in the correct dictionary format, no conversion needed

    model = GraphModel(data)
    view = QTreeView()
    view.setSelectionMode(QTreeView.ExtendedSelection)
    view.setModel(model)
    view.setWindowTitle("TreeModel Example")
    view.resize(400, 300)

    main_widget = MainWidget(model, view)
    main_widget.setWindowTitle("TreeModel Example")
    main_widget.resize(400, 350)
    main_widget.show()


    sys.exit(app.exec())