import numpy as np
from .qt import QtCore, QtGui, QtWidgets, Color, Pen, GraphicsItemGroup
from .keyboard import Keyboard


class NotesItem(GraphicsItemGroup):
    def __init__(self):
        super().__init__()
        self._bounds = QtCore.QRectF()
        self.notes = []

        self.track_colors = {}

        self.key_spec = Keyboard.key_spec()
        self.bars = [QtWidgets.QGraphicsLineItem(self.key_spec[0]['x_pos'], 0, self.key_spec[-1]['x_pos'] + self.key_spec[-1]['width'], 0)]
        for item in self.bars:
            item.setPen(Pen((100, 100, 100)))
            self.addToGroup(item)

    def set_track_colors(self, track_colors):
        self.track_colors = track_colors
        for note_item in self.notes:
            note_item.set_color(self.get_color(note_item.track_key))

    def get_color(self, track_key):
        return self.track_colors.get(track_key, (100, 100, 100))

    def set_notes(self, notes):
        bounds = QtCore.QRectF()

        # Clear any existing notes
        for note_item in self.notes:
            self.scene().removeItem(note_item)
        self.notes.clear()

        # Create new notes
        for i, note in enumerate(notes):
            if note.pitch.key < 0 or note.pitch.key >= len(self.key_spec):
                continue
            keyspec = self.key_spec[note.pitch.key]
            track_key = (note.part, note.staff)
            color = self.get_color(track_key)

            # Ensure minimum note height for Qt display (5px minimum)
            # The waterfall transform scales Y by -6 * zoom_factor, so we need
            # duration * 6 * zoom_factor >= 5 pixels
            # For zoom_factor = 1.0, this means duration >= 5/6 ≈ 0.833 seconds
            # But zoom can vary, so we'll use a conservative minimum
            min_duration = max(note.duration, 0.1)  # 0.1 seconds minimum
            
            note_item = NoteItem(x=keyspec['x_pos'], y=note.start_time, w=keyspec['width'], h=min_duration, 
                                 color=color, z=i, note=note)
            self.notes.append(note_item)
            self.addToGroup(note_item)
            bounds = bounds.united(note_item.boundingRect())

        self._bounds = bounds

    def boundingRect(self):
        return self._bounds


class NoteItem(QtWidgets.QGraphicsRectItem):
    def __init__(self, x, y, w, h, color, z, note):
        self.note = note
        self.track_key = (note.part, note.staff)

        self.grad = QtGui.QLinearGradient(QtCore.QPointF(0, 0), QtCore.QPointF(0, 1))
        self.grad.setCoordinateMode(QtGui.QGradient.CoordinateMode.ObjectMode)
        color = 0.5 * Color(color)
        self.grad.setColorAt(0, Color((255, 255, 255)))
        self.grad.setColorAt(np.clip(.05/h, 0, 1), color)
        self.grad.setColorAt(1, color * 0.5)

        QtWidgets.QGraphicsRectItem.__init__(self, x, y, w, h)
        self.setBrush(self.grad)
        self.setPen(Pen((0, 0, 0, 208)))
        self.setZValue(z)

    def set_color(self, color):
        self.grad.setColorAt(np.clip(.05/self.rect().height(), 0, 1), Color(color))
        self.grad.setColorAt(1, Color(color) * 0.5)
        self.setBrush(self.grad)
        self.update()
