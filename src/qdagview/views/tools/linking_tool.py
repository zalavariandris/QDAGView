from __future__ import annotations

import logging
logger = logging.getLogger(__name__)

from typing import *
from enum import Enum
from dataclasses import dataclass

from qtpy.QtGui import *
from qtpy.QtCore import *
from qtpy.QtWidgets import *

from .payload import Payload
from ..widgets.link_widget import LinkWidget
from ...utils import makeLineBetweenShapes
from ...core import GraphItemType

if TYPE_CHECKING:
    from ..graphview import GraphView


class LinkingTool:
    """A tool to handle linking operations in the graph view."""
    def __init__(self, view: GraphView):
        self._view = view
        self._is_active = False
        self._draft_link: QGraphicsLineItem | None = None
        self._linking_payload: QModelIndex = QModelIndex()  # This will hold the index of the item being dragged or linked
        self._link_end: Literal['head', 'tail'] | None = None  # This will hold the end of the link being dragged

    def isActive(self) -> bool:
        return self._is_active

    def startLinking(self, index: QModelIndex, scene_pos: QPointF|None) -> bool:
        """
        Start linking from the given index.
        return True if the drag operation was started, False otherwise.
        """

        if self._is_active:
            # Already in linking state, cannot start linking
            return False
        
        index_type = self._view._model.itemType(index)
        if index_type not in (GraphItemType.INLET, GraphItemType.OUTLET, GraphItemType.LINK):
            # Only inlets, outlets and links can be dragged
            return False
        
        ##
        match self._view._model.itemType(index):
            case GraphItemType.INLET:
                # create a draft link line
                if not self._draft_link:
                    self._draft_link = LinkWidget()
                    self._view.scene().addItem(self._draft_link)
                self._linking_payload = Payload(index, 'inlet')
                self._is_active = True
                return True

            case GraphItemType.OUTLET:
                # create a draft link line
                if not self._draft_link:
                    self._draft_link = LinkWidget()
                    self._view.scene().addItem(self._draft_link)
                self._linking_payload = Payload(index, 'outlet')
                self._is_active = True
                return True

            case GraphItemType.LINK:
                # If the item is a link, determine which end to drag
                def getClosestLinkEnd(link_index:QModelIndex, scene_pos:QPointF) -> Literal['head', 'tail']:
                    source_index = self._view._model.linkSource(link_index)
                    target_index = self._view._model.linkTarget(link_index)
                    if source_index and source_index.isValid() and target_index and target_index.isValid():
                        link_widget = cast(LinkWidget, self._view._widget_manager.getWidget(link_index))
                        local_pos = link_widget.mapFromScene(scene_pos)  # Ensure scene_pos is in the correct coordinate system
                        tail_distance = (local_pos-link_widget.line().p1()).manhattanLength()
                        head_distance = (local_pos-link_widget.line().p2()).manhattanLength()

                        if head_distance < tail_distance:
                            return 'head'  # Drag the head if closer to the mouse position
                        else:
                            return 'tail'
                        
                    elif source_index and source_index.isValid():
                        return 'head'
                    
                    elif target_index and target_index.isValid():
                        return 'tail'
                    
                    else:
                        return 'tail'
                
                link_end = getClosestLinkEnd(index, scene_pos) if scene_pos else 'tail' # Default to tail if scene_pos is not provided

                self._linking_payload = Payload(index, kind=link_end)
                self._is_active = True
                return True
            case _:
                return False

    def updateLinking(self, pos:QPoint):
        """
        Update the linking position
        """
        if not self._is_active:
            # Not in linking state, cannot update linking
            return
        
        pos = QPoint(int(pos.x()), int(pos.y())) # defense against passing QPointF
        
        # Determine the source and target types
        payload = self._linking_payload
        target_index = self._view.rowAt(pos)  # Ensure the index is updated
        drop_target_type = self._view._model.itemType(target_index)
        drag_source_type = payload.kind

        # find relevant indexes
        outlet_index, inlet_index, link_index = None, None, None
        match drag_source_type, drop_target_type:
            case 'outlet', GraphItemType.INLET:
                link_index = None
                outlet_index = payload.index
                inlet_index = target_index

            case 'inlet', GraphItemType.OUTLET:
                # inlet dragged over outlet
                link_index = None
                outlet_index = target_index
                inlet_index = payload.index

            case 'tail', GraphItemType.OUTLET:
                # link tail dragged over outlet
                link_index = payload.index
                outlet_index = target_index
                inlet_index = self._view._model.linkTarget(link_index)

            case 'head', GraphItemType.INLET:
                # link head dragged over inlet
                link_index = payload.index
                outlet_index = self._view._model.linkSource(link_index)
                inlet_index = target_index

            case 'outlet', _:
                # outlet dragged over empty space
                link_index = None
                outlet_index = payload.index
                inlet_index = None  

            case 'inlet', _:
                # inlet dragged over empty space
                link_index = None
                outlet_index = None
                inlet_index = payload.index
                
            case 'head', _:
                # link head dragged over empty space
                link_index = payload.index
                outlet_index = self._view._model.linkSource(link_index)
                inlet_index = None

            case 'tail', _:
                # link tail dragged over empty space
                link_index = payload.index
                outlet_index = None
                inlet_index = self._view._model.linkTarget(link_index)

            case _:
                # No valid drag source or drop target, do nothing
                return None


        link_widget = self._view._widget_manager.getWidget(link_index) if link_index else self._draft_link

        if outlet_index and inlet_index and self._view._model.canLink(outlet_index, inlet_index):
            outlet_widget = self._view._widget_manager.getWidget(outlet_index)
            inlet_widget = self._view._widget_manager.getWidget(inlet_index)
            line = makeLineBetweenShapes(outlet_widget, inlet_widget)
            line = QLineF(link_widget.mapFromScene(line.p1()), link_widget.mapFromScene(line.p2()))

        elif outlet_index:
            outlet_widget = self._view._widget_manager.getWidget(outlet_index)
            line = makeLineBetweenShapes(outlet_widget, self._view.mapToScene(pos))
            line = QLineF(link_widget.mapFromScene(line.p1()), link_widget.mapFromScene(line.p2()))

        elif inlet_index:
            inlet_widget = self._view._widget_manager.getWidget(inlet_index)
            line = makeLineBetweenShapes(self._view.mapToScene(pos), inlet_widget)
            line = QLineF(link_widget.mapFromScene(line.p1()), link_widget.mapFromScene(line.p2()))

        link_widget.setLine(line)

    def finishLinking(self, target_index:QModelIndex)->bool:
        """
        Finish linking operation.
        """

        if not self._is_active:
            # Not in linking state, cannot finish linking
            return False
        
        # Determine the drop target type
        drop_target_type = self._view._model.itemType(target_index)

        # Determine the drag source type based on the mime data
        payload = self._linking_payload
        drag_source_type:Literal['inlet', 'outlet', 'head', 'tail'] = payload.kind

        # Perform the linking based on the drag source and drop target types
        # return True if the linking was successful, False otherwise
        success = False
        match drag_source_type, drop_target_type:
            case "outlet", GraphItemType.INLET:
                # outlet dropped on inlet
                outlet_index = payload.index
                assert outlet_index.isValid(), "Outlet index must be valid"
                inlet_index = target_index
                if self._view._model.addLink(outlet_index, inlet_index):
                    success = True

            case "inlet", GraphItemType.OUTLET:
                # inlet dropped on outlet
                inlet_index = payload.index
                assert inlet_index.isValid(), "Inlet index must be valid"
                outlet_index = target_index
                if self._view._model.addLink(outlet_index, inlet_index):
                    success = True

            case "head", GraphItemType.INLET:
                # link head dropped on inlet
                link_index = payload.index
                new_inlet_index = target_index
                current_outlet_index = self._view._model.linkSource(link_index)
                if self._view._model.removeLink(link_index):
                    if self._view._model.addLink(current_outlet_index, new_inlet_index):
                        success = True

            case "tail", GraphItemType.OUTLET:
                # link tail dropped on outlet
                link_index = payload.index
                new_outlet_index = target_index
                current_inlet_index = self._view._model.linkTarget(link_index)
                if self._view._model.removeLink(link_index):
                    if self._view._model.addLink(new_outlet_index, current_inlet_index):
                        success = True

            case 'tail', _:
                # tail dropped on empty space
                link_index = payload.index
                assert link_index.isValid(), "Link index must be valid"
                link_source = self._view._model.linkSource(link_index)
                link_target = self._view._model.linkTarget(link_index)
                IsLinked = link_source and link_source.isValid() and link_target and link_target.isValid()
                if IsLinked:
                    if self._view._model.removeLink(link_index):
                        success = True

            case 'head', _:
                # head dropped on empty space
                link_index = payload.index
                assert link_index.isValid(), "Link index must be valid"
                link_source = self._view._model.linkSource(link_index)
                link_target = self._view._model.linkTarget(link_index)
                IsLinked = link_source and link_source.isValid() and link_target and link_target.isValid()
                if IsLinked:
                    if self._view._model.removeLink(link_index):
                        success = True

        # cleanup DraftLink
        if self._draft_link:
            self._view.scene().removeItem(self._draft_link)
            self._draft_link = None

        self._is_active = False
        return success

    def cancelLinking(self):
        """
        Cancel the linking operation.
        This is used to remove the draft link and reset the state.
        """
        if self._is_active:

            if self._view._model.itemType(self._linking_payload.index) == GraphItemType.LINK:
                link_widget = cast(LinkWidget, self._view._widget_manager.getWidget(self._linking_payload.index))
                assert link_widget is not None, "Link widget must not be None"
                source_widget = self._view._link_manager.getLinkSource(link_widget)
                target_widget = self._view._link_manager.getLinkTarget(link_widget)
                self._view._update_link_position(link_widget, source_widget, target_widget)

            else:
                assert self._draft_link is not None, "Draft link must not be None"
                if self._draft_link:
                    self._view.scene().removeItem(self._draft_link)
                    self._draft_link = None

            # Reset state
            self._is_active = False
            self._linking_payload = None
