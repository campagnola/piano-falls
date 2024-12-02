import numpy as np
from .qt import QtCore, QtGui, QtWidgets, RectItem, Color, Pen, GraphicsItemGroup
from . import qt
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
        print('track_colors:', track_colors)
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
            if note.duration == 0:
                continue
            keyspec = self.key_spec[note.pitch.key]
            track_key = (note.part, note.staff)
            color = self.get_color(track_key)

            note_item = NoteItem(x=keyspec['x_pos'], y=note.start_time, w=keyspec['width'], h=note.duration, 
                                 color=color, z=i, note=note)
            self.notes.append(note_item)
            self.addToGroup(note_item)
            bounds = bounds.united(note_item.boundingRect())

        self._bounds = bounds

    def boundingRect(self):
        return self._bounds


class NoteItem(GraphicsItemGroup):
    def __init__(self, x, y, w, h, color, z, note):
        self.note = note
        self.track_key = (note.part, note.staff)

        self.grad = QtGui.QLinearGradient(QtCore.QPointF(0, 0), QtCore.QPointF(0, 1))
        self.grad.setCoordinateMode(QtGui.QGradient.CoordinateMode.ObjectMode)
        color = 0.5 * Color(color)
        self.grad.setColorAt(0, Color((255, 255, 255)))
        self.grad.setColorAt(np.clip(.05/h, 0, 1), color)
        self.grad.setColorAt(1, color * 0.5)
        super().__init__()

        self.rect = QtWidgets.QGraphicsRectItem(x, y, w, h)
        self.addToGroup(self.rect)
        self.rect.setBrush(self.grad)
        self.rect.setPen(Pen((0, 0, 0, 208)))
        self.setZValue(z)

        # self.line = QtWidgets.QGraphicsLineItem(x, y, x+w, y)
        # self.addToGroup(self.line)
        # self.line.setPen(Pen((255, 255, 255)))

    def set_color(self, color):
        self.grad.setColorAt(np.clip(.05/self.rect.rect().height(), 0, 1), Color(color))
        self.grad.setColorAt(1, Color(color) * 0.5)
        self.rect.setBrush(self.grad)
        self.update()
