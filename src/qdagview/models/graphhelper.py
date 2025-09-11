from __future__ import annotations

from typing import *
from qtpy.QtWidgets import *
from qtpy.QtCore import *
from qtpy.QtGui import *

from ..core import GraphDataRole

import networkx as nx

class ItemGraphHelper:
    def __init__(self, model:QAbstractItemModel):
        self.model = model

    def nodes(self)->List[QModelIndex]:
        return [self.model.index(row, 0, QModelIndex()) for row in range(self.model.rowCount())]

    def createOperator(self, expression:str, name:str)->QPersistentModelIndex|None:
        assert isinstance(expression, str) and expression, "Expression must be a non-empty string"
        assert isinstance(name, str) and name, "Name must be a non-empty string"

        position = self.model.rowCount(QModelIndex())
        assert self.model.insertRows(position, 1, QModelIndex())       
        new_operator_index = self.model.index(position, 0, QModelIndex())
        assert new_operator_index.isValid(), "Created index is not valid"
        new_node_name = name
        assert self.model.setData(new_operator_index, new_node_name, Qt.ItemDataRole.EditRole), "Failed to set data for the new child item"
        assert self.model.setData(new_operator_index.siblingAtColumn(1), expression, Qt.ItemDataRole.EditRole), "Failed to set data for the new child item"
        return QPersistentModelIndex(new_operator_index)
    
    def expression(self, node:QModelIndex|QPersistentModelIndex)->str:
        return self.model.data(node.sibling(node.row(), 1), Qt.ItemDataRole.EditRole)

    def setExpression(self, node:QModelIndex|QPersistentModelIndex, expression:str):
        expression_index = node.sibling(node.row(), 1)
        self.model.setData(expression_index, expression, Qt.ItemDataRole.EditRole)

    def inlets(self, operator:QModelIndex|QPersistentModelIndex)->List[QModelIndex]:
        inlets_count = self.model.rowCount(operator) - 1
        return [self.model.index(row, 0, operator) for row in range(inlets_count)]

    def outlet(self, operator:QModelIndex|QPersistentModelIndex)->QModelIndex|None:
        if operator.isValid():
            outlet_position = self.model.rowCount(operator)-1
            return self.model.index(outlet_position, 0, operator)
        return None
    
    def deleteOperator(self, operator:QModelIndex|QPersistentModelIndex):
        assert operator.isValid(), "Invalid operator index"
        assert self.model.removeRows(operator.row(), 1, QModelIndex()), "Failed to remove operator"

    def createLink(self, outlet:QModelIndex|QPersistentModelIndex, inlet:QModelIndex|QPersistentModelIndex)->QPersistentModelIndex|None:
        assert outlet.isValid(), "Source outlet index is not valid"
        assert inlet.isValid(), "Target inlet index is not valid"
        assert outlet.parent().isValid(), "Source node index is not valid"
        assert inlet.parent().isValid(), "Target node index is not valid"
        assert outlet.parent() != inlet.parent(), "Source and target must not have the same parent"

        position = self.model.rowCount(inlet)
        # Make sure the parent has at least one column for children, otherwise the treeview won't show them
        if self.model.columnCount(inlet) == 0:
            self.model.insertColumns(0, 1, inlet)

        # create the link index
        assert self.model.insertRows(position, 1, inlet)
        new_link_index = self.model.index(position, 0, inlet)
        assert new_link_index.isValid(), "Created index is not valid"
        persistent_outlet = outlet if isinstance(outlet, QPersistentModelIndex) else QPersistentModelIndex(outlet)
        assert self.model.setData(new_link_index, persistent_outlet, GraphDataRole.SourceRole), "Failed to set data for the new link"
        return QPersistentModelIndex(new_link_index)

    def deleteLink(self, link:QModelIndex|QPersistentModelIndex):
        assert link.isValid(), "Invalid link index"
        inlet_index = link.parent()
        assert inlet_index.isValid(), "Link is not a child of a valid inlet"
        assert self.model.removeRows(link.row(), 1, inlet_index), "Failed to remove link"

    def toNetworkX(self):
        G = nx.MultiDiGraph()

        # add nodes
        node_count = self.model.rowCount()
        for node_row in range(node_count):
            node_index = self.model.index(node_row, 0)
            node_name = self.model.data(node_index, Qt.ItemDataRole.EditRole)
            node_expression = self.model.data(node_index.siblingAtColumn(1), Qt.ItemDataRole.EditRole)

            inlets = []
            for inlet_row in range(self.model.rowCount(node_index) - 1):
                target_inlet_index = self.model.index(inlet_row, 0, node_index)
                inlet_name = self.model.data(target_inlet_index, Qt.ItemDataRole.EditRole)
                inlets.append(inlet_name)

            G.add_node(node_name, 
                expression=node_expression,
                inlets=inlets
            )

        
        for node_row in range(node_count):
            target_node_index = self.model.index(node_row, 0)
            target_node_name = self.model.data(target_node_index, Qt.ItemDataRole.EditRole)
            inlets_count = self.model.rowCount(target_node_index) - 1
            for inlet_row in range(inlets_count):
                target_inlet_index = self.model.index(inlet_row, 0, target_node_index)
                links_count = self.model.rowCount(target_inlet_index)
                for link_row in range(links_count):
                    link_index = self.model.index(link_row, 0, target_inlet_index)
                    source_outlet_index = self.model.data(link_index, role=GraphDataRole.SourceRole)
                    if (
                        isinstance(source_outlet_index, (QModelIndex, QPersistentModelIndex))
                        and source_outlet_index.isValid()
                    ):
                        source_node_index = source_outlet_index.parent()
                        source_node_name = self.model.data(source_node_index, Qt.EditRole)
                        G.add_edge(source_node_name, target_node_name, inlet=self.model.data(target_inlet_index, Qt.EditRole))

        return G
