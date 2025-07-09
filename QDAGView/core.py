from qtpy.QtCore import *
from enum import IntEnum, StrEnum


class GraphDataRole(IntEnum):
    TypeRole= Qt.ItemDataRole.UserRole+1
    SourceRole= Qt.ItemDataRole.UserRole+2


class GraphItemType(StrEnum):
    BASE = "BASE"
    SUBGRAPH = "SUBGRAPH"
    INLET = "INLET"
    OUTLET = "OUTLET"
    NODE = "NODE"
    LINK = "LINK"


class GraphMimeType(StrEnum):
    OutletData = 'application/outlet'
    InletData = 'application/inlet'
    LinkTailData = 'application/link/source'
    LinkHeadData = 'application/link/target'