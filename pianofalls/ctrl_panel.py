import os
from .qt import QtWidgets, QtCore
from .config import config


class CtrlPanel(QtWidgets.QWidget):
    speed_changed = QtCore.Signal(float)
    zoom_changed = QtCore.Signal(float)
    transpose_changed = QtCore.Signal(int)
    autoplay_volume_changed = QtCore.Signal(float)
    scroll_mode_changed = QtCore.Signal(str)

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

        self.autoplay_volume_label = QtWidgets.QLabel('Autoplay Vol:')
        self.autoplay_volume_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.layout.addWidget(self.autoplay_volume_label)
        self.autoplay_volume_spin = QtWidgets.QSpinBox(
            minimum=0, maximum=100, singleStep=5, value=80, suffix='%'
        )
        self.layout.addWidget(self.autoplay_volume_spin)

        self.scroll_mode_label = QtWidgets.QLabel('Scroll Mode:')
        self.scroll_mode_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.layout.addWidget(self.scroll_mode_label)
        self.scroll_mode_combo = QtWidgets.QComboBox()
        self.scroll_mode_combo.addItem('Wait for Player', 'wait')
        self.scroll_mode_combo.addItem('Constant Tempo', 'tempo')
        self.layout.addWidget(self.scroll_mode_combo)

        # Track current song info for settings persistence
        self.song_info = None

        self.load_button.clicked.connect(self.on_load)
        self.speed_spin.valueChanged.connect(self.on_speed_changed)
        self.zoom_spin.valueChanged.connect(self.on_zoom_changed)
        self.transpose_spin.valueChanged.connect(self.on_transpose_changed)
        self.autoplay_volume_spin.valueChanged.connect(self.on_autoplay_volume_changed)
        self.scroll_mode_combo.currentIndexChanged.connect(self.on_scroll_mode_changed)

    def load_config(self):
        scroll_mode = config.data.get('scroll_mode', 'wait')
        index = self.scroll_mode_combo.findData(scroll_mode)
        if index >= 0:
            self.scroll_mode_combo.setCurrentIndex(index)
        # Ensure signal is emitted even if index doesn't change
        self.scroll_mode_changed.emit(scroll_mode)

        # Load autoplay volume after scroll mode is set
        autoplay_volume = config.data.get('autoplay_volume', 80)
        self.autoplay_volume_spin.setValue(autoplay_volume)
        # Ensure signal is emitted even if value doesn't change
        self.autoplay_volume_changed.emit(autoplay_volume / 100.0)

    def on_load(self):
        mw = self.window()
        path = None
        if mw.song_info is not None:
            path = os.path.dirname(mw.song_info.filename)
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

    def on_autoplay_volume_changed(self, value):
        self.autoplay_volume_changed.emit(value / 100.0)  # Convert to 0.0-1.0
        # Save to global config
        config['autoplay_volume'] = value

    def on_scroll_mode_changed(self, index):
        scroll_mode = self.scroll_mode_combo.itemData(index)
        self.scroll_mode_changed.emit(scroll_mode)
        # Save to global config
        config['scroll_mode'] = scroll_mode

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
