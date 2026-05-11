from .qt import QtCore, QtGui, QtWidgets, GraphicsItemGroup, Pen, Brush, Color
from .song import Song
from .notes_item import NotesItem


class Waterfall(QtWidgets.QGraphicsWidget):
    def __init__(self, display_model):
        super().__init__()
        self.setFlag(self.GraphicsItemFlag.ItemClipsChildrenToShape)

        self.group = GraphicsItemGroup(self)

        self.notes_item = NotesItem(display_model)
        self.group.addToGroup(self.notes_item)

        self._loop_items = []

        self.current_time = 0.0
        self.requested_time = 0.0
        self.zoom_factor = 1.0

        # limit the update rate to 60 fps
        self.update_timer = QtCore.QTimer()
        self.update_timer.timeout.connect(self._update_time)
        self.update_timer.start(16)

        self.update_transform()

    def set_time(self, time):
        self.requested_time = time

    def _update_time(self):
        req_time = self.requested_time
        if req_time != self.current_time:    
            self.current_time = req_time
            self.update_transform()

    def zoom(self, factor: float):
        """Multiply the zoom by the given factor"""
        self.set_zoom(self.zoom_factor * factor)

    def set_zoom(self, factor: float):
        self.zoom_factor = factor
        self.update_transform()

    def update_transform(self):
        transform = QtGui.QTransform()
        transform.translate(0, self.geometry().height())
        transform.scale(1, -6 * self.zoom_factor)
        transform.translate(0, -self.current_time)
        self.group.setTransform(transform)

    def set_loops(self, loops):
        """Update the display to show active loop regions as horizontal bands."""
        # Remove existing loop items from the scene
        for item in self._loop_items:
            if item.scene() is not None:
                item.scene().removeItem(item)
        self._loop_items = []

        fill_brush = Brush((100, 200, 100, 40))
        line_pen = Pen((100, 200, 100, 180))

        for loop in loops:
            if not loop.get('active'):
                continue
            start = loop['start']
            end = loop['end']

            # Low-opacity filled region between loop boundaries
            rect = QtWidgets.QGraphicsRectItem(0, start, 88, end - start)
            rect.setBrush(fill_brush)
            rect.setPen(Pen(None))
            rect.setZValue(-2)
            self.group.addToGroup(rect)
            self._loop_items.append(rect)

            # Boundary lines at start and end
            for y in (start, end):
                line = QtWidgets.QGraphicsLineItem(0, y, 88, y)
                line.setPen(line_pen)
                line.setZValue(-1)
                self.group.addToGroup(line)
                self._loop_items.append(line)

    def resizeEvent(self, event):
        self.set_time(self.current_time)


