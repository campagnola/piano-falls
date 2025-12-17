import os
from .qt import QtWidgets, QtCore
from .config import config


class CtrlPanel(QtWidgets.QWidget):
    autoplay_volume_changed = QtCore.Signal(float)
    scroll_mode_changed = QtCore.Signal(str)

    def __init__(self):
        super().__init__()

        self.layout = QtWidgets.QHBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.layout)

        self.load_button = QtWidgets.QPushButton('Load')
        self.layout.addWidget(self.load_button)

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

        self.load_button.clicked.connect(self.on_load)
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

    def on_autoplay_volume_changed(self, value):
        self.autoplay_volume_changed.emit(value / 100.0)  # Convert to 0.0-1.0
        # Save to global config
        config['autoplay_volume'] = value

    def on_scroll_mode_changed(self, index):
        scroll_mode = self.scroll_mode_combo.itemData(index)
        self.scroll_mode_changed.emit(scroll_mode)
        # Save to global config
        config['scroll_mode'] = scroll_mode
