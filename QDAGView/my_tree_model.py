from PySide6.QtCore import Qt, QModelIndex, QAbstractItemModel, QObject, Signal


class TreeItem(QObject):
    data_changed = Signal(int)            # column
    child_inserted = Signal(int, int)     # position, count
    child_removed = Signal(int, int)      # position, count

    def __init__(self, data, parent=None):
        super().__init__()
        self.item_data = data
        self.parent_item = parent
        self.child_items = []

    def set_data(self, column, value):
        if 0 <= column < len(self.item_data):
            if self.item_data[column] != value:
                self.item_data[column] = value
                self.data_changed.emit(column)
                return True
        return False

    def append_child(self, child):
        self.insert_child(len(self.child_items), child)

    def insert_child(self, position, child):
        child.parent_item = self
        self.child_items.insert(position, child)
        self.child_inserted.emit(position, 1)

    def remove_child(self, position):
        if 0 <= position < len(self.child_items):
            self.child_items.pop(position)
            self.child_removed.emit(position, 1)

    def child(self, row):
        return self.child_items[row] if 0 <= row < len(self.child_items) else None

    def child_count(self):
        return len(self.child_items)

    def column_count(self):
        return len(self.item_data)

    def data(self, column):
        return self.item_data[column] if 0 <= column < len(self.item_data) else None

    def parent(self):
        return self.parent_item

    def row(self):
        if self.parent_item:
            return self.parent_item.child_items.index(self)
        return 0


class TreeModel(QAbstractItemModel):
    def __init__(self, headers, parent=None):
        super().__init__(parent)
        self.root_item = TreeItem(headers)
        self._connect_item_signals(self.root_item)

    def _connect_item_signals(self, item):
        item.data_changed.connect(lambda col, i=item: self._emit_data_changed(i, col))
        item.child_inserted.connect(lambda pos, count, i=item: self._emit_rows_inserted(i, pos, count))
        item.child_removed.connect(lambda pos, count, i=item: self._emit_rows_removed(i, pos, count))
        for child in item.child_items:
            self._connect_item_signals(child)

    def _emit_data_changed(self, item, column):
        index = self.createIndex(item.row(), column, item)
        self.dataChanged.emit(index, index, [Qt.EditRole])

    def _emit_rows_inserted(self, parent_item, pos, count):
        parent_index = self.createIndex(parent_item.row(), 0, parent_item) if parent_item != self.root_item else QModelIndex()
        self.beginInsertRows(parent_index, pos, pos + count - 1)
        self.endInsertRows()
        for child in parent_item.child_items[pos:pos + count]:
            self._connect_item_signals(child)

    def _emit_rows_removed(self, parent_item, pos, count):
        parent_index = self.createIndex(parent_item.row(), 0, parent_item) if parent_item != self.root_item else QModelIndex()
        self.beginRemoveRows(parent_index, pos, pos + count - 1)
        self.endRemoveRows()

    def columnCount(self, parent=QModelIndex()):
        return self.root_item.column_count() if not parent.isValid() else parent.internalPointer().column_count()

    def rowCount(self, parent=QModelIndex()):
        parent_item = self.root_item if not parent.isValid() else parent.internalPointer()
        return parent_item.child_count()

    def index(self, row, column, parent=QModelIndex()):
        if not self.hasIndex(row, column, parent):
            return QModelIndex()

        parent_item = self.root_item if not parent.isValid() else parent.internalPointer()
        child_item = parent_item.child(row)
        if child_item:
            return self.createIndex(row, column, child_item)
        return QModelIndex()

    def parent(self, index):
        if not index.isValid():
            return QModelIndex()

        child_item = index.internalPointer()
        parent_item = child_item.parent()
        if parent_item == self.root_item or parent_item is None:
            return QModelIndex()

        return self.createIndex(parent_item.row(), 0, parent_item)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None

        item = index.internalPointer()
        if role in (Qt.DisplayRole, Qt.EditRole):
            return item.data(index.column())
        return None

    def setData(self, index, value, role=Qt.EditRole):
        if index.isValid() and role == Qt.EditRole:
            item = index.internalPointer()
            return item.set_data(index.column(), value)
        return False

    def flags(self, index):
        if not index.isValid():
            return Qt.ItemIsEnabled
        return Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self.root_item.data(section)
        return None

    def insertRows(self, position, rows, parent=QModelIndex()):
        parent_item = self.root_item if not parent.isValid() else parent.internalPointer()
        for _ in range(rows):
            child = TreeItem(["New Item"])
            parent_item.insert_child(position, child)
        return True

    def removeRows(self, position, rows, parent=QModelIndex()):
        parent_item = self.root_item if not parent.isValid() else parent.internalPointer()
        for _ in range(rows):
            parent_item.remove_child(position)
        return True


if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication, QTreeView

    app = QApplication(sys.argv)

    view = QTreeView()
    model = TreeModel(["Title"])
    view.setModel(model)

    # Add root children
    root = model.root_item
    child1 = TreeItem(["Item 1"])
    child2 = TreeItem(["Item 2"])
    root.append_child(child1)
    root.append_child(child2)

    # Add nested children
    child1.append_child(TreeItem(["Child 1"]))
    child1.append_child(TreeItem(["Child 2"]))

    # Direct item edit — model will emit signals!
    child1.set_data(0, "Updated Item 1")

    view.expandAll()
    view.show()
    sys.exit(app.exec())
