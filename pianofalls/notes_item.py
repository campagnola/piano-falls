
from .qt import QtCore, QtGui, QtWidgets, RectItem, Color, Pen, GraphicsItemGroup
from .keyboard import Keyboard


class NotesItem(GraphicsItemGroup):
    def __init__(self):
        super().__init__()
        self._bounds = QtCore.QRectF()
        self.notes = []
        self.key_spec = Keyboard.key_spec()
        self.bars = [QtWidgets.QGraphicsLineItem(self.key_spec[0]['x_pos'], 0, self.key_spec[-1]['x_pos'] + self.key_spec[-1]['width'], 0)]
        for item in self.bars:
            item.setPen(Pen((100, 100, 100)))
            self.addToGroup(item)

    def set_notes(self, notes):
        bounds = QtCore.QRectF()

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
            bounds = bounds.united(note_item.boundingRect())

        self._bounds = bounds

    def boundingRect(self):
        return self._bounds


class NoteItem(RectItem):
    def __init__(self, x, y, w, h, color, z):
        self.grad = QtGui.QLinearGradient(QtCore.QPointF(0, 0), QtCore.QPointF(0, 1))
        self.grad.setCoordinateMode(QtGui.QGradient.CoordinateMode.ObjectMode)
        color = 0.5 * Color(color)
        self.grad.setColorAt(0, Color((255, 255, 255)))
        self.grad.setColorAt(.05/h, color)
        self.grad.setColorAt(1, color * 0.5)
        super().__init__(
            x, y, w, h, 
            pen=(100, 100, 100, 100),
            brush=self.grad,
            z=z,
        )
