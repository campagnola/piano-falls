from .qt import QtCore, QtGui, QtWidgets, GraphicsItemGroup
from .song import Song
from .notes_item import NotesItem


class Waterfall(QtWidgets.QGraphicsWidget):
    def __init__(self):
        super().__init__()
        self.setFlag(self.GraphicsItemFlag.ItemClipsChildrenToShape)

        self.group = GraphicsItemGroup(self)

        self.song = None
        self.notes_item = NotesItem()
        self.group.addToGroup(self.notes_item)

        self.current_time = 0.0
        self.requested_time = 0.0
        self.zoom_factor = 1.0

        # limit the update rate to 60 fps
        self.update_timer = QtCore.QTimer()
        self.update_timer.timeout.connect(self._update_time)
        self.update_timer.start(16)

        self.update_transform()

    def set_track_colors(self, track_colors):
        self.notes_item.set_track_colors(track_colors)

    def set_track_modes(self, track_modes):
        self.notes_item.set_track_modes(track_modes)

    def set_song(self, song: Song):
        self.song = song
        self.notes_item.set_notes(song.notes)

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


