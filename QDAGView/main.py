from graphmodel import GraphModel, NodeItem, InletItem, OutletItem, BaseRowItem
from graphview import GraphView, GraphAdapter
from core import GraphDataRole, GraphItemType
from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *


if __name__ == "__main__":
    import sys

    from collections import defaultdict

    app = QApplication(sys.argv)
    class MainWidget(QWidget):
        def __init__(self):
            super().__init__()
            # Setup model
            self.model = GraphModel()
            self.selection = QItemSelectionModel(self.model)

            ## populate model with some initial data
            node1 = NodeItem("Node1", "content")
            node1.appendInlet(InletItem("in"))
            node1.appendOutlet(OutletItem("out"))
            self.model.addNode(node1)

            node2 = NodeItem("Node2")
            node2.appendInlet(InletItem("in"))
            node2.appendOutlet(OutletItem("out"))
            self.model.addNode(node2)

            node3 = NodeItem("Node3")
            node3.appendInlet(InletItem("in"))
            node3.appendOutlet(OutletItem("out"))
            self.model.addNode(node3)

            # self.model.addLink(LinkItem)

            # setup view
            self.setWindowTitle("Graph Model Example")

            # context aware toolbar
            button_layout = QHBoxLayout()
            self.add_btn = QPushButton("Add Item")
            self.add_btn.clicked.connect(self.add_item)
            self.remove_btn = QPushButton("Remove Selected")
            self.remove_btn.clicked.connect(self.remove_selected_items)
            button_layout.addWidget(self.add_btn)
            button_layout.addWidget(self.remove_btn)

            self.selection.currentChanged.connect(self.updateContextAwareToolbar)

            ## treeview
            self.treeview = QTreeView()
            self.treeview.viewport().installEventFilter(self)
            self.treeview.setSelectionMode(QTreeView.SelectionMode.ExtendedSelection)

            self.treeview.setModel(self.model)
            self.treeview.setSelectionModel(self.selection)
            
            self.treeview.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            self.treeview.customContextMenuRequested.connect(self.showContextAwareMenu)
            self.treeview.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked | QAbstractItemView.EditTrigger.SelectedClicked)
            self.treeview.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
            
            self.treeview.expandAll()

            ## graphview
            self.graphview = GraphView()
            self.adapter = GraphAdapter(self)
            self.adapter.setSourceModel(self.model)
            self.graphview.setAdapter(self.adapter)
            self.graphview.setSelectionModel(self.selection)
            self.graphview.setMinimumSize(400, 300)

            # layout widgets
            splitter = QSplitter(Qt.Orientation.Horizontal, self)
            layout = QVBoxLayout(self)
            layout.addLayout(button_layout)
            layout.addWidget(splitter)
            splitter.addWidget(self.treeview)
            splitter.addWidget(self.graphview)
            splitter.setSizes([100, 600])
            splitter.setStretchFactor(0, 0)
            self.setLayout(layout)

            self.resize(1000, 600)

        def sizeHint(self):
            return QSize(1000, 600)  # Set a default size hint for the main widget
            

        def showContextAwareMenu(self, pos):
            """Show context-aware menu based on the current selection."""
            menu = QMenu(self)
            # index = self.treeview.indexAt(pos)  # Ensure the context menu is shown at the correct position
            index = self.selection.currentIndex()
            item_type = self.model.data(index, GraphDataRole.TypeRole)
            match index.isValid(), item_type:
                case (False, _):
                    menu.addAction("Add Node", lambda: self.model.addNode(NodeItem("New Node"), QModelIndex()))
                case (True, GraphItemType.NODE):
                    menu.addAction("Add Inlet", lambda: self.model.addInlet(InletItem("in"), index))
                    menu.addAction("Add Outlet", lambda: self.model.addOutlet(OutletItem("out"), index))

                case (True, GraphItemType.INLET):
                    ...
                case (True, GraphItemType.OUTLET):
                    ...
                case (True, GraphItemType.LINK):
                    ...
                case _:
                    ...

            menu.addAction("Remove Selected Items", self.remove_selected_items)
            menu.exec(self.treeview.viewport().mapToGlobal(pos))

        def eventFilter(self, obj, event):
            if obj is self.treeview.viewport() and event.type() == QEvent.Type.MouseButtonPress:
                if  event.buttons() == Qt.MouseButton.LeftButton:
                    index = self.treeview.indexAt(event.position().toPoint())
                    if not index.isValid():
                        self.treeview.clearSelection()
                        self.treeview.setCurrentIndex(QModelIndex())
                        return True  # Allow the click to pass through
            # For other events or if the index is valid, let the default processing happen
            return super().eventFilter(obj, event)

        def add_item(self, current:QModelIndex|None = None):
            """Add a new item to the model at the current selection."""
            if not current:
                current = self.treeview.currentIndex()
            parent = current if current.isValid() else QModelIndex()
            self.model.insertRows(self.model.rowCount(parent), 1, parent)

        def remove_selected_items(self):
            indexes = self.treeview.selectionModel().selectedRows()
            # Group indexes by parent to avoid shifting issues
            parent_map = defaultdict(list)
            for index in indexes:
                parent_map[index.parent()].append(index.row())
            for parent, rows in parent_map.items():
                for row in sorted(rows, reverse=True):
                    self.model.removeRows(row, 1, parent)

        def updateContextAwareToolbar(self):
            """Update the context-aware toolbar based on the current selection."""
            current_index = self.treeview.currentIndex()
            item_type:GraphItemType = self.model.data(current_index, GraphDataRole.TypeRole)
            match current_index.isValid(), item_type:
                case (False, _):
                    self.add_btn.setText("Add Node")
                    self.add_btn.setDisabled(False)
                    self.remove_btn.setText("Remove Item")
                    self.remove_btn.setEnabled(False)
                case (True, GraphItemType.NODE):
                    self.add_btn.setText("Add Inlet")
                    self.add_btn.setEnabled(True)
                    self.remove_btn.setText("Remove Node")
                    self.remove_btn.setEnabled(True)
                case (True, GraphItemType.INLET):
                    self.add_btn.setText("Add Item")
                    self.add_btn.setEnabled(False)
                    self.remove_btn.setText("Remove Inlet")
                    self.remove_btn.setEnabled(True)
                case (True, GraphItemType.OUTLET):
                    self.add_btn.setText("Add Item")
                    self.add_btn.setEnabled(False)
                    self.remove_btn.setText("Remove Outlet")
                    self.remove_btn.setEnabled(True)
                case (True, GraphItemType.LINK):
                    self.add_btn.setText("Add Item")
                    self.add_btn.setEnabled(False)
                    self.remove_btn.setText("Remove Link")
                    self.remove_btn.setEnabled(True)
                case _:
                    self.add_btn.setText("Add Item")
                    self.add_btn.setEnabled(False)
                    self.remove_btn.setText("Remove Item")
                    self.remove_btn.setEnabled(False)



    main_widget = MainWidget()
    main_widget.show()

    sys.exit(app.exec())
