import os

from .qt import QtWidgets, QtCore
from .overview import Overview
from .view import View
from .ctrl_panel import CtrlPanel
from .scroller import TimeScroller
from .midi import load_midi
from .musicxml import load_musicxml
from .file_tree import FileTree


class MainWindow(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.last_filename = None

        self.scroller = TimeScroller()

        self.layout = QtWidgets.QGridLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        self.ctrl_panel = CtrlPanel()
        self.layout.addWidget(self.ctrl_panel, 0, 0, 1, 2)

        self.splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        self.layout.addWidget(self.splitter, 1, 0, 1, 1)

        self.file_tree = FileTree()
        self.file_tree.set_roots(['~/midi', '~/Downloads'])
        self.splitter.addWidget(self.file_tree)

        self.view = View()
        self.splitter.addWidget(self.view)

        self.splitter.setSizes([400, 400])

        self.overview = Overview()
        self.layout.addWidget(self.overview, 1, 1, 1, 1)
        self.overview.setMaximumWidth(100)

        self.setLayout(self.layout)

        self.scroller.current_time_changed.connect(self.time_changed)
        self.ctrl_panel.speed_changed.connect(self.scroller.set_scroll_speed)
        self.ctrl_panel.zoom_changed.connect(self.view.waterfall.set_zoom)
        self.view.wheel_event.connect(self.view_wheel_event)
        self.overview.clicked.connect(self.scroller.set_time)
        self.file_tree.file_double_clicked.connect(self.load)

        self.resize(1200, 800)
        self.show()
        self.view.focusWidget()
        self.overview.resizeEvent()

    def load(self, filename):
        """Load a MIDI or MusicXML file and display it on the waterfall"""
        filename = os.path.expanduser(filename)
        ext = os.path.splitext(filename)[1]
        if filename == '':
            return        
        elif ext in ['.mid', '.midi']:
            song = load_midi(filename)
        elif ext in ['.xml', '.mxl']:
            song = load_musicxml(filename)
        else:
            raise ValueError(f'Unsupported file type: {filename}')

        self.overview.set_song(song)
        self.view.set_song(song)
        self.scroller.set_song(song)

        self.window().setWindowTitle(filename)
        self.last_filename = filename
        self.view.focusWidget()

    def connect_midi_input(self, midi_input):
        self.view.connect_midi_input(midi_input)
        self.scroller.connect_midi_input(midi_input)

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key_Equal:
            self.view.waterfall.zoom(1.1)
        elif event.key() == QtCore.Qt.Key_Minus:
            self.view.waterfall.zoom(0.9)
        elif event.key() == QtCore.Qt.Key_Space:
            self.scroller.toggle_scrolling()

    def view_wheel_event(self, event):
        delta = event.angleDelta().y()
        self.scroller.scroll_by(-delta / (100 * self.view.waterfall.zoom_factor))

    def time_changed(self, time):
        self.view.set_time(time)
        self.overview.set_time(time)
