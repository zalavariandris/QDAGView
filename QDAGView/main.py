from typing import *
from PySide6.QtCore import *
from PySide6.QtGui import *
from PySide6.QtWidgets import *

from PySide6.QtGui import QStandardItemModel
from PySide6.QtWidgets import QHBoxLayout, QTreeView
from graphview import GraphView, GraphDataRole, RowType


class LinkTableDelegate(QStyledItemDelegate):
    def displayText(self, value: Any, locale: QLocale | QLocale.Language, /) -> str:
        print("display text for", value)
        match value:
            case QPersistentModelIndex():
                text = ""
                index = value
                path  = []
                while index.isValid():
                    path.append(index)
                    # text = f"{index.data(Qt.ItemDataRole.DisplayRole)}.{text}"
                    index = index.parent()



                return ".".join( map(lambda index: index.data(Qt.ItemDataRole.DisplayRole), reversed(path)) )
            case _:
                return super().displayText(value, locale)
        
class MainWindow(QMainWindow):
    def __init__(self, parent:QWidget|None=None):
        super().__init__(parent=parent)
        
        self.setWindowTitle("Python Visual Editor")

        ### Setup Menu Bar
        menubar = self.menuBar()
        edit_menu = menubar.addMenu("&Edit")

        # Add Node action
        add_node_action = QAction("Add Node", self)
        add_node_action.setShortcut(QKeySequence("Ctrl+N"))
        add_node_action.triggered.connect(lambda: self.addNode("new_node", ""))
        edit_menu.addAction(add_node_action)

        # Add submenu for selected node
        node_menu = edit_menu.addMenu("Selected Node")
        
        add_inlet_action = QAction("Add Inlet", self)
        add_inlet_action.setShortcut(QKeySequence("Ctrl+I"))
        add_inlet_action.triggered.connect(self.addInletToSelected)
        node_menu.addAction(add_inlet_action)

        add_outlet_action = QAction("Add Outlet", self)
        add_outlet_action.setShortcut(QKeySequence("Ctrl+O"))
        add_outlet_action.triggered.connect(self.addOutletToSelected)
        node_menu.addAction(add_outlet_action)

        # Delete action
        edit_menu.addSeparator()
        delete_action = QAction("Delete Selected", self)
        delete_action.setShortcut(QKeySequence.Delete)
        delete_action.triggered.connect(self.deleteSelected)
        edit_menu.addAction(delete_action)

        # Create central widget
        central_widget = QWidget()

        ### Setup base model
        self.nodes = QStandardItemModel()
        self.nodes.setHorizontalHeaderLabels(["name", "content"])

        # access roles in QML by name
        self.nodes.setItemRoleNames({
            Qt.ItemDataRole.DisplayRole: b'name',
            GraphDataRole.TypeRole: b'node_type',
            GraphDataRole.SourceRole: b'link_source'
        })

        # populate with initial nodes
        read_node = self.addNode(
            name="read_file",
            content="read_file('path/to/file')"
        )

        process_node = self.addNode(
            name="process_data",
            content="process_data(data)"
        )

        inlet = self.addInlet(read_node, "in")
        outlet = self.addOutlet(process_node, "out")

        link = self.addLink(
            outlet, inlet
        )

        ### Setup selection models
        self.selection = QItemSelectionModel(self.nodes)

        ### Setup table views
        self.node_tree = QTreeView()
        self.node_tree.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.node_tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.node_tree.setModel(self.nodes)
        self.node_tree.setSelectionModel(self.selection)
        self.node_tree.expandAll()

        ### Setup Graphview
        self.graphview = GraphView()
        self.graphview.setModel(self.nodes)
        self.graphview.setSelectionModel(self.selection)        ### Setup Layout
        layout = QHBoxLayout()
        layout.addWidget(self.node_tree)
        layout.addWidget(self.graphview)
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

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
    def addLink(self, source:QStandardItem, target:QStandardItem):
        # add link to inlet, store as the children of the inlet
        assert source.index().isValid(), "Source must be a valid index"
        assert source.data(GraphDataRole.TypeRole) == RowType.OUTLET, "Source must be an outlet"
        item = QStandardItem()
        item.setData(RowType.LINK, GraphDataRole.TypeRole)
        item.setData(f"{source.index().parent().data(Qt.ItemDataRole.DisplayRole)}.{source.data(Qt.ItemDataRole.DisplayRole)}", Qt.ItemDataRole.DisplayRole)
        item.setData(QPersistentModelIndex(source.index()), GraphDataRole.SourceRole)
        target.appendRow(item)
