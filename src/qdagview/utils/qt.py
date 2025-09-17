from qtpy.QtCore import *
from qtpy.QtWidgets import *

def distribute_items(items: list[QGraphicsItem], rect: QRectF, equal_spacing=True, orientation=Qt.Orientation.Horizontal):
    num_items = len(items)
    
    if num_items < 1:
        return

    is_horizontal = orientation == Qt.Orientation.Horizontal
    
    # Helper functions to abstract horizontal/vertical operations
    def item_size(item):
        return item.boundingRect().width() if is_horizontal else item.boundingRect().height()
    
    def set_item_position(item, pos):
        if is_horizontal:
            item.setX(pos)
        else:
            item.setY(pos)
    
    def container_size():
        return rect.width() if is_horizontal else rect.height()
    
    def container_start():
        return rect.left() if is_horizontal else rect.top()
    
    def container_center():
        return rect.center().x() if is_horizontal else rect.center().y()

    # Handle single item case
    if num_items < 2:
        set_item_position(items[0], container_center() - item_size(items[0]) / 2)
        return

    # Handle multiple items
    if equal_spacing:
        total_item_size = sum(item_size(item) for item in items)
        spacing = (container_size() - total_item_size) / (num_items - 1)
        position = container_start()
        
        for item in items:
            set_item_position(item, position)
            position += item_size(item) + spacing
    else:
        distance = container_size() / (num_items - 1)
        
        for i, item in enumerate(items):
            pos = container_start() + i * distance - item_size(item) / 2
            set_item_position(item, pos)