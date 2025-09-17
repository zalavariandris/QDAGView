from __future__ import annotations

from typing import *
from qtpy.QtWidgets import *
from qtpy.QtCore import *
from qtpy.QtGui import *

from collections import defaultdict

from ..core import GraphDataRole, GraphItemType


from .flowgraph2 import FlowGraph, ExpressionOperator, Link
import logging
logger = logging.getLogger(__name__)

from ..utils import make_unique_name

InternalPointer = Tuple[str, object|None, object]  # (kind, parent_data, data)

class FlowGraphModel(QAbstractItemModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._root = FlowGraph() 

    def invisibleRootItem(self) -> FlowGraph:
        """Return the root item of the model."""
        return self._root

    def index(self, row, column, parent=QModelIndex())-> QModelIndex:
        print("get index", row, column, parent, parent.isValid())
        parent = QModelIndex(parent)  # Ensure parent is a valid QModelIndex
        if parent.isValid():
            parent_kind, parent_parent_data, parent_data = parent.internalPointer()
        else:
            parent_kind, parent_parent_data, parent_data = 'graph', None, self.invisibleRootItem()

        # assert column == 0, "This model only supports one column."
        match parent_kind:
            case 'graph':
                graph = parent_data
                operators = graph.operators()
                if 0 <= row < len(operators):
                    node = operators[row]
                    ptr:InternalPointer = 'node', self._root, node
                    return self.createIndex(row, column, ptr)
                else:
                    return QModelIndex()
                
            case 'node':
                operator = parent_data
                inlets = operator.inlets()
                outlets = operator.outlets()
                n_inlets = len(inlets)
                n_outlets = len(outlets)
                if 0 <= row < n_inlets + n_outlets:
                    # Determine if the row corresponds to an inlet or outlet
                    if row < n_inlets:
                        inlet = inlets[row]
                        ptr:InternalPointer = 'inlet', operator, inlet
                        return self.createIndex(row, column, ptr)
                    else:
                        outlet = outlets[row - n_inlets]
                        ptr:InternalPointer = 'outlet', operator, outlet
                        return self.createIndex(row, column, ptr)
                else:
                    return QModelIndex()
                
            case 'inlet':
                inlet = parent_data
                graph = self.invisibleRootItem()
                links:List[Link] = graph.inLinks(inlet)

                if 0 <= row < len(links):
                    link = links[row]
                    ptr:InternalPointer = 'link', inlet, link
                    return self.createIndex(row, column, ptr)
                else:
                    return QModelIndex()
                
            case 'outlet':
                return QModelIndex()  # Outlets have no children

            case 'link':
                return QModelIndex()  # Links have no children
                
            case _:
                raise Exception(f"Invalid parent item type: {type(parent_data)}")

    def parent(self, index: QModelIndex) -> QModelIndex:
        print("get parent", index, index.isValid())
        index = QModelIndex(index)  # Ensure index is a valid QModelIndex
        if not index.isValid():
            return QModelIndex()
        
        kind, parent_data, data = index.internalPointer()
        match kind:
            case 'node':
                # return the parent graph index
                return QModelIndex()

            case 'inlet':
                # return the inlet's parent operator index
                graph_data = cast(FlowGraph, self.invisibleRootItem())
                row = graph_data.operators().index(parent_data)
                ptr:InternalPointer = 'node', graph_data, parent_data
                return self.createIndex(row, 0, ptr)

            case 'outlet':
                # return the outlet's parent operator index
                graph_data = cast(FlowGraph, self.invisibleRootItem())
                row = graph_data.operators().index(parent_data)
                ptr:InternalPointer = 'node', graph_data, parent_data
                return self.createIndex(row, 0, ptr)

            case 'link':
                # return the links's parent inlet index
                link = data
                parent_operator = link.target.operator if link.target else None
                if parent_operator is not None and link.target is not None:
                    inlets = list(parent_operator.inlets())
                    assert link.target in inlets, "Link's target inlet must be in its parent operator's inlets."
                    row = inlets.index(link.target)
                    ptr:InternalPointer = 'inlet', parent_operator, link.target
                    return self.createIndex(row, 0, ptr)
                return QModelIndex()
            case _:
                return QModelIndex()
            
    def rowCount(self, parent=QModelIndex())->int:
        print("get row count", parent, parent.isValid())
        parent = QModelIndex(parent)  # Ensure parent is a valid QModelIndex
        if parent.isValid():
            kind, parent_parent_data, parent_data = parent.internalPointer()
        else:
            kind, parent_parent_data, parent_data = 'graph', None, self.invisibleRootItem()
        
        match kind:
            case 'graph':
                graph = cast(FlowGraph, parent_data)
                return len(graph.operators())
            
            case 'node':
                operator = cast(ExpressionOperator, parent_data)
                n_inlets = len(operator.inlets())
                n_outlets = len(operator.outlets())
                return n_inlets + n_outlets

            case 'inlet':
                inlet = cast(str, parent_data)
                graph:FlowGraph = self.invisibleRootItem()
                in_links = graph.inLinks(inlet)
                return len(in_links)
                
            case 'outlet':
                return 0
            
            case 'link':
                return 0
            
            case _:
                raise Exception(f"Invalid parent item type, got: {kind}")

    def hasChildren(self, index: QModelIndex) -> bool:
        if index.isValid():
            kind, parent_parent_data, parent_data = index.internalPointer()
        else:
            kind, parent_parent_data, parent_data = 'graph', None, self.invisibleRootItem()

        match parent_data:
            case FlowGraph():
                return len(parent_data.operators())>0
            
            case ExpressionOperator():
                operator = parent_data
                n_inlets = len(operator.inlets())
                n_outlets = len(operator.outlets())
                return n_inlets + n_outlets > 0
            
            case Inlet():
                inlet = parent_data
                graph: FlowGraph = self.invisibleRootItem()
                in_links = graph.inLinks(inlet)
                return len(in_links) > 0
            
            case Outlet():
                return False
            
            case _:
                return False

    def columnCount(self, parent=QModelIndex())->int:
        if parent.isValid():
            kind, parent_parent_data, parent_data = parent.internalPointer()
        else:
            kind, parent_parent_data, parent_data = 'graph', None, self.invisibleRootItem()
        
        match parent_data:
            case FlowGraph():
                return 2
            
            case ExpressionOperator():
                return 1

            case Inlet():
                return 1
                
            case Outlet():
                return 1
            
            case Link():
                return 1
            
            case _:
                raise Exception(f"Invalid parent item type: {type(parent_data)}")

    def data(self, index:QModelIndex, role=Qt.ItemDataRole.DisplayRole)->object|None:

        if not index.isValid():
            return None
        
        kind, parent_data, data = index.internalPointer()
        match kind:
            case 'node':
                operator = cast(ExpressionOperator, data)

                match index.column(), role:
                    case 0, Qt.ItemDataRole.DisplayRole:
                        return f"{operator.name()}"
                    
                    case 0, Qt.ItemDataRole.EditRole:
                        return operator.name()

                    case 0, GraphDataRole.TypeRole:
                        return GraphItemType.NODE
                    
                    case 1, Qt.ItemDataRole.DisplayRole:
                        return f"{operator.expression()}"
                    
                    case 1, Qt.ItemDataRole.EditRole:
                        return operator.expression()
                    case _:
                        return None
                            
            case 'inlet':
                inlet = cast(str, data)

                match index.column(), role:
                    case 0, GraphDataRole.TypeRole:
                        return GraphItemType.INLET
                    
                    case 0, Qt.ItemDataRole.DisplayRole:
                        return f"{inlet}"
                    case 0, Qt.ItemDataRole.EditRole:
                        return inlet
                    case _:
                        return None
            
            case 'outlet':
                outlet = cast(str, data)

                match index.column(), role:
                    case 0, GraphDataRole.TypeRole:
                        return GraphItemType.OUTLET
                    
                    case 0, Qt.ItemDataRole.DisplayRole:
                        return f"{outlet}"
                    
                    case 0, Qt.ItemDataRole.EditRole:
                        return outlet
                    
                    case _:
                        return None

            
            case 'link':
                link = cast(Link, data)

                match index.column(), role:
                    case 0, GraphDataRole.TypeRole:
                        return GraphItemType.LINK
                    
                    case 0, GraphDataRole.SourceRole:
                        if not link.source:
                            return None
                        
                        source_node, source_outlet = link.source
                        graph = self.invisibleRootItem()
                        row = graph.operators().index(source_node)
                        ptr = 'node', graph, source_node
                        self.createIndex(row, 0, ptr)
                    
                    case 0, Qt.ItemDataRole.DisplayRole:
                        return f"{link.source} -> {link.target}"
                    
                    case _:
                        return None

                return None

            case _:
                return None
    
    def setData(self, index:QModelIndex, value, role:int = Qt.ItemDataRole.EditRole)->bool:
        if not index.isValid():
            logger.warning("Invalid index")
            return False

        kind, parent_data, data = index.sibling(index.row(), 0).internalPointer()
        match data:
            case ExpressionOperator():
                operator = data
                match index.column():
                    case 0: # name
                        name_index = index.sibling(index.row(), 0)
                        match role:
                            case Qt.ItemDataRole.EditRole | Qt.ItemDataRole.DisplayRole:
                                if not isinstance(value, str):
                                    return False
                                operator.setName(value)
                                self.dataChanged.emit(name_index, name_index, [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole])
                                return True
                            case _:
                                return False
                    case 1: # expression
                        operator_index = index.sibling(index.row(), 0)
                        expression_index = index.sibling(index.row(), 1)
                        match role:
                            case Qt.ItemDataRole.EditRole | Qt.ItemDataRole.DisplayRole:
                                if not isinstance(value, str):
                                    logger.warning("expression value must be a string")
                                    return False
                                                                
                                current_inlet_count = len(operator.inlets())
                                previous_inlets = list(operator.inlets())
                                
                                # DON'T change the data yet - first calculate what will change
                                temp_operator = ExpressionOperator(value)  # Create temporary to see what inlets would be
                                next_inlets = list(temp_operator.inlets())
                                new_inlet_count = len(next_inlets)

                                if new_inlet_count < current_inlet_count:
                                    # Signal removals if there are less inlets
                                    self.beginRemoveRows(operator_index, new_inlet_count, current_inlet_count-1)
                                    operator.setExpression(value)  # NOW change the data
                                    self.endRemoveRows()

                                elif new_inlet_count > current_inlet_count:
                                    # Signal insertions if there are more inlets
                                    self.beginInsertRows(operator_index, current_inlet_count, new_inlet_count-1)
                                    operator.setExpression(value)  # Change the data
                                    self.endInsertRows()

                                else:
                                    # No structure change, just update the expression
                                    operator.setExpression(value)

                                # emit dataChanged signal for the operator expression
                                self.dataChanged.emit(expression_index, expression_index, [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole])
                                
                                # emit dataChanged for all inlets because their names are derived from the operator's expression,
                                # and updating the expression may change the names of all inlets
                                if new_inlet_count > 0:
                                    self.dataChanged.emit(
                                        self.index(0, 0, operator_index),
                                        self.index(new_inlet_count-1, self.columnCount(operator_index), operator_index),
                                        [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole]
                                    )
                                return True
                            case _:
                                return False
                    
                
            case Inlet():
                inlet = data
                match role:
                    case Qt.ItemDataRole.EditRole | Qt.ItemDataRole.DisplayRole:
                        if not isinstance(value, str):
                            return False # Ensure value is a string
                        inlet.name = value
                        self.dataChanged.emit(index, index, [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole])
                        return True
                    case _:
                        return False

            case Outlet():
                outlet = data
                match role:
                    case Qt.ItemDataRole.EditRole | Qt.ItemDataRole.DisplayRole:
                        if not isinstance(value, str):
                            return False # Ensure value is a string
                        outlet.name = value
                        self.dataChanged.emit(index, index, [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole])
                        return True
                    case _:
                        return False

            case Link():
                link = data
                match role:
                    case GraphDataRole.SourceRole:
                        assert isinstance(value, (QModelIndex, QPersistentModelIndex)), "Source must be a valid QModelIndex."
                        assert value.isValid(), "Source index must be valid."
                        source_item = self._itemFromIndex(value)
                        graph = self.invisibleRootItem()
                        graph.setLinkSource(link, source_item)  # Relink the existing link to the new source
                        self.dataChanged.emit(index, index, [GraphDataRole.SourceRole])
                        return True

        return False
            
    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        
        kind, parent_data, data = index.internalPointer()
        match data:
            case ExpressionOperator():
                return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEditable
            
            case Inlet() | Outlet():
                return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
            
            case Link():
                return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
            
            case _:
                return Qt.ItemFlag.NoItemFlags
            
    def insertRows(self, row, count, parent:QModelIndex)->bool:
        parent = QModelIndex(parent)  # Ensure parent is a valid QModelIndex

        if parent.isValid():
            kind, parent_parent_data, parent_data = parent.internalPointer()
        else:
            kind, parent_parent_data, parent_data = 'graph', None, self.invisibleRootItem()

        assert count > 0, "Count must be greater than 0 for insertRows."
        match parent_data:
            case FlowGraph():
                graph = parent_data
                success = True
                self.beginInsertRows(parent, row, row + count - 1)
                for i in range(count):
                    unique_name = make_unique_name("n1", [op.name() for op in graph.operators()])
                    op = ExpressionOperator("a+b", unique_name)
                    print(f"Inserting operator {op} at position {row + i}")
                    if not graph.insertOperator(row + i, op):
                        raise Exception("Failed to add operator to the graph.")
                        success = False
                self.endInsertRows()
                return success

            case ExpressionOperator():
                raise Exception("With this model inlets cannot be inserted directly under an operator. they are determined by the operator's implementation.")
                return False # Cannot insert rows directly under an operator. It is dependent on the Operator expression
            
            case Inlet():
                # Note: insertRows must support dangling link, 
                # because it's called by the default graphview delegate to create new links.
                inlet = parent_data
                target = inlet.operator
                graph:FlowGraph = self.invisibleRootItem()
                success = True
                self.beginInsertRows(parent, row, row + count - 1)
                for i in range(count):
                    if not graph.insertLink(i, source=None, target=inlet):
                        success = False
                self.endInsertRows()
                return success
            case _:
                raise Exception(f"Invalid parent item type: {type(parent_data)}")
            
    def removeRows(self, row:int, count:int, parent:QModelIndex)-> bool:
        if parent.isValid():
            kind, parent_parent_data, parent_data = parent.internalPointer()
        else:
            kind, parent_parent_data, parent_data = 'graph', None, self.invisibleRootItem()

        match parent_data:
            case FlowGraph():
                # remove nodes
                graph = parent_data

                # first remove outgoing links
                links_to_remove:List[QModelIndex] = []
                for node_row in range(row, row + count):
                    node_idx = self.index(node_row, 0, parent)
                    _, _, node = cast(ExpressionOperator, node_idx.internalPointer())
                    
                    for outlet in node.outlets():
                        for link in graph.outLinks(outlet):
                            link_index = self._indexFromItem(link)
                            if link_index.isValid():
                                links_to_remove.append(link_index)

                # group links by their target inlet
                links_by_inlet: DefaultDict[QModelIndex, List[QModelIndex]] = defaultdict(list)
                for link in links_to_remove:
                    inlet = link.parent()
                    links_by_inlet[inlet].append(link)

                for inlet in sorted(links_by_inlet.keys(), key=lambda x: (x.row()), reverse=True):
                    # Remove links in reverse order to avoid shifting issues
                    links = links_by_inlet[inlet]
                    for link in sorted(links, key=lambda x: x.row(), reverse=True):
                        self.removeRows(link.row(), 1, inlet)

                # remove the nodes
                self.beginRemoveRows(parent, row, row + count - 1)
                for i in reversed(list(range(row, row + count))):
                    logger.info(f"Removing operator at index {i}")
                    operators = graph.operators()
                    if i < len(operators):
                        operator = operators[i]
                        if not graph.removeOperator(operator):
                            self.endRemoveRows()
                            return False
                self.endRemoveRows()
                return True
            
            case ExpressionOperator():
                # Cannot remove inlets/outlets directly from an operator
                # These are determined by the operator's implementation
                return False
            
            case Inlet():
                inlet_item = parent_data
                graph = self.invisibleRootItem()
                self.beginRemoveRows(parent, row, row + count - 1)
                # Remove links connected to this inlet
                # This is a simplified implementation - you may need more sophisticated link management
                for link_row in reversed(range(row, row + count)):
                    link_index = self.index(link_row, 0, parent)
                    if not link_index.isValid():
                        logger.warning(f"Invalid link index at row {link_row}")
                        continue
                    _, _, link = link_index.internalPointer()
                    assert isinstance(link, Link), f"Expected Link, got {type(link)}"
                    outlet = link.source
                    if not graph.removeLink(link):
                        logger.warning(f"Failed to remove link at row {link_row}")
                self.endRemoveRows()
                return True
            case _:
                logger.warning(f"Invalid parent item type: {type(inlet_item)}")
                return False

    def evaluate(self, index: QModelIndex) -> Any:
        """create a python script from the selected operator and its ancestors."""
        print(f"Evaluating from index: {index}")
        graph = self.invisibleRootItem()
        item = self._itemFromIndex(index)  # Ensure the index is valid
        return graph.buildScript(item)
        # script_text = ""
        # item = self.itemFromIndex(index)  # Ensure the index is valid
        # ancestors = list(self._root.ancestors(item))
        # for op in reversed(ancestors):
        #     params = dict()
        #     inlets = op.inlets()  # Ensure inlets are populated
        #     for inlet in inlets:
        #         links = self._root.inLinks(inlet)
        #         outlets = [link.source for link in links if link.source is not None]
        #         if len(outlets) > 0:
        #             params[inlet.name] = outlets[0].operator.name()

        #     line = f"{op.name()} = {op.expression()}({', '.join(f'{k}={v}' for k, v in params.items())})"
            
        #     script_text += f"{line}\n"
            
        # return script_text
    