import os
from .qt import QtWidgets, QtCore
from .config import config


class CtrlPanel(QtWidgets.QWidget):
    speed_changed = QtCore.Signal(float)
    zoom_changed = QtCore.Signal(float)

    def __init__(self):
        super().__init__()

        self.layout = QtWidgets.QHBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.layout)

        self.load_button = QtWidgets.QPushButton('Load')
        self.layout.addWidget(self.load_button)

        self.speed_label = QtWidgets.QLabel('Speed:')
        self.speed_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.layout.addWidget(self.speed_label)
        self.speed_spin = QtWidgets.QSpinBox(
            minimum=1, maximum=1000, singleStep=10, value=100, suffix='%'
        )
        self.layout.addWidget(self.speed_spin)

        self.zoom_label = QtWidgets.QLabel('Zoom:')
        self.zoom_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.layout.addWidget(self.zoom_label)
        self.zoom_spin = QtWidgets.QSpinBox(
            minimum=1, maximum=1000, singleStep=10, value=100, suffix='%'
        )
        self.layout.addWidget(self.zoom_spin)

        # Track current song's SHA for settings persistence
        self.current_song_sha = None
        self.current_filename = None

        self.load_button.clicked.connect(self.on_load)
        self.speed_spin.valueChanged.connect(self.on_speed_changed)
        self.zoom_spin.valueChanged.connect(self.on_zoom_changed)

    def on_load(self):
        mw = self.window()
        if mw.last_filename is not None:
            path = os.path.dirname(mw.last_filename)
        filename, _ = QtWidgets.QFileDialog.getOpenFileName(self, 'Open File', path, 'MIDI Files (*.mid);;MusicXML Files (*.xml)')
        mw.load(filename)

    def on_speed_changed(self, value):
        self.speed_changed.emit(value / 100)
        self._save_current_settings()
        
    def on_zoom_changed(self, value):
        self.zoom_changed.emit(value / 100)
        self._save_current_settings()

    def load_song_settings(self, filename):
        """Load settings for a song file and update the UI controls."""
        if not filename:
            return
            
        self.current_filename = filename
        self.current_song_sha = config.get_sha(filename)
        settings = config.get_song_settings(self.current_song_sha)
        
        # Update UI controls without triggering signals
        self.speed_spin.blockSignals(True)
        self.zoom_spin.blockSignals(True)
        
        self.speed_spin.setValue(int(settings['speed']))
        self.zoom_spin.setValue(int(settings['zoom'] * 100))  # Convert from decimal to percentage
        
        self.speed_spin.blockSignals(False)
        self.zoom_spin.blockSignals(False)
        
        # Emit signals to update the application state
        self.speed_changed.emit(settings['speed'] / 100)
        self.zoom_changed.emit(settings['zoom'])

    def _save_current_settings(self):
        """Save current speed and zoom settings for the current song."""
        if self.current_song_sha and self.current_filename:
            config.update_song_settings(
                sha=self.current_song_sha,
                filename=self.current_filename,
                speed=self.speed_spin.value(),
                zoom=self.zoom_spin.value() / 100  # Convert from percentage to decimal
            )
            config.save()
