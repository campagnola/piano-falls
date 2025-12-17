import os

from .qt import QtWidgets, QtCore
from .overview import Overview
from .view import View
from .ctrl_panel import CtrlPanel
from .scroller import TimeScroller
from .file_tree import FileTree
from .song_info_panel import SongInfoPanel
from .song_info import SongInfo
from .config import config
from .display_model import DisplayModel


class MainWindow(QtWidgets.QWidget):
    song_changed = QtCore.Signal(object)

    def __init__(self):
        super().__init__()
        self.song_info = None
        self.current_transpose = 0

        # Create display model - central source of truth for what to display
        self.display_model = DisplayModel()

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

        # Create container for search bar and file tree
        file_tree_container = QtWidgets.QWidget()
        file_tree_layout = QtWidgets.QVBoxLayout()
        file_tree_layout.setContentsMargins(0, 0, 0, 0)
        file_tree_layout.setSpacing(2)

        # Add search bar
        self.file_search = QtWidgets.QLineEdit()
        self.file_search.setPlaceholderText('Search files...')
        self.file_search.setClearButtonEnabled(True)
        self.file_search.textChanged.connect(self._on_search_changed)
        file_tree_layout.addWidget(self.file_search)

        # Add file tree
        self.file_tree = FileTree()
        self.file_tree.set_roots(config['search_paths'])
        file_tree_layout.addWidget(self.file_tree)

        file_tree_container.setLayout(file_tree_layout)
        self.left_splitter.addWidget(file_tree_container)

        self.song_info_panel = SongInfoPanel()
        self.left_splitter.addWidget(self.song_info_panel)

        self.view = View(self.display_model)
        self.splitter.addWidget(self.view)

        self.overview = Overview(self.display_model)
        self.layout.addWidget(self.overview, 1, 1, 1, 1)
        self.overview.setMaximumWidth(100)

        self.setLayout(self.layout)

        self.scroller.current_time_changed.connect(self.time_changed)
        self.ctrl_panel.autoplay_volume_changed.connect(self.scroller.set_autoplay_volume)
        self.ctrl_panel.scroll_mode_changed.connect(self.scroller.set_scroll_mode)
        self.song_info_panel.speed_changed.connect(self.scroller.set_scroll_speed)
        self.song_info_panel.zoom_changed.connect(self.view.waterfall.set_zoom)
        self.song_info_panel.transpose_changed.connect(self.on_transpose_changed)
        self.song_info_panel.colors_changed.connect(self.update_track_colors)
        self.song_info_panel.modes_changed.connect(self.update_track_modes)
        self.view.wheel_event.connect(self.view_wheel_event)
        self.overview.clicked.connect(self.scroller.set_time)
        self.file_tree.file_double_clicked.connect(self.load)

        # Connect display model to song changes
        self.song_changed.connect(self.display_model.set_song)

        self.resize(1200, 800)
        self.left_splitter.setSizes([700, 100])
        self.splitter.setSizes([600, 600])
        self.show()
        self.view.focusWidget()
        self.overview.resizeEvent()

        self.ctrl_panel.load_config()

    def _on_search_changed(self, text):
        """Handle search text changes."""
        self.file_tree.search(text)

    def load(self, filename):
        """Load a MIDI or MusicXML file and display it on the waterfall"""
        filename = os.path.expanduser(filename)
        if filename == '':
            return

        # Create SongInfo (handles file loading, registration, etc.)
        song_info = SongInfo.load(filename, parent=self)

        # Get the Song instance
        song = song_info.get_song()

        # Apply transpose if non-zero
        if self.current_transpose != 0:
            self._apply_transpose_to_song(song, self.current_transpose)

        self.set_song(song_info)

    def set_song(self, song_info):
        """
        Set the current song from a SongInfo instance.

        Parameters
        ----------
        song_info : SongInfo
            The song information object
        """
        self.song_info = song_info

        self.overview.set_song(song_info)
        self.view.set_song(song_info)
        self.scroller.set_song(song_info)
        self.song_info_panel.set_song(song_info)

        self.window().setWindowTitle(song_info.filename)

        # Load song-specific settings
        self.song_info_panel.load_song_settings(song_info)
        self.song_info_panel.restore_modes(song_info)

        self.update_track_colors()

        # Apply restored track modes to scroller and display (but don't save)
        self.track_modes = self.song_info_panel.track_modes()
        self.scroller.set_track_modes(self.track_modes)
        self.display_model.set_track_modes(self.track_modes)

        self.view.focusWidget()
        self.song_changed.emit(song_info.get_song())

    def connect_midi_input(self, midi_input):
        self.view.connect_midi_input(midi_input)
        self.scroller.connect_midi_input(midi_input)

    def connect_midi_output(self, midi_output):
        """Connect MIDI output to scroller for autoplay"""
        self.scroller.connect_midi_output(midi_output)

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
        self.track_colors = self.song_info_panel.track_colors()
        self.display_model.set_track_colors(self.track_colors)

    def update_track_modes(self):
        self.track_modes = self.song_info_panel.track_modes()
        self.scroller.set_track_modes(self.track_modes)
        self.display_model.set_track_modes(self.track_modes)

        # Save track modes to config
        if self.song_info:
            serialized = self.song_info_panel.serialize_modes()
            self.song_info.update_settings(track_modes=serialized)

    def _apply_transpose_to_song(self, song, semitones):
        """Apply transpose to all notes by modifying Pitch objects"""
        from .song import Pitch

        for note in song.notes:
            if note.pitch is not None:
                new_midi_note = note.pitch.midi_note + semitones
                # Clamp to valid MIDI range
                new_midi_note = max(0, min(127, new_midi_note))
                note.pitch = Pitch(new_midi_note)

    def on_transpose_changed(self, transpose):
        """Handle transpose control change - reload song with new transpose value"""
        if self.song_info is None:
            return

        # Only reload if transpose actually changed
        if self.current_transpose == transpose:
            return

        self.current_transpose = transpose

        # Reload the song from file with new transpose
        self.load(self.song_info.filename)
