import numpy as np
from .qt import QtCore, QtGui, QtWidgets, RectItem, Color, Pen, GraphicsItemGroup
from . import qt
from .keyboard import Keyboard


class NotesItem(GraphicsItemGroup):
    def __init__(self):
        super().__init__()
        self._bounds = QtCore.QRectF()
        self.notes = []
        self.colors = {}

        alpha = 220
        self.default_colors = [
            (100, 255, 100, alpha),
            (100, 100, 255, alpha),
            (255, 100, 100, alpha),
            (255, 255, 100, alpha),
            (255, 100, 255, alpha),
            (100, 255, 255, alpha),
        ]

        self.key_spec = Keyboard.key_spec()
        self.bars = [QtWidgets.QGraphicsLineItem(self.key_spec[0]['x_pos'], 0, self.key_spec[-1]['x_pos'] + self.key_spec[-1]['width'], 0)]
        for item in self.bars:
            item.setPen(Pen((100, 100, 100)))
            self.addToGroup(item)

    def set_colors(self, colors):
        self.colors = colors
        self.update()

    def set_color(self, track_key, color):
        self.colors[track_key] = color
        self.update()

    def get_color(self, track_key):
        if track_key not in self.colors:
            color = self.default_colors[len(self.colors) % len(self.default_colors)]
            self.colors[track_key] = color
        return self.colors[track_key]

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
                                 color=color, z=i)
            self.notes.append(note_item)
            self.addToGroup(note_item)
            bounds = bounds.united(note_item.boundingRect())

        self._bounds = bounds

    def boundingRect(self):
        return self._bounds


class NoteItem(GraphicsItemGroup):
    def __init__(self, x, y, w, h, color, z):
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
