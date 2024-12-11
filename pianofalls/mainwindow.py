import os

from .qt import QtWidgets, QtCore
from .overview import Overview
from .view import View
from .ctrl_panel import CtrlPanel
from .scroller import TimeScroller
from .midi import load_midi
from .musicxml import load_musicxml
from .file_tree import FileTree
from .tracklist import TrackList
from .config import config


class MainWindow(QtWidgets.QWidget):
    song_changed = QtCore.Signal(object)

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

        self.left_splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        self.splitter.addWidget(self.left_splitter)

        self.file_tree = FileTree()
        self.file_tree.set_roots(config['search_paths'])
        self.left_splitter.addWidget(self.file_tree)

        self.track_list = TrackList()
        self.left_splitter.addWidget(self.track_list)

        self.view = View()
        self.splitter.addWidget(self.view)

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
        self.track_list.colors_changed.connect(self.update_track_colors)
        self.track_list.modes_changed.connect(self.update_track_modes)

        self.resize(1200, 800)
        self.left_splitter.setSizes([700, 100])
        self.splitter.setSizes([600, 600])
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
        self.set_song(song, filename)

    def set_song(self, song, filename):
        self.song = song
        
        # self.overview.set_song(song)
        self.view.set_song(song)
        self.scroller.set_song(song)
        self.track_list.set_song(song)

        self.window().setWindowTitle(filename)
        self.last_filename = filename
        self.update_track_colors()
        self.view.focusWidget()
        self.song_changed.emit(song)

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

    def update_track_colors(self):
        self.track_colors = self.track_list.track_colors()
        self.view.set_track_colors(self.track_colors)
        self.overview.set_track_colors(self.track_colors)

    def update_track_modes(self):
        pass
