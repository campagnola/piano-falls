import os
from .qt import QtWidgets, QtCore


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

    def on_zoom_changed(self, value):
        self.zoom_changed.emit(value / 100)

    def on_transpose_changed(self, value):
        self.transpose_changed.emit(value)
