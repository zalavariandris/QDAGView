from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *
from collections import defaultdict


class TreeModelEditor(QWidget):
    def __init__(self):
        super().__init__()
        # setup view
        self.setWindowTitle("Graph Model Example")

        # toolbar
        button_layout = QHBoxLayout()
        self.add_btn = QPushButton("Add Item")
        self.add_btn.clicked.connect(self.add_item)
        self.add_child_btn = QPushButton("Add Child")
        self.add_child_btn.clicked.connect(self.add_child_item)
        self.remove_btn = QPushButton("Remove Selected")
        self.remove_btn.clicked.connect(self.remove_selected_items)
        button_layout.addWidget(self.add_btn)
        button_layout.addWidget(self.add_child_btn)
        button_layout.addWidget(self.remove_btn)

        ## treeview
        self.treeview = QTreeView()
        self.treeview.viewport().installEventFilter(self)
        self.treeview.setSelectionMode(QTreeView.SelectionMode.ExtendedSelection)
        self.treeview.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked | QAbstractItemView.EditTrigger.SelectedClicked)
        self.treeview.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)

        # layout widgets
        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        layout = QVBoxLayout(self)
        layout.addLayout(button_layout)
        layout.addWidget(splitter)
        splitter.addWidget(self.treeview)
        self.setLayout(layout)

    def setModel(self, model: QAbstractItemModel):
        """Set the model for the treeview."""
        self.model = model
        self.treeview.setModel(self.model)

    def setSelectionModel(self, selection: QItemSelectionModel):
        """Set the selection model for the treeview."""
        self.selection = selection
        self.treeview.setSelectionModel(self.selection)

    def sizeHint(self):
        return QSize(1000, 600)  # Set a default size hint for the main widget
        
    def eventFilter(self, obj, event):
        if obj is self.treeview.viewport() and event.type() == QEvent.Type.MouseButtonPress:
            # clear selection on left click if no index is under the cursor
            if  event.buttons() == Qt.MouseButton.LeftButton:
                index = self.treeview.indexAt(event.position().toPoint())
                if not index.isValid():
                    self.treeview.clearSelection()
                    self.treeview.setCurrentIndex(QModelIndex())
                    return True
                
        # For other events or if the index is valid, let the default processing happen
        return super().eventFilter(obj, event)

    def add_item(self, current: QModelIndex | None = None):
        """Add a new item to the root level of the model."""
        if not hasattr(self, 'model') or self.model is None:
            return
            
        # Always add to root level
        parent = QModelIndex()  # Root parent
        row = self.model.rowCount(parent)
        
        if self.model.insertRows(row, 1, parent):
            index = self.model.index(row, 0, parent)
            self.model.setData(index, f"New Item {row + 1}", Qt.ItemDataRole.DisplayRole)
            # Select the newly created item
            self.treeview.setCurrentIndex(index)
        
    def add_child_item(self):
        """Add a child item to the currently selected item."""
        if not hasattr(self, 'model') or self.model is None:
            return
            
        current = self.treeview.currentIndex()
        if not current.isValid():
            # If nothing is selected, add to root
            self.add_item()
            return
        
        # Add child to the selected item using generic methods
        parent = current
        row = self.model.rowCount(parent)
        
        if self.model.insertRows(row, 1, parent):
            index = self.model.index(row, 0, parent)
            self.model.setData(index, f"Child Item {row + 1}", Qt.ItemDataRole.DisplayRole)
            # Expand the parent to show the new child
            self.treeview.expand(parent)
            # Select the newly created child
            self.treeview.setCurrentIndex(index)

    def remove_selected_items(self):
        """Remove all selected items from the model."""
        if not hasattr(self, 'model') or self.model is None:
            return
            
        indexes = self.treeview.selectionModel().selectedRows()
        if not indexes:
            return
            
        # Group indexes by parent to avoid shifting issues
        parent_map = defaultdict(list)
        for index in indexes:
            parent_map[index.parent()].append(index.row())
            
        # Remove rows in reverse order to maintain correct row numbers
        for parent, rows in parent_map.items():
            for row in sorted(rows, reverse=True):
                self.model.removeRows(row, 1, parent)


if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)

    main_widget = TreeModelEditor()
    model = QStandardItemModel()
    
    # Add some initial data to test
    model.setHorizontalHeaderLabels(['Name'])
    
    main_widget.setModel(model)
    main_widget.show()

    sys.exit(app.exec())