import os
from .qt import QtWidgets, QtCore
from .config import config


class CtrlPanel(QtWidgets.QWidget):
    speed_changed = QtCore.Signal(float)
    zoom_changed = QtCore.Signal(float)
    transpose_changed = QtCore.Signal(int)

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

        self.transpose_label = QtWidgets.QLabel('Transpose:')
        self.transpose_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.layout.addWidget(self.transpose_label)
        self.transpose_spin = QtWidgets.QSpinBox(
            minimum=-48, maximum=48, singleStep=1, value=0, suffix=' half-steps'
        )
        self.layout.addWidget(self.transpose_spin)

        # Track current song's filename for settings persistence
        self.current_filename = None

        self.load_button.clicked.connect(self.on_load)
        self.speed_spin.valueChanged.connect(self.on_speed_changed)
        self.zoom_spin.valueChanged.connect(self.on_zoom_changed)
        self.transpose_spin.valueChanged.connect(self.on_transpose_changed)

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

    def on_transpose_changed(self, value):
        self._save_current_settings()
        self.transpose_changed.emit(value)

    def load_song_settings(self, filename):
        """Load settings for a song file and update the UI controls."""
        if not filename:
            return

        self.current_filename = filename
        settings = config.get_song_settings(filename)

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
        if self.current_filename:
            config.update_song_settings(
                filename=self.current_filename,
                speed=self.speed_spin.value(),
                zoom=self.zoom_spin.value() / 100,  # Convert from percentage to decimal
                transpose=self.transpose_spin.value()
            )
