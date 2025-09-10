#!/usr/bin/env python3
"""Test script to check if QGraphicsProxyWidget accepts drops by default"""

import sys
from PySide6.QtWidgets import QApplication, QLabel, QGraphicsView, QGraphicsScene, QGraphicsProxyWidget
from PySide6.QtCore import Qt

def test_proxy_widget_drops():
    app = QApplication(sys.argv)
    
    # Create a simple QGraphicsProxyWidget
    proxy = QGraphicsProxyWidget()
    label = QLabel("Test Label")
    proxy.setWidget(label)
    
    # Check the default acceptDrops state
    print(f"QGraphicsProxyWidget acceptDrops() default: {proxy.acceptDrops()}")
    print(f"QLabel acceptDrops() default: {label.acceptDrops()}")
    
    # Also check QGraphicsItem and QWidget defaults for comparison
    from PySide6.QtWidgets import QGraphicsRectItem, QWidget
    
    rect_item = QGraphicsRectItem()
    widget = QWidget()
    
    print(f"QGraphicsRectItem acceptDrops() default: {rect_item.acceptDrops()}")
    print(f"QWidget acceptDrops() default: {widget.acceptDrops()}")
    
    app.quit()

if __name__ == "__main__":
    test_proxy_widget_drops()