# 
    def sizeHint(self):
        return QSize(2048, 900) 

    ### Commands
    def create_new_node(self, scenepos:QPointF=QPointF()):
        assert self._model
        existing_names = list(self._model.nodes())

        func_name = make_unique_id(6)
        self._model.addNode(func_name, "None", kind='expression')

        ### position node widget
        node_graphics_item = self.graph_view.nodeItem(func_name)
        if node_graphics_item := self.graph_view.nodeItem(func_name):
            node_graphics_item.setPos(scenepos-node_graphics_item.boundingRect().center())

    def delete_selected(self):
        assert self._model
        # delete selected links
        link_indexes:list[QModelIndex] = self.link_selection_model.selectedIndexes()
        link_rows = set(index.row() for index in link_indexes)
        for link_row in sorted(link_rows, reverse=True):
            source, target, outlet, inlet = self.link_proxy_model.mapToSource(self.link_proxy_model.index(link_row, 0))
            self._model.unlinkNodes(source, target, outlet, inlet)

        # delete selected nodes
        node_indexes:list[QModelIndex] = self.node_selection_model.selectedRows(column=0)
        for node_index in sorted(node_indexes, key=lambda idx:idx.row(), reverse=True):
            node = self.node_proxy_model.mapToSource(node_index)
            self._model.removeNode(node)

    def connect_nodes(self, source:str, target:str, inlet:str):
        assert self._model
        self._model.linkNodes(source, target, "out", inlet)

    def eventFilter(self, watched, event):
        if watched == self.graph_view:
            ### Create node on double click
            if event.type() == QEvent.Type.MouseButtonDblClick:
                event = cast(QMouseEvent, event)
                self.create_new_node(self.graph_view.mapToScene(event.position().toPoint()))
                return True

        return super().eventFilter(watched, event)

    def addInletToSelected(self):
        """Add an inlet to the currently selected node"""
        indexes = self.selection.selectedIndexes()
        if not indexes:
            return
            
        # Get the first selected node
        index = indexes[0]
        # Get to the root item (node)
        while index.parent().isValid():
            index = index.parent()
            
        item = self.nodes.itemFromIndex(index)
        if item.data(GraphDataRole.TypeRole) == GraphView.RowKind.NODE:
            self.addInlet(item, f"in{item.rowCount()}")

    def addOutletToSelected(self):
        """Add an outlet to the currently selected node"""
        indexes = self.selection.selectedIndexes()
        if not indexes:
            return
            
        # Get the first selected node
        index = indexes[0]
        # Get to the root item (node)
        while index.parent().isValid():
            index = index.parent()
            
        item = self.nodes.itemFromIndex(index)
        if item.data(GraphDataRole.TypeRole) == GraphView.RowKind.NODE:
            self.addOutlet(item, f"out{item.rowCount()}")

    def deleteSelected(self):
        """Delete selected items from the model"""
        if not self.selection.hasSelection():
            return

        indexes = self.selection.selectedIndexes()
        # Group by parent to handle children properly
        to_delete = {}
        for index in indexes:
            if index.column() == 0:  # Only process first column to avoid duplicates
                parent = index.parent()
                if parent not in to_delete:
                    to_delete[parent] = []
                to_delete[parent].append(index.row())

        # Delete from bottom up to maintain valid indices
        for parent, rows in to_delete.items():
            for row in sorted(rows, reverse=True):
                if parent.isValid():
                    self.nodes.itemFromIndex(parent).removeRow(row)
                else:
                    self.nodes.removeRow(row)

if __name__ == "__main__":
    import sys
    from pathlib import Path
    import pathlib
    parent_folder = pathlib.Path(__file__).parent.resolve()
    print("Python Visual Editor starting...\n  working directory:", Path.cwd())

    app = QApplication([])

    window = MainWindow()
    window.setGeometry(QRect(QPoint(), app.primaryScreen().size()).adjusted(40,80,-30,-300))
    window.show()
    app.exec()
    # window.openFile(Path.cwd()/"./tests/dissertation_builder.yaml")

