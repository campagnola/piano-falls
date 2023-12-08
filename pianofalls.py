import sys
from pianofalls.midi import MidiInput
from pianofalls.qt import QtWidgets
from pianofalls.mainwindow import MainWindow


if __name__ == '__main__':
    ports = MidiInput.get_available_ports()
    print(ports)
    midi_input = MidiInput('Virtual Keyboard:Virtual Keyboard 129:0')

    app = QtWidgets.QApplication([])
    w = MainWindow()
    w.show()

    w.connect_midi_input(midi_input)

    w.load('arabesque.mid')

    def print_transforms(item):
        while True:
            tr = item.transform()
            print(item)
            print(tr.m11(), tr.m12(), tr.m13())
            print(tr.m21(), tr.m22(), tr.m23())
            print(tr.m31(), tr.m32(), tr.m33())

            item = item.parentItem()
            if item is None:
                break   

    if sys.flags.interactive == 0:
        app.exec_()