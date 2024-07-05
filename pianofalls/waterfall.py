from .keyboard import Keyboard
from .qt import QtCore, QtGui, QtWidgets, RectItem, Color, Pen, GraphicsItemGroup
from .song import Song


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


class NotesItem(GraphicsItemGroup):
    def __init__(self):
        super().__init__()
        self.notes = []
        self.key_spec = Keyboard.key_spec()
        self.bars = [QtWidgets.QGraphicsLineItem(self.key_spec[0]['x_pos'], 0, self.key_spec[-1]['x_pos'] + self.key_spec[-1]['width'], 0)]
        for item in self.bars:
            item.setPen(Pen((100, 100, 100)))
            self.addToGroup(item)

    def set_notes(self, notes):
        # Clear any existing notes
        for note_item in self.notes:
            self.scene().removeItem(note_item)
        self.notes.clear()

        # Create new notes
        alpha = 220
        colors = {
            0: (100, 255, 100, alpha),
            1: (100, 100, 255, alpha),
            2: (255, 100, 100, alpha),
            3: (255, 255, 100, alpha),
            4: (255, 100, 255, alpha),
            5: (100, 255, 255, alpha),
        }
        for i, note in enumerate(notes):
            keyspec = self.key_spec[note.pitch.key]
            note_item = NoteItem(keyspec['x_pos'], note.start_time, keyspec['width'], note.duration, 
                                 color=colors[note.track_n], z=i)
            self.notes.append(note_item)
            self.addToGroup(note_item)


class NoteItem(RectItem):
    def __init__(self, x, y, w, h, color, z):
        self.grad = QtGui.QLinearGradient(QtCore.QPointF(0, 0), QtCore.QPointF(0, 1))
        self.grad.setCoordinateMode(QtGui.QGradient.CoordinateMode.ObjectMode)
        color = Color(color)
        self.grad.setColorAt(0, Color((255, 255, 255)))
        self.grad.setColorAt(.05/h, color)
        self.grad.setColorAt(1, color * 0.5)
        super().__init__(
            x, y, w, h, 
            pen=(100, 100, 100, 100),
            brush=self.grad,
            z=z,
        )
