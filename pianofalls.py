import sys
from pianofalls.midi import MidiInput
from pianofalls.qt import QtWidgets
from pianofalls.mainwindow import MainWindow


if __name__ == '__main__':
    midi_ports = MidiInput.get_available_ports()
    if len(sys.argv) == 1:
        for i, port in enumerate(midi_ports):
            print(f"[{i}] {port}")
        port = input("Select MIDI port: ")
    else:
        port = sys.argv[1]
    try:
        port_num = int(port)
        port = midi_ports[port_num]
    except ValueError:
        pass

    midi_input = MidiInput(port)


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