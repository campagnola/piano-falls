import numpy as np
from .qt import QtCore, QtGui, QtWidgets, Color, Pen, GraphicsItemGroup
from .keyboard import Keyboard


class NotesItem(GraphicsItemGroup):
    def __init__(self, display_model):
        super().__init__()
        self._bounds = QtCore.QRectF()
        self.notes = []

        # Display model (central source of truth)
        self.display_model = display_model
        display_model.display_events_changed.connect(self._rebuild_notes)

        self.key_spec = Keyboard.key_spec()
        self.bars = [QtWidgets.QGraphicsLineItem(self.key_spec[0]['x_pos'], 0, self.key_spec[-1]['x_pos'] + self.key_spec[-1]['width'], 0)]
        for item in self.bars:
            item.setPen(Pen((100, 100, 100)))
            self.addToGroup(item)

    def _rebuild_notes(self):
        """Rebuild notes from display model."""
        bounds = QtCore.QRectF()

        # Clear any existing notes
        for note_item in self.notes:
            self.scene().removeItem(note_item)
        self.notes.clear()

        # Get visible events from display model
        visible_events = self.display_model.get_visible_events()

        # Create NoteItems from DisplayEvents
        for i, display_evt in enumerate(visible_events):
            # Only render Note events (skip Barlines, etc.)
            from .song import Note
            if not isinstance(display_evt.event, Note):
                continue

            note_item = NoteItem(
                x=display_evt.x_pos,
                y=display_evt.y_start,
                w=display_evt.width,
                h=display_evt.height,
                color=display_evt.color,
                z=i,
                note=display_evt.event
            )
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
