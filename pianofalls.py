import sys
from pianofalls.midi import MidiInput, MidiOutput
from pianofalls.qt import QtWidgets
from pianofalls.mainwindow import MainWindow
from pianofalls.rpi_display import GraphicsViewUpdateWatcher, FrameSender, RPiRenderer
from pianofalls.config import config


def excepthook(*args):
    sys.__excepthook__(*args)

if __name__ == '__main__':
    sys.excepthook = excepthook

    try:
        midi_ports = MidiInput.get_available_ports()
    except ImportError as e:
        if 'rtmidi' in str(e).lower():
            print("Error: rtmidi backend not found for MIDI input.")
            print("Please install rtmidi with: pip install python-rtmidi")
            print("Or install via conda: conda install -c conda-forge rtmidi")
            print("Alternatively, install a different mido backend of your choice.")
            sys.exit(1)
        else:
            raise
    port_name = None
    for i, port_name in enumerate(midi_ports):
        if 'piano' in port_name.lower():
            break

    if port_name is None:
        if len(midi_ports) == 0:
            print("No MIDI ports found.")
            sys.exit(1) 
        for i, port in enumerate(midi_ports):
            print(f"[{i}] {port}")
        port = int(input("Select MIDI port: "))
        port_name = midi_ports[port]

    print(f"Selected MIDI port {port_name}")
    midi_input = MidiInput(port_name)

    # Setup MIDI output for autoplay
    try:
        output_ports = MidiOutput.get_available_ports()
        if len(output_ports) > 0:
            # Auto-select first output port, or prefer synthesizer/wavetable
            output_port_name = output_ports[0]
            for port in output_ports:
                if 'synthesizer' in port.lower() or 'wavetable' in port.lower():
                    output_port_name = port
                    break

            print(f"Selected MIDI output port: {output_port_name}")
            midi_output = MidiOutput(output_port_name)
        else:
            print("No MIDI output ports available - autoplay will not produce sound")
            midi_output = None
    except Exception as e:
        print(f"Error initializing MIDI output: {e}")
        midi_output = None

    app = QtWidgets.QApplication([])
    w = MainWindow()

    if config['rpi_display'] is not None:
        rpi = config['rpi_display']
        sender = FrameSender(rpi['ip_address'], rpi['port'], udp=rpi.get('udp', False))
        renderer = RPiRenderer(w, sender)
        w.ctrl_panel.zoom_changed.connect(renderer.set_zoom)
        # watcher = GraphicsViewUpdateWatcher(w.view)
        # watcher.new_frame.connect(sender.send_frame)

    w.show()

    if midi_input is not None:
        w.connect_midi_input(midi_input)

    if midi_output is not None:
        w.connect_midi_output(midi_output)

    if len(sys.argv) > 1:
        w.load(sys.argv[1])

    if sys.flags.interactive == 0:
        app.exec_()
