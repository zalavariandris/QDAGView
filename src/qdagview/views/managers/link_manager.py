from collections import defaultdict
from typing import Dict, List, Any
from typing import Protocol

# Dummy types
class LinkWidget: pass
class InletWidget: pass
class OutletWidget: pass


class LinkManager:
    def __init__(self):
        self._link_source: Dict[LinkWidget, OutletWidget | None] = {}
        self._link_target: Dict[LinkWidget, InletWidget | None] = {}
        self._inlet_links: Dict[InletWidget, List[LinkWidget]] = defaultdict(list)
        self._outlet_links: Dict[OutletWidget, List[LinkWidget]] = defaultdict(list)

    ## Querying
    def getLinkSource(self, link: LinkWidget) -> OutletWidget | None:
        return self._link_source.get(link, None)
    
    def getLinkTarget(self, link: LinkWidget) -> InletWidget | None:
        return self._link_target.get(link, None)
    
    def getOutletLinks(self, outlet: OutletWidget) -> List[LinkWidget]:
        return self._outlet_links.get(outlet, [])
    
    def getInletLinks(self, inlet: InletWidget) -> List[LinkWidget]:
        return self._inlet_links.get(inlet, [])
    
    ## Modification
    def link(self, link_widget: LinkWidget, source_widget: OutletWidget | None, target_widget: InletWidget):
        assert link_widget is not None, "link_widget must not be None"
        assert target_widget is not None, "target_widget must not be None"

        if source_widget:
            self._link_source[link_widget] = source_widget
            self._outlet_links[source_widget].append(link_widget)
        else:
            self._link_source[link_widget] = None

        self._link_target[link_widget] = target_widget
        self._inlet_links[target_widget].append(link_widget)

    def unlink(self, link_widget: LinkWidget):
        source_widget = self._link_source.get(link_widget, None)
        target_widget = self._link_target.get(link_widget, None)

        if source_widget:
            self._outlet_links[source_widget].remove(link_widget)
        if target_widget:
            self._inlet_links[target_widget].remove(link_widget)

        self._link_source.pop(link_widget, None)
        self._link_target.pop(link_widget, None)

    def clear(self):
        self._link_source.clear()
        self._link_target.clear()
        self._inlet_links.clear()
        self._outlet_links.clear()
