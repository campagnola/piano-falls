import math, sys
from qtpy import QtWidgets, QtGui, QtCore


# Needed to prevent abort when exceptions are raised in Qt slots
def excepthook(type, value, traceback):
    sys.__excepthook__(type, value, traceback)
sys.excepthook = excepthook


class Pen(QtGui.QPen):
    def __init__(self, arg):
        if isinstance(arg, tuple):
            arg = Color(arg)
        elif arg is None:
            arg = QtCore.Qt.PenStyle.NoPen
        super().__init__(arg)        
        self.setCosmetic(True)


class Brush(QtGui.QBrush):
    def __init__(self, arg):
        if isinstance(arg, tuple):
            arg = Color(arg)
        elif arg is None:
            arg = QtCore.Qt.BrushStyle.NoBrush
        super().__init__(arg)        


class Color(QtGui.QColor):
    def __init__(self, arg):
        super().__init__(QtGui.QColor(*arg))

    def __mul__(self, x):
        return Color((
            int(self.red() * x),
            int(self.green() * x),
            int(self.blue() * x),
            self.alpha(),
        ))

    def mix(self, color):
        return Color((
            (self.red() + color.red()) // 2,
            (self.green() + color.green()) // 2,
            (self.blue() + color.blue()) // 2,
            (self.alpha() + color.alpha()) // 2,
        ))


class GraphicsItemGroup(QtWidgets.QGraphicsItem):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.items = []

    def addToGroup(self, item):
        self.items.append(item)
        item.setParentItem(self)

    def removeFromGroup(self, item):
        self.items.remove(item)
        item.setParentItem(None)

    def boundingRect(self):
        return self.childrenBoundingRect()

    def paint(self, painter, option, widget):
        pass


class RectItem(QtWidgets.QGraphicsPolygonItem):
    def __init__(self, x, y, w, h, pen, brush, radius=0.1, radius_steps=4, z=0):
        corners = [
            [x+radius, y+radius], 
            [x+w-radius, y+radius], 
            [x+w-radius, y+h-radius], 
            [x+radius, y+h-radius]
        ]
        points = []
        for i, corner in enumerate(corners):
            start_angle = math.pi * (i / 2 - 1)
            stop_angle = math.pi * (i / 2 - 0.5)
            d_angle = (stop_angle - start_angle) / (radius_steps - 1)
            for j in range(radius_steps):
                angle = start_angle + j * d_angle
                x = corner[0] + radius * math.cos(angle)
                y = corner[1] + radius * math.sin(angle)
                points.append(QtCore.QPointF(x, y))
        self.poly = QtGui.QPolygonF(points)
        super().__init__(self.poly)
        self.setPen(Pen(pen))
        self.setBrush(Brush(brush))
        self.setZValue(z)
