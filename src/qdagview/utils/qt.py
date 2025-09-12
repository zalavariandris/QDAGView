from qtpy.QtCore import *
from qtpy.QtWidgets import *

def distribute_items_horizontal(items:list[QGraphicsItem], rect:QRectF, equal_spacing=True):
    num_items = len(items)
    
    if num_items < 1:
        return

    if num_items < 2:
        items[0].setX(rect.center().x())
        return

    if equal_spacing:
        items_overal_width = 0
        for item in items:
            items_overal_width+=item.boundingRect().width() #TODO use reduce?

        spacing = ( rect.width() - items_overal_width) / (num_items-1)
        position = 0
        for i, item in enumerate(items):
            item.setX(position)
            position+=item.boundingRect().width()+spacing

    else:
        distance = rect.width() / (num_items - 1)
        for i, item in enumerate(items):
            x = rect.left() + i * distance
            item.setX(x - item.boundingRect().width() / 2)