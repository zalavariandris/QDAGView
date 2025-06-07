from PySide6.QtCore import *
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


class GraphMimeData(StrEnum):
    OutletData = 'application/outlet'
    InletData = 'application/inlet'
    LinkSourceData = 'application/link/source'
    LinkTargetData = 'application/link/target'