from abc import ABC, abstractmethod
from typing import Type


class AbstractWidgetFactory(ABC):
    @abstractmethod
    def createNodeWidget(self, parent_widget, index, graphview=None):
        pass

    @abstractmethod
    def createInletWidget(self, parent_widget, index, graphview=None):
        pass

    @abstractmethod
    def createOutletWidget(self, parent_widget, index, graphview=None):
        pass

    @abstractmethod
    def createLinkWidget(self, parent_widget, index, graphview=None):
        pass

    @abstractmethod
    def createCellWidget(self, parent_widget, index, graphview=None):
        pass

    @abstractmethod
    def destroyNodeWidget(self, parent_widget, widget):
        pass

    @abstractmethod
    def destroyInletWidget(self, parent_widget, widget):
        pass

    @abstractmethod
    def destroyOutletWidget(self, parent_widget, widget):
        pass

    @abstractmethod
    def destroyLinkWidget(self, parent_widget, widget):
        pass

    @abstractmethod
    def destroyCellWidget(self, parent_widget, widget):
        pass