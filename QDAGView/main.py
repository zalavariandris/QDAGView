from qtpy.QtWidgets import *
from qtpy.QtCore import *
from qtpy.QtGui import *
from collections import defaultdict

from standardgraphmodel import StandardGraphModel, NodeItem, InletItem, OutletItem, BaseRowItem
from graphview import GraphView

from core import GraphDataRole, GraphItemType


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        # setup view
        self.setWindowTitle("Graph Model Example")

        # toolbar
        button_layout = QHBoxLayout()
        self.add_btn = QPushButton("Add Child")
        self.add_btn.clicked.connect(self.add_child)
        self.remove_btn = QPushButton("Remove Selected")
        self.remove_btn.clicked.connect(self.remove_selected_items)
        button_layout.addWidget(self.add_btn)
        button_layout.addWidget(self.remove_btn)

        ## treeview
        self._treeview = QTreeView()
        self._treeview.viewport().installEventFilter(self)
        self._treeview.setSelectionMode(QTreeView.SelectionMode.ExtendedSelection)
        self._treeview.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked | QAbstractItemView.EditTrigger.SelectedClicked)
        self._treeview.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._treeview.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._treeview.customContextMenuRequested.connect(self.showContextMenu)

        ## graphview
        self._graphview = GraphView()

        # layout widgets
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._treeview)
        splitter.addWidget(self._graphview)

        layout = QVBoxLayout(self)
        layout.addLayout(button_layout)
        layout.addWidget(splitter)
        self.setLayout(layout)

        # setup model and selection
        self._model:QStandardItemModel|None = None
        self._selection:QItemSelectionModel|None = None 
        self.setModel(QStandardItemModel())
        self.setSelectionModel(QItemSelectionModel(self.model()))
        
    def setModel(self, model: QAbstractItemModel):
        """Set the model for the treeview."""
        self._model = model
        self._treeview.setModel(model)
        self._graphview.setModel(model)
        
    def model(self) -> QStandardItemModel:
        """Get the current model."""
        assert self._model is not None, "Model must be set before accessing it"
        return self._model

    def setSelectionModel(self, selection: QItemSelectionModel):
        """Set the selection model for the treeview."""
        self._selection = selection
        self._treeview.setSelectionModel(self._selection)
        self._graphview.setSelectionModel(self._selection)

    def selection(self) -> QItemSelectionModel:
        """Get the current selection model."""
        assert self._selection is not None, "Selection model must be set before accessing it"
        return self._selection

    def sizeHint(self):
        return QSize(1000, 600)  # Set a default size hint for the main widget
        
    def eventFilter(self, obj, event):
        if obj is self._treeview.viewport() and event.type() == QEvent.Type.MouseButtonPress:
            # clear selection on left click if no index is under the cursor
            if  event.buttons() == Qt.MouseButton.LeftButton:
                index = self._treeview.indexAt(event.position().toPoint())
                if not index.isValid():
                    self._treeview.clearSelection()
                    self._treeview.setCurrentIndex(QModelIndex())
                    return True
                
        # For other events or if the index is valid, let the default processing happen
        return super().eventFilter(obj, event)
    
    def showContextMenu(self, pos):
        """Show context-aware menu based on the current selection."""
        menu = QMenu(self)
        # index = self.treeview.indexAt(pos)  # Ensure the context menu is shown at the correct position
        index = self.selection().currentIndex()
        item_type = self._graphview._delegate.itemType(index)

        match item_type:
            case GraphItemType.SUBGRAPH:
                menu.addAction("Add Node", lambda: self.add_node())
            case GraphItemType.NODE:
                menu.addAction("Add Inlet", lambda: self.add_inlet(index))
                menu.addAction("Add Outlet", lambda: self.add_outlet(index))
            case GraphItemType.INLET:
                ...
            case GraphItemType.OUTLET:
                ...
            case GraphItemType.LINK:
                ...
            case _:
                ...

        menu.addAction("Remove Selected Items", self.remove_selected_items)
        menu.exec(self._treeview.viewport().mapToGlobal(pos))
    
    def add_node(self):
        """Add a new node to the model."""
        node_item = QStandardItem("New Node")
        self._model.appendRow(node_item)

    def add_inlet(self, parent:QModelIndex):
        """Add an inlet to the specified node."""
        inlet_item = QStandardItem("in")
        parent_node_item = self._model.itemFromIndex(parent)
        parent_node_item.appendRow(inlet_item)

    def add_outlet(self, parent:QModelIndex):
        """Add an inlet to the specified node."""
        node_item = self._model.itemFromIndex(parent)
        outlet_item = QStandardItem("out")
        outlet_item.setData(GraphItemType.OUTLET, GraphDataRole.TypeRole)
        node_item.appendRow(outlet_item)
    
    def add_child(self):
        """Add a child item to the currently selected item."""
        assert self._model is not None, "Model must be set before adding child items"
            
        parent = self._treeview.currentIndex()
        row = self._model.rowCount(parent)

        if self._model.columnCount(parent) == 0:
            # Make sure the parent has at least one column for children, otherwise the treeview won't show them
            self._model.insertColumns(0, 1, parent)
            
        if self._model.insertRows(row, 1, parent):
            new_index = self._model.index(row, 0, parent)
            assert new_index.isValid(), "Created index is not valid"
            success = self._model.setData(new_index, f"{'Child Item' if parent.isValid() else 'Item'} {row + 1}", Qt.ItemDataRole.DisplayRole)
            assert success, "Failed to set data for the new child item"
            self._treeview.expand(parent)
        else:
            print("insertRows failed")

    def remove_selected_items(self):
        """Remove all selected items from the model."""
        selection = self.selection()
        indexes = selection.selectedRows()
        if not indexes:
            return

        # Remove from bottom to top to avoid shifting row indices
        for index in sorted(indexes, key=lambda x: (x.parent(), -x.row())):
            parent = index.parent()
            self._model.removeRow(index.row(), parent)

if __name__ == "__main__":
    import sys
    from qt_material import apply_stylesheet
    app = QApplication(sys.argv)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())