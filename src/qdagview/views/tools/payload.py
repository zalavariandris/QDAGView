from qtpy.QtGui import *
from qtpy.QtCore import *
from qtpy.QtWidgets import *
from typing import Literal
from dataclasses import dataclass

from ...core import GraphMimeType, indexFromPath, indexToPath
from typing import Self

@dataclass
class Payload:
    index: QModelIndex | None
    kind: Literal['head', 'tail', 'inlet', 'outlet']

    @staticmethod
    def fromMimeData(model, mime:QMimeData) -> Self | None:
        """
        Parse the payload from the mime data.
        This is used to determine the source and target of the link being dragged.
        """
        drag_source_type:Literal['inlet', 'outlet', 'head', 'tail']
        if mime.hasFormat(GraphMimeType.LinkTailData):
            drag_source_type = "tail"
        elif mime.hasFormat(GraphMimeType.LinkHeadData):
            drag_source_type = "head"
        elif mime.hasFormat(GraphMimeType.OutletData):
            drag_source_type = "outlet"
        elif mime.hasFormat(GraphMimeType.InletData):
            drag_source_type = "inlet"


        if mime.hasFormat(GraphMimeType.InletData):
            index_path = mime.data(GraphMimeType.InletData).data().decode("utf-8")

        elif mime.hasFormat(GraphMimeType.OutletData):
            index_path = mime.data(GraphMimeType.OutletData).data().decode("utf-8")

        elif mime.hasFormat(GraphMimeType.LinkTailData):
            index_path = mime.data(GraphMimeType.LinkTailData).data().decode("utf-8")

        elif mime.hasFormat(GraphMimeType.LinkHeadData):
            index_path = mime.data(GraphMimeType.LinkHeadData).data().decode("utf-8")
        else:
            # No valid mime type found
            return None

        index = indexFromPath(model, list(map(int, index_path.split("/"))))

        return Payload(index=index, kind=drag_source_type)
    
    def toMimeData(self) -> QMimeData:
        """
        Convert the payload to mime data.
        This is used to initiate a drag-and-drop operation for linking.
        """
        mime = QMimeData()

        # mime type
        mime_type = self.kind
            
        if mime_type is None:
            return None
        
        index_path = "/".join(map(str, indexToPath(self.index)))
        logger.debug(f"Creating mime data for index: {self.index}, path: {index_path}, type: {self.kind}")
        mime.setData(self.kind, index_path.encode("utf-8"))
        return mime
