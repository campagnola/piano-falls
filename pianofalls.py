import sys
from pianofalls.midi import MidiInput
from pianofalls.qt import QtWidgets
from pianofalls.mainwindow import MainWindow
from pianofalls.rpi_display import GraphicsViewUpdateWatcher, FrameSender
from pianofalls.config import config


def excepthook(*args):
    sys.__excepthook__(*args)

if __name__ == '__main__':
    sys.excepthook = excepthook

    midi_ports = MidiInput.get_available_ports()
    port_name = None
    for i, port_name in enumerate(midi_ports):
        if 'piano' in port_name.lower():
            break

    if port_name is None:
        for i, port in enumerate(midi_ports):
            print(f"[{i}] {port}")
        port = int(input("Select MIDI port: "))
        port_name = midi_ports[port]

    print(f"Selected MIDI port {port_name}")
    midi_input = MidiInput(port_name)


    app = QtWidgets.QApplication([])
    w = MainWindow()

    if config['rpi_display'] is not None:
        rpi = config['rpi_display']
        watcher = GraphicsViewUpdateWatcher(w.view)
        sender = FrameSender(rpi['ip_address'], rpi['port'], udp=rpi.get('udp', False))
        # sender = FrameSender('10.10.10.10', 1337, udp=False)
        watcher.new_frame.connect(sender.send_frame)

    w.show()

    w.connect_midi_input(midi_input)

    if len(sys.argv) > 1:
        w.load(sys.argv[1])

    if sys.flags.interactive == 0:
        app.exec_()
