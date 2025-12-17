from .qt import QtCore, QtGui, QtWidgets, GraphicsItemGroup
from .song import Song
from .notes_item import NotesItem


class Waterfall(QtWidgets.QGraphicsWidget):
    def __init__(self, display_model):
        super().__init__()
        self.setFlag(self.GraphicsItemFlag.ItemClipsChildrenToShape)

        self.group = GraphicsItemGroup(self)

        self.notes_item = NotesItem(display_model)
        self.group.addToGroup(self.notes_item)

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

    def resizeEvent(self, event):
        self.set_time(self.current_time)


