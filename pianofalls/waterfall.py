import threading
import time

from .keyboard import Keyboard
from .qt import QtCore, QtGui, QtWidgets, RectItem, Color, Pen, GraphicsItemGroup


class Waterfall(QtWidgets.QGraphicsWidget):
    def __init__(self):
        super().__init__()
        self.setFlag(self.GraphicsItemFlag.ItemClipsChildrenToShape)

        self.group = GraphicsItemGroup(self)

        self.notes_item = NotesItem()
        self.group.addToGroup(self.notes_item)

        self.current_time = 0.0
        self.zoom_factor = 10.0

        self.scroll_thread = AutoScrollThread(self)
        self.scroll_timer = QtCore.QTimer()
        self.scroll_timer.timeout.connect(self.auto_scroll)

        self.update_transform()

    def set_notes(self, notes):
        self.notes_item.set_notes(notes)
        
    def scroll(self, amount):
        self.set_time(self.current_time + amount / self.zoom_factor)

    def set_time(self, time):
        self.current_time = time
        self.update_transform()

    def zoom(self, factor):
        self.zoom_factor *= factor
        self.update_transform()

    def update_transform(self):
        transform = QtGui.QTransform()
        transform.translate(0, self.geometry().height())
        transform.scale(1, -self.zoom_factor)
        transform.translate(0, -self.current_time)
        self.group.setTransform(transform)
        
    def auto_scroll(self):
        if self.scroll_thread.requested_time is not None:
            self.set_time(self.scroll_thread.requested_time)

    def toggle_scroll(self):
        if self.scroll_thread.scrolling:
            self.scroll_timer.stop()
        else:
            self.scroll_timer.start(1000//60)  # Update at 60Hz
        self.scroll_thread.set_scrolling(not self.scroll_thread.scrolling)

    def resizeEvent(self, event):
        self.set_time(self.current_time)

    def set_scroll_speed(self, speed):
        """Set the speed of the auto-scrolling (in fraction of written tempo)
        """
        self.scroll_thread.scroll_speed = speed


class AutoScrollThread(threading.Thread):
    def __init__(self, waterfall):
        super().__init__(target=self.auto_scroll_loop, daemon=True)
        self.waterfall = waterfall
        self.requested_time = None

        self.scroll_speed = 1.0
        self.scrolling = False
        self.scroll_mode = 'tempo'  # 'wait' or 'tempo'

        self.midi_queue = None

        self.start()

    def set_scrolling(self, scrolling):
        if scrolling:
            self.requested_time = self.waterfall.current_time
        else:
            self.requested_time = None
        self.scrolling = scrolling

    def connect_midi_input(self, midi_input):
        self.midi_queue = midi_input.add_queue()

    def auto_scroll_loop(self):
        last_time = time.perf_counter()
        midi_messages = []
        while True:
            now = time.perf_counter()
            dt = now - last_time
            last_time = now

            midi_queue = self.midi_queue
            if midi_queue is not None:
                while not midi_queue.empty():
                    midi_messages.append(midi_queue.get())
            
            if not self.scrolling:
                self.requested_time = None
                time.sleep(0.1)
                continue

            if self.scroll_mode == 'tempo':
                self.requested_time += dt * self.scroll_speed
            elif self.scroll_mode == 'wait':
                # wait for each key to be pressed before continuing
                pass
            time.sleep(0.001)


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
        for note_item in sorted(self.notes, key=lambda n: n['start_time']):
            self.scene().removeItem(note_item)
            self.removeFromGroup(note_item)
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
            keyspec = self.key_spec[note['pitch'].key]
            note_item = NoteItem(keyspec['x_pos'], note['start_time'], keyspec['width'], note['duration'], 
                                 color=colors[note['track_n']], z=i)
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
