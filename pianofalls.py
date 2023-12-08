import math
from time import perf_counter
from qtpy import QtWidgets, QtGui, QtCore


class View(QtWidgets.QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QtWidgets.QGraphicsScene(parent=self)
        self.setScene(self.scene)

        self.setBackgroundRole(QtGui.QPalette.ColorRole.NoRole)
        self.setBackgroundBrush(QtGui.QBrush(QtGui.QColor(0, 0, 0)))        
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        self.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setTransformationAnchor(QtWidgets.QGraphicsView.ViewportAnchor.NoAnchor)
        self.setResizeAnchor(QtWidgets.QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setViewportUpdateMode(QtWidgets.QGraphicsView.ViewportUpdateMode.MinimalViewportUpdate)
        self.setRenderHints(QtGui.QPainter.Antialiasing)

        self.keys = []
        self.items = []

        self.keyboard = Keyboard()
        self.scene.addItem(self.keyboard)

        self.waterfall = Waterfall()
        self.scene.addItem(self.waterfall)

        self.resizeEvent()

    def resizeEvent(self, event=None):
        w = 88
        h = w * self.height() / self.width()
        self.fitInView(QtCore.QRectF(0, 0, w, h), QtCore.Qt.AspectRatioMode.IgnoreAspectRatio)

        key_height = 88 * 0.114
        waterfall_height = h - key_height
        self.keyboard.setGeometry(0, waterfall_height, 88, key_height)
        self.waterfall.setGeometry(0, 0, 88, waterfall_height)

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        self.waterfall.scroll(delta / 20)

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key_Equal:
            self.waterfall.zoom(1.1)
        elif event.key() == QtCore.Qt.Key_Minus:
            self.waterfall.zoom(0.9)
        elif event.key() == QtCore.Qt.Key_Space:
            self.waterfall.toggle_scroll()

    def load_midi(self, filename):
        """Load a MIDI file and display it on the waterfall"""
        import mido
        midi = mido.MidiFile(filename)
        assert midi.type in (0, 1)

        messages = []
        for i, track in enumerate(midi.tracks):
            # create a dict for each message that contains the absolute tick count
            # and the message itself
            ticks = 0
            prev_track_msg = None
            for msg in track:
                ticks += msg.time
                messages.append({'ticks': ticks, 'midi': msg, 'track': track, 'track_n': i, 'prev_track_msg': prev_track_msg})
                prev_track_msg = messages[-1]

        # sort messages by tick
        messages = sorted(messages, key=lambda m: m['ticks'])

        # calculate absolute time of each message, accounting for tempo changes that affect all tracks
        tempo = 500000
        ticks_per_beat = midi.ticks_per_beat
        for msg in messages:
            last_msg = msg['prev_track_msg']
            last_msg_time = 0 if last_msg is None else last_msg['time']
            if msg['midi'].type == 'set_tempo':
                tempo = msg['midi'].tempo
            dt = mido.tick2second(msg['midi'].time, ticks_per_beat, tempo)
            msg['time'] = last_msg_time + dt

        # collapse note_on / note_off messages into a single event with duration
        current_notes = {}  # To store the notes currently being played
        notes = []  # Store the complete notes
        for message in messages:
            msg = message['midi']
            msg_time = message['time']
            if msg.type == 'note_on' and msg.velocity > 0:
                note_dict = {
                    'start_time': msg_time, 'pitch': Pitch(midi_note=msg.note), 'duration': None, 
                    'track': message['track'], 'track_n': message['track_n'],
                    'on_msg': message, 'off_msg': None
                }
                notes.append(note_dict)
                if msg.note in current_notes:
                    # end previous note here
                    prev_note = current_notes[msg.note]
                    prev_note['duration'] = msg_time - prev_note['start_time']
                current_notes[msg.note] = note_dict
            elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
                if msg.note not in current_notes:
                    continue
                note_end = msg_time
                note_start = current_notes[msg.note]['start_time']
                current_notes[msg.note]['duration'] = note_end - note_start
                current_notes[msg.note]['off_msg'] = msg
                del current_notes[msg.note]

        # filter out empty notes
        notes = [n for n in notes if n['duration'] > 0]

        self.waterfall.set_notes(notes)
        self.notes = notes
        self.window().setWindowTitle(filename)
        self.resizeEvent()

    def load_musicxml(self, filename):
        """Load a MusicXML file and display it on the waterfall"""
        # use musicxml api to load filename
        import musicxml.parser.parser
        xml = musicxml.parser.parser.parse_musicxml(filename)
        notes = []
        for note in xml.notes:
            note_dict = {'start_time': note.start_time, 'pitch': note.pitch, 'duration': note.duration}
            notes.append(note_dict)
        self.waterfall.set_notes(notes)

    def load(self, filename):
        """Load a MIDI or MusicXML file and display it on the waterfall"""
        if filename.endswith('.mid'):
            self.load_midi(filename)
        elif filename.endswith('.xml'):
            self.load_musicxml(filename)
        else:
            raise ValueError('Unsupported file type')

    def connect_midi_input(self, midi_input):
        midi_input.message.connect(self.on_midi_message)

    def on_midi_message(self, midi_input, msg):
        self.keyboard.midi_message(msg)


class Waterfall(QtWidgets.QGraphicsWidget):
    def __init__(self):
        super().__init__()
        self.setFlag(self.GraphicsItemFlag.ItemClipsChildrenToShape)

        self.group = GraphicsItemGroup(self)

        self.notes_item = NotesItem()
        self.group.addToGroup(self.notes_item)

        self.current_time = 0.0
        self.zoom_factor = 10.0

        self.scroll_speed = 1.0
        self.scroll_start_time = None
        self.scroll_offset = None
        self.scroll_timer = QtCore.QTimer()
        self.scroll_timer.timeout.connect(self.scroll_down)
        self.scrolling = False

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
        
    def scroll_down(self):
        elapsed = perf_counter() - self.scroll_start_time
        self.set_time(self.scroll_offset + elapsed * self.scroll_speed)

    def toggle_scroll(self):
        if self.scrolling:
            self.scroll_timer.stop()
        else:
            self.scroll_timer.start(1000//60)  # Update at 60Hz
            self.scroll_offset = self.current_time
            self.scroll_start_time = perf_counter()
        self.scrolling = not self.scrolling

    def resizeEvent(self, event):
        self.set_time(self.current_time)


class GraphicsItemGroup(QtWidgets.QGraphicsItem):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.items = []

    def addToGroup(self, item):
        self.items.append(item)
        item.setParentItem(self)

    def removeFromGroup(self, item):
        self.items.remove(item)
        item.setParentItem(None)

    def boundingRect(self):
        return self.childrenBoundingRect()

    def paint(self, painter, option, widget):
        pass


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


class Keyboard(QtWidgets.QGraphicsWidget):
    def __init__(self):
        super().__init__()
        self.keys = self.key_spec()
        for key in self.keys:
            key['pressed'] = False
            key['item'] = KeyItem(key)
            key['item'].setParentItem(self)

    @staticmethod
    def key_spec():
        """Generate a list of dicts describing the shape and location of piano keys."""
        width = 88
        height = 0.114 * width
        white_key_width = 88 / 52
        black_key_width = 88 * (7 / 52) / 12
        black_key_offset = 3.5 * white_key_width - 5.5 * black_key_width
        white_key_index = 0
        black_key_index = 0
        keys = []

        for key_id in range(88):
            is_black_key = (key_id % 12) in [1, 4, 6, 9, 11]
            if is_black_key:
                key = {
                    'x_pos': key_id * black_key_width + black_key_offset,
                    'height': 0.6,
                    'width': black_key_width,
                    'color': (0, 0, 0),
                    'sub_index': black_key_index,
                    'is_black_key': True,
                }
            else:
                key = {
                    'x_pos': white_key_index * white_key_width,
                    'height': 1.0,
                    'width': white_key_width,
                    'color': (255, 255, 255),
                    'sub_index': white_key_index,
                    'is_black_key': False,
                }
            key['key_id'] = key_id
            keys.append(key)
            if is_black_key:
                black_key_index += 1
            else:
                white_key_index += 1
        return keys

    def midi_message(self, msg):
        if msg.type == 'note_on':
            self.key_on(msg.note - 21)
        elif msg.type == 'note_off':
            self.key_off(msg.note - 21)

    def key_on(self, key_id):
        key = self.keys[key_id]
        key['pressed'] = True
        key['item'].update_press_state()

    def key_off(self, key_id):
        key = self.keys[key_id]
        key['pressed'] = False
        key['item'].update_press_state()


class Pitch:
    def __init__(self, midi_note):
        self.midi_note = midi_note
        self.key = midi_note - 21    


class Pen(QtGui.QPen):
    def __init__(self, arg):
        if isinstance(arg, tuple):
            arg = Color(arg)
        elif arg is None:
            arg = QtCore.Qt.PenStyle.NoPen
        super().__init__(arg)        
        self.setCosmetic(True)


class Brush(QtGui.QBrush):
    def __init__(self, arg):
        if isinstance(arg, tuple):
            arg = Color(arg)
        elif arg is None:
            arg = QtCore.Qt.BrushStyle.NoBrush
        super().__init__(arg)        


class Color(QtGui.QColor):
    def __init__(self, arg):
        super().__init__(QtGui.QColor(*arg))

    def __mul__(self, x):
        return Color((
            int(self.red() * x),
            int(self.green() * x),
            int(self.blue() * x),
            self.alpha(),
        ))

    def mix(self, color):
        return Color((
            (self.red() + color.red()) // 2,
            (self.green() + color.green()) // 2,
            (self.blue() + color.blue()) // 2,
            (self.alpha() + color.alpha()) // 2,
        ))


class RectItem(QtWidgets.QGraphicsPolygonItem):
    def __init__(self, x, y, w, h, pen, brush, radius=0.1, radius_steps=4, z=0):
        corners = [
            [x+radius, y+radius], 
            [x+w-radius, y+radius], 
            [x+w-radius, y+h-radius], 
            [x+radius, y+h-radius]
        ]
        points = []
        for i, corner in enumerate(corners):
            start_angle = math.pi * (i / 2 - 1)
            stop_angle = math.pi * (i / 2 - 0.5)
            d_angle = (stop_angle - start_angle) / (radius_steps - 1)
            for j in range(radius_steps):
                angle = start_angle + j * d_angle
                x = corner[0] + radius * math.cos(angle)
                y = corner[1] + radius * math.sin(angle)
                points.append(QtCore.QPointF(x, y))
        self.poly = QtGui.QPolygonF(points)
        super().__init__(self.poly)
        self.setPen(Pen(pen))
        self.setBrush(Brush(brush))
        self.setZValue(z)


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


class KeyItem(RectItem):
    def __init__(self, key):
        super().__init__(
            x=key['x_pos'], 
            y=-0.1, 
            w=key['width'], 
            h=10.1 * key['height'],
            brush=key['color'],
            pen=(0, 0, 0),
            radius=0.2,
            z=10 if key['is_black_key'] else 0,
        )
        self.key = key

    def update_press_state(self):
        if self.key['pressed']:
            color = Color(self.key['color']).mix(Color((128, 128, 128)))
            self.setBrush(Brush(color))
        else:
            self.setBrush(Brush(self.key['color']))


class MidiInput(QtCore.QObject):
    message = QtCore.Signal(object, object)

    @classmethod
    def get_available_ports(cls):
        import mido
        return mido.get_input_names()

    def __init__(self, port):
        import mido
        self.port = mido.open_input(port)
        self.port.callback = self.callback
        super().__init__()

    def callback(self, msg):
        self.message.emit(self, msg)



if __name__ == '__main__':
    import sys

    ports = MidiInput.get_available_ports()
    print(ports)
    midi_input = MidiInput('Virtual Keyboard:Virtual Keyboard 129:0')

    app = QtWidgets.QApplication([])
    w = View()
    w.show()

    w.connect_midi_input(midi_input)

    w.load('arabesque.mid')

    def print_transforms(item):
        while True:
            tr = item.transform()
            print(item)
            print(tr.m11(), tr.m12(), tr.m13())
            print(tr.m21(), tr.m22(), tr.m23())
            print(tr.m31(), tr.m32(), tr.m33())

            item = item.parentItem()
            if item is None:
                break   

    if sys.flags.interactive == 0:
        app.exec_()