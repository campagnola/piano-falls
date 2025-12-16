from .qt import QtWidgets, QtCore
from .tracklist import TrackList


class SongInfoPanel(QtWidgets.QWidget):
    """Panel containing song-specific controls and track list."""

    speed_changed = QtCore.Signal(float)
    zoom_changed = QtCore.Signal(float)
    transpose_changed = QtCore.Signal(int)
    colors_changed = QtCore.Signal()
    modes_changed = QtCore.Signal()

    def __init__(self):
        super().__init__()

        # Main vertical layout
        self.layout = QtWidgets.QVBoxLayout()
        self.layout.setContentsMargins(5, 5, 5, 5)
        self.setLayout(self.layout)

        # Grid layout for song controls
        self.controls_layout = QtWidgets.QGridLayout()
        self.controls_layout.setSpacing(5)
        self.layout.addLayout(self.controls_layout)

        # Speed control
        row = 0
        self.speed_label = QtWidgets.QLabel('Speed:')
        self.speed_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.controls_layout.addWidget(self.speed_label, row, 0)
        self.speed_spin = QtWidgets.QSpinBox(
            minimum=1, maximum=1000, singleStep=10, value=100, suffix='%'
        )
        self.controls_layout.addWidget(self.speed_spin, row, 1)

        # Zoom control
        row += 1
        self.zoom_label = QtWidgets.QLabel('Zoom:')
        self.zoom_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.controls_layout.addWidget(self.zoom_label, row, 0)
        self.zoom_spin = QtWidgets.QSpinBox(
            minimum=1, maximum=1000, singleStep=10, value=100, suffix='%'
        )
        self.controls_layout.addWidget(self.zoom_spin, row, 1)

        # Transpose control
        row += 1
        self.transpose_label = QtWidgets.QLabel('Transpose:')
        self.transpose_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.controls_layout.addWidget(self.transpose_label, row, 0)
        self.transpose_spin = QtWidgets.QSpinBox(
            minimum=-48, maximum=48, singleStep=1, value=0, suffix=' half-steps'
        )
        self.controls_layout.addWidget(self.transpose_spin, row, 1)

        # Track list (spans both columns)
        self.track_list = TrackList()
        self.layout.addWidget(self.track_list)

        # Track current song info for settings persistence
        self.song_info = None

        # Connect signals
        self.speed_spin.valueChanged.connect(self.on_speed_changed)
        self.zoom_spin.valueChanged.connect(self.on_zoom_changed)
        self.transpose_spin.valueChanged.connect(self.on_transpose_changed)
        self.track_list.colors_changed.connect(self.colors_changed.emit)
        self.track_list.modes_changed.connect(self.modes_changed.emit)

    def on_speed_changed(self, value):
        self.speed_changed.emit(value / 100)
        self._save_current_settings()

    def on_zoom_changed(self, value):
        self.zoom_changed.emit(value / 100)
        self._save_current_settings()

    def on_transpose_changed(self, value):
        self._save_current_settings()
        self.transpose_changed.emit(value)

    def load_song_settings(self, song_info):
        """Load settings from a SongInfo instance and update the UI controls."""
        if not song_info:
            return

        self.song_info = song_info
        settings = song_info.get_settings()

        # Update UI controls without triggering signals
        self.speed_spin.blockSignals(True)
        self.zoom_spin.blockSignals(True)
        self.transpose_spin.blockSignals(True)

        self.speed_spin.setValue(int(settings['speed']))
        self.zoom_spin.setValue(int(settings['zoom'] * 100))  # Convert from decimal to percentage
        self.transpose_spin.setValue(settings['transpose'])

        self.speed_spin.blockSignals(False)
        self.zoom_spin.blockSignals(False)
        self.transpose_spin.blockSignals(False)

        # Emit signals to update the application state
        self.speed_changed.emit(settings['speed'] / 100)
        self.zoom_changed.emit(settings['zoom'])
        self.transpose_changed.emit(settings['transpose'])

    def _save_current_settings(self):
        """Save current speed, zoom, and transpose settings for the current song."""
        if self.song_info:
            self.song_info.update_settings(
                speed=self.speed_spin.value(),
                zoom=self.zoom_spin.value() / 100,  # Convert from percentage to decimal
                transpose=self.transpose_spin.value()
            )

    def set_song(self, song_info):
        """Set the song for the track list."""
        self.track_list.set_song(song_info)

    def restore_modes(self, song_info):
        """Restore track modes from song settings."""
        self.track_list.restore_modes(song_info)

    def track_colors(self):
        """Get track colors from track list."""
        return self.track_list.track_colors()

    def track_modes(self):
        """Get track modes from track list."""
        return self.track_list.track_modes()

    def serialize_modes(self):
        """Serialize track modes for saving."""
        return self.track_list.serialize_modes()
