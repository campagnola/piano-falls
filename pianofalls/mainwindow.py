from qtpy import QtWidgets, QtGui, QtCore
from .view import View
from .ctrl_panel import CtrlPanel
from .midi import load_midi


class MainWindow(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QtWidgets.QVBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.view = View()
        self.ctrl_panel = CtrlPanel()
        self.layout.addWidget(self.ctrl_panel)
        self.layout.addWidget(self.view)
        self.setLayout(self.layout)
        self.view.focusWidget()
        self.ctrl_panel.speed_changed.connect(self.view.waterfall.set_scroll_speed)

    def load_musicxml(self, filename):
        """Load a MusicXML file and display it on the waterfall"""
        # use musicxml api to load filename
        import musicxml.parser.parser
        xml = musicxml.parser.parser.parse_musicxml(filename)
        notes = []
        for note in xml.notes:
            note_dict = {'start_time': note.start_time, 'pitch': note.pitch, 'duration': note.duration}
            notes.append(note_dict)
        self.view.waterfall.set_notes(notes)

    def load(self, filename):
        """Load a MIDI or MusicXML file and display it on the waterfall"""
        if filename.endswith('.mid'):
            notes = load_midi(filename)
        elif filename.endswith('.xml'):
            notes = self.load_musicxml(filename)
        else:
            raise ValueError('Unsupported file type')

        self.view.set_notes(notes)
        self.window().setWindowTitle(filename)

    def connect_midi_input(self, midi_input):
        self.view.connect_midi_input(midi_input)

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key_Equal:
            self.view.waterfall.zoom(1.1)
        elif event.key() == QtCore.Qt.Key_Minus:
            self.view.waterfall.zoom(0.9)
        elif event.key() == QtCore.Qt.Key_Space:
            self.view.waterfall.toggle_scroll()
