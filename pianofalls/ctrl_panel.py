from .qt import QtWidgets, QtCore


class CtrlPanel(QtWidgets.QWidget):
    speed_changed = QtCore.Signal(float)

    def __init__(self):
        super().__init__()
        self.layout = QtWidgets.QHBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.layout)

        self.load_button = QtWidgets.QPushButton('Load')
        self.layout.addWidget(self.load_button)

        self.speed_label = QtWidgets.QLabel('Speed:')
        self.layout.addWidget(self.speed_label)
        self.speed_spin = QtWidgets.QSpinBox(
            minimum=1, maximum=1000, singleStep=10, value=100, suffix='%'
        )
        self.layout.addWidget(self.speed_spin)

        self.load_button.clicked.connect(self.on_load)
        self.speed_spin.valueChanged.connect(self.on_speed_changed)

    def on_load(self):
        filename, _ = QtWidgets.QFileDialog.getOpenFileName(self, 'Open File', '', 'MIDI Files (*.mid);;MusicXML Files (*.xml)')
        self.window().load(filename)

    def on_speed_changed(self, value):
        self.speed_changed.emit(value / 100)
        
