from collections import defaultdict
from typing import Dict, List, Any
from typing import Protocol
from typing import TypeVar, Generic

# Generic types
LinkType = TypeVar('L')  # LinkType
InletType = TypeVar('I')  # InletType
OutletType = TypeVar('O')  # OutletType

class LinkingManager(Generic[LinkType, InletType, OutletType]):
    def __init__(self):
        self._link_source: Dict[LinkType, OutletType | None] = {}
        self._link_target: Dict[LinkType, InletType | None] = {}
        self._inlet_links: Dict[InletType, List[LinkType]] = defaultdict(list)
        self._outlet_links: Dict[OutletType, List[LinkType]] = defaultdict(list)

    ## Querying
    def getLinkSource(self, link: LinkType) -> OutletType | None:
        return self._link_source.get(link, None)
    
    def getLinkTarget(self, link: LinkType) -> InletType | None:
        return self._link_target.get(link, None)
    
    def getOutletLinks(self, outlet: OutletType) -> List[LinkType]:
        return self._outlet_links.get(outlet, [])
    
    def getInletLinks(self, inlet: InletType) -> List[LinkType]:
        return self._inlet_links.get(inlet, [])
    
    ## Modification
    def link(self, link: LinkType, source: OutletType | None, target: InletType):
        assert link is not None, "link must not be None"
        assert target is not None, "target must not be None"

        if source:
            self._link_source[link] = source
            self._outlet_links[source].append(link)
        else:
            self._link_source[link] = None

        self._link_target[link] = target
        self._inlet_links[target].append(link)

    def unlink(self, link: LinkType):
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
