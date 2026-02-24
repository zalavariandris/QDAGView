from collections import defaultdict
from typing import Dict, List, Any
from typing import Protocol
from typing import TypeVar, Generic

# Generic types
LinkT = TypeVar('L')  # LinkType
InletT = TypeVar('I')  # InletType
OutletT = TypeVar('O')  # OutletType

class LinkingManager(Generic[LinkT, InletT, OutletT]):
    def __init__(self):
        self._link_source: Dict[LinkT, OutletT | None] = {}
        self._link_target: Dict[LinkT, InletT | None] = {}
        self._inlet_links: Dict[InletT, List[LinkT]] = defaultdict(list)
        self._outlet_links: Dict[OutletT, List[LinkT]] = defaultdict(list)

    ## Querying
    def getLinkSource(self, link: LinkT) -> OutletT | None:
        return self._link_source.get(link, None)
    
    def getLinkTarget(self, link: LinkT) -> InletT | None:
        return self._link_target.get(link, None)
    
    def getOutletLinks(self, outlet: OutletT) -> List[LinkT]:
        return self._outlet_links.get(outlet, [])
    
    def getInletLinks(self, inlet: InletT) -> List[LinkT]:
        return self._inlet_links.get(inlet, [])
    
    ## Modification
    def link(self, link: LinkT, source: OutletT | None, target: InletT):
        assert link is not None, "link must not be None"
        assert target is not None, "target must not be None"

        if source:
            self._link_source[link] = source
            self._outlet_links[source].append(link)
        else:
            self._link_source[link] = None

        self._link_target[link] = target
        self._inlet_links[target].append(link)

    def unlink(self, link: LinkT):
        source = self._link_source.get(link, None)
        target = self._link_target.get(link, None)

        if source:
            self._outlet_links[source].remove(link)
        if target:
            self._inlet_links[target].remove(link)

        self._link_source.pop(link, None)
        self._link_target.pop(link, None)

    def clear(self):
        self._link_source.clear()
        self._link_target.clear()
        self._inlet_links.clear()
        self._outlet_links.clear()
